"""
The :class:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer`
allows to measure the spectrum (= the squared modulus of the
Fourier-transformed autocorrelation function) of internal and external
signals in PyRPL.

The SpectrumAnalyzer has 2 different working modes:

* :attr:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.baseband` :code:`= True`
  *(baseband mode)*: The Fourier transform is directly applied on the sampled
  data. The frequency range of spectra always starts at zero by design in
  baseband mode. Two inputs can be used in this mode to compute spectra of
  two different signals. Furthermore, the complex cross-spectrum (containing
  magnitude and phase information) between the two inputs can be computed.
* :attr:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.baseband` :code:`= False`
  (*iq-mode - not available in the current version*):
  The input signals are first frequency-shifted by an
  :mod:`~pyrpl.hardware_modules.iq`-module and only then Fourier-transformed.
  This mode allows to study a narrow frequency span around an arbitrary center
  frequency.

The following attributes can be manipulated by the SpectrumAnalyzer widget:

* :attr:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.span`:
  The span of frequencies over which a spectrum is acquired.
  In baseband mode, the actual span is half of this value
  (because no additional information is given in half-spectrum with negative
  frequencies).
* :attr:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.rbw`:
  Resolution bandwidth of the spectrum to acquire (:code:`span` and
  :code:`bandwidth` are linked and cannot be set independently).
* :attr:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.display_unit`:
  The unit in which the spectrum is plotted on the screen. Internally, e.g.
  in saved measurements, all spectra are represented in units of
  :math:`\\mathrm{V}_\\mathrm{pk}^2`.
* :attr:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.window`:
  The type of window used for the Fourier transform. See
  scipy.signal.get_window for a list of available options.
* :attr:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.acbandwidth`
  *(only available with* :code:`baseband=False` *)*: The cut-off frequency of
  the high-pass filter before frequency-shifting (=demodulation) of the input
  signal.

Below the buttons, *SHO fit* fits a simple harmonic oscillator plus white
noise to the spectrum (see
:meth:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.fit_sho`).
Drag the shaded region in the plot to choose the fit range, then press *Fit*,
or check *auto* to refit every new spectrum (at most twice per second). The
fitted curve is drawn dashed. The results are shown in fixed units whatever
the display unit: resonance frequency, Q, noise floor in Vrms/sqrt(Hz), and
the area under the noiseless curve as an rms voltage (Vrms). With few
averages, Q comes out somewhat high (about +10 % for a single spectrum).
"""

import logging
import time

import numpy as np
import pyqtgraph as pg
from qtpy import QtCore, QtWidgets

from ..attribute_widgets import DataWidget
from .acquisition_module_widget import AcquisitionModuleWidget

logger = logging.getLogger(name=__name__)

_SI_PREFIXES = (
    (1e-12, "p"),
    (1e-9, "n"),
    (1e-6, "µ"),
    (1e-3, "m"),
    (1.0, ""),
    (1e3, "k"),
    (1e6, "M"),
)


def format_value_error(value, error, unit, prefix=True, digits=4):
    """
    Formats value +- error, e.g. (150000.61, 2.13, "Hz") ->
    "150.0006 ± 0.0021 kHz": SI prefix chosen from the value, and as many
    decimals as needed to show two significant digits of the error.
    """
    if not np.isfinite(value):
        return f"nan {unit}".strip()
    factor, pfx = 1.0, ""
    if prefix and value != 0:
        factor, pfx = _SI_PREFIXES[0]
        for f, p in _SI_PREFIXES:
            if abs(value) >= f * (1 - 1e-9):
                factor, pfx = f, p
    v = value / factor
    unit = f"{pfx}{unit}"
    if error is None or not np.isfinite(error) or error <= 0:
        return f"{v:.{digits}g} {unit}".strip()
    e = error / factor
    decimals = int(min(max(1 - np.floor(np.log10(e)), 0), 9))
    return f"{v:.{decimals}f} ± {e:.{decimals}f} {unit}".strip()


class BasebandAttributesWidget(QtWidgets.QWidget):
    def __init__(self, specan_widget):
        super().__init__()
        self.h_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.h_layout)
        aws = specan_widget.attribute_widgets

        self.v_layout1 = QtWidgets.QVBoxLayout()
        self.h_layout.addLayout(self.v_layout1)
        for name in ["display_input1_baseband", "display_input2_baseband"]:
            widget = aws[name]
            specan_widget.attribute_layout.removeWidget(widget)
            self.v_layout1.addWidget(widget)

        self.v_layout2 = QtWidgets.QVBoxLayout()
        self.h_layout.addLayout(self.v_layout2)
        for name in ["input1_baseband", "input2_baseband"]:
            widget = aws[name]
            specan_widget.attribute_layout.removeWidget(widget)
            self.v_layout2.addWidget(widget)

        self.v_layout3 = QtWidgets.QVBoxLayout()
        self.h_layout.addLayout(self.v_layout3)
        for name in ["display_cross_amplitude"]:  # , "display_cross_phase"]:
            widget = aws[name]
            specan_widget.attribute_layout.removeWidget(widget)
            self.v_layout3.addWidget(widget)


