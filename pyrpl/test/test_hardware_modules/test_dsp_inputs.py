import logging
from pyrpl.test.test_base import TestPyrpl
import pytest

logger = logging.getLogger(name=__name__)


@pytest.fixture(scope="class")
def setup_lockbox(hardware_session):
    """
    Class-scoped fixture that sets up lockbox once for all tests in this class.
    Must use hardware_session directly since _inject_pyrpl is instance-scoped.
    """
    # Access pyrpl from the session
    pyrpl = hardware_session.pyrpl

    # Setup
    print("Setting up lockbox for TestInput...")
    pyrpl.lockbox.classname = "Interferometer"
    lockbox = pyrpl.lockbox

    yield

    # Teardown
    print("Tearing down lockbox for TestInput...")
    lockbox.auto_lock = False
    lockbox.unlock()
    for key in lockbox.outputs.keys():
        lockbox.outputs[key].pid.free()
        lockbox.outputs[key].pid.output_direct = "off"
    lockbox.asg.free()


class TestInput(TestPyrpl):
    @property
    def lockbox(self):
        return self.pyrpl.lockbox

    def test_input(self, setup_lockbox):
        self.lockbox.sequence[0].input = "port1"
        assert self.lockbox.sequence[0].input == "port1", self.lockbox.sequence[0].input
        self.lockbox.sequence[0].input = "port2"
        assert self.lockbox.sequence[0].input == "port2", self.lockbox.sequence[0].input
        self.lockbox.sequence[0].input = self.lockbox.inputs.port1
        assert self.lockbox.sequence[0].input == "port1", self.lockbox.sequence[0].input
        self.pyrpl.rp.pid0.input = self.lockbox.inputs.port2
        assert self.pyrpl.rp.pid0.input == "lockbox.inputs.port2", self.pyrpl.rp.pid0.input
        self.pyrpl.rp.pid0.input = self.lockbox.sequence[0].input
        assert self.pyrpl.rp.pid0.input == "lockbox.inputs.port1", self.pyrpl.rp.pid0.input
