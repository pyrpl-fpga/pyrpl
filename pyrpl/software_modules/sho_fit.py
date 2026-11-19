"""
Fit of a simple harmonic oscillator (SHO) plus white noise to a power
spectral density (PSD).

Model, for a PSD S(f) in Vrms^2/Hz::

    S(f) = S_n + S_0 * f_0^4 / ((f_0^2 - f^2)^2 + (f * f_0 / Q)^2)

This is the displacement spectrum of an oscillator driven by a white force
noise (e.g. thermal motion), read out with a voltage linear in position,
on top of a white (frequency independent) measurement noise S_n. S_0 is the
oscillator's PSD well below resonance; at resonance it is S_0 * Q^2.

The area under the noiseless curve is analytic::

    integral_0^inf (S - S_n) df = pi / 2 * S_0 * f_0 * Q    [Vrms^2]

and its square root is the rms voltage of the oscillator signal, over all
frequencies (not only over the fitted range).

The fit minimizes the squared difference between the logarithms of data and
model. For a spectrum averaged over n periodograms, each point has a
relative scatter of about 1/sqrt(n) independent of its value, so a fit in
log space weights the peak and the noise floor fairly. The mean of the
logarithm of such data is below the logarithm of the mean by
ln(n) - digamma(n) (0.58 for n = 1), which is corrected for.

Only scipy.optimize and scipy.special are used, and scipy is imported
only when a fit is done (scipy is not a core dependency of pyrpl).
"""

from dataclasses import dataclass

import numpy as np


def sho_psd(f, f0, q, s0, sn):
    """SHO + white noise PSD (see module docstring), same unit as s0 and sn."""
    f = np.asarray(f, dtype=float)
    return sn + s0 * f0**4 / ((f0**2 - f**2) ** 2 + (f * f0 / q) ** 2)


@dataclass
class ShoFitResult:
    """Result of fit_sho(). PSD values in Vrms^2/Hz, frequencies in Hz."""

    f0: float  # resonance frequency (Hz)
    q: float  # quality factor
    s0: float  # PSD of the oscillator well below resonance (Vrms^2/Hz)
    sn: float  # white noise floor (Vrms^2/Hz)
    f0_err: float
    q_err: float
    s0_err: float
    sn_err: float
    area_vrms: float  # sqrt of the area under the noiseless curve (Vrms)
    area_vrms_err: float
    fmin: float  # fitted frequency range (Hz)
    fmax: float
    n_points: int  # number of points used in the fit
    n_averages: int  # number of averaged periodograms assumed
    rbw: float  # resolution bandwidth of the data (Hz), nan if unknown

    @property
    def linewidth(self):
        """Full width at half maximum of the peak, f0 / Q (Hz)."""
        return self.f0 / self.q

    @property
    def noise_vrms_per_sqrt_hz(self):
        """Noise floor in Vrms/sqrt(Hz)."""
        return np.sqrt(self.sn)

    @property
    def noise_vrms_per_sqrt_hz_err(self):
        return 0.5 * self.sn_err / np.sqrt(self.sn)

    @property
    def resolution_limited(self):
        """True if the linewidth is not well above the rbw. The window then
        broadens the measured peak, so the fitted Q is too low (the area is
        not affected)."""
        return bool(np.isfinite(self.rbw) and self.linewidth < 3 * self.rbw)

    def psd(self, f):
        """The fitted model at frequencies f (Vrms^2/Hz)."""
        return sho_psd(f, self.f0, self.q, self.s0, self.sn)

    def psd_noiseless(self, f):
        """The fitted model without the noise floor (Vrms^2/Hz)."""
        return sho_psd(f, self.f0, self.q, self.s0, 0.0)


class ShoFitError(ValueError):
    pass


def _initial_guess(f, s):
    """Guesses (f0, Q, S0, Sn) from the data: noise floor from the lower
    percentiles, peak position and height from the maximum, Q from the
    width at half height."""
    sn = np.percentile(s, 10)
    i_max = int(np.argmax(s))
    f0 = f[i_max]
    height = s[i_max] - sn
    if height <= 0:
        raise ShoFitError("no peak above the noise floor in the fit range")
    above = s - sn > height / 2
    lo = i_max
    while lo > 0 and above[lo - 1]:
        lo -= 1
    hi = i_max
    while hi < len(f) - 1 and above[hi + 1]:
        hi += 1
    df = abs(f[1] - f[0]) if len(f) > 1 else 1.0
    fwhm = max(abs(f[hi] - f[lo]), df)
    q = max(f0 / fwhm, 0.6)
    s0 = height / q**2
    return f0, q, s0, max(sn, height * 1e-6)