class IqModeAttributesWidget(QtWidgets.QWidget):
    def __init__(self, specan_widget):
        super().__init__()
        self.h_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.h_layout)
        aws = specan_widget.attribute_widgets

        self.v_layout1 = QtWidgets.QVBoxLayout()
        self.h_layout.addLayout(self.v_layout1)
        for name in ["center", "input"]:
            widget = aws[name]
            specan_widget.attribute_layout.removeWidget(widget)
            self.v_layout1.addWidget(widget)


class OtherAttributesWidget(QtWidgets.QWidget):
    def __init__(self, specan_widget):
        super().__init__()
        self.h_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.h_layout)
        aws = specan_widget.attribute_widgets

        self.v_layout1 = QtWidgets.QVBoxLayout()
        self.h_layout.addLayout(self.v_layout1)
        for name in ["baseband", "acbandwidth"]:
            widget = aws[name]
            specan_widget.attribute_layout.removeWidget(widget)
            self.v_layout1.addWidget(widget)

        self.v_layout2 = QtWidgets.QVBoxLayout()
        self.h_layout.addLayout(self.v_layout2)
        for name in ["span", "window"]:
            widget = aws[name]
            specan_widget.attribute_layout.removeWidget(widget)
            self.v_layout2.addWidget(widget)

        self.v_layout3 = QtWidgets.QVBoxLayout()
        self.h_layout.addLayout(self.v_layout3)
        for name in ["rbw", "display_unit"]:
            widget = aws[name]
            specan_widget.attribute_layout.removeWidget(widget)
            self.v_layout3.addWidget(widget)


