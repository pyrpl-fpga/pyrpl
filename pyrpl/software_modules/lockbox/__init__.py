from ...modules import Module
from ...module_attributes import ModuleProperty, ModuleDictProperty
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


from .input import (
    CalibrationData,
    Signal,
    InputDirect,
    InputSignal,
    InputFromOutput,
    IqQuadratureFactorProperty,
    IqFilterProperty,
    InputIq,
)
from .output import AdditionalFilterAttribute, OutputSignal, PiezoOutput
from .lockbox import Lockbox
from .gainoptimizer import GainOptimizer

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
