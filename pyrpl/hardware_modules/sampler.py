import contextlib

import numpy as np

from ..attributes import FloatRegister
from ..modules import HardwareModule
from ..pyrpl_utils import time
from .dsp import DSP_INPUTS, dsp_addr_base


class SamplerSignalRegister(FloatRegister):
    """Current value of one DSP signal.

    The register address follows the signal's routing code in the loaded FPGA
    profile, which may differ from the default code in ``DSP_INPUTS``.
    """

    def __init__(self, signal, **kwargs):
        self.signal = signal
        address = 0x10 + DSP_INPUTS[signal] * 0x10000
        super().__init__(address, **kwargs)

    def get_value(self, obj):
        address = dsp_addr_base(self.signal, obj) + 0x10 - obj.addr_base
        return self.to_python(obj, obj._read(address))


class Sampler(HardwareModule):
    """this module provides a sample of each signal.

    This is a momentary workaround, will be improved later on with an upgraded FPGA version"""

    addr_base = 0x40300000

    def stats(self, signal="in1", t=1e-2):
        """
        computes the mean, standard deviation, min and max of the chosen signal over duration t

        Parameters
        ----------
        signal: input signal
        t: duration over which to average

        obsolete:
        n: equivalent number of FPGA clock cycles to average over

        Returns
        -------
        mean, stddev, max, min: mean and standard deviation of all samples

        """

        # signal can be a string, or a module (whose name is the name of the signal we'll use)
        with contextlib.suppress(AttributeError):
            signal = signal.name

        nn = 0
        cum = 0
        cumsq = 0
        max = -np.inf
        min = np.inf
        t0 = time()  # get start time
        while nn == 0 or time() < t0 + t:  # do at least one sample
            nn += 1
            value = self.__getattribute__(signal)
            cum += value
            cumsq += value**2.0
            if value > max:
                max = value
            if value < min:
                min = value
        nn = float(nn)
        mean = cum / nn
        variance = cumsq / nn - mean**2.0
        # while mathematically nonsense, this can happen numerically
        if variance < 0:
            # this means the variance is tiny and can be assumed zero
            variance = 0
        stddev = variance**0.5
        return mean, stddev, max, min

    def mean_stddev(self, signal="in1", t=1e-2):
        """
        computes the mean and standard deviation of the chosen signal

        Parameters
        ----------
        signal: input signal
        t: duration over which to average

        obsolete:
        n: equivalent number of FPGA clock cycles to average over

        Returns
        -------
        mean, stddev: mean and standard deviation of all samples

        """
        self._logger.warning(
            "Sampler.mean_stddev() is obsolete. Please use Sampler.stats() instead!"
        )
        mean, stddev, max, min = self.stats(signal=signal, t=t)
        return mean, stddev


# generate one attribute in Sampler for each DSP signal
for inp in DSP_INPUTS:
    setattr(
        Sampler,
        inp,
        SamplerSignalRegister(inp, bits=14, norm=2**13 - 1, doc="current value of " + inp),
    )
