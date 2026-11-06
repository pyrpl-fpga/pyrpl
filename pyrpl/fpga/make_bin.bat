@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Vivado 2024.2 has multiple Windows path bugs in non-project synthesis:
REM helper processes can lose installed Tcl files, and the parent process can
REM fail to create .Xil/realtime files below a normal absolute workspace path.
REM Re-enter this script through a temporary drive mapped to the repository so
REM all paths seen by Vivado are short but .Xil is not at the drive root. The
REM mapping is removed on every normal exit.
if not defined PYRPL_FPGA_SHORT_PATH (
    set "FPGA_PHYSICAL_DIR=%~dp0"
    set "FPGA_PHYSICAL_DIR=!FPGA_PHYSICAL_DIR:~0,-1!"
    for %%I in ("!FPGA_PHYSICAL_DIR!\..\..") do set "FPGA_REPOSITORY_DIR=%%~fI"
    set "FPGA_BUILD_DRIVE="
    for %%D in (R S T U V W X Y Z) do (
        if not defined FPGA_BUILD_DRIVE (
            subst %%D: "!FPGA_REPOSITORY_DIR!" >nul 2>&1
            if !ERRORLEVEL! equ 0 set "FPGA_BUILD_DRIVE=%%D:"
        )
    )
    if not defined FPGA_BUILD_DRIVE (
        echo Could not allocate a temporary drive letter for the Vivado build.
        exit /b 3
    )
    set "PYRPL_FPGA_SHORT_PATH=1"
    set "PYRPL_FPGA_PHYSICAL_DIR=!FPGA_PHYSICAL_DIR!"
    echo Using temporary Vivado path !FPGA_BUILD_DRIVE!\pyrpl\fpga
    call "!FPGA_BUILD_DRIVE!\pyrpl\fpga\make_bin.bat" %*
    set "FPGA_BUILD_EXIT=!ERRORLEVEL!"
    subst !FPGA_BUILD_DRIVE! /D >nul 2>&1
    exit /b !FPGA_BUILD_EXIT!
)

REM Define variables
set "VIVADO_VER=2024.2"
set "FPGA_DIR=%~dp0"

REM Select a source profile; keep every profile's generated files isolated.
set "PROFILE=%~1"
if "%PROFILE%"=="" set "PROFILE=default"
set "PROFILE_TCL=%FPGA_DIR%profiles\%PROFILE%\profile.tcl"
if not exist "%PROFILE_TCL%" (
    echo Unknown FPGA profile "%PROFILE%".
    echo Available profiles:
    for /d %%D in ("%FPGA_DIR%profiles\*") do if exist "%%D\profile.tcl" echo   %%~nxD
    exit /b 2
)

REM Select the Zynq device of the target board (second argument):
REM   z7010 (default) - STEMlab 125-14, xc7z010clg400-1
REM   z7020           - STEMlab 125-14 Z7020 boards (e.g. PRO Z7020 Gen 2)
REM z7010 builds keep their historical build\<profile> directory; other parts
REM build into build\<part>\<profile>.
set "FPGA_PART=%~2"
if "%FPGA_PART%"=="" set "FPGA_PART=z7010"
if /I "%FPGA_PART%"=="z7010" (
    set "FPGA_PART=z7010"
    set "BUILD_SUBDIR=build\%PROFILE%"
) else if /I "%FPGA_PART%"=="z7020" (
    set "FPGA_PART=z7020"
    set "BUILD_SUBDIR=build\z7020\%PROFILE%"
) else (
    echo Unknown FPGA part "%FPGA_PART%". Use z7010 or z7020.
    exit /b 2
)

REM build results
set "OUT_DIR=%FPGA_DIR%%BUILD_SUBDIR%"
set "FPGA_BIN=%OUT_DIR%\red_pitaya.bin"
set "DISPLAY_OUT_DIR=%OUT_DIR%"
if defined PYRPL_FPGA_PHYSICAL_DIR set "DISPLAY_OUT_DIR=%PYRPL_FPGA_PHYSICAL_DIR%\%BUILD_SUBDIR%"
set "DISPLAY_FPGA_BIN=%DISPLAY_OUT_DIR%\red_pitaya.bin"

REM Vivado from Xilinx provides IP handling, FPGA compilation
REM Vitis / xsct provide software integration
REM both tools are run in batch mode with an option to avoid log/journal files

REM Create output directory
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
REM Never allow the publishing step to mistake an older image for the result
REM of a failed rebuild.
if exist "%FPGA_BIN%" del /Q "%FPGA_BIN%"

REM Vivado's launcher records its initial working directory before loading Tcl.
REM Start it in its installation directory; the Tcl script then anchors all
REM project paths to its own location. This is also robust to launchers that
REM remap user paths and keeps Vivado's installed Tcl apps discoverable.
echo Starting Vivado profile "%PROFILE%" for %FPGA_PART%...
pushd "c:\Xilinx\Vivado\%VIVADO_VER%"
call c:\Xilinx\Vivado\%VIVADO_VER%\bin\vivado.bat -nolog -nojournal -mode batch -source "%FPGA_DIR%red_pitaya_vivado.tcl" -tclargs "%PROFILE%" "%OUT_DIR%" "%FPGA_PART%" > "%OUT_DIR%\fpga.log" 2>&1
set "VIVADO_EXIT=%ERRORLEVEL%"
popd
if not "%VIVADO_EXIT%"=="0" (
    echo FPGA compilation failed with Vivado exit code %VIVADO_EXIT%. See %DISPLAY_OUT_DIR%\fpga.log
    exit /b 1
)

if not exist "%FPGA_BIN%" (
    echo FPGA compilation did not produce %DISPLAY_FPGA_BIN%.
    exit /b 1
)

echo Compilation finished: %DISPLAY_FPGA_BIN%
echo The packaged bitstream was not replaced. Publish it explicitly after hardware tests.
endlocal
