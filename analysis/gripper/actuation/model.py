"""Actuation model for the cloth-feed gripper: candidate loading, static checks and a vectorised close/hold
simulation that mirrors the shipped firmware (fsm.cpp CLOSE, motion.cpp, force_ctrl.cpp) at 1 kHz.

Every input is tagged [S] sourced, [D] derived by a repo script, or [A] assumed. The study is the rev A trade (it chose
the DS3230 MG that rev B.1 builds); its reference servo is the DS3218MG (A17). The firmware constants are therefore the
rev A firmware/gripper/config.h, pinned in rev_a/config.json by pin_rev_a.py and derived through
analysis/gripper/firmware_sim/fwconfig.py, and the mirror is validated against the pinned rev A fw_sim cases. Geometry,
grip loads and the arm fit come from rev_a/payload_reference.json at the same revision; reading the live payload
result would silently mix current CAD geometry into this historical study. actuation_trade.py is the one command.
"""
from __future__ import annotations

import csv
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "analysis/gripper/firmware_sim"))
import fwconfig  # noqa: E402

ACT_CSV = ROOT / "docs/gripper/research/actuators.csv"
REV_A = HERE / "rev_a"   # pin_rev_a.py: rev A (DS3218MG) config.h, fw_sim.json cases and thermal.json rows
PT_JSON = REV_A / "payload_reference.json"
FW_JSON = REV_A / "fw_sim_cases.json"

G = 9.80665
KGCM = G / 100.0  # N*m per kg*cm
CFG = json.loads((REV_A / "config.json").read_text(encoding="utf-8"))["config"]   # rev A, not the live config.h
DER = fwconfig.derived(CFG)
PT = json.loads(PT_JSON.read_text(encoding="utf-8"))
PIN = {k: v["value"] for k, v in PT["inputs"].items()}

# ------------------------------------------------------------------ inputs (value, tag, source)
INPUT = {
    "F_hold_N": (PT["grip"]["F_target_N"], "D", "payload_torque.json grip.F_target_N (R14)"),
    "T_hold_Nm": (PT["grip"]["T_hold_Nm"], "D", "payload_torque.json grip.T_hold_Nm: (2 F r_c + T x_f) / eta"),
    "r_c_mm": (PIN["r_c_mm"], "D", "payload_torque.json inputs.r_c_mm (DB D3)"),
    "x_f_mm": (PIN["x_f_mm"], "D", "payload_torque.json inputs.x_f_mm"),
    "tension_N": (PIN["tension_N"], "A", "payload_torque.json inputs.tension_N (M3 measures)"),
    "eta_link": (PIN["eta"], "A", "payload_torque.json inputs.eta (M18 measures); MC range below"),
    "eta_link_range": ((0.70, 0.95), "A", "payload_torque.py tornado range for eta"),
    "hold_frac": (PIN["hold_frac"], "A", "R16: hold <= 40 % of stall"),
    "hold_frac_vendor_pololu": (0.25, "S", "Pololu micro metal gearmotor page: 25 % of stall current or less, "
                                "https://www.pololu.com/category/60/micro-metal-gearmotors (via payload_torque.py)"),
    "V_rail_tol": (PIN["V_rail_tol"], "A", "buck set-point + load regulation (payload_torque.py)"),
    "V_headroom": (0.30, "A", "rail set this far below the part's rated maximum so the +0.15 V band stays inside it"),
    "V_rail_cap": (7.4, "A", "highest rail considered (2S Li-ion nominal, the SO-101 C001 7.4 V supply class)"),
    "V_dc_drive": (6.0, "A", "gearmotors driven at their 6 V rating through a DRV8833-class H-bridge (payload_torque.py)"),
    "R_wire_range": ((0.03, 0.10), "A", "servo lead + connector round trip, about 1 m of 22-26 AWG plus two crimps"),
    "unit_spread": (0.15, "A", "brief: unit-to-unit spread +/-15 % on stall torque and no-load speed, uniform"),
    "claim_factor_vendor": ((0.85, 1.0), "A", "rows whose torque is a vendor listing with no datasheet (spec_basis "
                            "vendor-listing): true stall torque = claim x U(0.85, 1.00) in the Monte Carlo. The DS3225 "
                            "is listed at 28 kg*cm (aifitlab, A33) and 25 kg*cm (MakerFocus, A18) at 6.8 V, an 11 % "
                            "spread for one part; listings are taken never to understate"),
    "T_wind_range": ((25.0, 80.0), "A", "winding temperature during the duty cycle; dyno.md thermal table 43-74 C "
                     "(average-value cases)"),
    "T_wind_hot": (120.0, "A", "sensitivity case: hot winding near the Fit A 30-min peak (dyno.md)"),
    "alpha_cu": (0.00393, "S", "copper resistance temperature coefficient 0.393 %/K (standard handbook value, "
                 "e.g. https://www.engineeringtoolbox.com/resistance-resisitivity-d_1382.html, 2026-10-11)"),
    "kt_tc": (-0.002, "A", "ferrite magnet torque constant -0.2 %/K (ferrite remanence -0.18 to -0.2 %/K, typical)"),
    "tau_range": ((0.030, 0.060), "A", "servo position-loop lag; config.h SERVO_TAU_S 40 ms [A, M8 measures]"),
    "k_tip_FEA": ((2 * 0.523, 2 * 0.621), "D", "finger.md 6.2 D7 pair k_pair 0.523 (E56) / 0.621 (E67) N/mm, as fw sim"),
    "k_tip_R12": ((CFG["FINGER_K_MIN_N_PER_MM"], CFG["FINGER_K_MAX_N_PER_MM"]), "S", "DB R12 window via config.h"),
    "fold_N": (8.41, "D", "finger.md: finger folds at 8.41 N with the nail (8.88 N E56 without)"),
    "stage_eta": (PIN["stage_eta"], "A", "one printed spur stage (payload_torque.py)"),
    "stage_eta_range": ((0.85, 0.95), "A", "printed spur stage, lubricated PA6-CF/POM"),
    "servo_stage_hw_g": (3.0, "A", "added stage: 4 mm shaft, two 4x8x3 bearings, bracket screws"),
    "dc_stage_pinion_z": (PIN["stage_pinion_z"], "A", "payload_torque.py printed stage pinion z12 m0.8 b5 PETG"),
    "servo_stage_module": (1.25, "A", "servo-side stage must carry 2-4 N*m: m1.25, b 8 mm, z15 pinion, PA6-CF"),
    "dc_price_extra": (5.0, "A", "H-bridge + JST cable, payload_torque.py"),
    "stage_price": (1.0, "A", "printed gears + bearings for one stage"),
    "gbp_usd": (1.35, "A", "GBP to USD, rounded up so the R8 check is conservative"),
    "gb_eff_fitA": (0.62, "D", "dyno.md Fit A: A17 3.77 A vs T_s w0 / V = 2.33 A at 6.5 V -> effective 0.62"),
    "I_idle_servo": (0.015, "A", "servo electronics idle current where the row gives none (A17 lists 5 mA)"),
    "I_idle_fwsim": (0.15, "A", "fw sim plant I_IDLE (sim.py)"),
    "jam_factor": (2.69 / 2.108, "D", "dyno.md jam shock 2.69 N*m at 120 deg/s over the 2.108 N*m LC3 stall"),
    "gear_sf_fit": ((1.61, 2.108, 0.806), "D", "gears.md: SF 1.61 at 2.108 N*m and 1.12 at 3.306 N*m -> "
                    "SF = 1.61 (T/2.108)^-0.806 (power fit through both points)"),
    "pocket_mm": ((40.4, 20.4), "D", "cad/gripper housing pocket (scout of build123d source, 2026-10-11)"),
    "ear_pattern_mm": ((49.5, 10.0), "D", "housing ear-hole pattern"),
    "ear_span_max_mm": (56.5, "D", "housing ear span limit"),
    "body_h_max_mm": (40.5, "D", "A17 body height the deck clears (8.5 mm free above the ears)"),
    "arm_fit": (None, "D", "payload_torque.json r40_design: arm_util_C001_7p4V is linear in actuator mass "
                "(fit below, worst pose, no camera)"),
}
V = {k: v[0] for k, v in INPUT.items()}

