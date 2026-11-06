import logging
import sys
import traceback

import pytest

from pyrpl import APP
from pyrpl.test.test_base import TestPyrpl

logger = logging.getLogger(name=__name__)


class TestModuleWidgets(TestPyrpl):
    OPEN_ALL_DOCKWIDGETS = True  # forces all DockWidgets to become visible

    @pytest.fixture
    def specan(self, monkeypatch):
        """
        Yields the spectrum analyzer and a widget for it, with asg0 as a test
        signal. Exceptions raised in Qt slots (e.g. by the GUI dock widget
        displaying the acquired data) do not reach the test, so they are
        collected here and make the test fail at teardown.
        """
        sa = self.pyrpl.spectrumanalyzer
        sa.stop()
        old_setup = sa.setup_attributes
        slot_errors = []
        monkeypatch.setattr(sys, "excepthook", lambda *exc_info: slot_errors.append(exc_info))
        self.pyrpl.rp.asg0.setup(
            frequency=1.2e5, amplitude=0.5, offset=0, waveform="sin", trigger_source="immediately"
        )
        widget = sa._create_widget()

        yield sa, widget

        sa.stop()
        APP.processEvents()
        errors = list(slot_errors)  # only those raised by the test itself
        sa.setup_attributes = old_setup
        sa.stop()
        widget.deleteLater()
        APP.processEvents()
        assert not errors, "\n".join(
            "".join(traceback.format_exception(*exc_info)) for exc_info in errors
        )

    def _acquire_and_display(self, sa, widget):
        """Acquires one trace, displays it and returns the indices of the visible curves."""
        sa.single()
        widget.display_curve([sa.data_x, sa.data_avg])
        APP.processEvents()
        return [i for i, curve in enumerate(widget.win2.curves) if curve.isVisible()]

    def test_specan_widget_iq_mode(self, specan):
        """
        Displaying an IQ-mode spectrum used to raise a ValueError (ragged
        array) with NumPy >= 1.24.
        """
        sa, widget = specan
        sa.setup(baseband=False, center=1e5, span=1e5, input="asg0", trace_average=1)
        assert self._acquire_and_display(sa, widget) == [0]
        _x, y = widget.win2.curves[0].getData()
        assert len(y) == len(sa.data_x)

    def test_specan_widget_baseband_no_curve(self, specan):
        """
        Deselecting all baseband curves used to raise a TypeError in the
        magnitude transform at every acquisition.
        """
        sa, widget = specan
        no_curve = dict(
            display_input1_baseband=False,
            display_input2_baseband=False,
            display_cross_amplitude=False,
        )
        sa.setup(baseband=True, span=1e6, input1_baseband="asg0", trace_average=1, **no_curve)
        assert self._acquire_and_display(sa, widget) == []

        sa.setup(**{key: True for key in no_curve})
        assert self._acquire_and_display(sa, widget) == [0, 1, 2]
        assert widget.win2.plot_item_phase.isVisible()  # the cross spectrum is complex

        sa.setup(**no_curve)
        assert self._acquire_and_display(sa, widget) == []
        assert not widget.win2.plot_item_phase.isVisible()

    def test_specan_widget_unit_change_after_mode_change(self, specan):
        """
        Changing display_unit redraws the last acquired data. After switching
        from IQ mode to baseband mode, that is still a single IQ spectrum,
        which display_curve() used to unpack as 4 baseband spectra
        (ValueError: too many values to unpack). setup() sets baseband before
        display_unit, so e.g. loading a state also raised.
        """
        sa, widget = specan

        def visible_curves():
            return [i for i, curve in enumerate(widget.win2.curves) if curve.isVisible()]

        def change_unit():
            unit = "Vpk" if sa.display_unit != "Vpk" else "dB(Vpk^2)"
            return dict(display_unit=unit)

        # IQ trace, redrawn in baseband mode: still one curve
        sa.setup(baseband=False, center=1e5, span=1e5, input="asg0", trace_average=1)
        self._acquire_and_display(sa, widget)
        n_points = len(sa.data_x)
        sa.setup(baseband=True, span=1e6, input1_baseband="asg0", **change_unit())
        widget.unit_changed()  # the signal reaches it only through the Qt event loop
        assert visible_curves() == [0]
        assert len(widget.win2.curves[0].getData()[1]) == n_points

        # baseband trace, redrawn in IQ mode: the selected baseband curves
        sa.setup(
            display_input1_baseband=True,
            display_input2_baseband=False,
            display_cross_amplitude=False,
        )
        self._acquire_and_display(sa, widget)
        sa.setup(baseband=False, center=1e5, span=1e5, **change_unit())
        widget.unit_changed()
        assert visible_curves() == [0]
