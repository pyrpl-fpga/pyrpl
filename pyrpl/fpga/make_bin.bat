@echo off
REM Define variables
set VIVADO_VER=2024.2

REM build results
set OUT_DIR=out
set FPGA_BIN=%OUT_DIR%\red_pitaya.bin

REM logfile for stdout and stderr
set LOG=>> fpga.log 2>&1

REM Vivado from Xilinx provides IP handling, FPGA compilation
REM Vitis / xsct provide software integration
REM both tools are run in batch mode with an option to avoid log/journal files

REM Create output directory
if not exist %OUT_DIR% mkdir %OUT_DIR%

REM Run Vivado synthesis
echo Starting Vivado...
call c:\Xilinx\Vivado\%VIVADO_VER%\bin\vivado.bat -nolog -nojournal -mode batch -source red_pitaya_vivado.tcl %LOG%

echo compilation finished

REM postclean
copy /Y %FPGA_BIN% .
move /Y *.log %OUT_DIR%

pause