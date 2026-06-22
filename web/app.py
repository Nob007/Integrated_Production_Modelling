"""
IPM App — Flask Backend API
Wraps core/ipr.py, core/pvt.py, core/vlp.py, core/solver_other.py
Engine modules are imported unchanged; no logic modifications.
"""
import sys
import os
import json
import io
import csv
import traceback
import numpy as np

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS

from core import ipr as ipr_mod
from core import pvt as pvt_mod
from core import vlp as vlp_mod
from core import solver_other as solver_mod

# ── App init ──────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# ─────────────────────────────────────────────────────────────────────────────
#  HELPER UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _err(msg: str, status: int = 400):
    return jsonify({"success": False, "error": msg}), status


def _build_pvt(d: dict) -> pvt_mod.BlackOilPVT:
    """Construct a BlackOilPVT instance from request dict."""
    sg_gas   = float(d.get("sg_gas", 0.65))
    sg_oil   = float(d.get("sg_oil", 0.84))
    oil_api  = d.get("oil_api")
    oil_api  = float(oil_api) if oil_api not in (None, "", "null") else None
    sg_water = float(d.get("sg_water", 1.03))
    wc       = float(d.get("wc", 0.0))
    return pvt_mod.BlackOilPVT(sg_gas=sg_gas, sg_oil=sg_oil, oil_api=oil_api,
                                sg_water=sg_water, watercut=wc)


def _build_ipr(d: dict):
    """Construct the correct IPR model from request dict."""
    model    = d.get("ipr_model", "composite")
    Pr       = float(d["Pr"])
    Pb       = float(d.get("Pb", Pr * 0.8))
    q_test   = float(d["Qo_test"])
    pwf_test = float(d["Pwf_test"])

    if model == "vogel":
        return ipr_mod.vogel_ipr(Pr, Pb, q_test, pwf_test)
    elif model == "darcy":
        return ipr_mod.darcy_ipr(Pr, Pb, q_test, pwf_test)
    else:
        return ipr_mod.composite_ipr(Pr, Pb, q_test, pwf_test)


def _build_vlp(d: dict, pvt_model: pvt_mod.BlackOilPVT, fp: dict):
    """Construct the correct VLP model from request dict."""
    model      = d.get("vlp_model", "hagedorn_brown")
    tubing_id  = float(d["tubing_id"])
    tubing_od  = float(d.get("tubing_od", tubing_id * 1.2))
    casing_id  = float(d.get("casing_id", tubing_id * 2))
    roughness  = float(d.get("roughness", 0.00015))
    wc         = float(d.get("wc", 0.0))
    theta      = float(d.get("theta", 0.0))

    if model == "beggs_brill":
        return vlp_mod.Beggs_Brill(tubing_id, tubing_od, casing_id,
                                    roughness, pvt_model, fp,
                                    watercut=wc, theta=theta)
    else:
        return vlp_mod.HagedornBrown(tubing_id, tubing_od, casing_id,
                                      roughness, pvt_model, fp,
                                      watercut=wc, theta=theta)


def _vlp_params(d: dict) -> dict:
    return {
        "Pth":            float(d["thp"]),
        "surface_temp":   float(d["T_surface"]),
        "bottomhole_temp": float(d["T_bh"]),
        "depth":          float(d["depth"]),
        "step_size":      float(d.get("dz_step", 50)),
    }


def _build_fp(pvt: pvt_mod.BlackOilPVT, d: dict) -> dict:
    """Build an initial fluid_properties_dict at reservoir conditions."""
    Pr  = float(d.get("Pr", 3000))
    T   = float(d.get("T_bh", 180))
    gor = float(d.get("gor", 500))
    Pb  = float(d.get("Pb", 0))
    Rsb = pvt.calc_true_rsb(Pb if Pb > 0 else pvt.calc_bubble_point(T, gor), T)
    return pvt.fluid_properties_dict(Pr, T, Rsb, gor, Pb)


