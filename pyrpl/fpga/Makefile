#######################################
#
# Authors: Matej Oblak, Iztok Jeras
# (C) Red Pitaya 2013-2015
#
# Red Pitaya FPGA/SoC Makefile
#

VIVADO_VER := $(shell vivado -version | head -n 1 | sed -e 's/ (/_/g' | sed -e 's/ /_/g' | sed -e 's/)//g')

PARENT  = ../../..
VITIS_VER = 2024.2
DTG     = $(PARENT)/device-tree-xlnx-xilinx-v$(VITIS_VER)

# Red Pitaya FPGA repo
RP_VER  = Release-2024.3
RPFPGA  = $(PARENT)/RedPitaya-FPGA

# build results
OUT_DIR=out
FPGA_BIN=$(OUT_DIR)/red_pitaya.bin
FPGA_DTBO=$(OUT_DIR)/red_pitaya.dtbo

#logfile for stdout and stderr
LOG=>> fpga.log 2>&1

# Vivado from Xilinx provides IP handling, FPGA compilation
# Vitis / xsct provide software integration
# both tools are run in batch mode with an option to avoid log/journal files
VIVADO = vivado -nolog -nojournal -mode batch
DTS_DIR = sdk/dts
PL_DEVICE_TREE = $(DTS_DIR)/pl.dtsi

all: $(FPGA_BIN) $(FPGA_DTBO) postclean

ifeq ($(VIVADO_VER),)
$(error "Vivado not detected: setup environment with source /opt/Xilinx/Vivado/$(VITIS_VER)/settings64.sh")
endif

ifneq ($(VIVADO_VER),vivado_v$(VITIS_VER)_64-bit)
$(error "Vivado version $(VIVADO_VER) consider changing DTG version $(VITIS_VER)")
endif

$(FPGA_BIN):
	$(VIVADO) -source red_pitaya_vivado.tcl $(LOG)

# required for the device tree creation
$(DTG):
	git clone https://github.com/Xilinx/device-tree-xlnx.git $(DTG)
	@cd $(DTG); git checkout xilinx_v$(VITIS_VER) $(LOG)

# required for the device tree creation
$(RPFPGA):
	git clone https://github.com/RedPitaya/RedPitaya-FPGA.git $(RPFPGA)
	@cd $(RPFPGA); git checkout $(RP_VER) $(LOG)

# device tree overlay creation
$(FPGA_DTBO): $(DTG) $(RPFPGA)
	xsct xsct_hsi_dtb.tcl DTG_VER=$(VITIS_VER) $(LOG)

#fix bug with #address-cells and #size-cells for overlay
	sed -i 's/#address-cells/\/\/#address-cells/g' $(DTS_DIR)/pl.dtsi
	sed -i 's/#size-cells/\/\/#size-cells/g' $(DTS_DIR)/pl.dtsi
	sed -i 's/red_pitaya.bit.bin/fpga.bit.bin/g' $(DTS_DIR)/pl.dtsi

	dtc -@ -O dtb -o $(FPGA_DTBO) -i $(DTS_DIR) -i $(RPFPGA)/dts $(PL_DEVICE_TREE) $(LOG)
	dtc -I dtb -O dts $(OUT_DIR)/red_pitaya.dtbo -o $(OUT_DIR)/red_pitaya.dts $(LOG)

postclean:
	cp $(FPGA_BIN) $(FPGA_DTBO) .
	cp .gen/sources_1/bd/system/ip/system_processing_system7_0/*.html $(OUT_DIR)
	cp sdk/red_pitaya.hwh $(OUT_DIR)
	mv *.log $(OUT_DIR)

clean:
	rm -rf out .Xil .srcs .gen sdk
