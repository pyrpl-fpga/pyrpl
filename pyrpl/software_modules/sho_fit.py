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

Q is capped at f0 / (one FFT bin) by default: a measured peak cannot be
narrower than the resolution, and the cap keeps the fit from collapsing onto
a single noise spike. A fit that ends at the cap (e.g. a narrow resonance in
a wide span) gives f0; its Q is then only a lower bound and its area is
underestimated. Narrowing the span around f0 resolves the peak.

Only numpy is used: a Levenberg-Marquardt least-squares fit with a trust
region (step size limit) as in MINPACK, and a series for the digamma function.
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
    min_linewidth: float = 0.0  # lower limit of the linewidth f0 / Q in the fit (Hz)
    linewidth_at_limit: bool = False  # Q ended at its cap: only a lower bound

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


def _digamma(x):
    """Digamma function for x > 0 (recurrence up to x >= 10, then the
    asymptotic series; accurate to about 1e-10)."""
    x = float(x)
    result = 0.0
    while x < 10:
        result -= 1.0 / x
        x += 1.0
    inv2 = 1.0 / (x * x)
    return result + np.log(x) - 0.5 / x - inv2 * (1 / 12 - inv2 * (1 / 120 - inv2 / 252))


def _levenberg_marquardt(fun_jac, x0, max_iter=200, ftol=1e-8, xtol=1e-8, gtol=1e-8, project=None):
    """
    Minimises sum(r**2) for (r, J) = fun_jac(x), J = dr/dx.

    Levenberg-Marquardt with a trust region, after More (1978) / MINPACK:
    the parameters are scaled by the column norms of J; a step may not be
    longer than the trust radius, which shrinks after steps that reduce the
    sum of squares much less than predicted and grows after good steps.
    Stops when the sum of squares or the parameters change by less than
    ftol / xtol (relative), or when the residuals are orthogonal to all
    columns of J to within gtol (a flat minimum or valley). project(x), if
    given, maps each new x back into the allowed region (e.g. caps a
    parameter).

    :return: (x, r, J, success, message)
    """
    x = np.asarray(x0, dtype=float)
    r, J = fun_jac(x)
    cost = r @ r
    if not np.isfinite(cost):
        return x, r, J, False, "non-finite residuals at the start"
    scale = np.maximum(np.linalg.norm(J, axis=0), 1e-12)
    radius = 100.0 * max(np.linalg.norm(scale * x), 1.0)
    lam = 0.0
    for _ in range(max_iter):
        column_norms = np.linalg.norm(J, axis=0)
        scale = np.maximum(scale, column_norms)
        A = J.T @ J
        g = J.T @ r
        r_norm = np.sqrt(cost)
        if r_norm == 0 or np.max(np.abs(g) / np.maximum(column_norms * r_norm, 1e-300)) <= gtol:
            return x, r, J, True, "converged (gradient)"
        d2 = scale**2
        # the undamped (Gauss-Newton) step if it lies within the trust
        # region, else the smallest damping (from the last one on) that
        # brings the scaled step within it
        damping = 0.0
        for _ in range(100):
            try:
                step = np.linalg.solve(A + damping * np.diag(d2), -g)
            except np.linalg.LinAlgError:
                step = None
            if step is not None and np.linalg.norm(scale * step) <= radius:
                break
            damping = max(4 * damping, lam, 1e-8 * np.max(np.diag(A) / d2))
        else:
            return x, r, J, False, "no step within the trust region"
        lam = damping
        step_norm = np.linalg.norm(scale * step)
        r_lin = r + J @ step
        predicted = cost - r_lin @ r_lin
        x_new = x + step
        if project is not None:
            x_new = project(x_new)
            step = x_new - x
            step_norm = np.linalg.norm(scale * step)
            r_lin = r + J @ step
            predicted = cost - r_lin @ r_lin
        r_new, J_new = fun_jac(x_new)
        cost_new = r_new @ r_new
        actual = cost - cost_new if np.isfinite(cost_new) else -np.inf
        rho = actual / predicted if predicted > 0 else -np.inf
        if rho < 0.25:
            radius = 0.5 * step_norm
            lam = max(4 * lam, 1e-8 * np.max(np.diag(A) / d2))
        elif rho > 0.75:
            radius = max(radius, 2 * step_norm)
            lam = lam / 4
        if rho > 1e-4:  # accept the step
            x, r, J, cost = x_new, r_new, J_new, cost_new
            if (actual <= ftol * cost_new and predicted <= ftol * cost_new) or (
                step_norm <= xtol * np.linalg.norm(scale * x)
            ):
                return x, r, J, True, "converged"
        elif radius <= xtol * np.linalg.norm(scale * x):
            return x, r, J, True, "converged (trust region at minimum)"
    # still descending slowly, e.g. a peak narrowing onto a single noise
    # spike: return the result (its uncertainties show that it is poor)
    return x, r, J, True, "maximum number of iterations reached"


