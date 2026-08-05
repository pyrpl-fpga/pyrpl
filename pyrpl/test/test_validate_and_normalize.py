import contextlib
import logging

from pyrpl import APP
from pyrpl.software_modules import Lockbox
from pyrpl.test.test_attribute import DummyModule
from pyrpl.test.test_base import TestPyrpl
from pyrpl.test.test_load_save import scramble_values

logger = logging.getLogger(name=__name__)


class TestValidateAndNormalize(TestPyrpl):
    """
    ensures that the result of validate_and_normalize corresponds
    to the value the register actually contains for a number of random
    changes to all registers
    """

    # def test_validate_and_normalize(self):
    #     for mod in self.pyrpl.modules:
    #         for exclude in [Lockbox]:  # lockbox is too complicated here
    #             if isinstance(mod, exclude):
    #                 break
    #         else:
    #             yield self.assert_validate_and_normalize, mod
    #             # make sure all modules are stopped at the end of this test
    #             try:
    #                 mod.stop()
    #             except:
    #                 pass

    def test_validate_and_normalize_pytest(self, subtests):
        # same test as above but without the yield not supported by pytest,
        # I don't think it changes anything here keeping both for nosetests
        for mod in self.pyrpl.modules:
            for exclude in [Lockbox, DummyModule]:  # lockbox is too complicated here
                if isinstance(mod, exclude):
                    break
            else:
                with subtests.test(mod=mod):
                    self.assert_validate_and_normalize(mod)
                # make sure all modules are stopped at the end of this test
                with contextlib.suppress(AttributeError, RuntimeError, OSError):
                    mod.stop()

    def assert_validate_and_normalize(self, mod):
        self.results = []

        def check_fpga_value_equals_signal_value(attr_name, list_value):
            print(
                "check_fpga_value_equals_signal_value("
                f"{mod.name}.{attr_name}, {list_value}) was called!"
            )
            # add an entry to results
            self.results.append(
                (
                    f"{mod.name}.{attr_name}",
                    list_value[0],
                    getattr(mod, attr_name),
                )
            )

        mod._signal_launcher.update_attribute_by_name.connect(check_fpga_value_equals_signal_value)
        attr_names, attr_vals = scramble_values(mod)
        APP.processEvents()
        mod._signal_launcher.update_attribute_by_name.disconnect(
            check_fpga_value_equals_signal_value
        )
        # check that enough results have been received
        assert len(attr_names) <= len(self.results), (
            f"{len(attr_names):d} attr_names > {len(self.results):d} results"
        )
        # check that all values that were modified have returned at least one result
        resultnames = [name for (name, _, __) in self.results]
        for attr_name in attr_names:
            fullname = f"{mod.name}.{attr_name}"
            assert fullname in resultnames, f"{fullname} not in resultnames"
        # check that the returned values are in agreement with our expectation
        exceptions = [
            "scope._reset_writestate_machine",  # always False
            "asg0._offset_masked",  # TODO: migrate bit mask from #317
            "asg1._offset_masked",  # set_value to validate_and_normalize #317
            "asg0.offset",  # TODO: fix offset as named in issue #317
            "asg1.offset",  # TODO: fix offset as named in issue #317
        ]
        for name, list_value, attr_value in self.results:
            if name not in exceptions:
                assert list_value == attr_value, (name, list_value, attr_value)