R_C = V["r_c_mm"]
DEG = math.pi / 180.0
TH_TOUCH_NOCLOTH = -0.44  # deg, 1 mm gap / (2 r_c) [DB R18], as fw sim
TH_TOUCH_PLY = -0.31      # deg, one 0.3 mm ply [TA 2.1], as fw sim
K_STIFF = DER["K_STIFF_N_PER_DEG"]
US_PER_DEG = DER["US_PER_DEG"]


def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ static relations
def t_req(F, eta_link, tension=V["tension_N"]):
    """Torque at the drive input of the 1:1 sector pair (N*m) for pad force F per pad: (2 F r_c + T x_f) / eta."""
    return (2 * F * R_C + tension * V["x_f_mm"]) / 1000.0 / eta_link


def stall_at(row, v):
    """Stall torque (kg*cm) at rail v: same piecewise-linear rule as payload_torque.py stall_at."""
    pts = sorted({(fnum(row.get(vk)), fnum(row.get(tk))) for tk, vk in (("torque_low_kgcm", "torque_low_at_V"),
                                                                      ("torque_mid_kgcm", "torque_mid_at_V"),
                                                                      ("torque_high_kgcm", "torque_high_at_V"))
                  if fnum(row.get(vk)) and fnum(row.get(tk))})
    if not pts:
        return None
    if v <= pts[0][0]:
        return pts[0][1] * min(1.0, v / pts[0][0])
    if v >= pts[-1][0]:
        return pts[-1][1]
    return float(np.interp(v, [p[0] for p in pts], [p[1] for p in pts]))


def speed_s60(row, v):
    """Seconds per 60 deg at v: payload_torque.py speed_s60 (linear between the two rated points)."""
    a, b = fnum(row["speed_low_s_per_60deg"]), fnum(row["speed_high_s_per_60deg"])
    vl, vh = fnum(row["voltage_min_V"]) or 4.8, fnum(row["voltage_max_V"]) or 6.0
    if a and b:
        return a + (b - a) * (min(max(v, vl), vh) - vl) / max(vh - vl, 1e-9)
    return a or b


def derate_T(T_w):
    """Stall-torque factor at winding temperature T_w (C): stall current falls with copper R, Kt with the magnet."""
    d = np.asarray(T_w, float) - 25.0
    return (1.0 + V["kt_tc"] * d) / (1.0 + V["alpha_cu"] * d)


def gear_sf(T_mesh):
    """Safety factor of the m1.5 z19 PA6-CF sector pair at mesh torque T (N*m), gears.md two-point fit."""
    a, T0, b = V["gear_sf_fit"]
    return a * (np.asarray(T_mesh, float) / T0) ** (-b)


def gear_allow(sf):
    a, T0, b = V["gear_sf_fit"]
    return T0 * (a / sf) ** (1.0 / b)


def _arm_fit():
    pts = [(e["mass_g"], e["arm_util_C001_7p4V"]) for e in PT["runs"]["r40_design"]["actuators"]
           if e.get("mass_g") is not None and e.get("arm_util_C001_7p4V") is not None and e["mass_g"] < 80]
    m, u = np.array(pts).T
    b, a = np.polyfit(m, u, 1)
    return float(a), float(b), float(np.max(np.abs(a + b * m - u)))


