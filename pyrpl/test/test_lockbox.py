import logging

import pytest

from ..async_utils import ensure_future, sleep, sleep_async
from .test_base import TestPyrpl

logger = logging.getLogger(name=__name__)


@pytest.fixture(scope="class")
def setup_fake_system_once(hardware_session):
    """
    Setup fake system once for the entire test class.
    When frequency modulation will be available on the IQ modules, we could
    simulate a Non-linear system such as a Fabry Perot cavity,
    which would be really cool... At the moment, we only simulate a linear
    system with a pid.
    """

    r = hardware_session.rp
    pyrpl = hardware_session.pyrpl

    # if pyrpl.lockbox.inputs is not None:
    #     pyrpl.lockbox._clear()  # make sure no old lockbox config exists
    pid = r.pid1
    pid.free()  # make sure pid is not used by another module

    print("Setting up fake system for TestLockbox...")
    pyrpl.lockbox.classname = "Interferometer"
    lockbox = pyrpl.lockbox
    pid.i = -1
    pid.p = -1
    pid.paused = False
    pid.differential_mode_enabled = False
    pid.input = lockbox.outputs.piezo
    lockbox.inputs.port1.input_signal = pid
    output = lockbox.outputs.values()[0]
    print(output.name)
    output.sweep_frequency = 50
    output.sweep_amplitude = 0.3
    output.sweep_offset = 0  # used to be 0.1 but if you sweep for too long, ival saturates
    output.sweep_waveform = "sin"

    lockbox.calibrate_all(timeout_min=20)  # extra timeout because of remote connection delays

    lockbox.sequence.append({"gain_factor": 1.0e6})
    lockbox.sequence[-1].input = "port1"
    output.desired_unity_gain_frequency = 1e7
    lockbox.sequence[-1].outputs.piezo.lock_on = True
    lockbox.sequence[-1].outputs.piezo.reset_offset = True
    lockbox.sequence[-1].duration = 1  # It takes 1 s to acquire lock

    yield

    # Cleanup after all tests (if needed)
    print("Tearing down fake system for TestLockbox...")
    lockbox.auto_lock = False
    lockbox.unlock()
    for output in lockbox.outputs:
        output.pid.free()
        output.pid.output_direct = "off"
    lockbox.asg.free()

    lockbox._clear()

    pid.p = 0
    pid.i = 0
    pid.ival = 0


class TestLockbox(TestPyrpl):
    # source_config_file = "nosetests_source_lockbox.yml"

    @property
    def lockbox(self):
        return self.pyrpl.lockbox

    def test_create_stage(self):
        old_len = len(self.lockbox.sequence)
        widget = self.lockbox._create_widget()
        self.lockbox.sequence.append({"gain_factor": 2.0})
        assert len(self.lockbox.sequence) == old_len + 1

        # wait for stage creation signal to impact the GUI (async sleep to
        # let the EventLoop handle the notifiction from sequence...)
        sleep(0.1)
        assert len(widget.sequence_widget.stage_widgets) == old_len + 1
        self.lockbox.sequence.append({"gain_factor": 3.0})

        assert self.lockbox.sequence[-1].gain_factor == 3.0
        assert self.lockbox.sequence[-2].name == old_len

        assert self.lockbox.sequence[old_len].gain_factor == 2.0
        self.lockbox.sequence.pop()

        assert len(self.lockbox.sequence) == old_len + 1
        assert self.lockbox.sequence.pop()["gain_factor"] == 2.0

    def test_change_classname(self):
        for classname in ["Linear", "FabryPerot", "Interferometer"]:
            self.pyrpl.lockbox.classname = classname
            assert self.pyrpl.lockbox.classname == classname

    def test_real_lock(self, setup_fake_system_once):
        self.lockbox.calibrate_all(timeout_min=20)
        self.lockbox.lock()
        assert self.lockbox.is_locked()

    def test_calibrate(self, setup_fake_system_once):
        lockbox = self.pyrpl.lockbox
        self.pyrpl.rp.pid1.i = 0
        self.pyrpl.rp.pid1.p = 1
        self.pyrpl.rp.pid1.ival = 0

        output = lockbox.outputs.values()[0]

        output.sweep_offset = 0.1

        lockbox.calibrate_all(timeout_min=20)
        cal = lockbox.inputs.port1.calibration_data
        assert abs(cal.mean - 0.1) < 0.01, cal.mean
        assert abs(cal.max - 0.4) < 0.01, cal.max
        assert abs(cal.min - (-0.2)) < 0.01, cal.min
        assert abs(cal.amplitude - (0.3)) < 0.01, cal.amplitude

        output.sweep_offset = 0

    def test_sleep_while_locked(self, setup_fake_system_once):
        self.lockbox.calibrate_all(timeout_min=20)
        self.lockbox.lock()
        pid = self.pyrpl.rp.pid1

        async def unlock_later(time_s):
            await sleep_async(time_s)
            pid.ival = 1
            pid.p = 0
            pid.i = 0

        res = self.lockbox.sleep_while_locked(1)
        assert res
        ensure_future(unlock_later(0.5))
        res = self.lockbox.sleep_while_locked(10)
        assert not res
        pid.ival = 0
        pid.p = -1
        pid.i = -1

    def test_auto_relock(self, setup_fake_system_once):
        self.lockbox.auto_lock = True

        # monkey patch a function to make sure lockbox went to first stage
        # again
        def increment(obj):
            obj.first_stage_counter += 1

        self.lockbox.__class__.increment = increment
        self.lockbox.first_stage_counter = 0

        self.lockbox.calibrate_all(timeout_min=20)
        self.lockbox.lock_async()
        assert self.lockbox.classname == "Interferometer"

        self.lockbox.sequence[0].function_call = "increment"
        pid = self.pyrpl.rp.pid1

        async def unlock_later(time_s):
            await sleep_async(time_s)
            pid.ival = 1
            pid.p = 0
            pid.i = 0
            await sleep_async(time_s)
            pid.p = -1
            pid.i = -1

        sleep(0.5)
        assert self.lockbox.is_locked()
        ensure_future(unlock_later(1))
        sleep(10)
        assert self.lockbox.is_locked()
        assert self.lockbox.first_stage_counter == 2

        # make a config file for a lock including iir that locks onto itself
        # then load another state and lock a pid with existing integrator
        # test lock with islocked, test autorelock, test unit issues,
        # test change of lockbox with incompatible settings, test saving of
        # relevant lock parameters.
