"""Stage a built FPGA image as a selectable PyRPL runtime profile."""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

FPGA_ROOT = Path(__file__).resolve().parent


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(profile_id, force=False):
    """Copy a completed build and create its checksum-locked manifest."""
    if re.fullmatch(r"[a-z0-9_-]+", profile_id) is None:
        raise ValueError(f"Invalid FPGA profile identifier {profile_id!r}")
    profile_dir = FPGA_ROOT / "profiles" / profile_id
    template_path = profile_dir / "manifest.template.json"
    source_bitstream = FPGA_ROOT / "build" / profile_id / "red_pitaya.bin"
    source_dtbo = FPGA_ROOT / "bitstreams" / "default" / "red_pitaya.dtbo"
    destination = FPGA_ROOT / "bitstreams" / profile_id

    for source in (template_path, source_bitstream, source_dtbo):
        if not source.is_file():
            raise FileNotFoundError(source)
    if destination.exists() and not force:
        raise FileExistsError(
            f"{destination} already exists; use --force to replace this staged profile"
        )

    with template_path.open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    if manifest["id"] != profile_id:
        raise ValueError(f"Template id {manifest['id']!r} does not match profile {profile_id!r}")

    destination.mkdir(parents=True, exist_ok=True)
    bitstream = destination / manifest["bitstream"]["filename"]
    dtbo = destination / manifest["dtbo"]["filename"]
    shutil.copy2(source_bitstream, bitstream)
    # The default profile is also the canonical source of the device-tree
    # overlay, so publishing default would otherwise copy the DTBO onto itself.
    if source_dtbo.resolve() != dtbo.resolve():
        shutil.copy2(source_dtbo, dtbo)
    manifest["bitstream"]["sha256"] = _sha256(bitstream)
    manifest["dtbo"]["sha256"] = _sha256(dtbo)
    with (destination / "manifest.json").open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", help="build profile to stage")
    parser.add_argument("--force", action="store_true", help="replace an already staged profile")
    args = parser.parse_args()
    destination = publish(args.profile, force=args.force)
    print(f"Staged runtime profile in {destination}")


if __name__ == "__main__":
    main()
