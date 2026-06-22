import numpy as np
from scipy.optimize import root_scalar
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class StabilityType(Enum):
    """
    Classifies an operating point by flow stability.

    Physical interpretation
    -----------------------
    STABLE   — A small perturbation (e.g. a rate kick) is self-correcting.
               At this point d(Pwf_VLP)/dq > d(Pwf_IPR)/dq:
               if q rises slightly, VLP demands more pressure than the
               reservoir can supply → q falls back to equilibrium.

    UNSTABLE — The opposite: d(Pwf_VLP)/dq < d(Pwf_IPR)/dq.
               A small positive rate perturbation is self-amplifying →
               the well accelerates to the stable point (or to AOF if
               there is no stable point).  Wells sitting at an unstable
               operating point may surge, load up, or die.

    INDETERMINATE — Slopes are equal within numerical tolerance; stability
               cannot be resolved from a first-order analysis alone.
    """
    STABLE        = "Stable"
    UNSTABLE      = "Unstable"
    INDETERMINATE = "Indeterminate"


@dataclass
class OperatingPoint:
    """
    A single IPR × VLP intersection point with full diagnostic metadata.

    Attributes
    ----------
    rate : float
        Intersection flow rate, q* [STB/day].
    pwf : float
        Flowing bottomhole pressure at intersection [psia].
    stability : StabilityType
        Whether the point is stable, unstable, or indeterminate.
    drawdown : float
        Reservoir pressure minus Pwf  [psia].
    drawdown_pct : float
        Drawdown as a percentage of reservoir pressure [%].
    productivity_index : float
        J = q / drawdown  [STB/day/psi].  NaN when drawdown ≤ 0.
    ipr_slope : float
        Local dPwf_IPR/dq at the intersection  [psi / (STB/day)].
    vlp_slope : float
        Local dPwf_VLP/dq at the intersection  [psi / (STB/day)].
    message : str
        Human-readable summary of the result.
    """
    rate              : float
    pwf               : float
    stability         : StabilityType
    drawdown          : float
    drawdown_pct      : float
    productivity_index: float
    ipr_slope         : float
    vlp_slope         : float
    message           : str = ""

    def __str__(self) -> str:
        lines = [
            f"  ─── {self.stability.value} Operating Point ───",
            f"  Rate (q*)      : {self.rate:>10.2f}  STB/day",
            f"  Pwf*           : {self.pwf:>10.2f}  psia",
            f"  Drawdown       : {self.drawdown:>10.2f}  psia  ({self.drawdown_pct:.1f}%)",
            f"  PI (J)         : {self.productivity_index:>10.3f}  STB/day/psi",
            f"  IPR slope      : {self.ipr_slope:>10.4f}  psi/(STB/day)",
            f"  VLP slope      : {self.vlp_slope:>10.4f}  psi/(STB/day)",
        ]
        if self.message:
            lines.append(f"  Note           : {self.message}")
        return "\n".join(lines)


@dataclass
class NodalResult:
    """
    Full result container returned by find_operating_points().

    Attributes
    ----------
    success : bool
        True if at least one valid operating point was found.
    stable_point : Optional[OperatingPoint]
        The stable operating point, or None.
    unstable_point : Optional[OperatingPoint]
        The unstable operating point, or None.
    all_points : list[OperatingPoint]
        All intersections found, ordered by rate ascending.
    failure_reason : str
        Non-empty only when success=False; explains why no point was found.
    scan_rates : np.ndarray
        The rate array used for root bracketing.
    scan_objective : np.ndarray
        f(q) = Pwf_VLP(q) − Pwf_IPR(q) evaluated at every scan point.
        Useful for plotting the residual curve.
    """
    success          : bool
    stable_point     : Optional[OperatingPoint]   = None
    unstable_point   : Optional[OperatingPoint]   = None
    all_points       : list = field(default_factory=list)
    failure_reason   : str  = ""
    scan_rates       : Optional[np.ndarray] = None
    scan_objective   : Optional[np.ndarray] = None

    def __str__(self) -> str:
        if not self.success:
            return f"No operating point found.\nReason: {self.failure_reason}"
        lines = [f"Nodal Analysis — {len(self.all_points)} intersection(s) found\n"]
        for pt in self.all_points:
            lines.append(str(pt))
            lines.append("")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_vlp_evaluator(vlp_model, vlp_params: dict):
    """
    Returns a scalar callable  vlp(q) -> Pwf_VLP.

    Wraps calculate_pressure_traverse so the rest of the code only
    sees a simple f(q) interface.
    """
    def _vlp(q: float) -> float:
        _, pressures, _ = vlp_model.calculate_pressure_traverse(
            Pth             = vlp_params["Pth"],
            surface_temp    = vlp_params["surface_temp"],
            bottomhole_temp = vlp_params["bottomhole_temp"],
            total_depth     = vlp_params["depth"],
            step_size       = vlp_params["step_size"],
            Ql              = q,
        )
        return float(pressures[-1])
    return _vlp


def _build_ipr_evaluator(ipr_model):
    """Returns a scalar callable  ipr(q) -> Pwf_IPR."""
    def _ipr(q: float) -> float:
        return float(ipr_model.calculate_Pwf(q))
    return _ipr


