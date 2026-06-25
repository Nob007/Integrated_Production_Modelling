"""
core/choke.py  —  Surface Choke Correlations
==============================================
Pure-function implementation of critical and subcritical choke correlations
for oil-well surface (wellhead) chokes.

Critical-flow correlations (Gilbert / Ros / Achong / Baxendell):
    All take the same form:  Pwh = C · (q^m · GLR^n) / d^p
    where d is bean size in 1/64 in, q is liquid rate STB/day, GLR scf/STB.

Sachdeva (1986): handles both critical and subcritical flow regimes with
    a single mechanistic model.

API RP 14E erosional velocity check:
    Ve = C_factor / sqrt(rho_mix_lbm_ft3)  [ft/s]

All functions are pure (no global state). Does NOT import or modify
ipr.py, pvt.py, vlp.py, or solver_other.py.

Units convention (field units):
    q       : STB/day  (total liquid)
    GLR     : scf/STB
    bean    : 1/64 in
    P       : psia
    T       : °F
    rho     : lbm/ft³
    velocity: ft/s
"""

import numpy as np
from typing import Tuple, Optional


# ─────────────────────────────────────────────────────────────────────────────
#  CORRELATION CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# Gilbert (1954):   Pwh = 435 · q^0.546 · GLR^0.546 / d^1.89
# Ros (1960):       Pwh = 17.40 · q^0.500 · GLR^0.657 / d^2.00  (in field units)
# Achong (1961):    Pwh = 3.82  · q^0.650 · GLR^0.342 / d^1.88
# Baxendell (1958): Pwh = 1.13  · q^0.546 · GLR^0.546 / d^2.00

CRITICAL_FLOW_CONSTANTS = {
    "gilbert":    {"C": 435.87, "m": 0.546, "n": 0.546, "p": 1.89},
    "ros":        {"C": 17.40,  "m": 0.500, "n": 0.657, "p": 2.00},
    "achong":     {"C": 3.82,   "m": 0.650, "n": 0.342, "p": 1.88},
    "baxendell":  {"C": 1.13,   "m": 0.546, "n": 0.546, "p": 2.00},
}

# Critical pressure ratio for each correlation
# (Pwh_down / Pwh_up below which flow is critical/choke-controlled)
CRITICAL_PRESSURE_RATIO = {
    "gilbert":    0.546,
    "ros":        0.546,
    "achong":     0.546,
    "baxendell":  0.546,
    "sachdeva":   None,   # Sachdeva computes its own critical ratio
}


# ─────────────────────────────────────────────────────────────────────────────
#  CRITICAL-FLOW CORRELATIONS  (Gilbert/Ros/Achong/Baxendell)
# ─────────────────────────────────────────────────────────────────────────────

def critical_flow_rate(pwh: float, glr: float, bean_64: float,
                       model: str = "gilbert") -> float:
    """
    Predict liquid rate (STB/day) for a given wellhead pressure using a
    critical-flow choke correlation.

    Args:
        pwh      : Wellhead (upstream choke) pressure, psia
        glr      : Gas-Liquid Ratio at wellhead, scf/STB
        bean_64  : Bean (choke) size in 1/64 inch (e.g., 32 = 32/64 = 1/2 inch)
        model    : One of 'gilbert', 'ros', 'achong', 'baxendell'

    Returns:
        Predicted liquid rate in STB/day, or 0 if inputs are non-physical.
    """
    model_lower = model.lower()
    if model_lower not in CRITICAL_FLOW_CONSTANTS:
        raise ValueError(f"Unknown critical-flow model: '{model}'. "
                         f"Choose from {list(CRITICAL_FLOW_CONSTANTS.keys())}.")

    k = CRITICAL_FLOW_CONSTANTS[model_lower]
    if pwh <= 0 or glr <= 0 or bean_64 <= 0:
        return 0.0

    # Solve for q from:  Pwh = C * q^m * GLR^n / d^p
    #   => q = (Pwh * d^p / (C * GLR^n)) ^ (1/m)
    q = ((pwh * bean_64 ** k["p"]) / (k["C"] * glr ** k["n"])) ** (1.0 / k["m"])
    return max(0.0, q)


def critical_flow_pwh(q: float, glr: float, bean_64: float,
                      model: str = "gilbert") -> float:
    """
    Predict wellhead pressure (psia) for a given rate using a critical-flow
    choke correlation.

    Args:
        q        : Liquid rate, STB/day
        glr      : Gas-Liquid Ratio at wellhead, scf/STB
        bean_64  : Bean size in 1/64 inch
        model    : One of 'gilbert', 'ros', 'achong', 'baxendell'

    Returns:
        Predicted wellhead pressure in psia, or 0 if inputs are non-physical.
    """
    model_lower = model.lower()
    if model_lower not in CRITICAL_FLOW_CONSTANTS:
        raise ValueError(f"Unknown critical-flow model: '{model}'.")

    k = CRITICAL_FLOW_CONSTANTS[model_lower]
    if q <= 0 or glr <= 0 or bean_64 <= 0:
        return 0.0

    pwh = k["C"] * (q ** k["m"]) * (glr ** k["n"]) / (bean_64 ** k["p"])
    return max(0.0, pwh)


