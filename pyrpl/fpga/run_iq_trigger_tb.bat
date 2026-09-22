@echo off
setlocal

set "VIVADO_VER=2024.2"
set "FPGA_DIR=%~dp0"
set "VIVADO_BIN=C:\Xilinx\Vivado\%VIVADO_VER%\bin"
set "SIM_DIR=%FPGA_DIR%build\iq_trigger_sim"
set "TCL_BATCH=%FPGA_DIR:\=/%sim/run_all.tcl"

if not exist "%VIVADO_BIN%\xvlog.bat" (
    echo Vivado %VIVADO_VER% was not found under C:\Xilinx\Vivado.
    exit /b 2
)

if not exist "%SIM_DIR%" mkdir "%SIM_DIR%"
pushd "%SIM_DIR%"

call "%VIVADO_BIN%\xvlog.bat" --sv "%FPGA_DIR%rtl\red_pitaya_iq_trigger.v" "%FPGA_DIR%sim\red_pitaya_iq_trigger_tb.sv"
if errorlevel 1 goto :failed

call "%VIVADO_BIN%\xelab.bat" red_pitaya_iq_trigger_tb -s iq_trigger_tb
if errorlevel 1 goto :failed

call "%VIVADO_BIN%\xsim.bat" iq_trigger_tb -tclbatch "%TCL_BATCH%"
if errorlevel 1 goto :failed
findstr /C:"IQ_TRIGGER_TEST_PASS" xsim.log >nul
if errorlevel 1 (
    echo XSim did not report IQ_TRIGGER_TEST_PASS. See %SIM_DIR%\xsim.log
    goto :failed
)

popd
echo IQ trigger RTL simulation passed.
exit /b 0

:failed
set "SIM_EXIT=%ERRORLEVEL%"
popd
echo IQ trigger RTL simulation failed with exit code %SIM_EXIT%.
exit /b %SIM_EXIT%
