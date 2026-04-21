import logging

from pyrpl.software_modules.module_managers import ModuleManager
from pyrpl.test.test_base import TestPyrpl
from pyrpl.widgets.yml_editor import YmlEditor

logger = logging.getLogger(name=__name__)


class TestYmlEditor(TestPyrpl):
    # somehow the file seems to suffer from other nosetests, so pick an
    # individual name for this test:
    # tmp_config_file = "nosetests_config_scope.yml"

    def teardown_method(self):
        pass

    def test_yml_editor(self):
        for mod in self.pyrpl.modules:
            if not isinstance(mod, ModuleManager):
                widg = YmlEditor(mod, None)  # Edit current state
                widg.show()
                widg.load_all()
                widg.save()
                widg.cancel()
