@echo off
REM Define variables
set PARENT=..\..\..
set VITIS_VER=2024.2
set DTG=%PARENT%\device-tree-xlnx-xilinx-v%VITIS_VER%

REM Red Pitaya FPGA repo
set RP_VER=Release-2024.3
set RPFPGA=%PARENT%\RedPitaya-FPGA

REM build results
set OUT_DIR=out
set FPGA_DTBO=%OUT_DIR%\red_pitaya.dtbo

REM logfile for stdout and stderr
set LOG=>> fpga.log 2>&1

REM Vitis / xsct provide software integration
REM both tools are run in batch mode with an option to avoid log/journal files
set DTS_DIR=sdk\dts
set PL_DEVICE_TREE=%DTS_DIR%\pl.dtsi

REM Create output directory
if not exist %OUT_DIR% mkdir %OUT_DIR%

REM required for the device tree creation
if not exist "%DTG%" (
    echo Cloning device tree generator...
    git clone https://github.com/Xilinx/device-tree-xlnx.git "%DTG%" 
    pushd "%DTG%"
    git checkout xilinx_v%VITIS_VER% >> ..\fpga.log 2>&1
    popd
) else (
    echo Device tree generator already exists at %DTG%
)

REM required for the device tree creation
if not exist "%RPFPGA%" (
    echo Cloning Red Pitaya FPGA repo...
    git clone https://github.com/RedPitaya/RedPitaya-FPGA.git "%RPFPGA%" 
    pushd "%RPFPGA%"
    git checkout %RP_VER% >> ..\fpga.log 2>&1
    popd
) else (
    echo Red Pitaya FPGA repo already exists at %RPFPGA%
)

REM device tree overlay creation
call c:\Xilinx\Vitis\%VITIS_VER%\bin\xsct.bat xsct_hsi_dtb.tcl DTG_VER=%VITIS_VER%

REM fix bug with #address-cells and #size-cells for overlay
powershell -Command "(Get-Content '%PL_DEVICE_TREE%') -replace '#address-cells', '//#address-cells' | Set-Content '%PL_DEVICE_TREE%'"
powershell -Command "(Get-Content '%PL_DEVICE_TREE%') -replace '#size-cells', '//#size-cells' | Set-Content '%PL_DEVICE_TREE%'"
powershell -Command "(Get-Content '%PL_DEVICE_TREE%') -replace 'red_pitaya.bit.bin', 'fpga.bit.bin' | Set-Content '%PL_DEVICE_TREE%'"

REM Set dtc.exe path (from Lopper in Vivado installation)
set DTC_PATH=C:\Xilinx\Vivado\%VITIS_VER%\tps\win64\lopper-1.1.0-packages\min_sdk\usr\bin\dtc.exe
"%DTC_PATH%" -@ -O dtb -o %FPGA_DTBO% -i %DTS_DIR% %PL_DEVICE_TREE% %LOG%
"%DTC_PATH%" -I dtb -O dts %FPGA_DTBO% -o %OUT_DIR%\red_pitaya.dts %LOG%

REM postclean
copy /Y %FPGA_DTBO% .
copy /Y .gen\sources_1\bd\system\ip\system_processing_system7_0\*.html %OUT_DIR%
copy /Y sdk\red_pitaya.hwh %OUT_DIR%
move /Y *.log %OUT_DIR%

pause