ARM_A, ARM_B, ARM_RESID = _arm_fit()


def arm_util(mass_g):
    """Worst-pose SO-101 hold utilisation (C001 7.4 V, no camera) for actuator + stage mass at the servo station."""
    return ARM_A + ARM_B * mass_g


def stage_gear_mass(N, module, z_p, b_mm, rho, fill):
    dp = module * z_p
    return rho * 1e-3 * fill * b_mm * math.pi / 4 * (dp ** 2 + (dp * N) ** 2)


def servo_stage_mass(N):
    if N <= 1.0:
        return 0.0
    return stage_gear_mass(N, V["servo_stage_module"], 15, 8.0, 1.20, 0.6) + V["servo_stage_hw_g"]


def dc_stage_mass(N, n_st):
    """payload_torque.py stage_mass per stage (m0.8 z12 b5 PETG, 60 % fill)."""
    return n_st * stage_gear_mass(N ** (1.0 / n_st), 0.8, V["dc_stage_pinion_z"], 5.0, 1.25, PIN["stage_gear_fill"])

# ------------------------------------------------------------------ candidates
SCREEN_HOLD_MARGIN = 0.6  # parts below this hold margin at their strongest ratio are not modelled [A]
# vendor-listing rows whose torque claim a datasheet for the SAME part (same gear ratio) confirms: no claim derate.
# Empty on purpose: A34 (DS3235 SG, gear ratio 342) is a different variant from the A19 datasheet unit (ratio 373,
# 30 vs 35 kg*cm at 7.4 V; actuators.csv A34 notes), so that datasheet does not corroborate it (review 2026-10-11).
CORROBORATED: dict[str, str] = {}


def evidence(row):
    """Torque evidence class: datasheet, corroborated (listing checked against a datasheet), mixed, vendor claim."""
    b = row.get("spec_basis") or ""
    if b == "vendor-listing":
        return "corroborated" if row["id"] in CORROBORATED else "vendor claim"
    return b or "not recorded"
GEARBOX_LIMIT = {"M01": 2.0, "M02": 2.5, "M03": 2.5, "M04": 2.0, "M09": 2.0, "M10": 2.0, "M11": 2.0}  # kg*cm [S rows]
PRICE_GBP = {"A36": 18.74, "A37": 18.56}  # [S Maplin UK pages, actuators.csv notes, 2026-10-11]
MASS_FILL = {"M10": (11.0, "A: same HPCB micro-gearmotor + encoder body as M01/M02/M09 (11 g [S])"),
             "M11": (11.0, "A: same HPCB micro-gearmotor + encoder body as M01/M02/M09 (11 g [S])")}
AVAIL = {  # id -> (0..1, reason) [D from actuators.csv stock_checked / recheck_stock, 2026-10-11]
    "A13": (0.4, "Pololu: backorders allowed, category lists it out of stock"),
    "A16": (0.1, "Adafruit: out of stock"),
    "A17": (1.0, "SpeedyFPV: in stock ($12.99)"),
    "A18": (0.4, "MakerFocus: unclear (cart + back-in-stock signup)"),
    "A19": (0.2, "RCDrone sold out / HTTP 403; DS3235 SG variant backordered"),
    "A20": (0.1, "RCDrone sold out, not rechecked"),
    "A28": (1.0, "goBILDA: in stock"),
    "A29": (1.0, "goBILDA: in stock"),
    "A30": (1.0, "REV: in stock"),
    "A31": (1.0, "REV: in stock"),
    "A32": (0.4, "aifitlab: backordered"),
    "A33": (0.4, "aifitlab: backordered"),
    "A39": (0.4, "aifitlab DS3230 PRO: product page backordered, collection page 'In stock' (conflict, treated as backordered)"),
    "A34": (0.4, "aifitlab: backordered"),
    "A35": (1.0, "ServoCity: in stock"),
    "A36": (0.3, "Maplin UK only, 5 left"),
    "A37": (0.3, "Maplin UK only, 3 left"),
    "A38": (0.4, "Pololu: backorders allowed, category lists it out of stock"),
}
for _m in ("M01", "M02", "M03", "M04", "M09", "M10", "M11"):
    AVAIL[_m] = (0.7, "Pololu: Active and Preferred, backorders allowed, no count shown")


def availability(row):
    if row["id"] in AVAIL:
        return AVAIL[row["id"]]
    s = ((row.get("recheck_stock") or "") + " " + (row.get("stock_checked") or "") + " " + row["notes"]).lower()
    if any(x in s for x in ("sold out", "out of stock", "unavailable")):
        return 0.1, "sold out (row text)"
    return (1.0, "in stock (row text)") if "in stock" in s else (0.5, "listed, stock not shown")


def kind_of(row):
    rid, cat = row["id"], row["category"]
    if rid.startswith("A"):
        return "continuous" if "continuous" in cat else "servo"
    return {"M": "gearmotor", "W": "worm", "L": "linear"}[rid[0]]


def price_usd(row):
    p = fnum(row["price_usd"])
    if p is None and row["id"] in PRICE_GBP:
        return round(PRICE_GBP[row["id"]] * V["gbp_usd"], 2), "GBP x 1.35 [A]"
    return p, "[S]"


def load_rows():
    return list(csv.DictReader(ACT_CSV.open(encoding="utf-8")))


def rail_for(row, kind):
    if kind in ("gearmotor", "worm"):
        return V["V_dc_drive"]
    vm = fnum(row["voltage_max_V"]) or 6.0
    return round(min(vm - V["V_headroom"], V["V_rail_cap"]), 2)


