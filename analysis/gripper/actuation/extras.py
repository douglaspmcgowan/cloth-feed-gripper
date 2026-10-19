"""Add-on calculations for the actuation trade that need no close/hold simulation: the thermal scaling estimate, the
gear face-width table and the bench stall floor. Imported by actuation_trade.py; each function is tested.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import model as M

ROOT = M.ROOT
THERMAL_JSON = M.REV_A / "thermal_reference.json"   # rev A thermal.json rows (DS3218MG), pin_rev_a.py
BACKOFF = 0.4225      # thermal.md F1: current factor = eta_g^2 with eta_g 0.65 [A there]
FITS = {"Fit A": "A_mech", "Fit B": "B_elec"}
R26_C = 60.0


# ------------------------------------------------------------------ thermal scaling estimate
def _thermal():
    return json.loads(THERMAL_JSON.read_text(encoding="utf-8"))


COND = {"avg": "continuous conduction (average-value model)", "pwm": "discontinuous conduction (dyno.md bound)"}


def thermal_reference():
    """Per (fit, conduction): reference heat of the present servo (5 N hold, 6.5 V) and the case / cradle-seat rise per
    watt at 25 and 40 C ambient, all read from thermal.json (steady state, no back-off rows)."""
    t = _thermal()
    ref = {}
    for lab, key in FITS.items():
        for cond in COND:
            st = t["step2_steady"][f"{key}|{cond}|F5"]
            h = t["step1_heat_sources"][f"{key}|F5|{cond}"]
            mx = t["step4b_mitigated_matrix"]
            P = st["heat_W"]["P_avg_total_W"]
            row = {"P_avg_total_W": P, "P_hold_winding_W": st["heat_W"]["P_hold_winding_W"], "f_hold": st["f_hold"],
                   "I_stall_A": h["I_stall_A"], "T_hold_Nm": st["T_hold_Nm"], "K_per_W": {}}
            for amb in (25, 40):
                m = mx[f"{key}|{cond}|amb{amb}|backoff_none"]
                row["K_per_W"][amb] = {"case": (m["case_C"] - amb) / P, "mount": (m["mount_C"] - amb) / P}
            ref[(lab, cond)] = row
    return ref


def hold_power_ratio(c, fit, cond, ref):
    """Candidate hold heat over the present servo's. With R ~ V / I_stall and I_hold = I_stall f (f = hold torque over
    stall torque): continuous conduction I^2 R = V I_stall f^2; discontinuous conduction I V = V I_stall f.
    Fit A takes the rail-sizing stall current (power relation), Fit B the listed one, as thermal.md does for A17."""
    r_ = ref[(fit, cond)]
    Ts = float(_stall_nom(c))
    f_c = r_["T_hold_Nm"] / (Ts * c["N"] * c["eta_stage"])
    I_c = M.stall_current_sizing(c, c["V_rail"]) if fit == "Fit A" else M.stall_current(c, c["V_rail"])[0]
    f_ref = r_["T_hold_Nm"] / M.CFG["SERVO_STALL_NM"]
    e = 2 if cond == "avg" else 1
    return (c["V_rail"] * I_c * f_c ** e) / (6.5 * r_["I_stall_A"] * f_ref ** e)


def _stall_nom(c):
    return M.stall_at(c["row"], c["V_rail"]) * M.KGCM


def thermal_estimate(c, ref=None, current_scale=1.0):
    """SCALING ESTIMATE, not a thermal model. Case and cradle-seat temperature of configuration c at steady state,
    5 N hold, from thermal.md's published numbers: the cycle-average heat of the present servo is rescaled by the
    hold-heat ratio, then multiplied by the K/W that thermal.json implies at 25 and 40 C ambient. Back-off (F1) scales
    the hold heat by BACKOFF^2 (continuous conduction) or BACKOFF (discontinuous), as thermal.md section 4.4 states.
    Linear in power, so it understates the rise where copper resistance grows with temperature.
    current_scale: hold current of c over that of the present servo, relative to the nominal ratio (1.0 = nominal
    units; the Monte Carlo median currents give a different value), applied as scale^2 (continuous) or scale (discontinuous)."""
    ref = ref or thermal_reference()
    out = {}
    for fit in FITS:
        for cond in COND:
            r_ = ref[(fit, cond)]
            ratio = hold_power_ratio(c, fit, cond, ref) * current_scale ** (2 if cond == "avg" else 1)
            hold_part = r_["f_hold"] * r_["P_hold_winding_W"]
            rest = r_["P_avg_total_W"] - hold_part
            for bo, b in (("no back-off", 1.0), ("back-off F1", BACKOFF if cond == "pwm" else BACKOFF ** 2)):
                P = rest + hold_part * ratio * b
                for amb in (25, 40):
                    k = r_["K_per_W"][amb]
                    case, mount = amb + k["case"] * P, amb + k["mount"] * P
                    out[f"{fit} | {cond} | {bo} | {amb} C"] = {
                        "power_ratio_vs_present": round(ratio, 3), "P_avg_W": round(P, 3), "case_C": round(case, 1),
                        "mount_C": round(mount, 1), "case_margin_to_R26_K": round(R26_C - case, 1)}
    return out


# ------------------------------------------------------------------ bench stall floor
def bench_stall_floor(c, eta_link=None):
    """Lowest stall torque at the SERVO shaft (N*m) at the rail low end for which the R16 rule (hold <= hold_rule of
    stall) still holds 5 N: T_req(5 N, eta) / (hold_rule * N * eta_stage). 1:1: 0.792 / 0.40 = 1.98 N*m."""
    eta = M.V["eta_link"] if eta_link is None else eta_link
    return M.t_req(M.V["F_hold_N"], eta) / (c["hold_rule"] * c["N"] * c["eta_stage"])


# ------------------------------------------------------------------ gear face width
GEAR_RATIO = {"A17": 300.0, "A19": 373.0, "A32": 221.0, "A34": 342.0}   # servo gearbox ratio: S where listed (rows), A17 [A, gears.py]
WIDTHS = (8, 10, 12)
TARGET_SF = 1.15   # [A] covers a +15 % unit-to-unit torque spread (the Monte Carlo's spread)


def gear_width_table(configs):
    """LC3 (stall) and jam-shock safety factors of the m1.5 z19 a25 PA6-CF printed pair for each candidate, from
    gears.py evaluate() with that candidate's stall torque at the mesh and gears.shock() for its own jam torque."""
    sys.path.insert(0, str(ROOT / "analysis/gripper"))
    import gears as G
    g = G.geometry(1.5, 19, 25, 0.0, G.V["jt_print_mm"])
    out = {}
    for cfg in ("A32@1:1", "A34@1:1", "A19@1:1", "A17@1.5:1"):
        c = next(x for x in configs if x["cfg"] == cfg)
        Ts_hi = float(M.stall_at(c["row"], c["V_rail"] + M.V["V_rail_tol"])) * M.KGCM
        T_mesh = Ts_hi * c["N"] * c["eta_stage"]
        w0 = c["w0_dps"] * M.DEG / c["N"]
        ratio = GEAR_RATIO[c["id"]] * c["N"]
        sh = G.shock(T_mesh, w0, ratio)
        T_sim = [r["T_peak"] for r in sh["finger_snag"]["rows"] if r["J_rotor"] == 5e-8][0]
        T_sh = T_mesh * M.V["jam_factor"]        # dyno.md basis, as the rest of the study (section 5)
        row = {"T_mesh_LC3_Nm": round(T_mesh, 3), "T_jam_Nm": round(T_sh, 3), "T_jam_gears_shock_Nm": round(T_sim, 3),
               "beyond_3p306_fit_point": T_mesh > G.T_STALL_BACKUP or T_sh > G.T_STALL_BACKUP, "by_width": {}}
        for b in WIDTHS:
            e = G.evaluate(g, b, "PA6-CF", T3=T_mesh, Tsh=T_sh)
            e2 = G.evaluate(g, b, "PA6-CF", T3=T_mesh, Tsh=T_sim)
            row["by_width"][str(b)] = {"SF_LC3": e["SF"]["F_LC3"], "SF_jam": e["SF"]["F_shock"],
                                       "SF_jam_gears_shock": e2["SF"]["F_shock"]}
        row["min_width_mm_for_target"] = _min_width(G, g, T_mesh, T_sh)
        out[cfg] = row
    return {"geometry": "PA6-CF m1.5 z19 alpha 25 x 0, printed (gears.json recommendation.printed)",
            "target_SF": TARGET_SF, "target_note": "1.15 covers the Monte Carlo's +15 % unit spread [A]", "cases": out}


