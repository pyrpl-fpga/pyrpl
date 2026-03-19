Installing PyRPL
*********************************


Running from binary files (fastest)
====================================

The easiest and fastest way to get PyRPL running is to download and execute the latest precompiled executable from `the releases page <https://github.com/pyrpl-fpga/pyrpl/releases>`__. This option requires no extra programs to be installed on the computer.


.. _installation_from_source:

Running the Python source code
===================================

If you would like to use and/or modify the source code, make sure you have an installation of Python (3.7 to 3.13, as in the project README).


Prerequisites: Getting a working Python environment
-------------------------------------------------------

There are many ways to get Python working with PyRPL. The following list is non-exhaustive.

.. _anaconda_installation:

Option 1: Installation from Anaconda (optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are new to Python or unexperienced with dependency issues, install the `Anaconda <https://www.continuum.io/downloads>`__ distribution, then create and activate a dedicated environment::

    conda create -y -n pyrpl-env numpy paramiko pip pyqt qtpy pyqtgraph pyyaml scp qasync
    conda activate pyrpl-env

Check :ref:`anaconda_problems` for hints if you cannot execute conda in a terminal.


Option 2: Installation on a regular Python environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use pip to install the latest code directly from GitHub::

    pip install "git+https://github.com/pyrpl-fpga/pyrpl.git#egg=pyrpl[qt-pyqt5]"

PyRPL requires a Qt binding. You can replace ``qt-pyqt5`` with ``qt-pyqt6``, ``qt-pyside2`` or ``qt-pyside6``.


.. _actual_installation:

Downloading and installing PyRPL from source
-------------------------------------------------------

Option 1: Clone/download the repository (recommended for developers)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have a `git client <https://git-scm.com/downloads>`__ installed (recommended), clone the pyrpl repository::

    git clone https://github.com/pyrpl-fpga/pyrpl.git

If you do not want to install git, you can download and extract the repository `from GitHub <https://github.com/pyrpl-fpga/pyrpl/archive/master.zip>`__.

From the project root directory, install PyRPL with pip::

    pip install -e .[qt-pyqt5]

For a non-editable installation, use::

    pip install .[qt-pyqt5]


Option 2: Direct pip install from GitHub (quick setup)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you do not need a local clone, install directly from GitHub::

    pip install "git+https://github.com/pyrpl-fpga/pyrpl.git#egg=pyrpl[qt-pyqt5]"

.. warning::

    Do **not** use ``pip install pyrpl``. The PyPI package is outdated.
