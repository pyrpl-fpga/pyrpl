# unitary test for the RedPitaya and Pyrpl modules and baseclass for all other
# tests
import logging
import pytest
from ..async_utils import sleep

logger = logging.getLogger(name=__name__)

# I don't know why, in nosetests, the logger goes to UNSET...
logger_quamash = logging.getLogger(name="quamash")
logger_quamash.setLevel(logging.INFO)


class TestPyrpl:
    """Base class for all pyrpl tests."""

    # names of the configfiles to use
    source_config_file = "nosetests_source.yml"
    tmp_config_file = "nosetests_config.yml"
    OPEN_ALL_DOCKWIDGETS = False

    @pytest.fixture(autouse=True)
    def _inject_pyrpl(self, hardware_session):
        """Inject the shared pyrpl instance into each test class instance."""

        # 1. UNPACK THE SESSION CONTAINER
        # hardware_session is the namedtuple from conftest.py
        self.r = hardware_session.rp
        self.pyrpl = hardware_session.pyrpl  # This is the actual Pyrpl app object (or None)

        # 2. EXTRACT TIMING (Use the clean names defined in conftest.py)
        self.read_time = hardware_session.read_time
        self.write_time = hardware_session.write_time
        self.communication_time = (self.read_time + self.write_time) / 2.0

        # 3. WIDGET SETUP (Only if Pyrpl app exists)
        if self.pyrpl is not None and self.OPEN_ALL_DOCKWIDGETS:
            if not getattr(self.pyrpl, "_widgets_opened", False):
                # Safeguard against empty widgets list
                if hasattr(self.pyrpl, "widgets") and len(self.pyrpl.widgets) > 0:
                    for name, dock_widget in self.pyrpl.widgets[0].dock_widgets.items():
                        print("Showing widget %s..." % name)
                        dock_widget.setVisible(True)
                    sleep(3.0)  # give some time for startup
                    self.pyrpl._widgets_opened = True

        # Initialize curves list for this test class
        if not hasattr(self, "curves"):
            self.curves = []

        yield

        # Per-class teardown
        if hasattr(self, "curves"):
            while len(self.curves) > 0:
                self.curves.pop().delete()


# only one test class per file is allowed due to conflicts with
# inheritance from TestPyrpl base class
