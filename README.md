[<img src="http://pyrpl.readthedocs.io/en/latest/_static/logo.png" width="250" alt="PyRPL">](http://www.pyrpl.org/)
[![Pyversions](https://img.shields.io/pypi/pyversions/ibm-analytics-engine-python.svg?style=flat-square)](https://pypi.python.org/pypi/ibm-analytics-engine-python)
[![code coverage](https://codecov.io/github/pyrpl-fpga/pyrpl/coverage.svg?branch=master "Code coverage")](https://codecov.io/gh/pyrpl-fpga/pyrpl)
[![Python versions on PyPI](https://img.shields.io/pypi/pyversions/pyrpl.svg)](https://pypi.python.org/pypi/pyrpl/)
[![PyRPL version on PyPI](https://img.shields.io/pypi/v/pyrpl.svg "PyRPL on PyPI")](https://pypi.python.org/pypi/pyrpl/)
[![Download pyrpl](https://img.shields.io/sourceforge/dt/pyrpl.svg)](https://sourceforge.net/projects/pyrpl/files/)
[![Documentation Status](https://readthedocs.org/projects/pyrpl/badge/?version=latest)](http://pyrpl.readthedocs.io/en/latest/)
[![join chat on gitter](https://badges.gitter.im/JoinChat.svg "Join chat on gitter")](https://gitter.im/pyrpl-fpga/pyrpl)
[![License](https://img.shields.io/pypi/l/pyrpl.svg)](https://github.com/pyrpl-fpga/pyrpl/blob/master/LICENSE)

[![Download PyRPL](https://a.fsdn.com/con/app/sf-download-button)](https://sourceforge.net/projects/pyrpl/files/)

PyRPL (Python RedPitaya Lockbox) turns your RedPitaya into a powerful DSP device, especially suitable as a digital lockbox and measurement device in quantum optics experiments.

## Website
The official PyRPL website address is [http://pyrpl.readthedocs.io/](http://pyrpl.readthedocs.io). The information on the website is more up-to-date than in this readme.

## Installation
The easiest and fastest way to get PyRPL is to download and execute the [precompiled executable for windows](https://drive.google.com/file/d/1uj5GfKSBs_ceQcKP73JrwaT5-82ZKx1D/view). This option requires no extra programs to be installed on the computer.

If instead you would like to use and/or modify the source code, make sure you have an
installation of Python (3.7 to 3.13). If you are new to Python or unexperienced with fighting installation issues, it is recommended to install the [Anaconda](https://www.continuum.io/downloads) Python distribution, which allows to install all PyRPL dependencies via
```
conda install numpy scipy paramiko pandas nose pip pyqt qtpy pyqtgraph pyyaml nbconvert scp qasync
```
Check [this documentation section](http://pyrpl.readthedocs.io/en/latest/user_guide/installation/common_problems.html#anaconda-problems) for hints if you are unable to execute conda in a terminal. Alternatively, if you prefer creating a virtual environment for pyrpl, do so with the following two commands
```
conda create -y -n pyrpl-env numpy scipy paramiko pandas nose pip pyqt qtpy pyqtgraph pyyaml nbconvert scp qasync
conda activate pyrpl-env
```
If you are not using Anaconda, and using pip, you can just run: 
```
pip install numpy scipy paramiko pandas nose pip pyqt qtpy pyqtgraph pyyaml nbconvert scp qasync
```
or clone the reposetory before and use the requirements.txt.

Next, clone (if you have a [git client](https://git-scm.com/downloads) installed - recommended option) the pyrpl repository to your computer with 
```
git clone https://github.com/pyrpl-fpga/pyrpl.git
```
or [download and extract](https://github.com/pyrpl-fpga/pyrpl/archive/master.zip) (if you do not want to install git on your computer) the repository. 

If you are using pip, you can just navigate to the pyrpl directory and run 

```
pip install -r requirements.txt
```
if you want a manual installation of pyrpl (it will not be automatically added to your python modules list) or 

```
pip install -e .
```
for an automatic installation. I recommend this method as conda tends to become very slow at solving environments.

You can also use the environment config file "environment_pyrpl.yml"
```
conda env create -f environment_pyrpl.yml
conda activate pyrpl-env
```

if you want a manual installation of pyrpl (it will not be automatically added to your python modules list) or 

```
pip install -e .
```
for an automatic installation. I recommend this method as conda tends to become very slow at solving environments.

You can also use the environment config file "environment_pyrpl.yml"
```
conda env create -f environment_pyrpl.yml
conda activate pyrpl-env
```


## Quick start
First, hook up your Red Pitaya / STEMlab to a LAN accessible from your computer (follow the instructions for this on redpitya.com and make sure you can access your Red Pitaya with a web browser by typing its ip-address /  hostname into the address bar).
In a command line terminal, type
```
python -m pyrpl your_configuration_name
```
A GUI should open, let you configure the RedPitaya device you would like to use, and you can start playing around with pyrpl. Different strings for 'your_configuration_name' create different configurations that will be automatically remembered by PyRPL, for example if you have several different redpitayas. Different RedPitayas with different configuration names can be run simultaneously in separate terminals.
A GUI should open, let you configure the RedPitaya device you would like to use, and you can start playing around with pyrpl. Different strings for 'your_configuration_name' create different configurations that will be automatically remembered by PyRPL, for example if you have several different redpitayas. Different RedPitayas with different configuration names can be run simultaneously in separate terminals.

## Issues
We collect a list of common problems on the [documentation website](http://pyrpl.readthedocs.io/en/latest/user_guide/installation/common_problems.html). If you do not find your problem listed there, please report all problems or wishes as new issues on [this page](https://github.com/pyrpl-fpga/pyrpl/issues), so we can fix it and improve the future user experience.

## Unit test
If you want to check whether PyRPL works correctly on your machine, navigate with a command line terminal into the pyrpl root directory and type the  following commands (by substituting the ip-address / hostname of your Red Pitaya, of course)
```
set REDPITAYA_HOSTNAME=your_redpitaya_ip_address
pytest
```
All tests should take about 3 minutes and finish without failures or errors. If there are errors, please report the console output as an issue (see the section "Issues" below for detailed explanations).

## Next steps / documentation
The full html documentation is hosted at [http://pyrpl.readthedocs.io](http://pyrpl.readthedocs.io). Alternatively, you can download a .pdf version at [https://media.readthedocs.org/pdf/pyrpl/latest/pyrpl.pdf](https://media.readthedocs.org/pdf/pyrpl/latest/pyrpl.pdf). We are still in the process of creating an fully up-to-date version of the documentation of the current code. If the current documentation is wrong or insufficient, please post an [issue](https://github.com/pyrpl-fpga/pyrpl/issues/new) and we will prioritize documenting the part of code you need.

## Updates
Since PyRPL is continuously improved, you should install upgrades if you expect bugfixes. 
If you have cloned the GitHub repository (recommended for bleeding-edge updates), navigate into the pyrpl root directory on your local harddisk computer and type
If you have cloned the GitHub repository (recommended for bleeding-edge updates), navigate into the pyrpl root directory on your local harddisk computer and type
```
git pull
```

## FPGA bitfile generation (only for developers)
In case you would like to modify the logic running on the FPGA, you should make sure that you are able to [generate a working bitfile on your machine](http://pyrpl.readthedocs.io/en/latest/developer_guide/fpga_compilation.html). In short, to do so, you must install Vivado 2024.2 [(64-bit windows](windows web-installer](https://www.xilinx.com/member/forms/download/xef.html?filename=Xilinx_Vivado_SDK_2024.2_1118_2_Win64.exe&akdm=1) or [Linux)](https://www.xilinx.com/member/forms/download/xef.html?filename=Xilinx_Vivado_SDK_2024.2_1118_2_Lin64.bin&akdm=1) [together with a working license](http://pyrpl.readthedocs.io/en/latest/developer_guide/fpga_compilation.html#fpga-license). Next, with a terminal in the pyrpl root directory, type
```
cd pyrpl/fpga
make
```
Compilation should take between 10 and 30 minutes, depending on your machine. If there are no errors during compilation, the new bitfile will be in the (pyrpl/fpga/out) repository. If you replace the (pyrpl/fpga/red_pitaya.bin), it will be automatically used at the next restart of PyRPL. The best way to getting started is to skim through the very short Makefile in the fpga directory and to continue by reading the files mentioned in the makefile and the refences therein. All verilog source code is located in the subdirectory pyrpl/fpga/rtl/. 

## License
Please read our license file [LICENSE](https://github.com/pyrpl-fpga/pyrpl/blob/master/LICENSE) for more information. 