def envelope(row, kind, N):
    """Fit in the current housing: (class, utility, reason). Pocket and ear data from the CAD scout."""
    if kind in ("gearmotor", "worm"):
        return "new bay", 0.1, "gearmotor + printed stage: new mount, new bay"
    if N > 1.0:
        return "new bay", 0.1, f"added {N:g}:1 stage: no room above the ears (8.5 mm), new bay"
    L, W, H = (fnum(row[k]) for k in ("dim_L_mm", "dim_W_mm", "dim_H_mm"))
    ears = row.get("ear_hole_pattern_mm") or ""
    span = fnum(row.get("flange_span_mm"))
    spl = (row.get("output_interface") or "").lower()
    spline_ok = "25" in spl and "c24" not in spl
    pen = 0.0 if spline_ok or not spl else 0.2
    if not (L and W and H):
        return "unverified", 0.6 - pen, "body dimensions not published"
    pl, pw = V["pocket_mm"]
    if L > pl + 0.3 or W > pw + 0.3 or H > V["body_h_max_mm"] + 0.5:
        return "pocket change", 0.4 - pen, f"body {L:g} x {W:g} x {H:g} mm vs pocket {pl} x {pw}, height {V['body_h_max_mm']}"
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", ears)]
    if len(nums) >= 2 and abs(max(nums[:2]) - 49.5) < 0.6 and abs(min(nums[:2]) - 10.0) < 0.6:
        return "drop-in", 1.0 - pen, "body fits the pocket, ear pattern 49.5 x 10 mm"
    if span and span <= V["ear_span_max_mm"]:
        return "likely drop-in", 0.8 - pen, f"body fits, ear span {span:g} mm; ear-hole pattern to verify"
    return "likely drop-in", 0.7 - pen, "body fits; ear span and pattern not published"


def build_configs(rows=None):
    """Every R7/R8 row with torque and speed data, at the existing train and two alternative ratios.
    Servos: 1:1 (existing horn on knuckle A), 1.5:1 and 2:1 added stage. Gearmotors/worm: 8:1 (existing DC branch
    in config.h DC_EXTRA_RATIO), 5:1 and 12:1."""
    rows = rows or load_rows()
    out, screened = [], []
    for row in rows:
        rid, kind = row["id"], kind_of(row)
        p, ptag = price_usd(row)
        why = []
        if kind in ("continuous", "linear"):
            why.append("R7: no position control (continuous rotation)" if kind == "continuous" else "linear: price > $50")
        if "serial" in row["category"].lower() or "bus" in row["category"].lower():
            why.append("R7: serial bus")
        if p is None or p > 50:
            why.append("R8: price > $50 or unknown")
        mass = fnum(row["weight_g"])
        mass_tag = "S"
        if mass is None and rid in MASS_FILL:
            mass, mass_tag = MASS_FILL[rid]
        if mass is None:
            why.append("no mass data")
        Vr = rail_for(row, kind)
        if kind == "servo":
            Ts = stall_at(row, Vr)
            s60 = speed_s60(row, Vr)
            w0 = 60.0 / s60 if s60 else None
        elif kind in ("gearmotor", "worm"):
            Ts = fnum(row["torque_high_kgcm"])
            rpm = fnum(row["no_load_speed_rpm"])
            w0 = rpm * 6.0 if rpm else None
        else:
            Ts = w0 = None
        if not Ts:
            why.append("no stall torque")
        if not w0:
            why.append("no speed data")
        if why:
            screened.append({"id": rid, "model": row["model"], "reasons": why})
            continue
        ratios = (1.0, 1.5, 2.0) if kind == "servo" else (8.0, 5.0, 12.0)
        avail = availability(row)
        # strength screen: hold capacity at the strongest ratio, rail low end, nominal efficiencies
        Ts_lo = (stall_at(row, Vr - V["V_rail_tol"]) * KGCM) if kind == "servo" else Ts * KGCM * (Vr - V["V_rail_tol"]) / Vr
        rule = V["hold_frac"] if kind == "servo" else (1.0 if kind == "worm" else
                                                        (V["hold_frac_vendor_pololu"] if rid in GEARBOX_LIMIT else V["hold_frac"]))
        cap_m = rule * Ts_lo
        if GEARBOX_LIMIT.get(rid):
            cap_m = min(cap_m, GEARBOX_LIMIT[rid] * KGCM)
        n_best = max(ratios)
        eta_best = V["stage_eta"] ** (1 if kind == "servo" else 2)
        hm_best = cap_m * n_best * eta_best / t_req(V["F_hold_N"], V["eta_link"])
        if hm_best < SCREEN_HOLD_MARGIN:
            screened.append({"id": rid, "model": row["model"],
                             "reasons": [f"hold margin {hm_best:.2f} < {SCREEN_HOLD_MARGIN} even at {n_best:g}:1"]})
            continue
        for N in ratios:
            c = {"id": rid, "cfg": f"{rid}@{N:g}:1", "model": row["model"], "kind": kind, "N": N, "row": row,
                 "price": p, "price_tag": ptag, "mass_act_g": mass, "mass_tag": mass_tag, "V_rail": Vr,
                 "spec_basis": row.get("spec_basis") or "not recorded", "evidence": evidence(row),
                 "avail": avail[0], "avail_note": avail[1]}
            if kind == "servo":
                c["n_stages"] = 0 if N == 1.0 else 1
                c["eta_stage"] = 1.0 if N == 1.0 else V["stage_eta"]
                c["stage_mass_g"] = servo_stage_mass(N)
                c["T_stall_Nm"] = Ts * KGCM
                c["w0_dps"] = w0
                c["hold_rule"] = V["hold_frac"]
                c["gb_limit_Nm"] = None
                c["price_total"] = p + (V["stage_price"] if N > 1 else 0.0)
            else:
                n_st = 1 if N <= 5.0 else 2
                c["n_stages"] = n_st
                c["eta_stage"] = V["stage_eta"] ** n_st
                c["stage_mass_g"] = dc_stage_mass(N, n_st)
                c["T_stall_Nm"] = Ts * KGCM
                c["w0_dps"] = w0
                lim = GEARBOX_LIMIT.get(rid)
                c["gb_limit_Nm"] = lim * KGCM if lim else None
                c["hold_rule"] = 1.0 if kind == "worm" else min(V["hold_frac"], V["hold_frac_vendor_pololu"]
                                                                if rid in GEARBOX_LIMIT else V["hold_frac"])
                c["price_total"] = p + V["dc_price_extra"] + n_st * V["stage_price"]
            c["mass_total_g"] = mass + c["stage_mass_g"]
            env = envelope(row, kind, N)
            c["envelope"], c["u_envelope"], c["envelope_note"] = env
            out.append(c)
    return out, screened


