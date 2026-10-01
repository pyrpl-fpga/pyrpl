"""Standalone two-input vectoring CORDIC hardware module."""

from math import tau

from ..attributes import FloatRegister, IntRegister, SelectRegister
from ..widgets.module_widgets import CordicWidget
from .dsp import DspModule, InputSelectRegister, all_inputs


def turns_to_radians(turns):
    """Convert a CORDIC phase expressed in turns to radians."""
    return turns * tau


def turns_to_degrees(turns):
    """Convert a CORDIC phase expressed in turns to degrees."""
    return turns * 360.0


class Cordic(DspModule):
    """Compute the continuous phase of two independently routed signals.

    With ``input_pair='independent'``, ``input`` is the in-phase component and
    ``input_q`` is the quadrature component. Selecting ``iq0``, ``iq1`` or
    ``iq2`` instead uses that module's filtered quadrature pair directly. The
    output represents ``atan2(Q, I)`` in turns and includes a saturating
    two-bit turn counter around a 12-bit fractional phase.
    """

    _widget_class = CordicWidget
    _setup_attributes = ["input_pair", "input", "input_q", "output_direct"]
    _gui_attributes = _setup_attributes
    _delay = 10

    input_q = InputSelectRegister(
        0x14,
        options=all_inputs,
        default="in2",
        doc="selects the quadrature input signal of the CORDIC module",
    )
    input_pair = SelectRegister(
        0x1C,
        options={"independent": 0, "iq0": 1, "iq1": 2, "iq2": 3},
        default="independent",
        doc=(
            "selects independent DSP inputs or the directly connected, filtered "
            "I/Q pair of one IQ module"
        ),
    )
    abi_version = IntRegister(
        0x18,
        doc="CORDIC hardware ABI signature ('COR' followed by its revision)",
    )
    current_output_signal = FloatRegister(
        0x10,
        bits=14,
        norm=2**12,
        doc="current unwrapped phase [turns]",
    )

    @property
    def input_i(self):
        """Alias for the ordinary DSP input, used as the in-phase input."""
        return self.input

    @input_i.setter
    def input_i(self, value):
        self.input = value

    @staticmethod
    def to_radians(turns):
        """Convert an output value in turns to radians."""
        return turns_to_radians(turns)

    @staticmethod
    def to_degrees(turns):
        """Convert an output value in turns to degrees."""
        return turns_to_degrees(turns)
