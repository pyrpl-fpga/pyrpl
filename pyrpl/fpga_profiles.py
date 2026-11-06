"""Runtime descriptions of the FPGA images shipped with PyRPL."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PROFILE_ALIASES = {
    "iir24x8": "default",
    "iir32x14": "legacy",
}

# Zynq devices that PyRPL bitstreams are built for. The keys are the short
# names used in manifests, build directories and the ``fpga_part`` setting;
# the values are the Vivado part numbers (see red_pitaya_vivado.tcl).
#   z7010: STEMlab 125-14 (original and Gen 2, non-Z7020 variants)
#   z7020: STEMlab 125-14 Z7020 variants, e.g. the PRO Z7020 Gen 2
FPGA_PARTS = {
    "z7010": "xc7z010clg400-1",
    "z7020": "xc7z020clg400-1",
}
DEFAULT_FPGA_PART = "z7010"

# Device codes in bits [16:12] of the Zynq-7000 IDCODE (also readable by the
# CPU from the SLCR PSS_IDCODE register, see ``ZYNQ_PSS_IDCODE_ADDRESS``).
ZYNQ_PSS_IDCODE_ADDRESS = 0xF8000530
_ZYNQ_DEVICE_CODES = {
    0x02: "z7010",
    0x07: "z7020",
}
# Bits [11:0] of every Xilinx IDCODE: manufacturer 0x49 shifted left, plus 1.
_XILINX_IDCODE_LOW_BITS = 0x093


def normalize_fpga_part(part):
    """Return the short part name (``"z7010"`` or ``"z7020"``) for ``part``.

    Accepts the short names, their ``xc7``-prefixed spellings and full Vivado
    part numbers such as ``"xc7z020clg400-1"``.
    """
    text = str(part).strip().lower()
    for name, vivado_part in FPGA_PARTS.items():
        if text in (name, vivado_part.split("clg")[0], vivado_part):
            return name
    choices = ", ".join(FPGA_PARTS)
    raise ValueError(f"Unknown FPGA part {part!r}. Known parts: {choices}")


def fpga_part_from_idcode(idcode):
    """Map a Zynq-7000 IDCODE value to a short part name, or ``None``."""
    idcode = int(idcode)
    if idcode & 0xFFF != _XILINX_IDCODE_LOW_BITS:
        return None
    return _ZYNQ_DEVICE_CODES.get((idcode >> 12) & 0x1F)


def parse_fpga_part(text):
    """Find a Zynq IDCODE in command output and return its part, or ``None``.

    The output of an interactive shell also echoes the command, which contains
    the register address. Only values carrying the Xilinx manufacturer code
    are considered, so the echoed address cannot be mistaken for the IDCODE.
    """
    for token in re.findall(r"0x[0-9a-fA-F]{8}", str(text)):
        part = fpga_part_from_idcode(int(token, 16))
        if part is not None:
            return part
    return None


@dataclass(frozen=True)
class FpgaProfile:
    """Hardware/software contract associated with one packaged bitstream."""

    id: str
    description: str
    abi_version: int
    capabilities: frozenset
    hardware_modules: tuple
    software_managers: tuple
    timing: dict
    hardware: dict
    bitstream: Path  # image for DEFAULT_FPGA_PART (or the only image)
    dtbo: Path
    # Images per FPGA part. Empty means only ``bitstream`` (for z7010) exists.
    bitstreams: dict = field(default_factory=dict)

    def module_attributes(self, class_name):
        """Return profile-specific attributes for a hardware or software module."""
        return self.timing.get(class_name.lower(), {})

    @property
    def fpga_parts(self):
        """Short names of the FPGA parts for which this profile has an image."""
        return tuple(sorted(self.bitstreams)) if self.bitstreams else (DEFAULT_FPGA_PART,)

    def bitstream_for(self, part=DEFAULT_FPGA_PART):
        """Return the image built for ``part``.

        Raises ``ValueError`` if this profile has not been published for it.
        """
        part = normalize_fpga_part(part)
        bitstreams = self.bitstreams or {DEFAULT_FPGA_PART: self.bitstream}
        try:
            return bitstreams[part]
        except KeyError:
            raise ValueError(
                f"FPGA profile {self.id!r} has no bitstream for the {part} "
                f"({FPGA_PARTS[part]}). Available for: {', '.join(self.fpga_parts)}. "
                f"Build it with 'make_bin.bat {self.id} {part}' and stage it with "
                f"'python publish_fpga_profile.py {self.id} --part {part}'."
            ) from None


def _profiles_root():
    return Path(__file__).resolve().parent / "fpga" / "bitstreams"


def manifest_bitstreams(manifest):
    """Return ``{part: {"filename", "sha256"}}`` for a profile manifest.

    Manifests list their images under ``bitstreams`` keyed by FPGA part. The
    older single ``bitstream`` entry is read as the image for z7010.
    """
    if "bitstreams" in manifest:
        return {
            normalize_fpga_part(part): entry for part, entry in manifest["bitstreams"].items()
        }
    return {DEFAULT_FPGA_PART: manifest["bitstream"]}


def available_fpga_profiles(part=None):
    """Return the identifiers of all packaged profiles.

    With ``part`` (e.g. ``"z7020"``), only list profiles that contain an image
    for that FPGA part.
    """
    root = _profiles_root()
    manifests = sorted(root.glob("*/manifest.json"))
    if part is None:
        return tuple(path.parent.name for path in manifests)
    part = normalize_fpga_part(part)
    profiles = []
    for path in manifests:
        with path.open(encoding="utf-8") as stream:
            if part in manifest_bitstreams(json.load(stream)):
                profiles.append(path.parent.name)
    return tuple(profiles)


def _verify_file(path, expected_sha256):
    if not path.is_file():
        raise OSError(f"FPGA profile file does not exist: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest.lower() != expected_sha256.lower():
        raise OSError(f"FPGA profile file has an invalid checksum: {path}")


@lru_cache(maxsize=None)
def get_fpga_profile(profile_id="default"):
    """Load and validate a packaged FPGA profile manifest."""
    requested_id = str(profile_id).strip().lower()
    profile_id = PROFILE_ALIASES.get(requested_id, requested_id)
    if re.fullmatch(r"[a-z0-9_-]+", profile_id) is None:
        raise ValueError(f"Invalid FPGA profile identifier {profile_id!r}")
    manifest_path = _profiles_root() / profile_id / "manifest.json"
    if not manifest_path.is_file():
        choices = ", ".join(available_fpga_profiles())
        raise ValueError(f"Unknown FPGA profile {profile_id!r}. Available profiles: {choices}")

    with manifest_path.open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    if manifest.get("id") != profile_id:
        raise ValueError(
            f"FPGA profile directory {profile_id!r} contains manifest id {manifest.get('id')!r}"
        )

    bitstreams = {}
    for part, entry in manifest_bitstreams(manifest).items():
        bitstreams[part] = manifest_path.parent / entry["filename"]
        _verify_file(bitstreams[part], entry["sha256"])
    dtbo = manifest_path.parent / manifest["dtbo"]["filename"]
    _verify_file(dtbo, manifest["dtbo"]["sha256"])
    # A profile published only for another part has no default image; keep
    # ``bitstream`` pointing at an existing file of this profile in that case.
    bitstream = bitstreams.get(DEFAULT_FPGA_PART, next(iter(bitstreams.values())))

    return FpgaProfile(
        id=manifest["id"],
        description=manifest["description"],
        abi_version=int(manifest["abi_version"]),
        capabilities=frozenset(manifest["capabilities"]),
        hardware_modules=tuple(manifest["hardware_modules"]),
        software_managers=tuple(manifest["software_managers"]),
        timing=manifest["timing"],
        hardware=manifest["hardware"],
        bitstream=bitstream,
        dtbo=dtbo,
        bitstreams=bitstreams,
    )