def _min_width(G, g, T3, Tsh):
    for b2 in range(16, 41):          # 8.0 .. 20.0 mm in 0.5 mm steps
        b = b2 / 2.0
        e = G.evaluate(g, b, "PA6-CF", T3=T3, Tsh=Tsh)
        if min(e["SF"]["F_LC3"], e["SF"]["F_shock"]) >= TARGET_SF:
            return b
    return None


# ------------------------------------------------------------------ arm-utilisation uncertainty
def arm_gate(c):
    """util, its uncertainty u and a pass / marginal / fail verdict. u = fit residual + slope * (mass uncertainty):
    +/-2 g on a datasheet or mixed row (A17 listings differ 58 vs 60 g), +/-3.5 g on a one-vendor listing (A33 / A18
    differ 60 vs 67 g), +/-25 % on an estimated stage mass [A]. Marginal = the interval straddles 1.00."""
    util = M.arm_util(c["mass_total_g"])
    d_act = 3.5 if c["evidence"] == "vendor claim" else 2.0
    d_stage = 0.25 * c["stage_mass_g"]
    u = M.ARM_RESID + M.ARM_B * (d_act + d_stage)
    status = "pass" if util + u <= 1.0 else ("fail" if util - u > 1.0 else "marginal")
    return {"util": round(util, 4), "u": round(u, 4), "mass_g": round(c["mass_total_g"], 2),
            "mass_basis": f"actuator {c['mass_act_g']} g [{c['mass_tag']}] +/-{d_act} g; stage {c['stage_mass_g']:.2f} g [A] +/-{d_stage:.2f} g",
            "status": status, "mass_at_util_1_g": round((1.0 - M.ARM_A) / M.ARM_B, 1)}
