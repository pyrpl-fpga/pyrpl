import logging
logger = logging.getLogger(name=__name__)
from .test_base import TestPyrpl
import pytest


class TestExample(TestPyrpl):
    @pytest.fixture(autouse=True)
    def setup_asg(self):
        self.asg = self.pyrpl.rp.asg0

    #you are welcome to change the following silly tests to something useful
    def test_example(self):
        if 1 > 2:
            assert False

    def test_example2(self):
        if self.asg.frequency < 0:
            assert False

    def test_example3(self):
        if not self.asg.frequency >= 0:
            assert False
