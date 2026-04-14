from ._version import __version_info__, __version__

import os
import sys

sys.path.append(os.path.dirname(os.path.realpath(__file__)))

__author__ = "Leonhard Neuhaus <neuhaus@lkb.upmc.fr>"
__license__ = "MIT License"

# manage warnings of numpy
import warnings
import numpy as np

# pyqtgraph is throwing a warning on ScatterPlotItem
try:
    warnings.simplefilter("ignore", np.exceptions.VisibleDeprecationWarning)
    warnings.simplefilter("error", np.exceptions.ComplexWarning)
except AttributeError:
    warnings.simplefilter("ignore", np.VisibleDeprecationWarning)
    warnings.simplefilter("error", np.ComplexWarning)

# former issue with IIR, now resolved
# from scipy.signal import BadCoefficients
# warnings.simplefilter("error", BadCoefficients)

# set up loggers
import logging
from pyrpl_utils import isnotebook
from qtpy import QtCore, QtWidgets
from .pyrpl_utils import setloglevel
from .directories import (
    user_dir,
    user_config_dir,
    user_curve_dir,
    user_lockbox_dir,
    default_config_dir,
)
from .memory import MemoryTree

logging.basicConfig()
logger = logging.getLogger(name=__name__)
# only show errors or warnings until userdefine log level is set up
logger.setLevel(logging.INFO)

# enable ipython QtGui support if needed

INTERACTIVE = isnotebook()  # True if we are in an interactive IPython session

if INTERACTIVE:
    from IPython import get_ipython

    IPYTHON = get_ipython()
    IPYTHON.run_line_magic("gui", "qt")

# get QApplication instance

APP = QtWidgets.QApplication.instance()
if APP is None:
    logger.debug('Creating new QApplication instance "pyrpl"')
    APP = QtWidgets.QApplication(["pyrpl"])

# get user directories

try:  # first try from environment variable
    user_dir = os.environ["PYRPL_USER_DIR"]
except KeyError:  # otherwise, try ~/pyrpl_user_dir (where ~ is the user's home dir)
    user_dir = os.path.join(os.path.expanduser("~"), "pyrpl_user_dir")


# try to set log level (and automatically generate custom global_config file)

global_config = MemoryTree("global_config", source="global_config")
try:
    setloglevel(global_config.general.loglevel, loggername=logger.name)
except (AttributeError, KeyError, TypeError, ValueError):  # pragma: no cover
    pass

# main imports
from .redpitaya import RedPitaya
from .hardware_modules import *
from .attributes import *
from .modules import *
from .curvedb import *
from .pyrpl import *