def fit_sho(
    frequencies,
    psd,
    fmin=None,
    fmax=None,
    n_averages=1,
    rbw=np.nan,
    step=1,
    error_scale=1.0,
    min_linewidth=None,
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
    :param min_linewidth: lower limit of the linewidth f0 / Q in Hz, i.e. an
        upper limit of Q (default: the spacing of the fitted points, one FFT
        bin; 0: no limit). It keeps the fit from collapsing onto a single
        noise spike. A fit that ends at the limit has linewidth_at_limit
        set: f0 is valid, Q is only a lower bound (q_err is nan) and the
        area is underestimated; narrowing the span resolves the peak.
    :return: ShoFitResult
    """
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
    log_bias = _digamma(n) - np.log(n)  # <ln(estimate)> - ln(true PSD)
    log_s = np.log(s)

    def unpack(x):
        return f0_g + x[0] * width_g, np.exp(x[1]), np.exp(x[2]), np.exp(x[3])

    f2 = f**2

    def residuals_and_jacobian(x):
        f0, q, s0, sn = unpack(x)
        detuning = f0**2 - f2
        damping = f2 * f0**2 / q**2
        denominator = detuning**2 + damping
        peak = s0 * f0**4 / denominator
        model = sn + peak
        d_model = np.empty((len(f), 4))  # d model / d x
        d_denominator_df0 = 4 * f0 * detuning + 2 * damping / f0
        d_model[:, 0] = width_g * peak * (4 / f0 - d_denominator_df0 / denominator)
        d_model[:, 1] = peak * 2 * damping / denominator
        d_model[:, 2] = peak
        d_model[:, 3] = sn
        return log_s - np.log(model) - log_bias, -d_model / model[:, None]

    if min_linewidth is None:
        min_linewidth = float(np.median(np.diff(f)))
    lw_min = max(float(min_linewidth), 0.0)

    def ln_q_max(x):
        f0 = f0_g + x[0] * width_g
        return np.log(f0 / lw_min) if lw_min > 0 and f0 > 0 else np.inf

    def cap_q(x):
        x = x.copy()
        x[1] = min(x[1], ln_q_max(x))
        return x

    x0 = cap_q(np.array([0.0, np.log(q_g), np.log(s0_g), np.log(sn_g)]))
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        x, fun, jac, success, message = _levenberg_marquardt(
            residuals_and_jacobian, x0, project=cap_q
        )
    if not success:
        raise ShoFitError(f"fit did not converge: {message}")
    f0, q, s0, sn = unpack(x)
    if f0 <= 0:
        raise ShoFitError("fit gave a negative resonance frequency")
    q = abs(q)

    at_limit = bool(x[1] >= ln_q_max(x) - 1e-9)

    # covariance of x = (d, ln Q, ln S0, ln Sn), scaled by the residual
    # variance; at the limit, Q is held fixed (its row and column are zero)
    free = [0, 2, 3] if at_limit else [0, 1, 2, 3]
    dof = max(len(f) - len(free), 1)
    s2 = np.sum(fun**2) / dof
    cov = np.zeros((4, 4))
    try:
        jf = jac[:, free]
        cov[np.ix_(free, free)] = np.linalg.inv(jf.T @ jf) * s2 * error_scale**2
    except np.linalg.LinAlgError:
        cov[:] = np.nan
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
        q_err=np.nan if at_limit else err[1] * q,
        s0_err=err[2] * s0,
        sn_err=err[3] * sn,
        area_vrms=area_vrms,
        area_vrms_err=area_vrms_err,
        fmin=float(f[0]),
        fmax=float(f[-1]),
        n_points=len(f),
        n_averages=n,
        rbw=float(rbw),
        min_linewidth=lw_min,
        linewidth_at_limit=at_limit,
    )
