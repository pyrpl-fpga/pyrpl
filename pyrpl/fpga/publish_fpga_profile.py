"""Stage a built FPGA image as a selectable PyRPL runtime profile.

One profile can contain an image per Zynq device:

    python publish_fpga_profile.py default                 # z7010 image
    python publish_fpga_profile.py default --part z7020    # add the z7020 image

The images of all parts share one manifest, so they must be built from the same
hardware contract (everything in the manifest except the file entries).
"""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

FPGA_ROOT = Path(__file__).resolve().parent

# Keep in sync with pyrpl.fpga_profiles.FPGA_PARTS and red_pitaya_vivado.tcl.
FPGA_PARTS = ("z7010", "z7020")
DEFAULT_FPGA_PART = "z7010"
FILE_KEYS = ("bitstream", "bitstreams", "dtbo")


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_dir(profile_id, part=DEFAULT_FPGA_PART):
    """Directory into which make_bin.bat builds ``profile_id`` for ``part``."""
    if part == DEFAULT_FPGA_PART:
        return FPGA_ROOT / "build" / profile_id
    return FPGA_ROOT / "build" / part / profile_id


def bitstream_filename(part):
    """Name of the staged image for ``part`` inside the profile directory."""
    if part == DEFAULT_FPGA_PART:
        return "red_pitaya.bin"
    return f"red_pitaya_{part}.bin"


def _contract(manifest):
    return {key: value for key, value in manifest.items() if key not in FILE_KEYS}


def _bitstreams(manifest):
    if "bitstreams" in manifest:
        return dict(manifest["bitstreams"])
    if "bitstream" in manifest:
        return {DEFAULT_FPGA_PART: manifest["bitstream"]}
    return {}


def publish(profile_id, part=DEFAULT_FPGA_PART, force=False):
    """Copy a completed build and create or update its checksum-locked manifest."""
    if re.fullmatch(r"[a-z0-9_-]+", profile_id) is None:
        raise ValueError(f"Invalid FPGA profile identifier {profile_id!r}")
    if part not in FPGA_PARTS:
        raise ValueError(f"Unknown FPGA part {part!r}; expected one of {', '.join(FPGA_PARTS)}")
    template_path = FPGA_ROOT / "profiles" / profile_id / "manifest.template.json"
    source_bitstream = build_dir(profile_id, part) / "red_pitaya.bin"
    # The device-tree overlay only describes the PL address map, which is the
    # same for every profile and part.
    source_dtbo = FPGA_ROOT / "bitstreams" / "default" / "red_pitaya.dtbo"
    destination = FPGA_ROOT / "bitstreams" / profile_id
    manifest_path = destination / "manifest.json"

    existing = None
    if manifest_path.is_file():
        with manifest_path.open(encoding="utf-8") as stream:
            existing = json.load(stream)

    if template_path.is_file():
        with template_path.open(encoding="utf-8") as stream:
            manifest = json.load(stream)
    elif existing is not None:
        # Profiles without a template (legacy) keep their staged contract.
        manifest = existing
    else:
        raise FileNotFoundError(template_path)
    for source in (source_bitstream, source_dtbo):
        if not source.is_file():
            raise FileNotFoundError(source)
    if manifest["id"] != profile_id:
        raise ValueError(f"Template id {manifest['id']!r} does not match profile {profile_id!r}")

    bitstreams = {}
    if existing is not None:
        bitstreams = _bitstreams(existing)
        if part in bitstreams and not force:
            raise FileExistsError(
                f"{destination} already contains a {part} image; "
                "use --force to replace it"
            )
        if _contract(existing) != _contract(manifest):
            stale = sorted(other for other in bitstreams if other != part)
            if stale and not force:
                raise ValueError(
                    f"The template of {profile_id!r} differs from the staged manifest, "
                    f"whose images for {', '.join(stale)} were built for the old contract. "
                    "Rebuild and republish every part, using --force to drop the stale images."
                )
            for other in stale:
                print(f"Dropping the {other} image built for the previous contract")
                (destination / bitstreams.pop(other)["filename"]).unlink(missing_ok=True)

    destination.mkdir(parents=True, exist_ok=True)
    bitstream = destination / bitstream_filename(part)
    dtbo = destination / manifest["dtbo"]["filename"]
    shutil.copy2(source_bitstream, bitstream)
    # The default profile is also the canonical source of the device-tree
    # overlay, so publishing default would otherwise copy the DTBO onto itself.
    if source_dtbo.resolve() != dtbo.resolve():
        shutil.copy2(source_dtbo, dtbo)
    bitstreams[part] = {"filename": bitstream.name, "sha256": _sha256(bitstream)}

    manifest = _contract(manifest)
    manifest["bitstreams"] = {key: bitstreams[key] for key in FPGA_PARTS if key in bitstreams}
    manifest["dtbo"] = {"filename": dtbo.name, "sha256": _sha256(dtbo)}
    with manifest_path.open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", help="build profile to stage")
    parser.add_argument(
        "--part",
        default=DEFAULT_FPGA_PART,
        choices=FPGA_PARTS,
        help="Zynq device the image was built for (default: %(default)s)",
    )
    parser.add_argument(
        "--force", action="store_true", help="replace an already staged image for this part"
    )
    args = parser.parse_args()
    destination = publish(args.profile, part=args.part, force=args.force)
    print(f"Staged {args.part} image of runtime profile in {destination}")


if __name__ == "__main__":
    main()
