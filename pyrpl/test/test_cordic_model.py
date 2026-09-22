import json
from pathlib import Path

import pytest

from pyrpl.hardware_modules.cordic import Cordic, turns_to_degrees, turns_to_radians
from pyrpl.hardware_modules.dsp import DSP_INPUTS
from pyrpl.widgets.module_widgets import CordicWidget


def test_cordic_uses_the_iir_address_slot_and_independent_q_register():
    assert DSP_INPUTS["cordic"] == DSP_INPUTS["iir"] == 4
    assert Cordic.input.address == 0x0
    assert Cordic.input_q.address == 0x14
    assert Cordic.abi_version.address == 0x18


def test_cordic_uses_compact_widget_with_routing_controls():
    assert Cordic._widget_class is CordicWidget
    assert Cordic._gui_attributes == ["input", "input_q", "output_direct"]


@pytest.mark.parametrize(
    "register_value, turns",
    [(0x0000, 0.0), (0x0400, 0.25), (0x1000, 1.0), (0x3C00, -0.25)],
)
def test_cordic_phase_register_is_scaled_in_turns(register_value, turns):
    assert Cordic.current_output_signal.to_python(None, register_value) == turns


@pytest.mark.parametrize(
    "turns, radians, degrees",
    [(0.0, 0.0, 0.0), (0.25, 1.5707963267948966, 90.0)],
)
def test_cordic_phase_unit_conversions(turns, radians, degrees):
    assert turns_to_radians(turns) == pytest.approx(radians)
    assert turns_to_degrees(turns) == pytest.approx(degrees)
    assert Cordic.to_radians(turns) == pytest.approx(radians)
    assert Cordic.to_degrees(turns) == pytest.approx(degrees)


def test_cordic_profile_contract_has_no_pid_prefilters():
    manifest_path = (
        Path(__file__).parents[1] / "fpga" / "profiles" / "cordic" / "manifest.template.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert "cordic" in manifest["capabilities"]
    assert "pid_input_filters" not in manifest["capabilities"]
    assert manifest["hardware"]["pid_input_filter_stages"] == 0
    assert manifest["hardware"]["cordic_abi"] == 0x434F5201
    assert manifest["hardware_modules"].count("Cordic") == 1
    assert "Cordics" in manifest["software_managers"]
    assert manifest["hardware_modules"].count("Iq") == 3
    assert manifest["hardware_modules"].count("Pid") == 3
    assert "IIR" not in manifest["hardware_modules"]