def _safe_float(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return float(v)


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTES — Main App
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTES — IPR
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/ipr/curve", methods=["POST"])
def ipr_curve():
    d = request.get_json(force=True)
    try:
        model = _build_ipr(d)
        n = int(d.get("points", 80))
        q_arr   = np.linspace(0, model.q_max, n).tolist()
        pwf_arr = [float(model.calculate_Pwf(q)) for q in q_arr]
        result = {
            "success": True,
            "q":   q_arr,
            "pwf": pwf_arr,
            "J":   _safe_float(model.J),
            "q_max": _safe_float(model.q_max),
            "q_bp": _safe_float(getattr(model, "q_bp", None)),
            "Pb":   _safe_float(d.get("Pb")),
            "q_test": float(d["Qo_test"]),
            "pwf_test": float(d["Pwf_test"]),
        }
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTES — PVT
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/pvt/properties", methods=["POST"])
def pvt_properties():
    d = request.get_json(force=True)
    try:
        pvt  = _build_pvt(d)
        P    = float(d.get("P", d.get("Pr", 3000)))
        T    = float(d.get("T", d.get("T_bh", 180)))
        gor  = float(d.get("gor", 500))
        Pb   = float(d.get("Pb", 0))
        Rsb  = pvt.calc_true_rsb(Pb if Pb > 0 else pvt.calc_bubble_point(T, gor), T)
        fp   = pvt.fluid_properties_dict(P, T, Rsb, gor, Pb)
        # Clean NaN/inf for JSON
        clean = {k: (_safe_float(v) if isinstance(v, (float, int, np.floating)) else v)
                 for k, v in fp.items()}
        clean["success"]  = True
        clean["api"]      = _safe_float(pvt.api)
        clean["phase"]    = "Undersaturated" if P >= fp["Pb"] else "Two-Phase"
        clean["Pb_calc"]  = _safe_float(fp["Pb"])
        return jsonify(clean)
    except Exception as e:
        traceback.print_exc()
        return _err(str(e))


@app.route("/api/pvt/curve", methods=["POST"])
def pvt_curve():
    d = request.get_json(force=True)
    try:
        pvt    = _build_pvt(d)
        P_min  = float(d.get("P_min", 14.7))
        P_max  = float(d.get("P_max", d.get("Pr", 5000)))
        T      = float(d.get("T", d.get("T_bh", 180)))
        gor    = float(d.get("gor", 500))
        Pb     = float(d.get("Pb", 0))
        n      = int(d.get("points", 60))

        Pb_val = Pb if Pb > 0 else pvt.calc_bubble_point(T, gor)
        Rsb    = pvt.calc_true_rsb(Pb_val, T)

        pressures = np.linspace(P_min, P_max, n).tolist()
        rows = {"P": pressures, "Rs": [], "Bo": [], "Bg": [], "Bw": [], "Z": [],
                "mu_o": [], "mu_g": [], "mu_w": [], "rho_o_ins": [], "rho_g": [],
                "sigma_o": [], "sigma_w": []}

        for P in pressures:
            Rs  = pvt.calc_rs(P, T, Pb_val, Rsb)
            Z   = pvt.calculate_dak_z_factor(P, T, pvt.sg_g)
            Bo  = pvt.calc_bo(P, T, Rs, Pb_val)
            Bg  = pvt.calc_bg(P, T, Z)
            Bw  = pvt.calc_bw(P, T)
            rho_o = pvt.calc_density_oil(Rs, Bo)
            rho_g = pvt.calc_density_gas(P, T, Z)
            mu_o  = pvt.calc_viscosity_oil(P, T, Rs, Pb_val)
            mu_g  = pvt.calc_viscosity_gas(P, T, Z)
            mu_w  = pvt.calc_viscosity_water(T)
            sig_o = pvt.calc_surface_tension_oil(P, T)
            sig_w = pvt.calc_surface_tension_water(T)

            rows["Rs"].append(_safe_float(Rs))
            rows["Bo"].append(_safe_float(Bo))
            rows["Bg"].append(_safe_float(Bg))
            rows["Bw"].append(_safe_float(Bw))
            rows["Z"].append(_safe_float(Z))
            rows["mu_o"].append(_safe_float(mu_o))
            rows["mu_g"].append(_safe_float(mu_g))
            rows["mu_w"].append(_safe_float(mu_w))
            rows["rho_o_ins"].append(_safe_float(rho_o))
            rows["rho_g"].append(_safe_float(rho_g))
            rows["sigma_o"].append(_safe_float(sig_o))
            rows["sigma_w"].append(_safe_float(sig_w))

        rows["success"] = True
        rows["Pb"] = _safe_float(Pb_val)
        rows["api"] = _safe_float(pvt.api)
        return jsonify(rows)
    except Exception as e:
        traceback.print_exc()
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTES — VLP
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/vlp/curve", methods=["POST"])
def vlp_curve():
    d = request.get_json(force=True)
    try:
        pvt_model = _build_pvt(d)
        fp        = _build_fp(pvt_model, d)
        vlp_model = _build_vlp(d, pvt_model, fp)
        params    = _vlp_params(d)

        q_min  = float(d.get("q_min", 50))
        q_max  = float(d.get("q_max", 3000))
        q_step = float(d.get("q_step", 100))
        rates  = np.arange(q_min, q_max + q_step, q_step).tolist()
        pwfs   = []

        for q in rates:
            try:
                _, pressures, _ = vlp_model.calculate_pressure_traverse(
                    Pth=params["Pth"],
                    surface_temp=params["surface_temp"],
                    bottomhole_temp=params["bottomhole_temp"],
                    total_depth=params["depth"],
                    step_size=params["step_size"],
                    Ql=q,
                )
                pwfs.append(_safe_float(pressures[-1]))
            except Exception:
                pwfs.append(None)

        return jsonify({"success": True, "q": rates, "pwf": pwfs})
    except Exception as e:
        traceback.print_exc()
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTES — Nodal
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/nodal/solve", methods=["POST"])
def nodal_solve():
    d = request.get_json(force=True)
    try:
        ipr_model = _build_ipr(d)
        pvt_model = _build_pvt(d)
        fp        = _build_fp(pvt_model, d)
        vlp_model = _build_vlp(d, pvt_model, fp)
        params    = _vlp_params(d)
        Pr        = float(d["Pr"])

        result = solver_mod.find_operating_points(
            ipr_model=ipr_model,
            vlp_model=vlp_model,
            vlp_params=params,
            pr=Pr,
            q_min=float(d.get("q_min", 50)),
        )

        def _pt(p):
            if p is None:
                return None
            return {
                "rate":               _safe_float(p.rate),
                "pwf":                _safe_float(p.pwf),
                "stability":          p.stability.value,
                "drawdown":           _safe_float(p.drawdown),
                "drawdown_pct":       _safe_float(p.drawdown_pct),
                "productivity_index": _safe_float(p.productivity_index),
                "ipr_slope":          _safe_float(p.ipr_slope),
                "vlp_slope":          _safe_float(p.vlp_slope),
                "message":            p.message,
            }

        return jsonify({
            "success":        result.success,
            "failure_reason": result.failure_reason,
            "stable_point":   _pt(result.stable_point),
            "unstable_point": _pt(result.unstable_point),
            "all_points":     [_pt(p) for p in result.all_points],
        })
    except Exception as e:
        traceback.print_exc()
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTES — Traverse
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/traverse", methods=["POST"])
def traverse():
    d = request.get_json(force=True)
    try:
        pvt_model = _build_pvt(d)
        fp        = _build_fp(pvt_model, d)
        vlp_model = _build_vlp(d, pvt_model, fp)
        params    = _vlp_params(d)
        Ql        = float(d["Ql"])

        depths, pressures, profiles = vlp_model.calculate_pressure_traverse(
            Pth=params["Pth"],
            surface_temp=params["surface_temp"],
            bottomhole_temp=params["bottomhole_temp"],
            total_depth=params["depth"],
            step_size=params["step_size"],
            Ql=Ql,
        )

        rows = []
        for i, (dep, pres) in enumerate(zip(depths, pressures)):
            rows.append({
                "depth":            _safe_float(dep),
                "pressure":         _safe_float(pres),
                "holdup":           _safe_float(profiles["holdup"][i]),
                "friction_factor":  _safe_float(profiles["friction_factor"][i]),
                "hydrostatic_loss": _safe_float(profiles["hydrostatic_loss"][i]),
                "frictional_loss":  _safe_float(profiles["frictional_loss"][i]),
                "total_gradient":   _safe_float(profiles["total_gradient"][i]),
            })

        return jsonify({"success": True, "rows": rows,
                        "depths": depths, "pressures": [_safe_float(p) for p in pressures]})
    except Exception as e:
        traceback.print_exc()
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTES — Sensitivity
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/sensitivity/run", methods=["POST"])
def sensitivity_run():
    d = request.get_json(force=True)
    slots = d.get("slots", [])  # list of {param, min, max, steps}
    base  = d.get("base", {})

    results = []
    try:
        for slot in slots:
            if not slot.get("active"):
                continue
            param  = slot["param"]
            p_min  = float(slot["min"])
            p_max  = float(slot["max"])
            steps  = int(slot.get("steps", 5))
            values = np.linspace(p_min, p_max, steps).tolist()

            family = {"param": param, "values": [], "ipr_curves": [], "vlp_curves": [], "op_points": []}

            for val in values:
                snap = dict(base)
                snap[param] = val
                family["values"].append(val)

                # IPR curve
                try:
                    im = _build_ipr(snap)
                    n  = 60
                    q_arr   = np.linspace(0, im.q_max, n).tolist()
                    pwf_arr = [float(im.calculate_Pwf(q)) for q in q_arr]
                    family["ipr_curves"].append({"q": q_arr, "pwf": pwf_arr})
                except Exception:
                    family["ipr_curves"].append(None)

                # VLP curve
                try:
                    pv = _build_pvt(snap)
                    fp = _build_fp(pv, snap)
                    vm = _build_vlp(snap, pv, fp)
                    pm = _vlp_params(snap)
                    q_min  = float(snap.get("q_min", 50))
                    q_max_ = float(snap.get("q_max", 3000))
                    q_step = float(snap.get("q_step", 150))
                    rates  = np.arange(q_min, q_max_ + q_step, q_step).tolist()
                    pwfs   = []
                    for q in rates:
                        try:
                            _, pressures, _ = vm.calculate_pressure_traverse(
                                Pth=pm["Pth"], surface_temp=pm["surface_temp"],
                                bottomhole_temp=pm["bottomhole_temp"],
                                total_depth=pm["depth"], step_size=pm["step_size"], Ql=q)
                            pwfs.append(_safe_float(pressures[-1]))
                        except Exception:
                            pwfs.append(None)
                    family["vlp_curves"].append({"q": rates, "pwf": pwfs})
                except Exception:
                    family["vlp_curves"].append(None)

                # Operating point
                try:
                    im2 = _build_ipr(snap)
                    pv2 = _build_pvt(snap)
                    fp2 = _build_fp(pv2, snap)
                    vm2 = _build_vlp(snap, pv2, fp2)
                    pm2 = _vlp_params(snap)
                    nr  = solver_mod.find_operating_points(im2, vm2, pm2, float(snap["Pr"]),
                                                           q_min=float(snap.get("q_min", 50)))
                    if nr.success and nr.stable_point:
                        p = nr.stable_point
                        family["op_points"].append({"rate": _safe_float(p.rate),
                                                     "pwf":  _safe_float(p.pwf),
                                                     "stability": p.stability.value})
                    else:
                        family["op_points"].append(None)
                except Exception:
                    family["op_points"].append(None)

            results.append(family)

        return jsonify({"success": True, "families": results})
    except Exception as e:
        traceback.print_exc()
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTES — Export CSV
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/export/csv", methods=["POST"])
def export_csv():
    d = request.get_json(force=True)
    output = io.StringIO()
    w = csv.writer(output)

    try:
        Pr       = float(d["Pr"])
        ipr_model = _build_ipr(d)
        pvt_model = _build_pvt(d)
        fp        = _build_fp(pvt_model, d)
        vlp_model = _build_vlp(d, pvt_model, fp)
        params    = _vlp_params(d)

        # ── Operating Point ───────────────────────────────────────────────────
        nr = solver_mod.find_operating_points(ipr_model, vlp_model, params, Pr)
        w.writerow(["=== OPERATING POINT(S) ==="])
        w.writerow(["Rate (STB/day)", "Pwf (psia)", "Stability", "Drawdown (psia)",
                    "Drawdown %", "PI (STB/day/psi)"])
        if nr.success:
            for pt in nr.all_points:
                w.writerow([round(pt.rate, 2), round(pt.pwf, 2), pt.stability.value,
                             round(pt.drawdown, 2), round(pt.drawdown_pct, 2),
                             round(pt.productivity_index, 4) if pt.productivity_index else "N/A"])
        else:
            w.writerow(["No operating point", nr.failure_reason])
        w.writerow([])

        # ── PVT @ Operating Point ─────────────────────────────────────────────
        w.writerow(["=== PVT AT OPERATING POINT ==="])
        if nr.success and nr.stable_point:
            T   = float(d.get("T_bh", 180))
            gor = float(d.get("gor", 500))
            Pb  = float(d.get("Pb", 0))
            Rsb = pvt_model.calc_true_rsb(Pb if Pb > 0 else pvt_model.calc_bubble_point(T, gor), T)
            op_fp = pvt_model.fluid_properties_dict(nr.stable_point.pwf, T, Rsb, gor, Pb)
            for k, v in op_fp.items():
                w.writerow([k, round(v, 6) if isinstance(v, (float, int)) else v])
        w.writerow([])

        # ── IPR Curve ─────────────────────────────────────────────────────────
        w.writerow(["=== IPR CURVE ==="])
        w.writerow(["q (STB/day)", "Pwf (psia)"])
        q_arr = np.linspace(0, ipr_model.q_max, 80)
        for q in q_arr:
            w.writerow([round(q, 2), round(ipr_model.calculate_Pwf(q), 2)])
        w.writerow([])

        # ── VLP Curve ─────────────────────────────────────────────────────────
        w.writerow(["=== VLP CURVE ==="])
        w.writerow(["q (STB/day)", "Pwf (psia)"])
        rates = np.arange(float(d.get("q_min", 50)),
                          float(d.get("q_max", 3000)) + 100, 100)
        for q in rates:
            try:
                _, pressures, _ = vlp_model.calculate_pressure_traverse(
                    Pth=params["Pth"], surface_temp=params["surface_temp"],
                    bottomhole_temp=params["bottomhole_temp"],
                    total_depth=params["depth"], step_size=params["step_size"], Ql=q)
                w.writerow([round(q, 2), round(pressures[-1], 2)])
            except Exception:
                w.writerow([round(q, 2), "ERROR"])
        w.writerow([])

        # ── Pressure Traverse ─────────────────────────────────────────────────
        w.writerow(["=== PRESSURE TRAVERSE ==="])
        w.writerow(["Depth (ft)", "Pressure (psia)", "Holdup", "Friction Factor",
                    "Hydrostatic Loss (psi/ft)", "Frictional Loss (psi/ft)", "Total Gradient (psi/ft)"])
        if nr.success and nr.stable_point:
            q_op = nr.stable_point.rate
            depths, pressures, profiles = vlp_model.calculate_pressure_traverse(
                Pth=params["Pth"], surface_temp=params["surface_temp"],
                bottomhole_temp=params["bottomhole_temp"],
                total_depth=params["depth"], step_size=params["step_size"], Ql=q_op)
            for i, (dep, pres) in enumerate(zip(depths, pressures)):
                w.writerow([round(dep, 1), round(pres, 2),
                             round(profiles["holdup"][i], 4),
                             round(profiles["friction_factor"][i], 6),
                             round(profiles["hydrostatic_loss"][i], 6),
                             round(profiles["frictional_loss"][i], 6),
                             round(profiles["total_gradient"][i], 6)])

        csv_str = output.getvalue()
        return Response(
            csv_str,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=ipm_export.csv"}
        )
    except Exception as e:
        traceback.print_exc()
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
