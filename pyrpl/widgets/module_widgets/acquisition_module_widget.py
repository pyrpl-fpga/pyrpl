"""
Acquisition modules are the modules used to acquire data from the Red Pitaya.

At the moment, they include the

* :mod:`~pyrpl.hardware_modules.scope`,
* :mod:`~pyrpl.software_modules.network_analyzer`,
* :mod:`~pyrpl.software_modules.spectrum_analyzer`.

All the acquisition modules have in common a plot area where the data is
displayed and a control panel BELOW the plot for changing acquisition
settings. Widgets for specialized acquisition modules
(e.g. :class:`~pyrpl.hardware_modules.scope.Scope`) have an additional control
panel ABOVE the plot are for settings that are only available for that module.

The different buttons in the acquisition module control panel below the plot are:

- :attr:`~.AcquisitionModule.trace_average` chooses the number of successive
  traces to average together.
- :attr:`~.AcquisitionModule.curve_name` is the name for the next curve that is saved.
- :code:`Run single` starts a single acquisition of :code:`trace_average`
  traces (calls :meth:`.AcquisitionModule.single`).
- :code:`Run continuous` starts a continuous acquisition with a running
  average filter, where :code:`trace_average` is the decay constant of the
  running average filter (calls :meth:`.AcquisitionModule.continuous`).
- :code:`Restart average` resets trace averages to zero to start a new
  measurement from scratch.
- :code:`Save curve` saves the current measurement data to a new
  :class:`pyrpl.curvedb.CurveDB` object under the name
  :attr:`~.AcquisitionModule.curve_name`. The number of the saved curve is
  briefly shown on the button and logged together with the file name.
- :code:`Export...` asks for a file name and writes the current measurement
  data, as displayed, to a comma-separated text file for use in other
  programs (calls :meth:`.AcquisitionModule.export_curve`).
"""

import asyncio
import os

from qtpy import QtCore, QtWidgets

from ...curvedb import CurveDB
from . import ModuleWidget


class CurrentAvgLabel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_lay = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_lay)
        self.label = QtWidgets.QLabel("current_avg")
        self.main_lay.addWidget(self.label)
        self.value_label = QtWidgets.QLabel("0 /")
        self.main_lay.addWidget(self.value_label)
        self.main_lay.addStretch(1)
        self.value_label.setAlignment(QtCore.Qt.AlignCenter)
        self.main_lay.setContentsMargins(0, 0, 0, 0)

    def set_value(self, val):
        self.value_label.setText(str(val) + " /")


