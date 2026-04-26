Releases
**************

Version 0.9.8.0
=====================

- compatibility with Red Pitaya Gen 2
- smarter reloadfpga="auto" startup behavior : only reloads the FPGA image if the bitfile is not the one from pyrpl.
- Improved and modernized the documentation. Still a lot to do.
- Improved ssh connection handling.
- compatibility with up to python 3.13, still breaks with python 3.14 due to changes in the asyncio module. Python 3.14 support will be added in a future release.
- Tried to modernize continuous integration and testing. The problem that I have for now is that the github actions runners are in the US so connection to a Red Pitaya in Europe is very unstable. I will try to find a solution for this in the future, but for now I have to rely on manual testing.

Version 0.9.5.0
=====================

- merges the "0.9.3-develop" branch with accumulated upgrades from over 2 years
- last version to support Python 2.7 (though not running tests anymore)
- tested on Python 3.6 and 3.7
- significant improvements to IIR filter module


Version 0.9.4.0
=====================

* Smoother transitions of output voltages during stage transitions in lockbox.
* Automatic Red Pitaya device search extended to multiple network adapters and most recent STEMLab OS v0.98.
* Improved documentation hosted on `www.pyrpl.org <www.pyrpl.org>`_ and `video tutorial on youtube <https://www.youtube.com/watch?v=WnFkz1adhgs>`_.
* Binaries for Windows, Linux and Mac OSX automatically generated for new releases and `available on sourceforge <https://sourceforge.net/projects/pyrpl/files/>`_.


Version 0.9.3.X
=====================

There are no release notes for PyRPL versions prior to version 0.9.4.