def _local_slope(fn, x: float, h_frac: float = 0.005) -> float:
    """
    Central-difference derivative of fn at x.
    h_frac is the fractional step size relative to x (avoids tiny h for
    large x and zero-division for x ≈ 0).
    """
    h = max(abs(x) * h_frac, 0.1)   # at least 0.1 STB/day
    return (fn(x + h) - fn(x - h)) / (2.0 * h)


def _classify_stability(
    ipr_fn, vlp_fn,
    q_star: float,
    tol: float = 1e-3
) -> tuple[StabilityType, float, float]:
    """
    Returns (stability, ipr_slope, vlp_slope).

    Stability criterion (first-order):
        d(Pwf_VLP)/dq  >  d(Pwf_IPR)/dq  →  STABLE
        d(Pwf_VLP)/dq  <  d(Pwf_IPR)/dq  →  UNSTABLE
        |difference| ≤ tol                →  INDETERMINATE
    """
    s_ipr = _local_slope(ipr_fn, q_star)
    s_vlp = _local_slope(vlp_fn, q_star)
    diff  = s_vlp - s_ipr

    if abs(diff) <= tol:
        stability = StabilityType.INDETERMINATE
    elif diff > 0:
        stability = StabilityType.STABLE
    else:
        stability = StabilityType.UNSTABLE

    return stability, s_ipr, s_vlp


def _build_operating_point(
    q_star: float,
    ipr_fn,
    vlp_fn,
    pr: float,
) -> OperatingPoint:
    """Assembles a fully-annotated OperatingPoint from a converged root."""
    pwf       = ipr_fn(q_star)
    drawdown  = pr - pwf
    dd_pct    = 100.0 * drawdown / pr if pr > 0 else float("nan")
    pi        = q_star / drawdown if drawdown > 1e-6 else float("nan")
    stability, s_ipr, s_vlp = _classify_stability(ipr_fn, vlp_fn, q_star)

    msg = ""
    if stability == StabilityType.UNSTABLE:
        msg = (
            "Well is at an unstable equilibrium. A small rate perturbation "
            "will cause it to migrate toward the stable point or die."
        )
    elif stability == StabilityType.INDETERMINATE:
        msg = "Slopes are nearly equal; stability assessment is inconclusive."

    return OperatingPoint(
        rate               = q_star,
        pwf                = pwf,
        stability          = stability,
        drawdown           = drawdown,
        drawdown_pct       = dd_pct,
        productivity_index = pi,
        ipr_slope          = s_ipr,
        vlp_slope          = s_vlp,
        message            = msg,
    )


def _scan_objective(ipr_fn, vlp_fn, rates: np.ndarray) -> np.ndarray:
    """Vectorised evaluation of f(q) = Pwf_VLP(q) − Pwf_IPR(q)."""
    return np.array([vlp_fn(q) - ipr_fn(q) for q in rates])


def _find_sign_change_brackets(
    rates: np.ndarray,
    fvals: np.ndarray
) -> list[tuple[float, float]]:
    """
    Returns a list of (q_lo, q_hi) brackets where f changes sign.
    Each bracket contains exactly one root (assuming f is smooth).
    """
    brackets = []
    signs    = np.sign(fvals)
    for i in range(len(signs) - 1):
        if signs[i] != 0 and signs[i + 1] != 0 and signs[i] != signs[i + 1]:
            brackets.append((float(rates[i]), float(rates[i + 1])))
    return brackets


