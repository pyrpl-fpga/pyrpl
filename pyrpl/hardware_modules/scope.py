"""
The scope works similar to the ASG but in reverse: Two channels are
available. A table of :math:`2^{14}` datapoints for each channel is
filled with the time series of incoming data. Downloading a full trace
takes about 10 ms over standard ethernet. The rate at which the memory
is filled is the sampling rate (125 MHz) divided by the value of
'decimation'. The property 'average' decides whether each datapoint is a
single sample or the average of all samples over the decimation
interval.

.. code:: python

    s = r.scope # shortcut
    print("Available decimation factors:", s.decimations)
    print("Trigger sources:", s.trigger_sources)
    print("Available inputs: ", s.inputs)

Let's have a look at a signal generated by asg1. Later we will use
convenience functions to reduce the amount of code necessary to set up
the scope:

.. code:: python

    asg = r.asg1
    s = r.scope

    # turn off asg so the scope has a chance to measure its "off-state" as well
    asg.output_direct = "off"

    # setup scope
    s.input1 = 'asg1'

    # pass asg signal through pid0 with a simple integrator - just for fun (detailed explanations for pid will follow)
    r.pid0.input = 'asg1'
    r.pid0.ival = 0 # reset the integrator to zero
    r.pid0.i = 1000 # unity gain frequency of 1000 hz
    r.pid0.p = 1.0 # proportional gain of 1.0
    r.pid0.inputfilter = [0,0,0,0] # leave input filter disabled for now

    # show pid output on channel2
    s.input2 = 'pid0'

    # trig at zero volt crossing
    s.threshold_ch1 = 0

    # positive/negative slope is detected by waiting for input to
    # sweep through hysteresis around the trigger threshold in
    # the right direction
    s.hysteresis_ch1 = 0.01

    # trigger on the input signal positive slope
    s.trigger_source = 'ch1_positive_edge'

    # take data symetrically around the trigger event
    s.trigger_delay = 0

    # set decimation factor to 64 -> full scope trace is 8ns * 2^14 * decimation = 8.3 ms long
    s.decimation = 64

    # launch a single (asynchronous) curve acquisition, the asynchronous
    # acquisition means that the function returns immediately, eventhough the
    # data-acquisition is still going on.
    res = s.curve_async()

    print("Before turning on asg:")
    print("Curve ready:", s.curve_ready()) # trigger should still be armed

    # turn on asg and leave enough time for the scope to record the data
    asg.setup(frequency=1e3, amplitude=0.3, start_phase=90, waveform='halframp', trigger_source='immediately')
    sleep(0.010)

    # check that the trigger has been disarmed
    print("After turning on asg:")
    print("Curve ready:", s.curve_ready())
    print("Trigger event age [ms]:",8e-9*((
    s.current_timestamp&0xFFFFFFFFFFFFFFFF) - s.trigger_timestamp)*1000)

    # The function curve_async returns a *future* (or promise) of the curve. To
    # access the actual curve, use result()
    ch1, ch2 = res.result()

    # plot the data
    %matplotlib inline
    plt.plot(s.times*1e3, ch1, s.times*1e3, ch2)
    plt.xlabel("Time [ms]")
    plt.ylabel("Voltage")

What do we see? The blue trace for channel 1 shows just the output
signal of the asg. The time=0 corresponds to the trigger event. One can
see that the trigger was not activated by the constant signal of 0 at
the beginning, since it did not cross the hysteresis interval. One can
also see a 'bug': After setting up the asg, it outputs the first value
of its data table until its waveform output is triggered. For the
halframp signal, as it is implemented in pyrpl, this is the maximally
negative value. However, we passed the argument start\_phase=90 to the
asg.setup function, which shifts the first point by a quarter period.
Can you guess what happens when we set start\_phase=180? You should try
it out!

In green, we see the same signal, filtered through the pid module. The
nonzero proportional gain leads to instant jumps along with the asg
signal. The integrator is responsible for the constant decrease rate at
the beginning, and the low-pass that smoothens the asg waveform a
little. One can also foresee that, if we are not paying attention, too
large an integrator gain will quickly saturate the outputs.

.. code:: python

    # useful functions for scope diagnostics
    print("Curve ready:", s.curve_ready())
    print("Trigger source:",s.trigger_source)
    print("Trigger threshold [V]:",s.threshold_ch1)
    print("Averaging:",s.average)
    print("Trigger delay [s]:",s.trigger_delay)
    print("Trace duration [s]: ",s.duration)
    print("Trigger hysteresis [V]", s.hysteresis_ch1)
    print("Current scope time [cycles]:",hex(s.current_timestamp))
    print("Trigger time [cycles]:",hex(s.trigger_timestamp))
    print("Current voltage on channel 1 [V]:", r.scope.voltage_in1)
    print("First point in data buffer 1 [V]:", s.ch1_firstpoint)
"""

