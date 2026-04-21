from ...module_attributes import ModuleDictProperty, ModuleProperty
from ...modules import Module
from ...software_modules.module_managers import InsufficientResourceError
from ..loop import Loop, PlotLoop


class LockboxModule(Module):
    @property
    def lockbox(self):
        parent = self
        while not isinstance(parent, Lockbox):
            parent = parent.parent
        return parent


class LockboxModuleDictProperty(ModuleDictProperty):
    default_module_cls = LockboxModule


class LockboxLoop(Loop, LockboxModule):
    """
    A Loop with a property 'lockbox' referring to the lockbox
    """


class LockboxPlotLoop(PlotLoop, LockboxLoop):
    """
    A PlotLoop with a property 'lockbox' referring to the lockbox
    """


from .gainoptimizer import GainOptimizer
from .input import (
    CalibrationData,
    InputDirect,
    InputFromOutput,
    InputIq,
    InputSignal,
    IqFilterProperty,
    IqQuadratureFactorProperty,
    Signal,
)
from .lockbox import Lockbox
from .output import AdditionalFilterAttribute, OutputSignal, PiezoOutput

__all__ = [
    "LockboxModule",
    "LockboxModuleDictProperty",
    "LockboxLoop",
    "LockboxPlotLoop",
    "CalibrationData",
    "Signal",
    "InputDirect",
    "InputSignal",
    "InputFromOutput",
    "IqQuadratureFactorProperty",
    "IqFilterProperty",
    "InputIq",
    "AdditionalFilterAttribute",
    "OutputSignal",
    "PiezoOutput",
    "InsufficientResourceError",
    "Lockbox",
    "GainOptimizer",
]
