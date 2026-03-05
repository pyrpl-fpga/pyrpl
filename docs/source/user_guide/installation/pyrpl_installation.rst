Installing PyRPL
*********************************


Running from binary files (fastest)
====================================

The easiest and fastest way to get PyRPL running is to download and execute the binaries from the `latest GitHub release assets <https://github.com/pyrpl-fpga/pyrpl/releases/latest>`__. This option requires no extra programs to be installed on the computer.



.. _installation_from_source:

Running the Python source code
===================================

If you would like to use and/or modify the source code, make sure you have an installation of Python (tested up to python 3.13).


Prerequisites: Getting the right Python installation
-------------------------------------------------------

There are many ways to get the Python working with Pyrpl. The following list is non-exhaustive

.. _anaconda_installation:

Option 1: Installation from Anaconda
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are new to Python or inexperienced with installation issues, it is recommended to install the `Anaconda <https://www.anaconda.com/download>`__ Python distribution, which allows you to install all PyRPL dependencies via::

    conda install numpy scipy paramiko pip pyqt qtpy pyqtgraph pyyaml qasync

Check :ref:`anaconda_problems` for hints if you cannot execute conda in a terminal. Alternatively, if you prefer creating a virtual environment for pyrpl, do so with the following two commands::

    conda create -y -n pyrpl-env numpy scipy paramiko pip pyqt qtpy pyqtgraph pyyaml qasync
    activate pyrpl-env


Option 2: Installation on a regular (non-Anaconda) python version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are not using Anaconda, use pip and run:
    pip install git+https://github.com/pyrpl-fpga/pyrpl.git

to install the latest pyrpl version and all its dependencies directly from the github repository.

.. _actual_installation:

Downloading and installing PyRPL from source
-------------------------------------------------------

Various channels are available to obtain the PyRPL source code.


Option 1: Installation with pip (Not recommended as the version on pypi is outdated ! )
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have pip correctly installed, the following command installs PyRPL and all missing dependencies::

    pip install pyrpl



Option 2: From github.com (for developers and tinkerers)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have a `git client <https://git-scm.com/downloads>`__ installed (recommended), clone the pyrpl repository to your computer with::

    git clone https://github.com/pyrpl-fpga/pyrpl.git YOUR_PYRPL_DESTINATION_FOLDER

If you do not want to install git on your computer, download and extract the repository `from github.com <https://github.com/pyrpl-fpga/pyrpl/archive/refs/heads/master.zip>`__.