# ------------------------------------------------------------------ electrical
def stall_current(c, v):
    """(I_stall at v, tag). Row value scaled with voltage; else the dyno Fit A power relation."""
    row = c["row"]
    Iq, Vq = fnum(row["stall_current_A"]), fnum(row.get("stall_current_at_V"))
    if Iq:
        return Iq * (v / Vq if Vq else 1.0), "S scaled by V"
    w = c["w0_dps"] * DEG
    return c["T_stall_Nm"] * w / (v * V["gb_eff_fitA"]), "D: T_s w0 / (V 0.62), dyno Fit A relation"


def stall_current_sizing(c, v):
    """Rail sizing current: the larger of the listed value and the Fit A power relation (dyno.md)."""
    w = c["w0_dps"] * DEG
    i_pc = c["T_stall_Nm"] * w / (v * V["gb_eff_fitA"])
    i_l, _ = stall_current(c, v)
    return max(i_l, i_pc)


def idle_current(c):
    if c["kind"] != "servo":
        return 0.0
    i = fnum(c["row"]["idle_current_mA"])
    return i / 1000.0 if i else V["I_idle_servo"]


# ------------------------------------------------------------------ vectorised close/hold simulation
def sim(p, ms=2000, cal_ms=900, record=False):
    """Run CALIBRATE (no cloth) then a G 5 grip for every lane of p (dict of equal-length arrays).

    Plant per lane (jaw-referred): position servo with first-order lag tau, deadband, torque-speed line, ratio N;
    or a DC gearmotor with a 1 kHz duty loop (Kp 0.08 duty/deg, breakaway 0.10, max 0.90; config.h DC_*).
    Firmware per lane: motion.cpp search profile, fsm.cpp aContact/fcStart, force_ctrl.cpp fcStep (hold bias
    F_HOLD_BIAS_N, stiffness estimate and gain schedule, squeeze cap less F_CAP_MARGIN_N), fmUpdate contact /
    over-force trip / target band around the regulated force. Force sensing: fsr_filter.cpp, the EMA (alpha 0.10 at
    1 kHz) on the divider voltage of the fsr_model.h power law, read back as force (ADC noise and the unloaded offset
    left out; checked against fw_sim.json by the tests).
    """
    S = max(np.size(v) for v in p.values())
    f32 = lambda x: np.broadcast_to(np.asarray(x, float), (S,)).copy()  # noqa: E731
    N, K = f32(p["N"]), f32(p["k_tip"]) * R_C * DEG
    is_dc = np.broadcast_to(np.asarray(p.get("is_dc", False), bool), (S,)).copy()
    Tst_j = f32(p["T_stall_motor"]) * N * f32(p["eta_stage"])
    W0_j = f32(p["w0_motor"]) / N
    tau = f32(p["tau"])
    db = CFG["SERVO_DEADBAND_US"] / US_PER_DEG / 2.0 / N
    eta = f32(p["eta_link"])
    ten = f32(p.get("tension", 0.0))
    u_max = (f32(p["F_cap"]) - CFG.get("F_CAP_MARGIN_N", 0.0) - CFG["F_TOUCH_N"]) / K_STIFF  # force_ctrl.h CTRL_U_MAX_DEG
    soft = f32(p["F_soft"])
    trip = f32(p["F_trip"])
    v_fast = f32(p["v_fast"])
    zone = f32(p["slow_zone"])
    mid_zone = f32(p.get("mid_zone", 0.0))   # motion.cpp: middle speed from theta_c0 + JAW_MID_ZONE_DEG (0 = off)
    v_mid = f32(p.get("v_mid", 0.0))
    a_dec = f32(p.get("a_dec", 0.0))
    phase = np.broadcast_to(np.asarray(p.get("phase", 0), int) % 20, (S,)).copy()
    I_st, I_id = f32(p["I_stall"]), f32(p["I_idle"])
    alpha = CFG["FSR_EMA_ALPHA"]
    lag_s = CFG["CTRL_LAG_COMP_S"]
    v_slow = CFG["JAW_SPEED_NEAR_DPS"]
    dt_c = CFG["CONTROL_PERIOD_MS"] / 1000.0
    sp = CFG["F_TARGET_DEFAULT_N"]
    kp0, ti = DER["CTRL_KP_DEG_PER_N"], DER["CTRL_TI_S"]
    bias, f_set_max = CFG.get("F_HOLD_BIAS_N", 0.0), CFG["F_SET_MAX_N"]
    sched = bool(CFG.get("GAIN_SCHED_ENABLED", 0))
    k_sched_min = CFG.get("K_SCHED_MIN_N_PER_MM", CFG["FINGER_K_MAX_N_PER_MM"]) * R_C * DEG
    kest_lag = int(CFG.get("KEST_LAG_TICKS", 0))
    kest_alpha = CFG.get("KEST_ALPHA", 0.0)
    kest_fmin = CFG.get("KEST_F_MIN_N", 0.0)

    def sp_reg(x):  # force_ctrl.cpp spReg: setpoint + hold bias, never above the setpoint clamp
        r = x + bias
        return np.where(r > f_set_max, np.where(x > f_set_max, x, f_set_max), r)

    r_sp = float(sp_reg(np.asarray(sp)))
    u_min = CFG["CTRL_U_MIN_DEG"]
    jaw_min = CFG["JAW_MIN_DEG"]
    rate = CFG["CTRL_RATE_LIMIT_DPS"] * dt_c
    backoff = CFG["CTRL_SOFT_BACKOFF_DEG"]

    def plant_step(th, tgt, touch):
        d = touch - th
        F = np.where(d > 0, K * d, 0.0)
        T = (2 * F * R_C + ten * V["x_f_mm"]) / 1000.0 / eta
        load = np.clip(T / Tst_j, 0.0, None)
        e = tgt - th
        # hobby servo: first-order position loop with deadband, speed capped by the torque-speed line
        w = np.where(np.abs(e) <= db, 0.0, (e - np.sign(e) * db) / tau)
        wmax_close = W0_j * np.maximum(0.0, 1.0 - load)
        w_srv = np.clip(w, -wmax_close, W0_j)
        # gearmotor: duty loop at 1 kHz, static friction below breakaway, no back-drive
        duty = np.clip(0.08 * e, -0.90, 0.90)
        moving = np.abs(duty) >= 0.10
        w_dc = np.where(duty < 0, np.minimum(0.0, W0_j * (duty + load)), W0_j * duty)
        w_dc = np.where(moving, w_dc, 0.0)
        w_all = np.where(is_dc, w_dc, w_srv)
        th = th + w_all * 0.001
        d = touch - th
        F = np.where(d > 0, K * d, 0.0)
        return th, F, w_all

    def motion_step(cmd, tgt, slow0, active, vnow, decel, mid0=None):
        err = tgt - cmd
        closing = err < 0
        v = np.where(closing & (cmd <= slow0), v_slow, v_fast)
        if mid0 is not None:
            v = np.where(closing & (cmd > slow0) & (cmd <= mid0), v_mid, v)
        if decel is not None:
            vd = np.sqrt(v_slow ** 2 + 2 * a_dec * np.maximum(cmd - slow0, 0.0))
            v = np.where(closing & decel & (cmd > slow0), np.minimum(v_fast, vd), v)
        step = v * dt_c
        land = closing & (cmd > slow0) & (cmd - step < slow0)
        step = np.where(land, cmd - slow0, step)
        if mid0 is not None:
            step = np.where(closing & (cmd > mid0) & (cmd - step < mid0), cmd - mid0, step)
        done = np.abs(err) <= step
        new = np.where(done, tgt, cmd + np.where(err > 0, step, -step))
        cmd = np.where(active, new, cmd)
        vnow = np.where(active & ~done, v, np.where(active & done, v, 0.0))
        active = active & ~done
        vnow = np.where(active, vnow, 0.0)
        return cmd, active, vnow

    decel = a_dec > 0
    # ---------------- CALIBRATE: open, slow search from CAL_SEARCH_START, store theta_c0 = cmd + vNow * lag
    th = np.full(S, CFG["JAW_OPEN_DEG"])
    tgt = th.copy()
    pend = th.copy()
    ema = np.zeros(S)
    cmd = th.copy()
    slow0 = np.full(S, CFG["CAL_SEARCH_START_DEG"])
    end = np.full(S, CFG["CAL_C0_MIN_DEG"] - DER["CTRL_LAG_COMP_DEG"])
    active = np.ones(S, bool)
    vnow = np.zeros(S)
    c0 = np.full(S, np.nan)
    armed = np.ones(S, bool)
    touch_cal = f32(p.get("touch_cal", TH_TOUCH_NOCLOTH))
    for t in range(1, cal_ms + 1):
        tt = t + phase
        pend = np.where((tt % 20) == 10, cmd_to_tgt(cmd, N), pend)
        tgt = np.where(is_dc, cmd, np.where((tt % 20) == 0, pend, tgt))
        th, F, _ = plant_step(th, tgt, touch_cal)
        ema += alpha * (fsr_mv(F) - ema)
        hit = armed & (fsr_force(ema) >= CFG["F_TOUCH_N"])
        if (tt % 20 == 0).any():
            tick = (tt % 20) == 0
            c2, a2, v2 = motion_step(cmd, end, slow0, active, vnow, None)
            cmd, active, vnow = np.where(tick, c2, cmd), np.where(tick, a2, active), np.where(tick, v2, vnow)
        c0 = np.where(hit & np.isnan(c0), cmd + vnow * lag_s, c0)
        active = active & ~hit
        armed = armed & ~hit
    c0 = np.where(np.isnan(c0), 0.0, c0)

    # ---------------- GRIP from fully open
    th = np.full(S, CFG["JAW_OPEN_DEG"])
    tgt = th.copy()
    pend = th.copy()
    ema = np.zeros(S)
    cmd = th.copy()
    slow0 = c0 + zone
    mid0 = np.maximum(c0 + mid_zone, slow0) if (mid_zone > zone).any() else None
    end = c0 - CFG["NO_CONTACT_MARGIN_DEG"]
    # force_ctrl.cpp fcJawFloor: theta_c0 - JAW_FLOOR_BELOW_C0_DEG, never below JAW_MIN_DEG (0 = absolute floor only)
    below = CFG.get("JAW_FLOOR_BELOW_C0_DEG", 0.0)
    jaw_floor = np.maximum(jaw_min, c0 - below) if below > 0 else np.full(S, jaw_min)
    active = np.ones(S, bool)
    vnow = np.zeros(S)
    on = np.zeros(S, bool)
    th_ref = np.zeros(S)
    u = np.zeros(S)
    integ = np.zeros(S)
    k_est = np.full(S, K_STIFF)
    u_hist = np.zeros((kest_lag + 1, S))
    u_head = np.zeros(S, int)
    lanes = np.arange(S)
    sp_r = np.full(S, CFG["F_TOUCH_N"])
    armed = np.ones(S, bool)
    n_over = np.zeros(S, int)
    n_band = np.zeros(S, int)
    held = np.zeros(S, bool)
    fault = np.zeros(S, bool)
    t_contact = np.full(S, np.nan)
    t_45 = np.full(S, np.nan)
    t_hold = np.full(S, np.nan)
    F_peak = np.zeros(S)
    F_sum = np.zeros(S)
    I_sum = np.zeros(S)
    n_sum = 0
    v3 = np.full(S, np.nan)
    v2_ = np.full(S, np.nan)
    touch = f32(p.get("touch", TH_TOUCH_PLY))
    last = int(0.3 * 1000)
    rec = {"t": [], "F": [], "th": [], "cmd": []} if record else None
    for t in range(1, ms + 1):
        tt = t + phase
        sample = (tt % 20) == 10
        pend = np.where(sample, cmd_to_tgt(cmd, N), pend)
        apply = (tt % 20) == 0
        tgt = np.where(is_dc, cmd, np.where(apply, pend, tgt))
        th_old = th
        th, F, w = plant_step(th, tgt, touch)
        for lvl, arr in ((3.0, v3), (2.0, v2_)):
            cross = np.isnan(arr) & (th <= touch + lvl) & (th_old > touch + lvl)
            arr[cross] = -w[cross]
        ema += alpha * (fsr_mv(F) - ema)
        f = fsr_force(ema)
        F_peak = np.maximum(F_peak, F)
        t_45 = np.where(np.isnan(t_45) & (F >= 0.9 * sp), t / 1000.0, t_45)
        # force monitor (every ms)
        hit = armed & (f >= CFG["F_TOUCH_N"])
        armed = armed & ~hit
        n_over = np.where(f > trip, n_over + 1, 0)
        trip_now = (n_over > CFG["F_TRIP_MS"]) & ~fault
        inband = on & ~held & (f > r_sp - CFG["F_BAND_N"]) & (f < r_sp + CFG["CTRL_I_DB_HI_N"] + CFG["F_BAND_N"])
        n_band = np.where(inband, n_band + 1, 0)
        reach = n_band > CFG["F_SETTLE_MS"]
        t_hold = np.where(reach & np.isnan(t_hold), t / 1000.0, t_hold)
        held = held | reach
        # control tick
        tick = (tt % 20) == 0
        if tick.any():
            # force loop (fcStep) where on
            fc_tick = tick & on & ~fault
            # stiffness estimate from the force against the squeeze commanded KEST_LAG_TICKS ticks ago
            u_lag = u_hist[(u_head + 1) % (kest_lag + 1), lanes]
            upd = fc_tick & (f > kest_fmin) & (u_lag > 0.3)
            k_raw = np.clip((f - CFG["F_TOUCH_N"]) / np.where(u_lag > 0.3, u_lag, 1.0), k_sched_min, K_STIFF)
            k_est = np.where(upd, k_est + kest_alpha * (k_raw - k_est), k_est)
            k_ff = k_est if sched else np.full(S, K_STIFF)
            kp = kp0 * (K_STIFF / k_ff)
            ki = kp / ti
            sp_r2 = np.where(sp_r < sp, np.minimum(sp, sp_r + CFG["F_RAMP_NPS"] * dt_c), sp_r)
            ramping = sp_r2 != sp
            spR = sp_reg(sp_r2)
            e = spR - f
            eP = np.where(ramping, 0.0, e)
            cap = np.minimum(u_max, th_ref - jaw_floor)
            uff = (spR - CFG["F_TOUCH_N"]) / k_ff
            uraw = uff + kp * eP + integ
            wantI = ~ramping & ((e > 0) | (e < -CFG["CTRL_I_DB_HI_N"]))
            pushH = (uraw >= cap) & (e > 0)
            pushL = (uraw <= u_min) & (e < 0)
            doI = wantI & ~pushH & ~pushL
            integ2 = np.where(doI, np.clip(integ + ki * e * dt_c, u_min - cap, cap), integ)
            uraw = np.where(doI, uff + kp * eP + integ2, uraw)
            over = f > soft
            integ2 = np.where(over, np.clip(integ2 - backoff, u_min - cap, cap), integ2)
            uraw = np.where(over, np.minimum(uraw, u - backoff), uraw)
            uraw = np.clip(uraw, u_min, cap)
            lo = u - rate - np.where(over, backoff, 0.0)
            u2 = np.clip(uraw, lo, u + rate)
            sp_r = np.where(fc_tick, sp_r2, sp_r)
            integ = np.where(fc_tick, integ2, integ)
            u = np.where(fc_tick, u2, u)
            cmd = np.where(fc_tick, th_ref - u, cmd)
            u_head = np.where(fc_tick, (u_head + 1) % (kest_lag + 1), u_head)  # per lane, on its own ticks
            u_hist[u_head[fc_tick], lanes[fc_tick]] = u[fc_tick]
            # motion (search profile) where the force loop is off
            mv_tick = tick & ~on
            c2, a2, v2 = motion_step(cmd, end, slow0, active, vnow, decel if decel.any() else None, mid0)
            cmd, active, vnow = np.where(mv_tick, c2, cmd), np.where(mv_tick, a2, active), np.where(mv_tick, v2, vnow)
        # event drain (end of the ms): contact -> fcStart; over-force -> FAULT (open 5 deg past max(cmd, c0))
        start = hit & ~on & ~fault
        t_contact = np.where(start & np.isnan(t_contact), t / 1000.0, t_contact)
        v_at = vnow
        th_ref = np.where(start, cmd + v_at * lag_s, th_ref)
        u = np.where(start, np.minimum(v_at * lag_s, (r_sp - CFG["F_TOUCH_N"]) / K_STIFF), u)
        sp_r = np.where(start, CFG["F_TOUCH_N"], sp_r)
        k_est = np.where(start, K_STIFF, k_est)
        u_hist[:, start] = 0.0
        u_head = np.where(start, 0, u_head)
        integ = np.where(start, 0.0, integ)
        active = active & ~start
        vnow = np.where(start, 0.0, vnow)
        on = on | start
        if trip_now.any():
            fault = fault | trip_now
            on = on & ~trip_now
            back = np.minimum(np.maximum(cmd, c0) + 5.0, CFG["JAW_OPEN_DEG"])
            end = np.where(trip_now, back, end)
            slow0 = np.where(trip_now, back, slow0)
            if mid0 is not None:
                mid0 = np.where(trip_now, back, mid0)
            active = active | trip_now
        if t > ms - last:
            F_sum += F
            I_sum += I_id + I_st * np.minimum(1.0, (2 * F * R_C + ten * V["x_f_mm"]) / 1000.0 / eta / Tst_j)
            n_sum += 1
        if record:
            rec["t"].append(t / 1000.0)
            rec["F"].append(F.copy())
            rec["th"].append(th.copy())
            rec["cmd"].append(cmd.copy())
    out = {"c0": c0, "t_contact": t_contact, "t_45": t_45, "t_hold": t_hold, "F_peak": F_peak,
           "F_final": F_sum / max(n_sum, 1), "I_hold": I_sum / max(n_sum, 1), "fault": fault, "v_jaw_touch3": v3,
           "v_jaw_touch2": v2_}
    if record:
        out["rec"] = rec
    return out