import time
from .dsp import all_inputs, dsp_addr_base, InputSelectRegister
from ..acquisition_module import AcquisitionModule
from ..async_utils import wait, ensure_future, sleep_async
from ..pyrpl_utils import sorted_dict
from ..attributes import *
from ..modules import HardwareModule
from ..pyrpl_utils import time
from ..widgets.module_widgets import ScopeWidget

logger = logging.getLogger(name=__name__)

data_length = 2**14


# ==========================================
# The following properties are all linked:
#  - decimation
#  - duration
#  - sampling_time
# decimation is the "master": changing it updates
# the 2 others.
# ==========================================
class DecimationRegister(SelectRegister):
    """
    Careful: changing decimation changes duration and sampling_time as well
    """
    def set_value(self, obj, value):
        SelectRegister.set_value(self, obj, value)
        obj.__class__.duration.value_updated(obj, obj.duration)
        obj.__class__.sampling_time.value_updated(obj, obj.sampling_time)


class DurationProperty(SelectProperty):
    def get_value(self, obj):
        return obj.sampling_time * float(obj.data_length)

    def validate_and_normalize(self, obj, value):
        # gets next-higher value
        value = float(value)
        options = self.options(obj).keys()
        try:
            return min([opt for opt in options if opt >= value],
                   key=lambda x: abs(x - value))
        except ValueError:
            obj._logger.info("Selected duration is longer than "
                             "physically possible with the employed hardware. "
                             "Picking longest-possible value %s. ",
                             max(options))
            return max(options)

    def set_value(self, obj, value):
        """sets returns the duration of a full scope sequence the rounding
        makes sure that the actual value is longer or equal to the set value"""
        obj.sampling_time = float(value) / obj.data_length


class SamplingTimeProperty(SelectProperty):
    def get_value(self, obj):
        return 8e-9 * float(obj.decimation)

    def validate_and_normalize(self, obj, value):
        # gets next-lower value
        value = float(value)
        options = self.options(obj).keys()
        try:
            return min([opt for opt in options if opt <= value],
                   key=lambda x: abs(x - value))
        except ValueError:
            obj._logger.info("Selected sampling time is shorter than "
                             "physically possible with the employed hardware. "
                             "Picking shortest-possible value %s. ",
                             min(options))
            return min(options)

    def set_value(self, instance, value):
        """sets or returns the time separation between two subsequent
        points of a scope trace the rounding makes sure that the actual
        value is shorter or equal to the set value"""
        instance.decimation = float(value) / 8e-9