def is_critical_flow(p_up: float, p_down: float,
                     model: str = "gilbert") -> bool:
    """
    Check whether the flow through a choke is critical (choke-controlled)
    based on the downstream/upstream pressure ratio.

    For Gilbert/Ros/Achong/Baxendell, critical flow occurs when:
        p_down / p_up  ≤  0.546  (approximately)

    For Sachdeva, the critical ratio is composition-dependent and must be
    checked via sachdeva_choke's returned `is_critical` flag.

    Args:
        p_up   : Upstream (wellhead) pressure, psia
        p_down : Downstream (flowline) pressure, psia
        model  : Correlation name (for models other than sachdeva the ratio 0.546 is used)

    Returns:
        True if flow is critical (choke-controlled), False if subcritical.
    """
    if p_up <= 0:
        return False
    ratio = p_down / p_up
    return ratio <= CRITICAL_PRESSURE_RATIO.get(model.lower(), 0.546)


# ─────────────────────────────────────────────────────────────────────────────
#  SACHDEVA (1986) — CRITICAL + SUBCRITICAL
# ─────────────────────────────────────────────────────────────────────────────

def sachdeva_choke(
    q_l: float,
    glr: float,
    bean_64: float,
    p_up: float,
    p_down: float,
    sg_gas: float = 0.65,
    sg_oil: float = 0.84,
    wc: float = 0.0,
    t_up: float = 100.0,
) -> dict:
    """
    Sachdeva (1986) mechanistic choke model — handles both critical and
    subcritical flow regimes.

    The model uses a slip-flow (homogeneous) mixture approach. Simplifications
    used here (field-units, standing-curve Z=1 gas):
        - Gas compressibility: ideal gas at wellhead conditions
        - Critical pressure ratio:  Rc = (2 / (k+1))^(k/(k-1)) ≈ 0.546 (k=1.27)
        - Discharge coefficient Cd = 0.85 (typical for orifice chokes)

    Args:
        q_l      : Liquid rate, STB/day
        glr      : Gas-liquid ratio at wellhead, scf/STB
        bean_64  : Bean size in 1/64 inch
        p_up     : Upstream pressure, psia
        p_down   : Downstream pressure, psia
        sg_gas   : Gas specific gravity (air=1)
        sg_oil   : Oil specific gravity (water=1)
        wc       : Watercut (fraction, 0–1)
        t_up     : Upstream (wellhead) temperature, °F

    Returns:
        dict with keys:
            pwh_pred    : Predicted upstream pressure for given rate (psia)
            q_pred      : Predicted rate for given upstream pressure (STB/day)
            is_critical : bool — True if critical flow
            p_crit      : Critical downstream pressure (psia)
            Cd          : Discharge coefficient used
    """
    Cd = 0.85
    k_gas = 1.27          # effective isentropic exponent for natural gas
    T_R = t_up + 459.67   # Rankine

    # Bean area in ft²
    bean_in = bean_64 / 64.0                      # inches
    A_bean = np.pi / 4.0 * (bean_in / 12.0) ** 2  # ft²

    # Mixture density at wellhead (lbm/ft³)
    rho_oil   = 62.4 * sg_oil * (1.0 - wc)
    rho_water = 62.4 * 1.07   * wc
    rho_gas   = 0.0764 * sg_gas  # at 14.7 psia, 60°F

    # Gas fraction by volume at wellhead (approx, Z=1)
    # In-situ gas rate / (in-situ gas + liquid)
    q_gas_insitu = glr * (14.7 / p_up) * (T_R / 520.0)  # scf→ res cf per STB liquid
    # Ignore volume difference here; treat as volumetric void fraction
    fvol_gas = q_gas_insitu / (q_gas_insitu + 5.615)  # reservoir bbl to ft³ factor

    rho_mix = rho_gas * fvol_gas + (rho_oil + rho_water) * (1.0 - fvol_gas)
    rho_mix = max(rho_mix, 1.0)

    # Critical pressure ratio
    Rc = (2.0 / (k_gas + 1.0)) ** (k_gas / (k_gas - 1.0))  # ≈ 0.546 for k=1.27
    p_crit = p_up * Rc

    flow_is_critical = p_down <= p_crit

    # Simplified homogeneous choke velocity model:
    #   v = Cd * sqrt(2 * gc * dP / rho_mix)  [ft/s]
    #   q_total = v * A_bean (ft³/s) → convert to STB/day

    gc = 32.174  # lbm·ft / (lbf·s²)

    if flow_is_critical:
        dp = p_up - p_crit
    else:
        dp = p_up - p_down

    dp_lbf_ft2 = dp * 144.0   # psi → lbf/ft²
    v = Cd * np.sqrt(max(2.0 * gc * dp_lbf_ft2 / rho_mix, 0.0))  # ft/s

    q_mix_ft3_s = v * A_bean                    # ft³/s total mixture
    q_liq_bbl_day = q_mix_ft3_s * (1.0 - fvol_gas) / 5.615 * 86400.0  # STB/day

    return {
        "q_pred": max(0.0, q_liq_bbl_day),
        "is_critical": flow_is_critical,
        "p_crit": p_crit,
        "Cd": Cd,
        "rho_mix": rho_mix,
        "fvol_gas": fvol_gas,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  EROSIONAL VELOCITY CHECK  (API RP 14E)
# ─────────────────────────────────────────────────────────────────────────────

def erosional_velocity_check(
    q_l: float,
    glr: float,
    bean_64: float,
    rho_liq_lbm_ft3: float,
    sg_gas: float = 0.65,
    p_up: float = 200.0,
    t_up: float = 100.0,
    c_factor: float = 100.0,
) -> dict:
    """
    API RP 14E erosional velocity check at the choke throat (bean).

    Erosional velocity:  Ve = c / sqrt(rho_mix)  [ft/s]
    where rho_mix is the no-slip mixture density at flowing conditions (lbm/ft³).

    Args:
        q_l             : Liquid rate, STB/day
        glr             : Gas-liquid ratio, scf/STB
        bean_64         : Bean size in 1/64 inch
        rho_liq_lbm_ft3: In-situ liquid density, lbm/ft³
        sg_gas          : Gas SG (air=1)
        p_up            : Upstream pressure, psia (for gas density)
        t_up            : Upstream temperature, °F
        c_factor        : API RP 14E constant: 100 (standard), 125 (limited corrosive)

    Returns:
        dict with keys:
            v_actual   : Actual mixture velocity through bean throat, ft/s
            v_erosional: API RP 14E erosional velocity limit, ft/s
            pass_check : True if v_actual < v_erosional
            ratio      : v_actual / v_erosional (< 1 = safe)
    """
    T_R = t_up + 459.67
    bean_in = bean_64 / 64.0                       # inches
    A_bean = np.pi / 4.0 * (bean_in / 12.0) ** 2  # ft²

    # Gas density at flowing conditions (ideal gas, Z≈1)
    rho_gas_flowing = (sg_gas * 28.97 * p_up) / (10.73 * T_R)  # lbm/ft³

    # In-situ gas volume fraction
    q_gas_insitu = glr * (14.7 / p_up) * (T_R / 520.0)  # res cf per STB
    fvol_gas = q_gas_insitu / (q_gas_insitu + 5.615) if (q_gas_insitu + 5.615) > 0 else 0.0

    # Mixture density (no-slip, lbm/ft³)
    rho_mix = rho_gas_flowing * fvol_gas + rho_liq_lbm_ft3 * (1.0 - fvol_gas)
    rho_mix = max(rho_mix, 0.1)

    # Total in-situ volumetric rate through the bean (ft³/s)
    # Liquid: q_l STB/day → ft³/s
    q_liq_ft3_s = q_l * 5.615 / 86400.0
    # Gas: q_l * glr scf/day → in-situ ft³/s
    q_gas_ft3_s = q_l * glr * (14.7 / p_up) * (T_R / 520.0) / 86400.0
    q_total_ft3_s = q_liq_ft3_s + q_gas_ft3_s

    v_actual = q_total_ft3_s / A_bean if A_bean > 0 else 0.0
    v_erosional = c_factor / np.sqrt(rho_mix)

    return {
        "v_actual": v_actual,
        "v_erosional": v_erosional,
        "pass_check": v_actual <= v_erosional,
        "ratio": v_actual / v_erosional if v_erosional > 0 else float("inf"),
        "rho_mix": rho_mix,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  JOULE-THOMSON COOLING ESTIMATE  (hydrate risk flag)
# ─────────────────────────────────────────────────────────────────────────────

def joule_thomson_estimate(
    p_up: float,
    p_down: float,
    t_up: float,
    jt_coeff_f_psi: float = 0.006,
) -> dict:
    """
    Estimate temperature drop across the choke using the Joule-Thomson
    coefficient for natural gas (approximate).

    ΔT ≈ JT_coeff × ΔP   (°F)

    A hydrate formation temperature of ~55°F is used as a conservative
    threshold (actual value depends on gas composition / water presence).

    Args:
        p_up              : Upstream pressure, psia
        p_down            : Downstream pressure, psia
        t_up              : Upstream temperature, °F
        jt_coeff_f_psi    : Joule-Thomson coefficient, °F/psi (default 0.006)

    Returns:
        dict with keys:
            delta_T      : Estimated temperature drop, °F (positive = cooling)
            t_down       : Estimated downstream temperature, °F
            hydrate_risk : True if t_down < 55°F (conservative threshold)
    """
    delta_P = max(0.0, p_up - p_down)
    delta_T = jt_coeff_f_psi * delta_P
    t_down = t_up - delta_T
    return {
        "delta_T": delta_T,
        "t_down": t_down,
        "hydrate_risk": t_down < 55.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  CHOKE PERFORMANCE CURVE SWEEP
# ─────────────────────────────────────────────────────────────────────────────

def choke_performance_curve(
    bean_sizes_64: list,
    glr: float,
    p_up: float,
    p_down: float,
    model: str = "gilbert",
    sg_gas: float = 0.65,
    sg_oil: float = 0.84,
    wc: float = 0.0,
    t_up: float = 100.0,
    c_factor: float = 100.0,
    rho_liq_lbm_ft3: float = 52.0,
) -> list:
    """
    Compute a choke performance curve over a list of candidate bean sizes.

    For each bean size, computes:
        - Predicted liquid rate (STB/day) at the given upstream pressure
        - Flow regime (critical vs. subcritical)
        - Erosional velocity check

    Args:
        bean_sizes_64    : List of bean sizes in 1/64 inch (e.g., [16,24,32,40,48,64])
        glr              : Gas-Liquid Ratio at wellhead, scf/STB
        p_up             : Upstream (wellhead) pressure, psia
        p_down           : Downstream (flowline/separator) pressure, psia
        model            : Choke correlation (gilbert / ros / achong / baxendell / sachdeva)
        sg_gas           : Gas specific gravity
        sg_oil           : Oil specific gravity
        wc               : Watercut fraction
        t_up             : Upstream temperature, °F
        c_factor         : API RP 14E erosional constant
        rho_liq_lbm_ft3  : In-situ liquid density, lbm/ft³ (from PVT at wellhead)

    Returns:
        List of dicts, one per bean size:
            bean_64      : Bean size (1/64 in)
            q_pred       : Predicted liquid rate (STB/day)
            is_critical  : Flow regime flag
            erosional    : Erosional check dict (v_actual, v_erosional, pass_check, ratio)
            p_up_pred    : Upstream pressure predicted for this rate (psia) [from correlation]
    """
    results = []
    model_lower = model.lower()

    for bean in bean_sizes_64:
        if model_lower == "sachdeva":
            sach = sachdeva_choke(
                q_l=0.0,    # q is output here, so we pass 0
                glr=glr, bean_64=bean,
                p_up=p_up, p_down=p_down,
                sg_gas=sg_gas, sg_oil=sg_oil,
                wc=wc, t_up=t_up,
            )
            q_pred = sach["q_pred"]
            flow_crit = sach["is_critical"]
        else:
            q_pred = critical_flow_rate(p_up, glr, bean, model_lower)
            flow_crit = is_critical_flow(p_up, p_down, model_lower)

        # Compute back-predicted wellhead pressure (what Pwh would the correlation give?)
        if model_lower != "sachdeva" and q_pred > 0:
            p_up_pred = critical_flow_pwh(q_pred, glr, bean, model_lower)
        else:
            p_up_pred = p_up

        # Erosional check
        eros = erosional_velocity_check(
            q_l=q_pred, glr=glr, bean_64=bean,
            rho_liq_lbm_ft3=rho_liq_lbm_ft3,
            sg_gas=sg_gas, p_up=p_up, t_up=t_up,
            c_factor=c_factor,
        )

        results.append({
            "bean_64": bean,
            "q_pred": round(q_pred, 2),
            "is_critical": flow_crit,
            "erosional": eros,
            "p_up_pred": round(p_up_pred, 2),
        })

    return results


def recommend_bean_size(
    performance_results: list,
    target_q: float,
) -> Optional[dict]:
    """
    From a list of choke performance results (from `choke_performance_curve`),
    recommend the smallest bean size that:
    1. Delivers at least `target_q` STB/day
    2. Passes the erosional velocity check

    Args:
        performance_results: Output of `choke_performance_curve`
        target_q           : Target plateau rate, STB/day

    Returns:
        The recommended entry dict, or None if no candidate meets both criteria.
    """
    candidates = [
        r for r in performance_results
        if r["q_pred"] >= target_q and r["erosional"]["pass_check"]
    ]
    if not candidates:
        # Relax: best available (max q) even if erosional fails
        by_rate = sorted(performance_results, key=lambda x: x["q_pred"])
        return by_rate[-1] if by_rate else None
    # Smallest passing bean
    return sorted(candidates, key=lambda x: x["bean_64"])[0]