def fsr_mv(F):
    """fsr_model.h fsrMvFromForce, vectorised."""
    F = np.asarray(F, float)
    r = CFG["FSR_FIT_R1N_OHM"] * np.power(np.where(F > 0, F, 1.0), -CFG["FSR_FIT_EXP"])
    return np.where(F > 0, CFG["ADC_VREF_MV"] * CFG["R_FSR_FIXED_OHM"] / (r + CFG["R_FSR_FIXED_OHM"]), 0.0)


def fsr_force(mv):
    """fsr_model.h fsrForceFromMv, vectorised (span 1)."""
    mv = np.minimum(np.asarray(mv, float), CFG["ADC_VREF_MV"] - 1.0)
    ok = mv > CFG["FSR_MV_NOISE_FLOOR"]
    r = CFG["R_FSR_FIXED_OHM"] * (CFG["ADC_VREF_MV"] / np.where(ok, mv, 1.0) - 1.0)
    return np.where(ok, np.power(r / CFG["FSR_FIT_R1N_OHM"], -1.0 / CFG["FSR_FIT_EXP"]), 0.0)


def cmd_to_tgt(cmd, N):
    """Firmware jaw command -> integer pulse (1 us quantisation) -> jaw angle the servo aims for.
    pulse = 1500 + N * theta * US_PER_DEG (servo_map.h with the ratio; clamp widened by the ratio, reported)."""
    us = np.floor(1500.0 + N * cmd * US_PER_DEG + 0.5)
    return (us - 1500.0) / (N * US_PER_DEG)


