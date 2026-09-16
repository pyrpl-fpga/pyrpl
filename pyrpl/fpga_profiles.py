"""Runtime descriptions of the FPGA images shipped with PyRPL."""

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROFILE_ALIASES = {
    "iir24x8": "default",
    "iir32x14": "legacy",
}


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
    bitstream: Path
    dtbo: Path

    def module_attributes(self, class_name):
        """Return per-instance Python attributes for a hardware class."""
        return self.timing.get(class_name.lower(), {})


def _profiles_root():
    return Path(__file__).resolve().parent / "fpga" / "bitstreams"


def available_fpga_profiles():
    """Return the identifiers of all packaged profiles."""
    root = _profiles_root()
    return tuple(sorted(path.parent.name for path in root.glob("*/manifest.json")))


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

    bitstream = manifest_path.parent / manifest["bitstream"]["filename"]
    dtbo = manifest_path.parent / manifest["dtbo"]["filename"]
    _verify_file(bitstream, manifest["bitstream"]["sha256"])
    _verify_file(dtbo, manifest["dtbo"]["sha256"])

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
    )
