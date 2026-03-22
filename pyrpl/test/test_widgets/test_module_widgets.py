import logging
from pyrpl.test.test_base import TestPyrpl

logger = logging.getLogger(name=__name__)


class TestModuleWidgets(TestPyrpl):
    OPEN_ALL_DOCKWIDGETS = True  # forces all DockWidgets to become visible