SHIPPED = {"v_fast": CFG["JAW_SPEED_FAST_DPS"], "slow_zone": CFG["JAW_SLOW_ZONE_DEG"], "a_dec": 0.0,
           "mid_zone": CFG["JAW_MID_ZONE_DEG"], "v_mid": CFG["JAW_SPEED_MID_DPS"]}


def fw_profile(close=None, cap=10.0, w0_jaw=None):
    """Firmware settings for one requirement value. close: dict(v_fast, slow_zone, a_dec) of the close profile
    (default = rev A config.h as shipped, rev_a/config.json). a_dec > 0 makes the command decelerate at a_dec (deg/s^2) down to 20 deg/s at
    the slow-zone edge instead of stepping. The fast speed is capped at 0.9 x the drive's no-load jaw speed."""
    if cap >= 10.0:
        f_soft, f_trip = CFG["F_SOFT_LIMIT_N"], CFG["F_TRIP_N"]
    else:  # 8 N cap: keep the hold band [r, r + 0.6] = [6.0, 6.6] N (r = setpoint + F_HOLD_BIAS_N) clear of the soft limit; trip 0.5 N below the cap [A]
        f_soft, f_trip = cap - 1.0, cap - 0.5
    d = dict(SHIPPED if close is None else close)
    if w0_jaw is not None:
        d["v_fast"] = min(d["v_fast"], 0.9 * w0_jaw)
    d.update({"F_cap": cap, "F_soft": f_soft, "F_trip": f_trip})
    return d
