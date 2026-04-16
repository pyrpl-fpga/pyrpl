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
from .hardware_modules import (
    AMS,
    Asg0,
    Asg1,
    DSP_INPUTS,
    DspModule,
    FilterModule,
    HK,
    IIR,
    InputSelectProperty,
    InputSelectRegister,
    Iq,
    Pid,
    Pwm,
    Sampler,
    Scope,
    Trig,
    all_inputs,
    all_output_directs,
    dsp_addr_base,
)
from .attributes import (
    AttributeList,
    BaseAttribute,
    BaseProperty,
    BasePropertyListProperty,
    BasePropertyListPropertyWidget,
    BaseRegister,
    BoolAttributeWidget,
    BoolIgnoreAttributeWidget,
    BoolIgnoreProperty,
    BoolProperty,
    BoolRegister,
    ComplexAttributeListProperty,
    ComplexAttributeWidget,
    ComplexProperty,
    ConstantIntRegister,
    CurveAttributeWidget,
    CurveProperty,
    CurveSelectAttributeWidget,
    CurveSelectListProperty,
    CurveSelectProperty,
    DataAttributeWidget,
    DataProperty,
    FilterAttributeWidget,
    FilterProperty,
    FilterRegister,
    FloatAttributeListProperty,
    FloatAttributeWidget,
    FloatProperty,
    FloatRegister,
    FrequencyProperty,
    FrequencyRegister,
    GainRegister,
    IORegister,
    IntAttributeWidget,
    IntProperty,
    IntRegister,
    LedAttributeWidget,
    LedProperty,
    LongRegister,
    ModuleAttribute,
    NumberProperty,
    PWMRegister,
    PhaseProperty,
    PhaseRegister,
    PlotAttributeWidget,
    Plotter,
    ProxyProperty,
    SelectAttributeWidget,
    SelectProperty,
    SelectRegister,
    StringAttributeWidget,
    StringProperty,
    TextAttributeWidget,
    TextProperty,
    epsilon,
    recursive_getattr,
    recursive_setattr,
)
from .modules import (
    DoSetup,
    DuplicateFilter,
    ExpectedPyrplError,
    HardwareModule,
    Module,
    ModuleMetaClass,
    ModuleWidget,
    SignalLauncher,
    SignalModule,
    unique_list,
)
from .curvedb import CurveDB, XYSeries
from .pyrpl import Pyrpl, default_pyrpl_config, get_module, help_message


__all__ = [
    "__version_info__",
    "__version__",
    "__author__",
    "__license__",
    "INTERACTIVE",
    "APP",
    "global_config",
    "MemoryTree",
    "RedPitaya",
    "setloglevel",
    "user_dir",
    "user_config_dir",
    "user_curve_dir",
    "user_lockbox_dir",
    "default_config_dir",
    "Pyrpl",
    "default_pyrpl_config",
    "get_module",
    "help_message",
    "AMS",
    "Asg0",
    "Asg1",
    "DSP_INPUTS",
    "DspModule",
    "FilterModule",
    "HK",
    "IIR",
    "InputSelectProperty",
    "InputSelectRegister",
    "Iq",
    "Pid",
    "Pwm",
    "Sampler",
    "Scope",
    "Trig",
    "all_inputs",
    "all_output_directs",
    "dsp_addr_base",
    "AttributeList",
    "BaseAttribute",
    "BaseProperty",
    "BasePropertyListProperty",
    "BasePropertyListPropertyWidget",
    "BaseRegister",
    "BoolAttributeWidget",
    "BoolIgnoreAttributeWidget",
    "BoolIgnoreProperty",
    "BoolProperty",
    "BoolRegister",
    "ComplexAttributeListProperty",
    "ComplexAttributeWidget",
    "ComplexProperty",
    "ConstantIntRegister",
    "CurveAttributeWidget",
    "CurveProperty",
    "CurveSelectAttributeWidget",
    "CurveSelectListProperty",
    "CurveSelectProperty",
    "DataAttributeWidget",
    "DataProperty",
    "FilterAttributeWidget",
    "FilterProperty",
    "FilterRegister",
    "FloatAttributeListProperty",
    "FloatAttributeWidget",
    "FloatProperty",
    "FloatRegister",
    "FrequencyProperty",
    "FrequencyRegister",
    "GainRegister",
    "IORegister",
    "IntAttributeWidget",
    "IntProperty",
    "IntRegister",
    "LedAttributeWidget",
    "LedProperty",
    "LongRegister",
    "ModuleAttribute",
    "NumberProperty",
    "PWMRegister",
    "PhaseProperty",
    "PhaseRegister",
    "PlotAttributeWidget",
    "Plotter",
    "ProxyProperty",
    "SelectAttributeWidget",
    "SelectProperty",
    "SelectRegister",
    "StringAttributeWidget",
    "StringProperty",
    "TextAttributeWidget",
    "TextProperty",
    "epsilon",
    "recursive_getattr",
    "recursive_setattr",
    "DoSetup",
    "DuplicateFilter",
    "ExpectedPyrplError",
    "HardwareModule",
    "Module",
    "ModuleMetaClass",
    "ModuleWidget",
    "SignalLauncher",
    "SignalModule",
    "unique_list",
    "CurveDB",
    "XYSeries",
]
