"""
A widget for pid modules.
"""

from .base_module_widget import ModuleWidget


class PidWidget(ModuleWidget):
    """
    Widget for a single PID.
    """

    def init_gui(self):
        self.init_main_layout(orientation="vertical")
        # self.main_layout = QtWidgets.QVBoxLayout()
        # self.setLayout(self.main_layout)
        self.init_attribute_layout()
        input_filter_widget = self.attribute_widgets["inputfilter"]
        self.attribute_layout.removeWidget(input_filter_widget)
        self.main_layout.addWidget(input_filter_widget)
        for prop in ["p", "i"]:
            self.attribute_widgets[prop].widget.set_log_increment()
        # The derivative attributes are added to the module GUI only for the
        # pid_derivative FPGA profile.  self.module.d is the current numeric
        # value; capability methods belong to its class descriptor instead.
        if "d" in self.attribute_widgets:
            self.attribute_widgets["d"].widget.set_log_increment()
        # can't avoid timer to update ival

        # self.timer_ival = QtCore.QTimer()
        # self.timer_ival.setInterval(1000)
        # self.timer_ival.timeout.connect(self.update_ival)
        # self.timer_ival.start()

    def update_ival(self):
        widget = self.attribute_widgets["ival"]
        if self.isVisible() and not widget.editing():
            widget.write_attribute_value_to_widget()
