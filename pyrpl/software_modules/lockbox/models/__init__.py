import logging

from .interferometer import (
    InterferometerPort1,
    InterferometerPort2,
    Interferometer,
    PdhInterferometerPort1,
    PdhInterferometerPort2,
    PdhInterferometer,
)
from .fabryperot import (
    Lorentz,
    FPReflection,
    FPTransmission,
    FPAnalogPdh,
    FPPdh,
    FPTilt,
    FabryPerot,
    HighFinesseInput,
    HighFinesseReflection,
    HighFinesseTransmission,
    HighFinesseAnalogPdh,
    HighFinessePdh,
    HighFinesseFabryPerot,
)
from .linear import LinearInputDirect, Linear
from .custom_lockbox_example import (
    CustomInputClass,
    CustomLockbox,
    ExampleLoop,
    ExampleLoopLockbox,
    GalvanicIsolationLoopLockbox,
    ShortLoopLockbox,
)
from .pll import PllInput, FilteredInput, PfdErrorSignal, FilteredSignal, SlowOutputProperty, Pll

# try to import user models if applicable
import sys
import os
from ....directories import user_lockbox_dir

logger = logging.getLogger(name=__name__)

__all__ = [
    "InterferometerPort1",
    "InterferometerPort2",
    "Interferometer",
    "PdhInterferometerPort1",
    "PdhInterferometerPort2",
    "PdhInterferometer",
    "Lorentz",
    "FPReflection",
    "FPTransmission",
    "FPAnalogPdh",
    "FPPdh",
    "FPTilt",
    "FabryPerot",
    "HighFinesseInput",
    "HighFinesseReflection",
    "HighFinesseTransmission",
    "HighFinesseAnalogPdh",
    "HighFinessePdh",
    "HighFinesseFabryPerot",
    "LinearInputDirect",
    "Linear",
    "CustomInputClass",
    "CustomLockbox",
    "ExampleLoop",
    "ExampleLoopLockbox",
    "GalvanicIsolationLoopLockbox",
    "ShortLoopLockbox",
    "PllInput",
    "FilteredInput",
    "PfdErrorSignal",
    "FilteredSignal",
    "SlowOutputProperty",
    "Pll",
]

sys.path.append(user_lockbox_dir)

usermodels = []
module = None
try:
    for module in os.listdir(user_lockbox_dir):
        if module == "__init__.py" or module[-3:] != ".py":
            continue
        usermodels.append(__import__(module[:-3], locals(), globals(), [], 0))
        logger.debug(f"Custom user models from {module} were successfully imported!")
except KeyError:
    logger.warning(
        "An error occured during the import of user model files! "
        "The exception occured during the import of module '%s'. ",
        module,
    )
    raise