class SpecAnWidget(AcquisitionModuleWidget):
    _display_max_frequency = 25  # max 25 Hz framerate

    def init_gui(self):
        """
        Sets up the gui.
        """
        self.ch_col = ("magenta", "blue", "green")
        self.last_data = None
        self.init_main_layout(orientation="vertical")
        # self.main_layout = QtWidgets.QVBoxLayout()
        self.module.__dict__["curve_name"] = "pyrpl spectrum"
        self.init_attribute_layout()

        self.other_widget = OtherAttributesWidget(self)
        self.attribute_layout.addWidget(self.other_widget)

        self.iqmode_widget = IqModeAttributesWidget(self)
        self.attribute_layout.addWidget(self.iqmode_widget)

        self.baseband_widget = BasebandAttributesWidget(self)
        self.attribute_layout.addWidget(self.baseband_widget)

        self.button_layout = QtWidgets.QHBoxLayout()
        # self.setLayout(self.main_layout)
        # self.setWindowTitle("Spec. An.")
        # self.win = pg.GraphicsLayoutWidget(title="PSD")
        # self.main_layout.addWidget(self.win)

        self.win2 = DataWidget(title="Spectrum")
        self.main_layout.addWidget(self.win2)

        # self.plot_item = self.win.addPlot(title="PSD")
        # self.curve = self.plot_item.plot(pen=self.ch_col[0][0])

        # self.curve2 = self.plot_item.plot(pen=self.ch_col[1][0]) # input2
        # spectrum in
        # baseband
        # self.curve_cross = self.plot_item.plot(pen=self.ch_col[2][0]) #
        # curve for

        super().init_gui()

        aws = self.attribute_widgets

        aws["display_input1_baseband"].setStyleSheet(f"color: {self.ch_col[0]}")
        aws["display_input2_baseband"].setStyleSheet(f"color: {self.ch_col[1]}")
        aws["display_cross_amplitude"].setStyleSheet(f"color: {self.ch_col[2]}")
        # Not sure why the stretch factors in button_layout are not good by
        # default...

        self.attribute_layout.addStretch(1)
        self.init_sho_fit_gui()
        self.update_baseband_visibility()

    def init_sho_fit_gui(self):
        """Controls for the SHO fit, below the buttons, plus the fit range
        region and the fitted curve in the plot."""
        self._sho_fit = None  # last ShoFitResult
        self._sho_fit_rbw = None  # rbw of the fitted data
        self._sho_fit_time = 0.0  # time of the last automatic fit
        self._sho_region_placed = False

        self.sho_layout = QtWidgets.QHBoxLayout()
        self.checkbox_sho = QtWidgets.QCheckBox("SHO fit")
        self.checkbox_sho.setToolTip(
            "Fit a simple harmonic oscillator plus white noise to the spectrum,\n"
            "within the shaded region of the plot (drag it or its edges)."
        )
        self.checkbox_sho.stateChanged.connect(self.sho_fit_toggled)
        self.button_sho_fit = QtWidgets.QPushButton("Fit")
        self.button_sho_fit.clicked.connect(self.sho_fit_clicked)
        self.checkbox_sho_auto = QtWidgets.QCheckBox("auto")
        self.checkbox_sho_auto.setToolTip("Refit every new spectrum (at most twice per second)")
        self.combo_sho_channel = QtWidgets.QComboBox()
        self.combo_sho_channel.addItems(["input 1", "input 2"])
        self.combo_sho_channel.setToolTip("Spectrum to fit in baseband mode")
        self.label_sho = QtWidgets.QLabel("")
        self.label_sho.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        for widget in (
            self.checkbox_sho,
            self.button_sho_fit,
            self.checkbox_sho_auto,
            self.combo_sho_channel,
        ):
            self.sho_layout.addWidget(widget)
        self.sho_layout.addWidget(self.label_sho, stretch=1)
        self.main_layout.addLayout(self.sho_layout)

        plot_item = self.win2.plot_item
        self.sho_region = pg.LinearRegionItem(brush=pg.mkBrush(255, 255, 0, 40))
        self.sho_region.setZValue(-10)
        plot_item.addItem(self.sho_region, ignoreBounds=True)
        self.sho_region.hide()
        self.sho_curve = pg.PlotDataItem(pen=pg.mkPen("c", width=2, style=QtCore.Qt.DashLine))
        self.sho_curve.setZValue(10)  # on top of the spectra
        plot_item.addItem(self.sho_curve, ignoreBounds=True)
        self.sho_curve.hide()
        self.update_sho_fit_controls()

    def update_sho_fit_controls(self):
        on = self.checkbox_sho.isChecked()
        self.button_sho_fit.setEnabled(on)
        self.checkbox_sho_auto.setEnabled(on)
        self.combo_sho_channel.setEnabled(on and bool(self.module.baseband))
        self.label_sho.setVisible(on)

    def sho_fit_toggled(self):
        on = self.checkbox_sho.isChecked()
        if on and not self._sho_region_placed:
            # start with the displayed span (slightly inset, so that the
            # edges can be grabbed)
            x0, x1 = self.win2.plot_item.viewRange()[0]
            inset = 0.03 * (x1 - x0)
            self.sho_region.setRegion((x0 + inset, x1 - inset))
            self._sho_region_placed = True
        self.sho_region.setVisible(on)
        if not on:
            self.clear_sho_fit()
        self.update_sho_fit_controls()

    def clear_sho_fit(self):
        self._sho_fit = None
        self.sho_curve.hide()
        self.label_sho.setText("")

    def sho_fit_clicked(self):
        self.do_sho_fit(log=True)

    def do_sho_fit(self, log=False):
        """Fits the last spectrum within the region and shows the result."""
        fmin, fmax = self.sho_region.getRegion()
        channel = self.combo_sho_channel.currentIndex() + 1
        try:
            result = self.module.fit_sho(fmin=fmin, fmax=fmax, channel=channel)
        except Exception as e:  # e.g. too few points in the range
            self.clear_sho_fit()
            self.label_sho.setText(f"Fit failed: {e}")
            if log:
                self.module._logger.warning("SHO fit failed: %s", e)
            return None
        self._sho_fit = result
        self._sho_fit_rbw = self.module.attributes_last_run["rbw"]
        text = self.sho_fit_text(result)
        self.label_sho.setText(text)
        self.draw_sho_fit()
        if log:
            # plain ASCII for consoles with a legacy code page (Windows)
            ascii_text = (
                text.replace("₀", "0")
                .replace("≥", ">=")
                .replace("≤", "<=")
                .replace("±", "+-")
                .replace("√", "sqrt")
            )
            self.module._logger.info("SHO fit: %s", ascii_text.replace("µ", "u"))
        return result

    @staticmethod
    def sho_fit_text(result):
        if result.linewidth_at_limit:  # Q only a lower bound
            q_text = f"Q ≥ {result.q:.4g} (at resolution limit)"
        else:
            q_text = "Q = " + format_value_error(result.q, result.q_err, "", prefix=False)
        parts = [
            "f₀ = " + format_value_error(result.f0, result.f0_err, "Hz"),
            q_text,
            "noise = "
            + format_value_error(
                result.noise_vrms_per_sqrt_hz, result.noise_vrms_per_sqrt_hz_err, "V/√Hz"
            ),
            "area = " + format_value_error(result.area_vrms, result.area_vrms_err, "Vrms"),
        ]
        if result.linewidth_at_limit:
            parts.append("linewidth ≤ 1 bin: Q and area too low, narrow the span")
        elif result.resolution_limited:
            parts.append("linewidth < 3 rbw: Q too low")
        return "   ".join(parts)

    def draw_sho_fit(self):
        """Draws the fitted curve in the current display unit."""
        result = self._sho_fit
        if result is None or not self.checkbox_sho.isChecked():
            self.sho_curve.hide()
            return
        f = np.linspace(result.fmin, result.fmax, 2000)
        vpk2 = result.psd(f) * 2 * self._sho_fit_rbw  # Vrms^2/Hz -> Vpk^2
        self.sho_curve.setData(f, self.module.data_to_display_unit(vpk2, self._sho_fit_rbw))
        self.sho_curve.show()

    def update_attribute_by_name(self, name, new_value_list):
        super().update_attribute_by_name(name, new_value_list)
        if name in ["_running_state"]:
            self.update_running_buttons()
        if name in ["baseband"]:
            self.update_baseband_visibility()
            self.clear_sho_fit()
            self.update_sho_fit_controls()

    def update_baseband_visibility(self):
        self.baseband_widget.setEnabled(self.module.baseband)
        self.iqmode_widget.setEnabled(not self.module.baseband)

    #### def update_rbw_visibility(self):
    ####     self.attribute_widgets["rbw"].widget.setEnabled(not
    #### self.module.rbw_auto)

    def autoscale_x(self):
        """Autoscale pyqtgraph"""
        mini = self.module.frequencies[0]
        maxi = self.module.frequencies[-1]
        self.win2.setRange(xRange=[mini, maxi])
        # self.plot_item.autoRange()

    def unit_changed(self):
        self.display_curve(self.last_data)
        self.win2.autoRange()

    # def run_continuous_clicked(self):
    #     """
    #     Toggles the button run_continuous to stop or vice versa and starts the acquisition timer
    #     """
    #
    #     if str(self.button_continuous.text()).startswith("Run continuous"):
    #         self.module.continuous()
    #     else:
    #         self.module.pause()

    # def run_single_clicked(self):
    #     if str(self.button_single.text()).startswith('Stop'):
    #         self.module.stop()
    #     else:
    #         self.module.single_async()

    def display_curve(self, datas):
        if datas is None:
            return
        self.last_data = datas
        freqs = datas[0]

        def to_units(x):
            return self.module.data_to_display_unit(x, self.module.attributes_last_run["rbw"])

        # use the mode of the data, not the current one: after switching
        # between iq and baseband mode, unit_changed() redraws older data
        if np.ndim(datas[1]) == 1:  # iq mode, only 1 curve to display
            self.win2._set_widget_value((freqs, datas[1]), transform_magnitude=to_units)
        else:  # baseband mode: data is (spec1, spec2, real(cross), imag(cross))
            spec1, spec2, cross_r, cross_i = datas[1]
            data = []
            if self.module.display_input1_baseband:
                data.append(spec1)  # np.array([np.nan]*len(x))
            if self.module.display_input2_baseband:
                data.append(spec2)  # = np.zeros(len(x))# np.array([np.nan]*len(x))
            if self.module.display_cross_amplitude:
                data.append(
                    cross_r + 1j * cross_i
                )  # = np.zeros(len(x)) # np.array([np.nan]*len(x))
            self.win2._set_widget_value((freqs, data), transform_magnitude=to_units)
        self.update_current_average()
        if self.checkbox_sho.isChecked():
            now = time.monotonic()
            if self.checkbox_sho_auto.isChecked() and now - self._sho_fit_time >= 0.5:
                self._sho_fit_time = now
                self.do_sho_fit()
            else:
                self.draw_sho_fit()  # e.g. in a new display unit

    def display_curve_old(self, datas):
        """
        Displays all active channels on the graph.
        """
        self.last_data = datas
        freqs = datas[0]

        def to_units(x):
            return self.module.data_to_display_unit(x, self.module.attributes_last_run["rbw"])

        if not self.module.baseband:  # baseband mode, only 1 curve to display
            self.curve.setData(freqs, to_units(datas[1]))
            self.curve.setVisible(True)
            self.curve2.setVisible(False)
            self.curve_cross.setVisible(False)
        else:  # baseband mode: data is (spec1, spec2, real(cross), imag(cross))
            spec1, spec2, cross_r, cross_i = datas[1]
            self.curve.setData(freqs, to_units(spec1))
            self.curve.setVisible(self.module.display_input1_baseband)

            self.curve2.setData(freqs, to_units(spec2))
            self.curve2.setVisible(self.module.display_input2_baseband)

            cross = cross_r + 1j * cross_i
            cross_mod = abs(cross)
            self.curve_cross.setData(freqs, to_units(cross_mod))
            self.curve_cross.setVisible(self.module.display_cross_amplitude)

            # phase still needs to be implemented
        self.update_running_buttons()