# ─────────────────────────────────────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def find_operating_points(
    ipr_model,
    vlp_model,
    vlp_params:   dict,
    pr:           float,
    q_min:        float = 50.0,
    q_max:        Optional[float] = None,
    n_scan:       int   = 120,
    xtol:         float = 1e-2,
) -> NodalResult:
    """
    Finds ALL IPR × VLP intersection points and classifies each as
    stable or unstable.

    Parameters
    ----------
    ipr_model : composite_ipr (or any IPR with .calculate_Pwf(q) and .q_max)
        Reservoir inflow model.
    vlp_model : HagedornBrown (or any VLP with .calculate_pressure_traverse(...))
        Wellbore lift model.
    vlp_params : dict
        Keys: 'Pth', 'surface_temp', 'bottomhole_temp', 'depth', 'step_size'.
    pr : float
        Static reservoir pressure [psia].  Required for drawdown diagnostics.
    q_min : float
        Lower bound for the rate search [STB/day].  Default 50.
    q_max : float, optional
        Upper bound for the rate search [STB/day].
        Defaults to ipr_model.q_max (absolute open flow).
    n_scan : int
        Number of evenly-spaced points used to scan for sign changes.
        Increase for highly non-monotonic VLP curves (e.g. severe slugging).
        Default 120.
    xtol : float
        Rate convergence tolerance for the Brent solver [STB/day].  Default 0.01.

    Returns
    -------
    NodalResult
        See NodalResult docstring for full field descriptions.
    """
    # ── 1. Resolve upper bound ────────────────────────────────────────────────
    if q_max is None:
        q_max = float(ipr_model.q_max)

    if q_min >= q_max:
        return NodalResult(
            success=False,
            failure_reason=(
                f"q_min ({q_min:.1f}) must be less than q_max ({q_max:.1f})."
            ),
        )

    # ── 2. Build lightweight function wrappers ────────────────────────────────
    ipr_fn = _build_ipr_evaluator(ipr_model)
    vlp_fn = _build_vlp_evaluator(vlp_model, vlp_params)

    # ── 3. Coarse scan to locate sign-change brackets ─────────────────────────
    #   Use a log-spaced scan so we don't miss narrow brackets at low rates
    #   (where the VLP minimum often lives).
    rates_scan = np.unique(np.concatenate([
        np.linspace(q_min, q_max, n_scan),
        np.geomspace(max(q_min, 1.0), q_max, n_scan // 2),
    ]))
    rates_scan = np.sort(rates_scan)

    try:
        fvals_scan = _scan_objective(ipr_fn, vlp_fn, rates_scan)
    except Exception as exc:
        return NodalResult(
            success=False,
            failure_reason=f"Objective function evaluation failed during scan: {exc}",
            scan_rates=rates_scan,
        )

    brackets = _find_sign_change_brackets(rates_scan, fvals_scan)

    if not brackets:
        # No sign changes found — diagnose the physical situation
        median_f = float(np.median(fvals_scan))
        if median_f > 0:
            reason = (
                "VLP pressure requirement exceeds IPR capability across the "
                "entire rate range.  The well cannot flow under current conditions "
                "(consider reducing THP, increasing tubing ID, or reducing GOR)."
            )
        else:
            reason = (
                "IPR capability exceeds VLP requirement everywhere in the range.  "
                f"The operating point is above q_max = {q_max:.1f} STB/day "
                "(consider increasing q_max or the well is limited by surface equipment)."
            )
        return NodalResult(
            success=False,
            failure_reason=reason,
            scan_rates=rates_scan,
            scan_objective=fvals_scan,
        )

    # ── 4. Refine each bracket with Brent's method ────────────────────────────
    raw_roots: list[float] = []
    for q_lo, q_hi in brackets:
        try:
            sol = root_scalar(
                lambda q: vlp_fn(q) - ipr_fn(q),
                bracket=[q_lo, q_hi],
                method="brentq",
                xtol=xtol,
            )
            if sol.converged:
                raw_roots.append(float(sol.root))
        except Exception:
            # If refinement fails for one bracket, skip it and keep going
            continue

    if not raw_roots:
        return NodalResult(
            success=False,
            failure_reason=(
                "Sign-change brackets were found but all Brent refinements "
                "failed to converge.  This may indicate a near-tangency; "
                "try increasing n_scan or widening the rate range."
            ),
            scan_rates=rates_scan,
            scan_objective=fvals_scan,
        )

    # ── 5. Deduplicate roots that are closer than xtol * 10 ──────────────────
    raw_roots.sort()
    unique_roots: list[float] = [raw_roots[0]]
    for r in raw_roots[1:]:
        if r - unique_roots[-1] > xtol * 10:
            unique_roots.append(r)

    # ── 6. Build OperatingPoint objects with full diagnostics ─────────────────
    all_points: list[OperatingPoint] = [
        _build_operating_point(q, ipr_fn, vlp_fn, pr)
        for q in unique_roots
    ]

    # ── 7. Separate stable from unstable ─────────────────────────────────────
    stable_pts   = [p for p in all_points if p.stability == StabilityType.STABLE]
    unstable_pts = [p for p in all_points if p.stability == StabilityType.UNSTABLE]
    indet_pts    = [p for p in all_points if p.stability == StabilityType.INDETERMINATE]

    # When the VLP has no minimum in range (purely monotonic, common in gas wells),
    # there is exactly one intersection.  It may appear "unstable" by the slope
    # test alone — re-classify it as stable in that specific case.
    if len(all_points) == 1 and all_points[0].stability == StabilityType.UNSTABLE:
        pt = all_points[0]
        all_points[0] = OperatingPoint(
            rate=pt.rate, pwf=pt.pwf,
            stability=StabilityType.STABLE,
            drawdown=pt.drawdown, drawdown_pct=pt.drawdown_pct,
            productivity_index=pt.productivity_index,
            ipr_slope=pt.ipr_slope, vlp_slope=pt.vlp_slope,
            message=(
                "Single intersection: classified as stable "
                "(VLP has no minimum in the scanned range)."
            ),
        )
        stable_pts   = all_points[:]
        unstable_pts = []

    # Choose the "primary" stable point (highest rate when multiple stable exist)
    stable_point   = stable_pts[-1]   if stable_pts   else None
    unstable_point = unstable_pts[0]  if unstable_pts else None

    # Fall back gracefully when only indeterminate points exist
    if stable_point is None and indet_pts:
        stable_point = indet_pts[-1]

    return NodalResult(
        success        = True,
        stable_point   = stable_point,
        unstable_point = unstable_point,
        all_points     = all_points,
        scan_rates     = rates_scan,
        scan_objective = fvals_scan,
    )