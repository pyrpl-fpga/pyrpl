@echo off
setlocal
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

REM build results
set "OUT_DIR=%FPGA_DIR%build\%PROFILE%"
set "FPGA_BIN=%OUT_DIR%\red_pitaya.bin"

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
echo Starting Vivado profile "%PROFILE%"...
pushd "c:\Xilinx\Vivado\%VIVADO_VER%"
call c:\Xilinx\Vivado\%VIVADO_VER%\bin\vivado.bat -nolog -nojournal -mode batch -source "%FPGA_DIR%red_pitaya_vivado.tcl" -tclargs "%PROFILE%" "%OUT_DIR%" > "%OUT_DIR%\fpga.log" 2>&1
set "VIVADO_EXIT=%ERRORLEVEL%"
popd
if not "%VIVADO_EXIT%"=="0" (
    echo FPGA compilation failed with Vivado exit code %VIVADO_EXIT%. See %OUT_DIR%\fpga.log
    exit /b 1
)

if not exist "%FPGA_BIN%" (
    echo FPGA compilation did not produce %FPGA_BIN%.
    exit /b 1
)

echo Compilation finished: %FPGA_BIN%
echo The packaged bitstream was not replaced. Publish it explicitly after hardware tests.
endlocal
