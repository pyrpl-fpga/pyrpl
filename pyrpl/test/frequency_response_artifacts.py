"""Save reproducible artifacts from hardware frequency-response tests."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def _safe_name(value):
    """Return a filename-safe representation of a test or bitstream name."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_.") or "unnamed"


def _json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return str(value)


def save_frequency_response(name, frequencies, measured, theory, metadata=None):
    """Save numeric data, summary statistics, and a comparison plot.

    ``PYRPL_BITSTREAM_LABEL`` selects the subdirectory used for a run, for
    example ``old`` or ``new``. ``PYRPL_RESPONSE_RESULTS_DIR`` can override
    the default ``.pyrpl_test_results/frequency_response`` output directory.
    """
    frequencies = np.asarray(frequencies, dtype=float)
    measured = np.asarray(measured, dtype=complex)
    theory = np.asarray(theory, dtype=complex)
    if not (frequencies.shape == measured.shape == theory.shape):
        raise ValueError("frequencies, measured and theory must have the same shape")

    difference = measured - theory
    absolute_error = np.abs(difference)
    denominator = np.maximum(np.abs(theory), np.finfo(float).eps)
    relative_error = absolute_error / denominator

    root = Path(
        os.environ.get(
            "PYRPL_RESPONSE_RESULTS_DIR",
            ".pyrpl_test_results/frequency_response",
        )
    )
    label = _safe_name(os.environ.get("PYRPL_BITSTREAM_LABEL", "unlabeled"))
    output_dir = root / label
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_name(name)

    summary = {
        "name": str(name),
        "bitstream_label": label,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "points": int(frequencies.size),
        "frequency_min_hz": float(np.min(frequencies)),
        "frequency_max_hz": float(np.max(frequencies)),
        "maximum_absolute_error": float(np.max(absolute_error)),
        "rms_absolute_error": float(np.sqrt(np.mean(absolute_error**2))),
        "maximum_relative_error": float(np.max(relative_error)),
        "rms_relative_error": float(np.sqrt(np.mean(relative_error**2))),
        "metadata": metadata or {},
    }

    np.savez_compressed(
        output_dir / f"{stem}.npz",
        frequency_hz=frequencies,
        measured=measured,
        theory=theory,
        difference=difference,
        absolute_error=absolute_error,
        relative_error=relative_error,
    )
    columns = np.column_stack(
        (
            frequencies,
            measured.real,
            measured.imag,
            np.abs(measured),
            np.unwrap(np.angle(measured)) * 180.0 / np.pi,
            theory.real,
            theory.imag,
            np.abs(theory),
            np.unwrap(np.angle(theory)) * 180.0 / np.pi,
            difference.real,
            difference.imag,
            absolute_error,
            relative_error,
        )
    )
    np.savetxt(
        output_dir / f"{stem}.csv",
        columns,
        delimiter=",",
        header=(
            "frequency_hz,measured_real,measured_imag,measured_magnitude,"
            "measured_phase_deg,theory_real,theory_imag,theory_magnitude,"
            "theory_phase_deg,difference_real,difference_imag,"
            "absolute_error,relative_error"
        ),
        comments="",
    )
    with (output_dir / f"{stem}.json").open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True, default=_json_default)

    # Use the object-oriented Agg canvas so saving plots does not select a
    # global matplotlib backend or interfere with Qt-based tests.
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(9, 10), constrained_layout=True)
    FigureCanvasAgg(figure)
    magnitude_axis, phase_axis, error_axis = figure.subplots(3, 1, sharex=True)
    magnitude_axis.plot(frequencies, np.abs(measured), label="measured")
    magnitude_axis.plot(frequencies, np.abs(theory), "--", label="theory")
    magnitude_axis.set_ylabel("Magnitude")
    magnitude_axis.grid(True, which="both")
    magnitude_axis.legend()

    phase_axis.plot(
        frequencies,
        np.unwrap(np.angle(measured)) * 180.0 / np.pi,
        label="measured",
    )
    phase_axis.plot(
        frequencies,
        np.unwrap(np.angle(theory)) * 180.0 / np.pi,
        "--",
        label="theory",
    )
    phase_axis.set_ylabel("Phase (degrees)")
    phase_axis.grid(True, which="both")
    phase_axis.legend()

    error_axis.plot(frequencies, absolute_error, label="absolute error")
    error_axis.plot(frequencies, relative_error, label="relative error")
    error_axis.set_xlabel("Frequency (Hz)")
    error_axis.set_ylabel("Difference")
    error_axis.grid(True, which="both")
    error_axis.legend()
    if frequencies.size > 2 and np.all(frequencies > 0):
        magnitude_axis.set_xscale("log")
        phase_axis.set_xscale("log")
        error_axis.set_xscale("log")
    figure.suptitle(f"{name} ({label})")
    figure.savefig(output_dir / f"{stem}.png", dpi=150)

    return output_dir / stem