def fit_sho(
    frequencies, psd, fmin=None, fmax=None, n_averages=1, rbw=np.nan, step=1, error_scale=1.0
):
    """
    Fits sho_psd() to a power spectral density.

    :param frequencies: frequencies in Hz
    :param psd: PSD in Vrms^2/Hz (must be > 0)
    :param fmin, fmax: fit range in Hz (default: all data)
    :param n_averages: number of averaged periodograms (for the log bias)
    :param rbw: resolution bandwidth in Hz (only used for the
        resolution_limited warning)
    :param step: use only every step-th point, e.g. the zero-padding factor
        of the FFT, to fit independent points only
    :param error_scale: factor applied to the fit uncertainties, e.g.
        sqrt(rbw / bin spacing) to account for neighbouring points being
        correlated through the window
    :return: ShoFitResult
    """
    from scipy.optimize import least_squares
    from scipy.special import digamma

    f = np.asarray(frequencies, dtype=float)
    s = np.asarray(psd, dtype=float)
    if f.shape != s.shape:
        raise ShoFitError("frequencies and psd must have the same shape")
    order = np.argsort(f)
    f, s = f[order], s[order]
    lo = -np.inf if fmin is None else fmin
    hi = np.inf if fmax is None else fmax
    mask = (f >= min(lo, hi)) & (f <= max(lo, hi)) & np.isfinite(s) & (s > 0)
    f, s = f[mask][::step], s[mask][::step]
    if len(f) < 8:
        raise ShoFitError(f"too few points in the fit range ({len(f)})")

    f0_g, q_g, s0_g, sn_g = _initial_guess(f, s)
    width_g = f0_g / q_g
    n = max(int(n_averages), 1)
    log_bias = digamma(n) - np.log(n)  # <ln(estimate)> - ln(true PSD)
    log_s = np.log(s)

    def unpack(x):
        return f0_g + x[0] * width_g, np.exp(x[1]), np.exp(x[2]), np.exp(x[3])

    def residuals(x):
        f0, q, s0, sn = unpack(x)
        return log_s - np.log(sho_psd(f, f0, q, s0, sn)) - log_bias

    x0 = np.array([0.0, np.log(q_g), np.log(s0_g), np.log(sn_g)])
    res = least_squares(residuals, x0, method="lm")
    if not res.success:
        raise ShoFitError(f"fit did not converge: {res.message}")
    f0, q, s0, sn = unpack(res.x)
    if f0 <= 0:
        raise ShoFitError("fit gave a negative resonance frequency")
    q = abs(q)

    # covariance of x = (d, ln Q, ln S0, ln Sn), scaled by the residual variance
    dof = max(len(f) - len(x0), 1)
    s2 = np.sum(res.fun**2) / dof
    try:
        cov = np.linalg.inv(res.jac.T @ res.jac) * s2 * error_scale**2
    except np.linalg.LinAlgError:
        cov = np.full((4, 4), np.nan)
    err = np.sqrt(np.abs(np.diag(cov)))

    area = np.pi / 2 * s0 * f0 * q
    # ln(area) = const + ln S0 + ln f0 + ln Q, with d ln f0 = width_g / f0 * dd
    grad = np.array([width_g / f0, 1.0, 1.0, 0.0])
    ln_area_err = np.sqrt(abs(grad @ cov @ grad))
    area_vrms = np.sqrt(area)
    area_vrms_err = 0.5 * ln_area_err * area_vrms
    return ShoFitResult(
        f0=f0,
        q=q,
        s0=s0,
        sn=sn,
        f0_err=err[0] * width_g,
        q_err=err[1] * q,
        s0_err=err[2] * s0,
        sn_err=err[3] * sn,
        area_vrms=area_vrms,
        area_vrms_err=area_vrms_err,
        fmin=float(f[0]),
        fmax=float(f[-1]),
        n_points=len(f),
        n_averages=n,
        rbw=float(rbw),
    )
