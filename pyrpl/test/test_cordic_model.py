import json
from pathlib import Path

import pytest

from pyrpl.hardware_modules.cordic import Cordic, turns_to_degrees, turns_to_radians
from pyrpl.hardware_modules.dsp import DSP_INPUTS
from pyrpl.hardware_modules.iq import Iq
from pyrpl.widgets.module_widgets import CordicWidget


def test_cordic_uses_the_iir_address_slot_and_independent_q_register():
    assert DSP_INPUTS["cordic"] == DSP_INPUTS["iir"] == 4
    assert Cordic.input.address == 0x0
    assert Cordic.input_q.address == 0x14
    assert Cordic.abi_version.address == 0x18
    assert Cordic.input_pair.address == 0x1C
    assert Cordic.input_pair.options(None) == {
        "independent": 0,
        "iq0": 1,
        "iq1": 2,
        "iq2": 3,
    }


def test_cordic_uses_compact_widget_with_routing_controls():
    assert Cordic._widget_class is CordicWidget
    assert Cordic._gui_attributes == [
        "input_pair",
        "input",
        "input_q",
        "output_direct",
    ]


@pytest.mark.parametrize(
    "register_value, turns",
    [(0x0000, 0.0), (0x0400, 0.25), (0x1000, 1.0), (0x3C00, -0.25)],
)
def test_cordic_phase_register_is_scaled_in_turns(register_value, turns):
    assert Cordic.current_output_signal.to_python(None, register_value) == turns
    assert Iq.cordic_phase.to_python(None, register_value) == turns


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

    assert {"cordic", "cordic_iq_pair", "iq_cordic"} <= set(
        manifest["capabilities"]
    )
    assert "pid_input_filters" not in manifest["capabilities"]
    assert manifest["hardware"]["pid_input_filter_stages"] == 0
    assert manifest["hardware"]["cordic_abi"] == 0x434F5202
    assert manifest["hardware"]["iq_cordic_abi"] == 0x434F5203
    assert manifest["hardware"]["iq_cordic_modules"] == ["iq0", "iq1"]
    assert manifest["timing"]["iq"]["_delay"] == 8
    assert manifest["timing"]["networkanalyzer"]["_delay"] == 4.0
    assert manifest["hardware_modules"].count("Cordic") == 1
    assert "Cordics" in manifest["software_managers"]
    assert manifest["hardware_modules"].count("Iq") == 3
    assert manifest["hardware_modules"].count("Pid") == 3
    assert "IIR" not in manifest["hardware_modules"]


def test_cordic_vco_profile_contract_and_register_map():
    manifest_path = (
        Path(__file__).parents[1]
        / "fpga"
        / "profiles"
        / "cordic_vco"
        / "manifest.template.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert {"cordic", "cordic_iq_pair", "iq_cordic", "iq_vco"} <= set(
        manifest["capabilities"]
    )
    assert "pid_input_filters" not in manifest["capabilities"]
    assert manifest["hardware"]["pid_input_filter_stages"] == 0
    assert manifest["hardware"]["cordic_abi"] == 0x434F5202
    assert manifest["hardware"]["iq_cordic_abi"] == 0x434F5203
    assert manifest["hardware"]["iq_cordic_modules"] == ["iq0", "iq1"]
    assert manifest["hardware"]["iq_vco_abi"] == 0x56434F01
    assert manifest["timing"]["iq"]["_delay"] == 8
    assert manifest["timing"]["iq"]["_vco_delay"] == 3
    assert manifest["timing"]["networkanalyzer"]["_delay"] == 4.0
    assert manifest["hardware_modules"].count("Iq") == 3
    assert manifest["hardware_modules"].count("Pid") == 3
    assert "IIR" not in manifest["hardware_modules"]

    assert Iq.vco_input.address == 0x14
    assert Iq.vco_range.address == 0x128
    assert Iq.vco_on.address == 0x12C
    assert Iq.vco_abi_version.address == 0x240
    assert Iq.cordic_phase.address == 0x150
    assert Iq.cordic_abi_version.address == 0x244


@pytest.mark.parametrize("frequency_range", [-20e6, -1e3, 0.0, 1e3, 20e6])
def test_vco_range_register_preserves_sign_and_scaling(frequency_range):
    encoded = Iq.vco_range.from_python(None, frequency_range)
    decoded = Iq.vco_range.to_python(None, encoded)

    assert decoded == pytest.approx(frequency_range, abs=Iq.vco_range.increment)
