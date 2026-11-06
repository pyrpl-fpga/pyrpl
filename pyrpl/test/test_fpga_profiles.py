"""Offline tests of FPGA part selection, profile DSP codes, and publishing."""

import importlib.util
import json
from pathlib import Path

import pytest

from pyrpl.fpga_profiles import (
    FpgaProfile,
    fpga_part_from_idcode,
    manifest_bitstreams,
    normalize_fpga_part,
    parse_fpga_part,
)
from pyrpl.hardware_modules.dsp import dsp_addr_base, dsp_code

FPGA_ROOT = Path(__file__).resolve().parents[1] / "fpga"


def _profile(hardware=None, bitstreams=None):
    return FpgaProfile(
        id="test",
        description="",
        abi_version=1,
        capabilities=frozenset(),
        hardware_modules=(),
        software_managers=(),
        timing={},
        hardware=hardware or {},
        bitstream=Path("red_pitaya.bin"),
        dtbo=Path("red_pitaya.dtbo"),
        bitstreams=bitstreams or {},
    )


@pytest.mark.parametrize(
    "idcode, part",
    [(0x13722093, "z7010"), (0x03727093, "z7020"), (0x1372C093, None), (0xF8000530, None)],
)
def test_fpga_part_from_idcode(idcode, part):
    assert fpga_part_from_idcode(idcode) == part


def test_parse_fpga_part_ignores_echoed_address():
    output = "root@rp:~# /opt/redpitaya/bin/monitor 0xF8000530\r\n0x13727093\r\nroot@rp:~# "
    assert parse_fpga_part(output) == "z7020"
    assert parse_fpga_part("monitor 0xF8000530\r\nnot found") is None


@pytest.mark.parametrize("name", ["z7020", "XC7Z020", "xc7z020clg400-1"])
def test_normalize_fpga_part(name):
    assert normalize_fpga_part(name) == "z7020"


def test_bitstream_for_part():
    legacy = _profile()
    assert legacy.fpga_parts == ("z7010",)
    assert legacy.bitstream_for("z7010") == Path("red_pitaya.bin")
    with pytest.raises(ValueError, match="no bitstream for the z7020"):
        legacy.bitstream_for("z7020")

    both = _profile(bitstreams={"z7010": Path("a.bin"), "z7020": Path("b.bin")})
    assert both.fpga_parts == ("z7010", "z7020")
    assert both.bitstream_for("xc7z020clg400-1") == Path("b.bin")


def test_manifest_bitstreams_reads_both_formats():
    entry = {"filename": "red_pitaya.bin", "sha256": "0"}
    assert manifest_bitstreams({"bitstream": entry}) == {"z7010": entry}
    assert manifest_bitstreams({"bitstreams": {"z7020": entry}}) == {"z7020": entry}


def test_profile_dsp_codes_and_addresses():
    assert dsp_code("cordic") == 4
    assert dsp_addr_base("cordic") == 0x40340000
    full = _profile(hardware={"dsp_codes": {"cordic": 16, "arithmetic": 17}})
    assert dsp_code("cordic", full) == 16
    assert dsp_addr_base("cordic", full) == 0x40500000
    assert dsp_addr_base("arithmetic", full) == 0x40510000
    # Unlisted signals keep their historical codes and addresses.
    assert dsp_addr_base("iir", full) == 0x40340000
    assert dsp_code("off", full) == 15


def test_full_manifest_template_is_consistent():
    template = json.loads(
        (FPGA_ROOT / "profiles" / "full" / "manifest.template.json").read_text(encoding="utf-8")
    )
    codes = template["hardware"]["dsp_codes"]
    assert codes == {"cordic": 16, "arithmetic": 17}
    assert set(codes) <= set(template["hardware"]["dsp_inputs"])
    rtl = (FPGA_ROOT / "rtl_profiles" / "full" / "red_pitaya_dsp.v").read_text(encoding="utf-8")
    assert "localparam CORDIC = 'd16;" in rtl
    assert "localparam ARITH  = 'd17;" in rtl


@pytest.fixture
def publish_module(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "publish_fpga_profile", FPGA_ROOT / "publish_fpga_profile.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "FPGA_ROOT", tmp_path)
    template = {"id": "demo", "hardware": {"x": 1}, "dtbo": {"filename": "red_pitaya.dtbo"}}
    (tmp_path / "profiles" / "demo").mkdir(parents=True)
    (tmp_path / "profiles" / "demo" / "manifest.template.json").write_text(json.dumps(template))
    (tmp_path / "bitstreams" / "default").mkdir(parents=True)
    (tmp_path / "bitstreams" / "default" / "red_pitaya.dtbo").write_bytes(b"dtbo")
    for part, directory in (("z7010", "build/demo"), ("z7020", "build/z7020/demo")):
        (tmp_path / directory).mkdir(parents=True)
        (tmp_path / directory / "red_pitaya.bin").write_bytes(part.encode())
    return module


def test_publish_merges_parts(publish_module, tmp_path):
    publish_module.publish("demo", part="z7020")
    publish_module.publish("demo", part="z7010")
    manifest = json.loads((tmp_path / "bitstreams" / "demo" / "manifest.json").read_text())
    assert set(manifest["bitstreams"]) == {"z7010", "z7020"}
    assert manifest["bitstreams"]["z7020"]["filename"] == "red_pitaya_z7020.bin"
    assert (tmp_path / "bitstreams" / "demo" / "red_pitaya_z7020.bin").read_bytes() == b"z7020"
    assert "bitstream" not in manifest
    with pytest.raises(FileExistsError):
        publish_module.publish("demo", part="z7020")


def test_publish_refuses_mixed_contracts(publish_module, tmp_path):
    publish_module.publish("demo", part="z7010")
    template_path = tmp_path / "profiles" / "demo" / "manifest.template.json"
    template = json.loads(template_path.read_text())
    template["hardware"]["x"] = 2
    template_path.write_text(json.dumps(template))
    with pytest.raises(ValueError, match="differs from the staged manifest"):
        publish_module.publish("demo", part="z7020")
    publish_module.publish("demo", part="z7020", force=True)
    manifest = json.loads((tmp_path / "bitstreams" / "demo" / "manifest.json").read_text())
    assert set(manifest["bitstreams"]) == {"z7020"}
    assert not (tmp_path / "bitstreams" / "demo" / "red_pitaya.bin").exists()
