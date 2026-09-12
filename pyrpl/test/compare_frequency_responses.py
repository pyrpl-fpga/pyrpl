"""Compare response artifacts produced with two FPGA bitstreams."""

import argparse
import json
from pathlib import Path

import numpy as np


def compare_artifacts(old_file, new_file, output_dir):
    """Compare two matching NPZ response artifacts and save a plot/summary."""
    old_file = Path(old_file)
    new_file = Path(new_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with np.load(old_file) as old, np.load(new_file) as new:
        old_frequency = old["frequency_hz"]
        new_frequency = new["frequency_hz"]
        if old_frequency.shape != new_frequency.shape or not np.allclose(
            old_frequency, new_frequency, rtol=1e-9, atol=1e-6
        ):
            raise ValueError(f"Frequency grids differ for {old_file.name}")
        frequency = old_frequency
        old_measured = old["measured"]
        new_measured = new["measured"]

    difference = new_measured - old_measured
    relative_difference = np.abs(difference) / np.maximum(
        np.abs(old_measured), np.finfo(float).eps
    )
    amplitude_floor = max(np.max(np.abs(old_measured)), np.max(np.abs(new_measured))) * 1e-6
    valid_amplitude = (np.abs(old_measured) > amplitude_floor) & (
        np.abs(new_measured) > amplitude_floor
    )
    ratio = np.full(old_measured.shape, np.nan + 0j, dtype=complex)
    # ``np.where`` evaluates the division before selecting its result, which
    # emits warnings at zero-response points.  The ``where`` argument of
    # ``np.divide`` avoids evaluating those divisions altogether.
    with np.errstate(divide="ignore", invalid="ignore"):
        np.divide(new_measured, old_measured, out=ratio, where=valid_amplitude)
    phase_difference = np.full(old_measured.shape, np.nan, dtype=float)
    phase_difference[valid_amplitude] = (
        np.unwrap(np.angle(ratio[valid_amplitude])) * 180.0 / np.pi
    )
    valid = np.isfinite(phase_difference)
    delay_seconds = np.nan
    if np.count_nonzero(valid) >= 2:
        slope, _ = np.polyfit(frequency[valid], phase_difference[valid], 1)
        delay_seconds = -slope / 360.0

    stem = old_file.stem
    summary = {
        "old": str(old_file),
        "new": str(new_file),
        "maximum_absolute_change": float(np.max(np.abs(difference))),
        "rms_absolute_change": float(np.sqrt(np.mean(np.abs(difference) ** 2))),
        "maximum_relative_change": float(np.nanmax(relative_difference)),
        "rms_relative_change": float(np.sqrt(np.nanmean(relative_difference**2))),
        "fitted_new_minus_old_delay_seconds": float(delay_seconds),
    }
    with (output_dir / f"{stem}.json").open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
    np.savetxt(
        output_dir / f"{stem}.csv",
        np.column_stack(
            (
                frequency,
                old_measured.real,
                old_measured.imag,
                np.abs(old_measured),
                new_measured.real,
                new_measured.imag,
                np.abs(new_measured),
                difference.real,
                difference.imag,
                np.abs(difference),
                relative_difference,
                phase_difference,
            )
        ),
        delimiter=",",
        header=(
            "frequency_hz,old_real,old_imag,old_magnitude,new_real,new_imag,"
            "new_magnitude,difference_real,difference_imag,absolute_change,"
            "relative_change,phase_change_deg"
        ),
        comments="",
    )

    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(9, 10), constrained_layout=True)
    FigureCanvasAgg(figure)
    magnitude_axis, phase_axis, difference_axis = figure.subplots(3, 1, sharex=True)
    magnitude_axis.plot(frequency, np.abs(old_measured), label="old")
    magnitude_axis.plot(frequency, np.abs(new_measured), "--", label="new")
    magnitude_axis.set_ylabel("Measured magnitude")
    magnitude_axis.legend()
    magnitude_axis.grid(True, which="both")

    phase_axis.plot(
        frequency,
        np.unwrap(np.angle(old_measured)) * 180.0 / np.pi,
        label="old",
    )
    phase_axis.plot(
        frequency,
        np.unwrap(np.angle(new_measured)) * 180.0 / np.pi,
        "--",
        label="new",
    )
    phase_axis.set_ylabel("Measured phase (degrees)")
    phase_axis.legend()
    phase_axis.grid(True, which="both")

    difference_axis.plot(frequency, relative_difference, label="|new-old| / |old|")
    difference_axis.set_xlabel("Frequency (Hz)")
    difference_axis.set_ylabel("Relative change")
    difference_axis.legend()
    difference_axis.grid(True, which="both")
    if frequency.size > 2 and np.all(frequency > 0):
        for axis in (magnitude_axis, phase_axis, difference_axis):
            axis.set_xscale("log")
    figure.suptitle(
        f"{stem}: old versus new\nFitted additional delay: {delay_seconds * 1e9:.3f} ns"
    )
    figure.savefig(output_dir / f"{stem}.png", dpi=150)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path, help="directory containing old-bitstream NPZ files")
    parser.add_argument("new", type=Path, help="directory containing new-bitstream NPZ files")
    parser.add_argument("--output", type=Path, default=Path("frequency_response_comparison"))
    args = parser.parse_args()

    old_files = {path.name: path for path in args.old.glob("*.npz")}
    new_files = {path.name: path for path in args.new.glob("*.npz")}
    common = sorted(old_files.keys() & new_files.keys())
    if not common:
        parser.error("the directories contain no matching NPZ artifact names")
    for name in common:
        compare_artifacts(old_files[name], new_files[name], args.output)
    print(f"Compared {len(common)} response artifact(s); results are in {args.output}")


if __name__ == "__main__":
    main()
