# Directory structure

|  path             | contents
|-------------------|-------------------------------------------------------------
| `fpga/Makefile`   | main Makefile, used to run FPGA related tools
| `fpga/*.tcl`      | TCL scripts to be run inside FPGA tools
| `fpga/ip/`        | third party IP, for now Zynq block diagrams
| `fpga/rtl/`       | Verilog (SystemVerilog) "Register-Transfer Level"
| `fpga/sdc/`       | "Synopsys Design Constraints" contains Xilinx design constraints
| `fpga/sim/`       | simulation scripts
| `fpga/tbn/`       | Verilog (SystemVerilog) "test bench"
|                   |
| `fpga/sdk/`       | generated red_pitaya.xsa file used to create a Vitis project
| `fpga/out`        | generated logs and other significant artifacts from the build

# Build process

> [!NOTE]
> First consider using the fpga build scripts in [RedPitaya/Makefile.x86](https://github.com/RedPitaya/RedPitaya/blob/master/Makefile.x86) that supports all the different RedPitaya board types using the [RedPitaya-FPGA](https://github.com/RedPitaya/RedPitaya-FPGA) hdl code rather than this fpga build.

Assuming you have a specific requirement to use this hdl code rather than the RedPitaya-FPGA hdl code in your design make sure that you update the part number and constraints sdc file specific to your target board in `fpga/red_pitaya_vivado.tcl`
```
set part xc7z010clg400-1
read_xdc                          $path_sdc/red_pitaya.xdc
```

Xilinx Vitis / Vivado 2023.2 is required. If installed at the default location, then the next command will properly configure system variables:
```bash
. /opt/Xilinx/Vivado/2023.2/settings64.sh
```

If you need to update to a more recent version of Vitis / Vivado then update the Vivado version in `fpga/ip/system_bd.tcl` - be prepared to fix up various build tcl scripts to replace depreciated tcl commands
```
set scripts_vivado_version 2023.2
```

The default mode for building the FPGA is to run a TCL script inside Vivado. Non project mode is used, to avoid the generation of project files, which are too many and difficult to handle. This allows us to only place source files and scripts under version control.

The next scripts perform various tasks for the xc7z010clg400-1 part:

| TCL script                      | action
|---------------------------------|---------------------------------------------
| `red_pitaya_vivado_project.tcl` | creates a Vivado project for graphical editing
| `red_pitaya_vivado.tcl`         | creates the bitstream and reports

To generate a redpitaya.bin file for the xc7z010clg400-1 part, redpitaya.dtbo device tree, reports, run these two commands:
```bash
source /opt/Xilinx/Vivado/2023.2/settings64.sh
make
```

# Device tree
> [!NOTE]
> You do not need to build the .bin file or the device tree to use Pyrpl.  They are provided pre-built.

Device tree is used by Linux to describe features and address space of memory mapped hardware attached to the CPU.  It can (optionally) be installed onto the RedPitaya board with the redpitaya.bin file generated (specify the full path to the files).  In this example assuming the generated .bin and .dtbo files are in the same directory as the python code:
```
from pyrpl import Pyrpl
p = Pyrpl(hostname=HOSTNAME,
    reloadfpga = True, filename = 'red_pitaya.bin',
    dtbo_filename = 'red_pitaya.dtbo'
    )
```
The pre-built .bin file and device tree are used if these files are not specified.  You can avoid reloading the fpga files each time you run your script by setting reloadfpga = False.  If you use the config, configuration file attribute, then the attributes that are used are stored in a .yaml file in the PYRPL_USER_DIR so next time you start your application the settings including reloadfpga will be restored.

# Signal mapping

## XADC inputs

XADC input data can be accessed through the Linux IIO (Industrial IO) driver interface.

| E2 con | schematic | ZYNQ p/n | XADC in | IIO filename     | measurement target | range |
|--------|-----------|----------|---------|------------------|--------------------|-------|
| AI0    | AIF[PN]0  | B19/A20  | AD8     | in_voltage11_raw | general purpose    | 7.01V |
| AI1    | AIF[PN]1  | C20/B20  | AD0     | in_voltage9_raw  | general purpose    | 7.01V |
| AI2    | AIF[PN]2  | E17/D18  | AD1     | in_voltage10_raw | general purpose    | 7.01V |
| AI3    | AIF[PN]3  | E18/E19  | AD9     | in_voltage12_raw | general purpose    | 7.01V |
|        | AIF[PN]4  | K9 /L10  | AD      | in_voltage0_raw  | 5V power supply    | 12.2V |

### Input range

The default mounting intends for unipolar XADC inputs, which allow for observing only positive signals with a saturation range of *0V ~ 1V*. There are additional voltage dividers use to extend this range up to the power supply voltage. It is possible to configure XADC inputs into a bipolar mode with a range of *-0.5V ~ +0.5V*, but it requires removing R273 and providing a *0.5V ~ 1V* common voltage on the E2 connector.

**NOTE:** Unfortunately there is a design error, where the XADC input range in unipolar mode was thought to be *0V ~ 0.5V*. Consequently the voltage dividers were miss designed for a range of double the supply voltage.

#### 5V power supply

```
                         -------------------0  Vout
           ------------  |  ------------
 Vin  0----| 56.0kOHM |-----| 4.99kOHM |----0  GND
           ------------     ------------
```
Ratio: 4.99/(56.0+4.99)=0.0818
Range: 1V / ratio = 12.2V

#### General purpose inputs

```
                         -------------------0  Vout
           ------------  |  ------------
 Vin  0----| 30.0kOHM |-----| 4.99kOHM |----0  GND
           ------------     ------------
```
Ratio: 4.99/(30.0+4.99)=0.143
Range: 1V / ratio = 7.01


## GPIO LEDs

| LED     | color  | SW driver       | dedicated meaning
|---------|--------|-----------------|----------------------------------
| `[7:0]` | yellow | RP API          | user defined
| `  [8]` | yellow | kernel `MIO[0]` | CPU heartbeat (user defined)
| `  [9]` | reg    | kernel `MIO[7]` | SD card access (user defined)
| ` [10]` | green  | none            | "Power Good" status
| ` [11]` | blue   | none            | FPGA programming "DONE"

For now only LED8 and LED9 are accessible using a kernel driver. LED [7:0] are not driven by a kernel driver, since the Linux GPIO/LED subsystem does not allow access to multiple pins simultaneously.

### Linux access to GPIO

This document is used as reference: http://www.wiki.xilinx.com/Linux+GPIO+Driver

The base value of `MIO` GPIOs was determined to be `906`.
```bash
redpitaya> find /sys/class/gpio/ -name gpiochip*
/sys/class/gpio/gpiochip906
```

GPIOs are accessible at base value + MIO index:
```bash
echo 906 > /sys/class/gpio/export
echo 913 > /sys/class/gpio/export
```

### Linux access to LED

This document is used as reference: http://www.wiki.xilinx.com/Linux+GPIO+Driver

By providing GPIO/LED details in the device tree, it is possible to access LEDs using a dedicated kernel interface.
NOTE: only LED 8 and LED 9 support this interface for now.

To show CPU load on LED 9 use:
```bash
echo heartbeat > /sys/class/leds/led9/trigger
```
To switch LED 8 on use:
```bash
echo 1 > /sys/class/leds/led8/brightness
```