class AcquisitionModuleWidget(ModuleWidget):
    def init_gui(self):
        self.button_single = QtWidgets.QPushButton("Run single")
        self.button_single.clicked.connect(self.run_single_clicked)

        self.button_continuous = QtWidgets.QPushButton("Run continuous")
        self.button_continuous.clicked.connect(self.run_continuous_clicked)

        self.button_stop = QtWidgets.QPushButton("Stop")
        self.button_stop.clicked.connect(self.stop_clicked)

        self.button_save = QtWidgets.QPushButton("Save curve")
        self.button_save.clicked.connect(self.save_curve_clicked)

        self.button_export = QtWidgets.QPushButton("Export...")
        self.button_export.clicked.connect(self.export_curve_clicked)

        self.current_avg_label = CurrentAvgLabel()

        aws = self.attribute_widgets
        self.attribute_layout.removeWidget(aws["trace_average"])
        self.attribute_layout.removeWidget(aws["curve_name"])

        self.button_layout.addWidget(self.current_avg_label)
        self.button_layout.addWidget(aws["trace_average"])
        self.button_layout.addWidget(aws["curve_name"])
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.button_layout.addWidget(self.button_stop)
        self.button_layout.addWidget(self.button_save)
        self.button_layout.addWidget(self.button_export)
        self.main_layout.addLayout(self.button_layout)

        self.button_layout.setStretchFactor(self.button_single, 1)
        self.button_layout.setStretchFactor(self.button_continuous, 1)
        self.button_layout.setStretchFactor(self.button_stop, 1)
        self.button_layout.setStretchFactor(self.button_save, 1)
        self.button_layout.setStretchFactor(self.button_export, 1)
        self.button_layout.addStretch(1)
        self.attribute_layout.setStretch(0, 0)  # since widgets are all removed
        # and re-added, the stretch ends up on the left, so better cancel it
        # and make a new one at the end
        self.update_running_buttons()

    def run_single_clicked(self):
        if str(self.button_single.text()).startswith("Run single"):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                self.module.single()
            else:
                self.module.single_async()
        else:
            if str(self.button_single.text()).startswith("Resume single"):
                if self.module.running_state == "paused_single":
                    self.module.resume()
                else:
                    self.module._resume_new_single()
            else:
                if str(self.button_single.text()).startswith("Pause"):
                    self.module.pause()

    def run_continuous_clicked(self):
        """
        Toggles the button run_continuous to stop or vice versa and starts
        he acquisition timer
        """

        if str(self.button_continuous.text()).startswith("Run continuous"):
            self.module.continuous()
        else:
            if str(self.button_continuous.text()).startswith("Resume continuous"):
                self.module._resume_new_continuous()
            else:
                if str(self.button_continuous.text()).startswith("Pause"):
                    self.module.pause()

    def save_curve_clicked(self):
        """
        Saves the current curve(s) and reports what was saved in the log and,
        for a moment, on the save button.
        """
        curves = self.module.save_curve()
        if not isinstance(curves, (list, tuple)):
            curves = [curves]
        curves = [curve for curve in curves if curve is not None]
        dirname = getattr(CurveDB, "_dirname", None)  # only for the default CurveDB
        for curve in curves:
            if dirname is None:
                self._logger.info("Saved curve %s '%s'", curve.pk, curve.name)
            else:
                filename = os.path.join(dirname, str(curve.pk) + CurveDB.file_extension)
                self._logger.info("Saved curve %s '%s' to %s", curve.pk, curve.name, filename)
        if curves:
            text = "Saved #" + ", #".join(str(curve.pk) for curve in curves)
        else:
            self._logger.warning("No curve saved: no channel is selected.")
            text = "Nothing saved"
        self._flash_button_text(self.button_save, text, "Save curve")

    _export_dir = ""  # folder of the last export, shared by all acquisition widgets

    def export_curve_clicked(self):
        """
        Asks for a file name and exports the current data there as a
        comma-separated text file.
        """
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export curve",
            os.path.join(AcquisitionModuleWidget._export_dir, self.module.curve_name + ".csv"),
            "CSV files (*.csv);;All files (*)",
        )
        if not filename:  # cancelled
            return
        AcquisitionModuleWidget._export_dir = os.path.dirname(filename)
        try:
            self.module.export_curve(filename)
        except Exception:
            self._logger.exception("Could not export curve to %s", filename)
            self._flash_button_text(self.button_export, "Export failed", "Export...")
            return
        self._logger.info("Exported curve '%s' to %s", self.module.curve_name, filename)
        self._flash_button_text(self.button_export, "Exported", "Export...")

    def _flash_button_text(self, button, text, label, duration_ms=2000):
        """Shows text on button for duration_ms, then restores label."""
        button.setText(text)
        QtCore.QTimer.singleShot(duration_ms, lambda: button.setText(label))

    def stop_clicked(self):
        # old_running_state = self.module.running_state
        self.module.stop()
        # if old_running_state in ["running_single", "running_continuous"]:
        #    self.module.running_state = old_running_state
        self.update_current_average()

    def update_current_average(self):
        self.current_avg_label.set_value(self.module.current_avg)

    def update_running_buttons(self):
        """
        Change text of Run continuous button and visibility of run single button
        according to module.running_continuous
        """
        self.update_current_average()
        if self.module.current_avg > 0:
            " (" + str(self.module.current_avg) + ")"
        else:
            pass
        if self.module.running_state == "running_continuous":
            # if self.module.current_avg >= self.module.trace_average:
            #    # shows a plus sign when number of averages is available
            #    number_str = number_str[:-1] + '+)'
            self.button_continuous.setText("Pause")
            self.button_continuous.setEnabled(True)
            self.button_single.setText("Run single")
            self.button_single.setEnabled(False)
            self.button_stop.setEnabled(True)
        else:
            if self.module.running_state == "running_single":
                self.button_continuous.setText("Run continuous")
                self.button_continuous.setEnabled(False)
                self.button_single.setText("Pause")
                self.button_single.setEnabled(True)
                self.button_stop.setEnabled(True)
            else:
                if self.module.running_state == "paused_single":
                    self.button_continuous.setText("Resume continuous")
                    self.button_continuous.setEnabled(True)
                    self.button_single.setText("Resume single")
                    self.button_single.setEnabled(True)
                    self.button_stop.setEnabled(True)
                else:
                    if self.module.running_state == "paused_continuous":
                        self.button_continuous.setText("Resume continuous")
                        self.button_continuous.setEnabled(True)
                        self.button_single.setText("Resume single")
                        self.button_single.setEnabled(True)
                        self.button_stop.setEnabled(True)
                    else:
                        if self.module.running_state == "stopped":
                            self.button_continuous.setText("Run continuous")
                            self.button_continuous.setEnabled(True)
                            self.button_single.setText("Run single")
                            self.button_single.setEnabled(True)
                            self.button_stop.setEnabled(False)
