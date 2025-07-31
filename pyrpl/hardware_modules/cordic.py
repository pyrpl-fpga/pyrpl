"""

"""

import time
from .dsp import all_inputs, dsp_addr_base, InputSelectRegister
from ..attributes import *
from ..modules import HardwareModule

logger = logging.getLogger(name=__name__)







class Cordic(HardwareModule):
    name = 'Cordic'
    # _widget_class = ScopeWidget
    # _gui_attributes = ["input1",
    #                    "input2",
    #                    "duration",
    #                    "average",
    #                    "trigger_source",
    #                    "trigger_delay",
    #                    "threshold",
    #                    #"threshold_ch1",
    #                    #"threshold_ch2",
    #                    "hysteresis",
    #                    "ch1_active",
    #                    "ch2_active",
    #                    "ch_math_active",
    #                    "math_formula",
    #                    "xy_mode"]
    # running_state last for proper acquisition setup
    # _setup_attributes = _gui_attributes + ["rolling_mode"]
    # changing these resets the acquisition and autoscale (calls setup())

    addr_base = dsp_addr_base('cordic')

    @property
    def inputs(self):
        return list(all_inputs(self).keys())

    # the scope inputs and asg outputs have the same dsp id
    inputI = InputSelectRegister(0x0,
                                 options=all_inputs,
                                 default='in1',
                                 ignore_errors=True,
                                 doc="selects the I input signal of the cordic module")

    inputQ = InputSelectRegister(- addr_base + dsp_addr_base('iq2_2') + 0x0,
                                 options=all_inputs,
                                 default='in2',
                                 ignore_errors=True,
                                 doc="selects the Q input signal of the cordic module")