class Scope(HardwareModule, AcquisitionModule):
    MIN_DELAY_CONTINUOUS_ROLLING_MS = 20
    addr_base = 0x40100000
    name = 'scope'
    _widget_class = ScopeWidget
    # run = ModuleProperty(ScopeAcquisitionManager)
    _gui_attributes = ["input1",
                       "input2",
                       "duration",
                       "average",
                       "trigger_source",
                       "trigger_delay",
                       "threshold",
                       #"threshold_ch1",
                       #"threshold_ch2",
                       "hysteresis",
                       "ch1_active",
                       "ch2_active",
                       "ch_math_active",
                       "math_formula",
                       "xy_mode"]
    # running_state last for proper acquisition setup
    _setup_attributes = _gui_attributes + ["rolling_mode"]
    # changing these resets the acquisition and autoscale (calls setup())

    data_length = data_length  # to use it in a list comprehension

    rolling_mode = BoolProperty(default=True,
                                doc="In rolling mode, the curve is "
                                    "continuously acquired and "
                                    "translated from the right to the "
                                    "left of the screen while new "
                                    "data arrive.",
                                call_setup=True)

    @property
    def inputs(self):
        return list(all_inputs(self).keys())

    # the scope inputs and asg outputs have the same dsp id
    input1 = InputSelectRegister(- addr_base + dsp_addr_base('asg0') + 0x0,
                                 options=all_inputs,
                                 default='in1',
                                 ignore_errors=True,
                                 doc="selects the input signal of the module")

    input2 = InputSelectRegister(- addr_base + dsp_addr_base('asg1') + 0x0,
                                 options=all_inputs,
                                 default='in2',
                                 ignore_errors=True,
                                 doc="selects the input signal of the module")

    _reset_writestate_machine = BoolRegister(0x0, 1,
                                             doc="Set to True to reset "
                                                 "writestate machine. "
                                                 "Automatically goes back "
                                                 "to false.")

    _trigger_armed = BoolRegister(0x0, 0, doc="Set to True to arm trigger")

    _trigger_sources = sorted_dict({"off": 0,
                                    "immediately": 1,
                                    "ch1_positive_edge": 2,
                                    "ch1_negative_edge": 3,
                                    "ch2_positive_edge": 4,
                                    "ch2_negative_edge": 5,
                                    "ext_positive_edge": 6,  # DIO0_P pin
                                    "ext_negative_edge": 7,  # DIO0_P pin
                                    "asg0": 8,
                                    "asg1": 9,
                                    "dsp": 10}, #dsp trig module trigger
                                    sort_by_values=True)

    trigger_sources = _trigger_sources.keys()  # help for the user

    _trigger_source_register = SelectRegister(0x4, doc="Trigger source",
                                              options=_trigger_sources)

    trigger_source = SelectProperty(default='immediately',
                                    options=_trigger_sources.keys(),
                                    doc="Trigger source for the scope. Use "
                                        "'immediately' if no "
                                        "synchronisation is required. "
                                        "Trigger_source will be ignored in "
                                        "rolling_mode.",
                                    call_setup=True)

    _trigger_debounce = IntRegister(0x90, doc="Trigger debounce time [cycles]")

    trigger_debounce = FloatRegister(0x90, bits=20, norm=125e6,
                                     doc="Trigger debounce time [s]")

    # same theshold and hysteresis for both channels
    threshold = FloatRegister(0x8, bits=14, norm=2 ** 13,
                                  doc="trigger threshold [volts]")
    hysteresis = FloatRegister(0x20, bits=14, norm=2 ** 13,
                                    doc="hysteresis for trigger [volts]")

    @property
    def threshold_ch1(self):
        self._logger.warning('The scope attribute "threshold_chx" is deprecated. '
                             'Please use "threshold" instead!')
        return self.threshold
    @threshold_ch1.setter
    def threshold_ch1(self, v):
        self._logger.warning('The scope attribute "threshold_chx" is deprecated. '
                             'Please use "threshold" instead!')
        self.threshold = v
    @property
    def threshold_ch2(self):
        self._logger.warning('The scope attribute "threshold_chx" is deprecated. '
                             'Please use "threshold" instead!')
        return self.threshold
    @threshold_ch2.setter
    def threshold_ch2(self, v):
        self._logger.warning('The scope attribute "threshold_chx" is deprecated. '
                             'Please use "threshold" instead!')
        self.threshold = v
    @property
    def hysteresis_ch1(self):
        self._logger.warning('The scope attribute "hysteresis_chx" is deprecated. '
                             'Please use "hysteresis" instead!')
        return self.hysteresis
    @hysteresis_ch1.setter
    def hysteresis_ch1(self, v):
        self._logger.warning('The scope attribute "hysteresis_chx" is deprecated. '
                             'Please use "hysteresis" instead!')
        self.hysteresis = v
    @property
    def hysteresis_ch2(self):
        self._logger.warning('The scope attribute "hysteresis_chx" is deprecated. '
                             'Please use "hysteresis" instead!')
        return self.hysteresis
    @hysteresis_ch2.setter
    def hysteresis_ch2(self, v):
        self._logger.warning('The scope attribute "hysteresis_chx" is deprecated. '
                             'Please use "hysteresis" instead!')
        self.hysteresis = v
    #threshold_ch1 = FloatRegister(0x8, bits=14, norm=2 ** 13,
    #                              doc="ch1 trigger threshold [volts]")
    #threshold_ch2 = FloatRegister(0xC, bits=14, norm=2 ** 13,
    #                              doc="ch1 trigger threshold [volts]")
    #hysteresis_ch1 = FloatRegister(0x20, bits=14, norm=2 ** 13,
    #                               doc="hysteresis for ch1 trigger [volts]")
    #hysteresis_ch2 = FloatRegister(0x24, bits=14, norm=2 ** 13,
    #                               doc="hysteresis for ch2 trigger [volts]")

    _trigger_delay_register = IntRegister(0x10,
                                 doc="number of decimated data after trigger "
                                     "written into memory [samples]")

    trigger_delay = FloatProperty(min=-10, # TriggerDelayAttribute
                                  max=8e-9 * 2 ** 30,
                                  doc="delay between trigger and "
                                      "acquisition start.\n"
                                      "negative values down to "
                                      "-duration are allowed for "
                                      "pretrigger. "
                                      "In trigger_source='immediately', "
                                      "trigger_delay is ignored.",
                                  call_setup=True)

    _trigger_delay_running = BoolRegister(0x0, 2,
                                          doc="trigger delay running ("
                                              "register adc_dly_do)")

    _adc_we_keep = BoolRegister(0x0, 3,
                                doc="Scope resets trigger automatically ("
                                    "adc_we_keep)")

    _adc_we_cnt = IntRegister(0x2C, doc="Number of samles that have passed "
                                        "since trigger was armed (adc_we_cnt)")

    current_timestamp = LongRegister(0x15C,
                                     bits=64,
                                     doc="An absolute counter "
                                         + "for the time [cycles]")

    trigger_timestamp = LongRegister(0x164,
                                     bits=64,
                                     doc="An absolute counter "
                                         + "for the trigger time [cycles]")

    _decimations = sorted_dict({2 ** n: 2 ** n for n in range(0, 17)},
                               sort_by_values=True)

    decimations = _decimations.keys()  # help for the user

    # decimation is the basic register, sampling_time and duration are slaves of it
    decimation = DecimationRegister(0x14, doc="decimation factor",
                                    default = 0x2000, # fpga default = 1s duration
                                    # customized to update duration and
                                    # sampling_time
                                    options=_decimations,
                                    call_setup=True)

    sampling_times = [8e-9 * dec for dec in decimations]

    sampling_time = SamplingTimeProperty(options=sampling_times)

    # list comprehension workaround for python 3 compatibility
    # cf. http://stackoverflow.com/questions/13905741
    durations = [st * data_length for st in sampling_times]

    duration = DurationProperty(options=durations)

    _write_pointer_current = IntRegister(0x18,
                                         doc="current write pointer "
                                             "position [samples]")

    _write_pointer_trigger = IntRegister(0x1C,
                                         doc="write pointer when trigger "
                                             "arrived [samples]")

    average = BoolRegister(0x28, 0,
                           doc="Enables averaging during decimation if set "
                               "to True")

    # equalization filter not implemented here

    voltage_in1 = FloatRegister(0x154, bits=14, norm=2 ** 13,
                                doc="in1 current value [volts]")

    voltage_in2 = FloatRegister(0x158, bits=14, norm=2 ** 13,
                                doc="in2 current value [volts]")

    voltage_out1 = FloatRegister(0x164, bits=14, norm=2 ** 13,
                                 doc="out1 current value [volts]")

    voltage_out2 = FloatRegister(0x168, bits=14, norm=2 ** 13,
                                 doc="out2 current value [volts]")

    ch1_firstpoint = FloatRegister(0x10000, bits=14, norm=2 ** 13,
                                   doc="1 sample of ch1 data [volts]")

    ch2_firstpoint = FloatRegister(0x20000, bits=14, norm=2 ** 13,
                                   doc="1 sample of ch2 data [volts]")

    pretrig_ok = BoolRegister(0x16c, 0,
                              doc="True if enough data have been acquired "
                                  "to fill the pretrig buffer")

    ch1_active = BoolProperty(default=True,
                              doc="should ch1 be displayed in the gui?")

    ch2_active = BoolProperty(default=True,
                              doc="should ch2 be displayed in the gui?")

    ch_math_active = BoolProperty(default=False,
                              doc="should ch_math be displayed in the gui?")

    math_formula = StringProperty(default='ch1 * ch2',
                                  doc="formula for channel math")

    xy_mode = BoolProperty(default=False,
                           doc="in xy-mode, data are plotted vs the other "
                               "channel (instead of time)")

    _acquisition_started = BoolProperty(default=False,
                                        doc="whether a curve acquisition has been "
                                            "initiated")

    def _ownership_changed(self, old, new):
        """
        If the scope was in continuous mode when slaved, it has to stop!!
        """
        if new is not None:
            self.stop()

    @property
    def _rawdata_ch1(self):
        """raw data from ch1"""
        # return np.array([self.to_pyint(v) for v in self._reads(0x10000,
        # self.data_length)],dtype=np.int32)
        x = np.array(self._reads(0x10000, self.data_length), dtype=np.int16)
        x[x >= 2 ** 13] -= 2 ** 14
        return x

    @property
    def _rawdata_ch2(self):
        """raw data from ch2"""
        # return np.array([self.to_pyint(v) for v in self._reads(0x20000,
        # self.data_length)],dtype=np.int32)
        x = np.array(self._reads(0x20000, self.data_length), dtype=np.int16)
        x[x >= 2 ** 13] -= 2 ** 14
        return x

    @property
    def _data_ch1(self):
        """ acquired (normalized) data from ch1"""
        return np.array(
            np.roll(self._rawdata_ch1, - (self._write_pointer_trigger +
                                          self._trigger_delay_register + 1)),
            dtype=np.float) / 2 ** 13

    @property
    def _data_ch2(self):
        """ acquired (normalized) data from ch2"""
        return np.array(
            np.roll(self._rawdata_ch2, - (self._write_pointer_trigger +
                                          self._trigger_delay_register + 1)),
            dtype=np.float) / 2 ** 13

    @property
    def _data_ch1_current(self):
        """ (unnormalized) data from ch1 while acquisition is still running"""
        return np.array(
            np.roll(self._rawdata_ch1, -(self._write_pointer_current + 1)),
            dtype=np.float) / 2 ** 13

    @property
    def _data_ch2_current(self):
        """ (unnormalized) data from ch2 while acquisition is still running"""
        return np.array(
            np.roll(self._rawdata_ch2, -(self._write_pointer_current + 1)),
            dtype=np.float) / 2 ** 13

    @property
    def times(self):
        # duration = 8e-9*self.decimation*self.data_length
        # endtime = duration*
        duration = self.duration
        trigger_delay = self.trigger_delay
        if self.trigger_source!='immediately':
            return np.linspace(trigger_delay - duration / 2.,
                               trigger_delay + duration / 2.,
                               self.data_length, endpoint=False)
        else:
            return np.linspace(0,
                               duration,
                               self.data_length, endpoint=False)

    async def wait_for_pretrigger_async(self):
        """sleeps until scope trigger is ready (buffer has enough new data)"""
        while not self.pretrig_ok:
            await sleep_async(0.001)
        ### For some reason, launching the trigger at that point would be too soon...
        await sleep_async(0.1)

    def wait_for_pretrigger(self):
        """sleeps until scope trigger is ready (buffer has enough new data)"""
        wait(self.wait_for_pretrigger_async())

    def curve_ready(self):
        """
        Returns True if new data is ready for transfer
        """
        return (not self._trigger_armed) and \
               (not self._trigger_delay_running) and self._acquisition_started

    def _curve_acquiring(self):
        """
        Returns True if data is in the process of being acquired, i.e.
        waiting for trigger event or for acquisition of data after
        trigger event.
        """
        return (self._trigger_armed or self._trigger_delay_running) \
            and self._acquisition_started

    def _get_ch(self, ch):
        if ch not in [1, 2]:
            raise ValueError("channel should be 1 or 2, got " + str(ch))
        return self._data_ch1 if ch == 1 else self._data_ch2

    # Concrete implementation of AcquisitionModule methods
    # ----------------------------------------------------

    def _prepare_averaging(self):
        super(Scope, self)._prepare_averaging()
        self.data_x = np.copy(self.times)
        self.data_avg = np.zeros((2, len(self.times)))
        self.current_avg = 0


    def _get_trace(self):
        """
        Simply pack together channel 1 and channel 2 curves in a numpy array
        """
        return np.array((self._get_ch(1), self._get_ch(2)))

    def _remaining_time(self):
        """
        :returns curve duration - ellapsed duration since last setup() call.
        """
        return self.duration - (time() - self._last_time_setup)

    async def _do_average_continuous_async(self):
        if not self._is_rolling_mode_active():
            await super(Scope, self)._do_average_continuous_async()
        else: # no need to prepare averaging
            self._start_acquisition_rolling_mode()
            while(self.running_state=="running_continuous"):
                await sleep_async(self.MIN_DELAY_CONTINUOUS_ROLLING_MS*0.001)
                self.data_x, self.data_avg = self._get_rolling_curve()
                self._emit_signal_by_name('display_curve', [self.data_x, self.data_avg])

    def _data_ready(self):
        """
        :return: True if curve is ready in the hardware, False otherwise.
        """
        return self.curve_ready()

    def _start_trace_acquisition(self):
        """
        Start acquisition of a curve in rolling_mode=False
        """
        autosave_backup = self._autosave_active
        self._autosave_active = False  # Don't save anything in config file
        # during setup!! # maybe even better in
        # BaseModule ??
        self._acquisition_started = True

        # 0. reset state machine
        self._reset_writestate_machine = True

        # set the trigger delay:
        # 1. in mode "immediately", trace goes from 0 to duration,
        if self.trigger_source == 'immediately':
            self._trigger_delay_register = self.data_length
        else: #  2. triggering on real signal
            #  a. convert float delay into counts
            delay = int(np.round(self.trigger_delay / self.sampling_time)) + \
                    self.data_length // 2
            #  b. Do the proper roundings of the trigger delay
            if delay <= 0:
                delay = 1  # bug in scope code: 0 does not work
            elif delay > 2 ** 32 - 1:
                delay = 2 ** 32 - 1
            # c. set the trigger_delay in the right fpga register
            self._trigger_delay_register = delay

        # 4. Arm the trigger: curve acquisition will only start passed this
        self._trigger_armed = True
        # 5. In case immediately, setting again _trigger_source_register
        # will cause a "software_trigger"
        self._trigger_source_register = self.trigger_source

        self._autosave_active = autosave_backup
        self._last_time_setup = time()

    def _start_acquisition_rolling_mode(self):
        self._start_trace_acquisition()
        self._trigger_source_register = 'off'
        self._trigger_armed = True

    # Rolling_mode related methods:
    # -----------------------------

    #def _start_acquisition_rolling_mode(self):
    #    self._start_acquisition()
    #    self._trigger_source_register = 'off'
    #   self._trigger_armed = True

    def _rolling_mode_allowed(self):
        """
        Only if duration larger than 0.1 s
        """
        return self.duration > 0.1

    def _is_rolling_mode_active(self):
        """
        Rolling_mode property evaluates to True and duration larger than 0.1 s
        """
        return self.rolling_mode and self._rolling_mode_allowed()

    def _get_ch_no_roll(self, ch):
        if ch not in [1, 2]:
            raise ValueError("channel should be 1 or 2, got " + str(ch))
        return self._rawdata_ch1 * 1. / 2 ** 13 if ch == 1 else \
            self._rawdata_ch2 * 1. / 2 ** 13

    def _get_rolling_curve(self):
        datas = np.zeros((2, len(self.times)))
        # Rolling mode
        wp0 = self._write_pointer_current  # write pointer
        # before acquisition
        times = self.times
        times -= times[-1]

        for ch, active in (
                (0, self.ch1_active),
                (1, self.ch2_active)):
            if active:
                datas[ch] = self._get_ch_no_roll(ch + 1)
        wp1 = self._write_pointer_current  # write pointer after
        #  acquisition
        for index, active in [(0, self.ch1_active),
                              (1, self.ch2_active)]:
            if active:
                data = datas[index]
                to_discard = (wp1 - wp0) % self.data_length  # remove
                #  data that have been affected during acq.
                data = np.roll(data, self.data_length - wp0)[
                       to_discard:]
                data = np.concatenate([[np.nan] * to_discard, data])
                datas[index] = data
        return times, datas

    # Custom behavior of AcquisitionModule methods for scope:
    # -------------------------------------------------------

    def save_curve(self):
        """
        Saves the curve(s) that is (are) currently displayed in the gui in
        the db_system. Also, returns the list [curve_ch1, curve_ch2]...
        """
        d = self.attributes_last_run
        curves = [None, None]
        for ch, active in [(0, self.ch1_active),
                           (1, self.ch2_active)]:
            if active:
                d.update({'ch': ch,
                          'name': self.curve_name + ' ch' + str(ch + 1)})
                curves[ch] = self._save_curve(self.data_x,
                                              self.data_avg[ch],
                                              **d)
        return curves
