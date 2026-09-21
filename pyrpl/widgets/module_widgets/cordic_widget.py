"""Compact widget for the standalone two-input CORDIC module."""

from .base_module_widget import ModuleWidget


class CordicWidget(ModuleWidget):
    """Display only the two signal selectors and direct-output routing."""

    def init_gui(self):
        super().init_gui()

        # Keep the module compact and make the I/Q signal flow read from left
        # to right: in-phase input, quadrature input, then physical output.
        for widget in self.attribute_widgets.values():
            self.attribute_layout.removeWidget(widget)
        for attribute_name in ("input", "input_q", "output_direct"):
            self.attribute_layout.addWidget(self.attribute_widgets[attribute_name])
        self.attribute_layout.setStretch(0, 0)
        self.attribute_layout.addStretch(1)
