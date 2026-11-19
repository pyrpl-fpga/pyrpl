"""Tests of the SHO fit on synthetic spectra (no hardware needed)."""

import numpy as np
import pytest

pytest.importorskip("scipy")

from pyrpl.software_modules.sho_fit import fit_sho, sho_psd  # noqa: E402

TRUE = dict(f0=150e3, q=2000.0, s0=1e-16, sn=4e-15)  # peak 50 dB above the noise floor
FREQS = np.linspace(110e3, 190e3, 8000)  # the noise floor is reached ~12 kHz from f0


def test_area_formula():
    """The analytic area equals the numerical integral of the noiseless model."""
    f = np.linspace(0, 20 * TRUE["f0"], 2_000_001)
    numerical = np.sum(sho_psd(f, TRUE["f0"], TRUE["q"], TRUE["s0"], 0.0)) * (f[1] - f[0])
    analytic = np.pi / 2 * TRUE["s0"] * TRUE["f0"] * TRUE["q"]
    assert numerical == pytest.approx(analytic, rel=1e-3)


@pytest.mark.parametrize("n_averages", [1, 10])
def test_fit_recovers_parameters(n_averages):
    rng = np.random.default_rng(0)
    psd = sho_psd(FREQS, **TRUE) * rng.gamma(n_averages, 1 / n_averages, FREQS.size)
    r = fit_sho(FREQS, psd, n_averages=n_averages)
    area = np.sqrt(np.pi / 2 * TRUE["s0"] * TRUE["f0"] * TRUE["q"])
    for est, err, true in (
        (r.f0, r.f0_err, TRUE["f0"]),
        (r.q, r.q_err, TRUE["q"]),
        (r.sn, r.sn_err, TRUE["sn"]),
        (r.area_vrms, r.area_vrms_err, area),
    ):
        assert abs(est - true) < 4 * err, (est, err, true)
    assert not r.resolution_limited


def test_log_bias_correction():
    """For single spectra the mean of the log is ln(PSD) - 0.577; without the
    correction the noise floor would come out 44 % low."""
    rng = np.random.default_rng(1)
    psd = sho_psd(FREQS, **TRUE) * rng.exponential(size=FREQS.size)
    corrected = fit_sho(FREQS, psd, n_averages=1)
    uncorrected = fit_sho(FREQS, psd, n_averages=10**6)
    assert corrected.sn == pytest.approx(TRUE["sn"], rel=0.05)
    assert uncorrected.sn == pytest.approx(TRUE["sn"] * np.exp(-np.euler_gamma), rel=0.05)


def test_fit_range_and_step():
    rng = np.random.default_rng(2)
    psd = sho_psd(FREQS, **TRUE) * rng.gamma(10, 1 / 10, FREQS.size)
    r = fit_sho(FREQS, psd, fmin=140e3, fmax=160e3, n_averages=10, step=2)
    assert r.fmin >= 140e3 and r.fmax <= 160e3
    assert r.n_points == pytest.approx(np.sum((FREQS >= 140e3) & (FREQS <= 160e3)) / 2, abs=1)
    assert r.f0 == pytest.approx(TRUE["f0"], rel=1e-4)


def test_resolution_limited_flag():
    rng = np.random.default_rng(3)
    psd = sho_psd(FREQS, **TRUE) * rng.gamma(10, 1 / 10, FREQS.size)
    linewidth = TRUE["f0"] / TRUE["q"]
    assert fit_sho(FREQS, psd, n_averages=10, rbw=linewidth / 2).resolution_limited
    assert not fit_sho(FREQS, psd, n_averages=10, rbw=linewidth / 10).resolution_limited


def test_weak_peak_below_noise_floor():
    """A peak lower than the noise floor is still fitted (not rejected): it
    is up to the user to judge the result, using the uncertainties."""
    q, sn = 200.0, 4e-15
    s0 = 0.5 * sn / q**2  # peak height half the noise floor
    rng = np.random.default_rng(4)
    psd = sho_psd(FREQS, 150e3, q, s0, sn) * rng.gamma(10, 1 / 10, FREQS.size)
    r = fit_sho(FREQS, psd, n_averages=10)
    area = np.sqrt(np.pi / 2 * s0 * 150e3 * q)
    assert abs(r.area_vrms - area) < 4 * r.area_vrms_err
    assert abs(r.f0 - 150e3) < 4 * r.f0_err
