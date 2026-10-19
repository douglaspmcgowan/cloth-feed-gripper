"""Design-basis calculator for the ME102B cloth-feed gripper.

Every derived number in docs/gripper/DESIGN-BASIS.md comes from this script.
Inputs: cad/gripper/params.json, docs/gripper/research/actuators.csv,
cad/so101/Simulation/SO101/so101_old_calib.xml (MuJoCo, zero pose = arm horizontal),
plus the INPUT table below (each value tagged S sourced / D derived / A assumed).
Output: docs/gripper/design_basis_out.json (and a printed summary).

Run from the repository root:
    uv run --with mujoco --with numpy python docs/gripper/design_basis.py
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARAMS = ROOT / "cad/gripper/params.json"
ACT_CSV = ROOT / "docs/gripper/research/actuators.csv"
MJCF = ROOT / "cad/so101/Simulation/SO101/so101_old_calib.xml"
OUT = Path(__file__).with_name("design_basis_out.json")

G = 9.80665
KGCM = G / 100.0  # 1 kg*cm in N*m

# ---------------------------------------------------------------- inputs
INPUT = {
    # grip force budget (cloth_and_camera.md 2.3)
    "tension_N": (2.0, "A", "process/guide tension held against the feed (cloth_and_camera.md)"),
    "mu_pad_cloth": (0.4, "A", "TPU 95A on cotton, range 0.3-0.6 (cloth_and_camera.md)"),
    "mu_range": ([0.3, 0.4, 0.5, 0.6], "A", "sweep"),
    "SF_grip": (2.0, "A", "slip safety factor"),
    "F_cap_N": (10.0, "A", "pad force cap: keeps Fin Ray lattice compliant (cloth_and_camera.md)"),
    "pad_centroid_from_tip_mm": (5.0, "A", "tip-pad contact centroid measured up from the finger tip"),
    "eta": (0.85, "A", "combined mesh + pivot efficiency"),
    "r_c_design_mm": (65.0, "D", "design-point moment arm; chosen so >=3 standard PWM servos <=$25 hold LC1"),
    # actuator
    "V_servo": (6.0, "A", "gripper servo supply (dedicated regulator)"),
    "hold_fraction": (0.40, "A", "continuous hold <= 40 % of stall (actuators.md: 30-50 %)"),
    "pulse_span_us": (2000.0, "A", "500-2500 us maps to 180 deg"),
    "travel_deg": (180.0, "A", ""),
    "dF_resolution_N": (0.5, "A", "force change per servo deadband step (10 % of target)"),
    "theta_over_max_deg": (10.0, "A", "max finger rotation past first contact to reach F_cap"),
    "gearbox_limit_kgcm": (2.5, "S", "Pololu micro metal gearmotor 380:1/1000:1 instantaneous limit, https://www.pololu.com/category/60/micro-metal-gearmotors"),
    # finger compliance estimate
    "c_fea_mm_per_N": (2.80, "D", "tools.md scikit-fem P1 smoke run, E=26 MPa, L=60 mm (stiff-biased)"),
    "E_fea_MPa": (26.0, "A", "value used in that run"),
    "E_tpu_xy_MPa": (67.0, "S", "Ultimaker TPU 95A TDS, ASTM D3039 XY, https://um-support-files.ultimaker.com/materials/2.85mm/tds/TPU-95A/Ultimaker-TPU95A-TDS-v5.00.pdf"),
    "E_tpu_z_MPa": (56.0, "S", "same TDS, Z"),
    # gears
    "KA": (1.25, "A", "application factor on LC2 (impact at contact)"),
    "SF_static": (1.5, "A", "LC2 vs X-Y tensile"),
    "SF_fatigue": (1.5, "A", "LC1 vs fatigue strength at N_design"),
    "SF_overload": (1.0, "A", "LC3 (stall, one finger blocked, <=0.2 s) vs X-Y tensile: no fracture"),
    "N_design": (1e5, "A", "grip cycles for fatigue sizing"),
    "face_width_mm": (6.0, "S", "params.json gear.face_width"),
    # arm / payload
    "hold_fraction_arm": (0.50, "A", "arm joints hold <= 50 % of stall (so101.md)"),
    "dyn_accel_g": (0.5, "A", "vertical acceleration during moves, in g"),
    "dyn_limit_fraction": (0.8, "A", "dynamic peak <= 80 % of stall"),
    "tension_vertical_offset_m": (0.05, "A", "work-cell rule: shoulder_lift axis within +-50 mm of the tension line"),
    "bed_height_m": (0.10, "A", "sewing bed above the table the arm base sits on"),
    "tilt_max_deg": (45.0, "A", "gripper axis within 45 deg of straight down at the bed"),
    # mass model of the new gripper (d = distance past horn face H along the roll axis)
    "H_to_pivot_mm": (40.7, "D", "params.json: body_y - shaft_from_bottom + wall + mount_t"),
    "servo_design": ("A17 DSServo DS3218MG", "A", "design-point servo for mass/torque bookkeeping; trade study decides"),
    "cloth_g": (13.5, "D", "300x300 mm, 150 g/m^2 cotton (cloth_and_camera.md)"),
    "camera_g": (10.0, "A", "32x32 UVC module (cloth_and_camera.md)"),
    "fsr_wiring_g": (5.0, "A", "FSR, backing puck, wires, connector"),
    "fasteners_g": (8.0, "A", "README.md estimate"),
}
V = {k: v[0] for k, v in INPUT.items()}

KITS = {  # arm servo stall torque at the kit supply
    "C001_5V": (16.5 * KGCM, "S README 6 V rating used for the 5 V kit (A: 5 V gives slightly less)"),
    "C001_7p4V": (19.5 * KGCM, "S Seeed C001"),
    "C018_12V": (30.0 * KGCM, "S Feetech C018"),
}

LEWIS_Y = {12: .245, 14: .277, 16: .296, 18: .309, 20: .322, 24: .337, 26: .346,
           28: .353, 30: .359, 34: .371, 36: .378, 38: .384}  # gears.md section 5

MATERIALS = {  # tensile X-Y MPa [S], fatigue sigma_max at 1e5 cycles MPa, tag of fatigue value
    "PLA": (35.0, 22.5, "D Basquin fit, gears.md 2.1"),
    "PETG": (51.0, 0.60 * 51.0, "A PLA ratio 22.5/37.2 applied"),
    "PA6-CF": (102.0, 57.0, "S gear-level: Onyx m1 z20 b6 Lewis 57 MPa at 6.3e6 cycles (gears.md 3)"),
    "POM": (69.0, 32.0, "S Delrin flexural fatigue 32 MPa at 1e6 (gears.md 2.2)"),
    "Al6061-T6": (276.0, 97.0, "S fatigue 97 MPa at 5e8 (gears.md 2.2)"),
}

GEARS = [(1.0, 24), (1.25, 24), (1.5, 18), (1.5, 20)]


def r(x, n=3):
    return None if x is None else float(round(x, n))


# ---------------------------------------------------------------- grip
def grip(P):
    f, k = P["finger"], P["knuckle"]
    n_req = {str(mu): V["SF_grip"] * V["tension_N"] / (2 * mu) for mu in V["mu_range"]}
    F_t = V["SF_grip"] * V["tension_N"] / (2 * V["mu_pad_cloth"])
    root = k["root_offset"] + k["root_thickness"]
    r_cad = root + f["length"] - V["pad_centroid_from_tip_mm"]
    x_f = P["gear"]["module"] * P["gear"]["teeth"] / 2 - f["closed_gap"] / 2
    viewer_rc = math.hypot(x_f, -root - f["length"] / 2)  # what viewer.html uses
    tip_radial = math.hypot(x_f, root + f["length"])
    out = {"N_required_by_mu": {m: r(v) for m, v in n_req.items()}, "F_target_N": r(F_t),
           "F_cap_N": V["F_cap_N"], "r_c_current_cad_mm": r(r_cad, 1),
           "r_c_viewer_mm": r(viewer_rc, 1), "tip_radial_mm": r(tip_radial, 1),
           "r_c_design_mm": V["r_c_design_mm"],
           "finger_length_for_design_mm": r(V["r_c_design_mm"] - root + V["pad_centroid_from_tip_mm"], 1)}
    for tag, rc in (("current", r_cad), ("design", V["r_c_design_mm"])):
        for lc, F in (("LC1", F_t), ("LC2", V["F_cap_N"])):
            T = 2 * F * rc / 1000 / V["eta"]
            out[f"T_servo_{lc}_{tag}_Nm"] = r(T)
            out[f"T_servo_{lc}_{tag}_kgcm"] = r(T / KGCM, 2)
            out[f"T_stall_needed_{lc}_{tag}_kgcm"] = r(T / KGCM / V["hold_fraction"], 1) if lc == "LC1" else None
    # stiffness window (per finger, at the tip-pad contact), design arm
    rc = V["r_c_design_mm"]
    db_deg = 3.0 * V["travel_deg"] / V["pulse_span_us"]  # DS3218MG deadband 3 us (actuators.csv)
    k_min = V["F_cap_N"] / (rc * math.radians(V["theta_over_max_deg"]))
    k_max = V["dF_resolution_N"] / (rc * math.radians(db_deg))
    k_def = 1.0
    c_scaled = V["c_fea_mm_per_N"] * V["E_fea_MPa"] / np.array([V["E_tpu_xy_MPa"], V["E_tpu_z_MPa"]])
    L_d = out["finger_length_for_design_mm"]
    c_scaled_Ld = c_scaled * (L_d / f["length"]) ** 3
    theta_min = -math.degrees((f["closed_gap"] / 2 + V["F_cap_N"] / k_min) / rc)
    out.update({
        "deadband_deg": r(db_deg), "k_tip_min_N_per_mm": r(k_min), "k_tip_max_N_per_mm": r(k_max),
        "k_tip_default_N_per_mm": k_def,
        "overtravel_LC1_mm_default": r(F_t / k_def, 2), "overtravel_cap_mm_default": r(V["F_cap_N"] / k_def, 2),
        "theta_over_LC1_deg_default": r(math.degrees(F_t / k_def / rc), 2),
        "theta_over_cap_deg_default": r(math.degrees(V["F_cap_N"] / k_def / rc), 2),
        "theta_min_deg_worst": r(theta_min, 2),
        "c_estimate_L60_mm_per_N_[E_xy,E_z]": [r(x) for x in c_scaled],
        "c_estimate_Ldesign_mm_per_N_[E_xy,E_z]": [r(x) for x in c_scaled_Ld],
        "overtravel_needed_current_cad_mm_5N_[c_lo,c_hi]": [r(F_t * c_scaled.min(), 1), r(F_t * V["c_fea_mm_per_N"], 1)],
    })
    return out


# ---------------------------------------------------------------- actuators
def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def torque_at(row, v):
    lo, vlo = fnum(row["torque_low_kgcm"]), fnum(row["torque_low_at_V"])
    hi, vhi = fnum(row["torque_high_kgcm"]), fnum(row["torque_high_at_V"])
    pts = sorted([p for p in ((vlo, lo), (vhi, hi)) if p[0] and p[1]])
    if not pts:
        return None
    if len(pts) == 1 or v <= pts[0][0]:
        vv, tt = pts[0]
        return tt * min(1.0, v / vv)  # scale down below the lowest rated voltage (A)
    if v >= pts[-1][0]:
        return pts[-1][1]  # no extrapolation above the top rating
    (v0, t0), (v1, t1) = pts
    return t0 + (t1 - t0) * (v - v0) / (v1 - v0)


def actuators(gr):
    rows = list(csv.DictReader(ACT_CSV.open(encoding="utf-8")))
    F = gr["F_target_N"]
    servos, motors = [], []
    for row in rows:
        cat = row["category"]
        if "continuous" in cat:
            continue
        if row["id"].startswith("M"):
            T = fnum(row["torque_high_kgcm"])
            lim = V["gearbox_limit_kgcm"] if row["id"] in ("M02", "M03") else (2.0 if row["id"].startswith("M0") and row["vendor"].startswith("Pololu") else None)
            motors.append({"id": row["id"], "model": row["model"], "price": fnum(row["price_usd"]),
                           "mass_g": fnum(row["weight_g"]), "stall_kgcm": T, "gearbox_limit_kgcm": lim})
            continue
        T = torque_at(row, V["V_servo"])
        if T is None:
            continue
        Th = V["hold_fraction"] * T * KGCM
        rmax = Th * V["eta"] / (2 * F) * 1000
        servos.append({"id": row["id"], "model": row["model"], "price": fnum(row["price_usd"]),
                       "mass_g": fnum(row["weight_g"]), "feedback": row["feedback"],
                       "stall_kgcm_at_V": r(T, 2), "hold_Nm": r(Th), "r_max_mm": r(rmax, 1),
                       "passes_current_cad": rmax >= gr["r_c_current_cad_mm"],
                       "passes_design": rmax >= gr["r_c_design_mm"],
                       "stock_note": "out of stock" if "out of stock" in row["notes"] or "sold out" in row["notes"] else ""})
    servos.sort(key=lambda s: -s["r_max_mm"])
    # DC gearmotor fallback: reduction needed after the gearbox so the gearbox stays under its limit
    need = {}
    for tag in ("current", "design"):
        for lc in ("LC1", "LC2"):
            T = gr[f"T_servo_{lc}_{tag}_kgcm"]
            need[f"ratio_{lc}_{tag}"] = r(T / V["gearbox_limit_kgcm"], 2)
    return {"servos_at_%.1fV" % V["V_servo"]: servos, "gearmotors": motors, "gearmotor_extra_reduction": need,
            "n_pass_current": sum(s["passes_current_cad"] for s in servos),
            "n_pass_design": sum(s["passes_design"] for s in servos),
            "pass_design_ids": [s["id"] for s in servos if s["passes_design"]]}


# ---------------------------------------------------------------- gears
def gears(gr, act):
    b = V["face_width_mm"]
    ds = next(s for s in act["servos_at_%.1fV" % V["V_servo"]] if s["id"] == "A17")
    T_stall = ds["stall_kgcm_at_V"] * KGCM
    Tm = {"LC1": gr["T_servo_LC1_design_Nm"] / 2, "LC2": gr["T_servo_LC2_design_Nm"] / 2 * V["KA"],
          "LC3": T_stall}
    allow = {}
    for mat, (st, sf, _) in MATERIALS.items():
        allow[mat] = {"LC1": sf / V["SF_fatigue"], "LC2": st / V["SF_static"], "LC3": st / V["SF_overload"]}
    table = []
    for m, z in GEARS:
        per_Nm = 2 * 1000 / (m * z) / (b * m * LEWIS_Y[z])  # MPa per N*m of mesh torque
        row = {"m": m, "z": z, "a_mm": m * z, "sigma_per_Nm": r(per_Nm, 2)}
        for lc, T in Tm.items():
            s = per_Nm * T
            row[f"sigma_{lc}"] = r(s, 1)
            row[f"pass_{lc}"] = [mat for mat in MATERIALS if s <= allow[mat][lc]]
        table.append(row)
    return {"mesh_torque_Nm": {k: r(v) for k, v in Tm.items()},
            "stall_servo": "A17 at %.1f V" % V["V_servo"],
            "allowables_MPa": {m: {k: r(v, 2) for k, v in d.items()} for m, d in allow.items()},
            "lewis_table": table}


# ---------------------------------------------------------------- payload (MuJoCo)
def mass_model(P, gr, act):
    ds = next(s for s in act["servos_at_%.1fV" % V["V_servo"]] if s["id"] == "A17")
    Hp = V["H_to_pivot_mm"]
    L_d = gr["finger_length_for_design_mm"]
    L0 = P["finger"]["length"]
    root = P["knuckle"]["root_offset"] + P["knuckle"]["root_thickness"]
    items = [  # (name, g, d_mm past H, tag)
        ("housing PLA (CAD)", 18.7, 25.0, "D gripper_concept.py mass table; d A"),
        ("knuckles PLA (CAD)", 6.0, Hp, "D"),
        ("fingers TPU (CAD scaled to design length)", 8.8 * L_d / L0, Hp + root + L_d / 3, "D"),
        ("servo " + ds["model"], ds["mass_g"], 29.0, "S mass; d D from concept layout"),
        ("horn, pins, fasteners", V["fasteners_g"], 20.0, "A"),
        ("FSR + wiring", V["fsr_wiring_g"], 40.0, "A"),
        ("cloth at tip", V["cloth_g"], Hp + gr["r_c_design_mm"], "D"),
    ]
    cam = ("wrist camera (optional)", V["camera_g"], 20.0, "A")
    return items, cam


def arm(P, gr, act):
    model = mujoco.MjModel.from_xml_path(str(MJCF))
    data = mujoco.MjData(model)
    jid = {model.joint(i).name: i for i in range(model.njnt)}
    bg, bj = model.body("gripper").id, model.body("moving_jaw_so101_v1").id
    q = lambda name: model.jnt_qposadr[jid[name]]
    names = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]

    def grav(qpos):
        data.qpos[:] = qpos
        data.qvel[:] = 0
        mujoco.mj_forward(model, data)
        return {n: float(data.qfrc_bias[model.jnt_dofadr[jid[n]]]) for n in names}

    zero = np.zeros(model.nq)
    stock = grav(zero)
    m_g, m_j = model.body_mass[bg], model.body_mass[bj]
    model.body_mass[bg] = 1e-9
    model.body_mass[bj] = 1e-9
    mujoco.mj_setConst(model, data)
    arm_only = grav(zero)
    H_world = data.xpos[bg].copy()
    sl_anchor = data.xanchor[jid["shoulder_lift"]].copy()
    lever_H = float(np.linalg.norm((H_world - sl_anchor)[:2]))

    items, cam = mass_model(P, gr, act)

    def set_gripper(its):
        m = sum(x[1] for x in its) / 1000
        d = sum(x[1] * x[2] for x in its) / sum(x[1] for x in its) / 1000
        model.body_mass[bg] = m
        model.body_ipos[bg] = [0, 0, -d]
        model.body_inertia[bg] = [1e-6, 1e-6, 1e-6]
        mujoco.mj_setConst(model, data)
        return m, d

    res = {"stock_gravity_Nm_full_ext": {k: r(v) for k, v in stock.items()},
           "arm_only_gravity_Nm_full_ext": {k: r(v) for k, v in arm_only.items()},
           "lever_shoulder_lift_to_H_mm": r(lever_H * 1000, 1),
           "stock_gripper_mass_g": r((m_g + m_j) * 1000, 1)}
    cases = {"no_camera": items, "with_camera": items + [cam]}
    res["mass_items"] = [{"name": n, "g": r(g, 1), "d_mm": r(d, 1), "tag": t} for n, g, d, t in items + [cam]]
    tip_d_extra = gr["r_c_design_mm"] + V["pad_centroid_from_tip_mm"]
    for cname, its in cases.items():
        m, d = set_gripper(its)
        full = grav(zero)
        res[cname] = {"mass_g": r(m * 1000, 1), "com_past_H_mm": r(d * 1000, 1),
                      "gravity_full_ext_Nm": {k: r(v) for k, v in full.items()}}
    # work-envelope sweep: fingertip at bed height, gripper axis within tilt_max of straight down
    set_gripper(items)
    fj = jid["wrist_flex"]
    tip_d = (V["H_to_pivot_mm"] + tip_d_extra) / 1000
    z_target = V["bed_height_m"] + 0.005
    tilt_max = math.radians(V["tilt_max_deg"])
    t = np.array([0, 0, -1.0])
    rng = lambda n, k: np.linspace(model.jnt_range[jid[n]][0], model.jnt_range[jid[n]][1], k)
    sweep = []
    for sl in rng("shoulder_lift", 81):
        for el in rng("elbow_flex", 81):
            for wf in rng("wrist_flex", 41):
                qp = zero.copy()
                qp[q("shoulder_lift")], qp[q("elbow_flex")], qp[q("wrist_flex")] = sl, el, wf
                data.qpos[:] = qp
                mujoco.mj_kinematics(model, data)
                v = -data.xmat[bg].reshape(3, 3)[:, 2]
                if v @ t < math.cos(tilt_max):
                    continue
                tip = data.xpos[bg] + v * tip_d
                if abs(tip[2] - z_target) > 0.008 or data.xpos[bg][2] < tip[2]:
                    continue
                pan = data.xanchor[jid["shoulder_pan"]]
                reach = float(np.linalg.norm((tip - pan)[:2]))
                gv = grav(qp)
                sweep.append((reach, gv["shoulder_lift"], gv["elbow_flex"], gv["wrist_flex"], float(tip[2]),
                              float(sl), float(el), float(wf), math.degrees(math.acos(min(1.0, float(v @ t))))))
    sweep.sort()
    res["work_pose_sweep_n"] = len(sweep)
    res["work_pose_reach_range_m"] = [r(sweep[0][0], 3), r(sweep[-1][0], 3)] if sweep else None
    res["work_pose_max_tau_Nm"] = {"shoulder_lift": r(max(abs(x[1]) for x in sweep)), "elbow_flex": r(max(abs(x[2]) for x in sweep)),
                                   "wrist_flex": r(max(abs(x[3]) for x in sweep))} if sweep else None
    tau_t = V["tension_N"] * V["tension_vertical_offset_m"]
    # per kit: max reach at which the feed pose (gravity + tension moment) holds within the arm hold rule
    kits = {}
    for kit, (Ts, src) in KITS.items():
        allow = V["hold_fraction_arm"] * Ts
        # best pose per 10 mm reach bin (the arm picks its configuration); feasible if its worst joint fits
        util = lambda s: max(abs(s[1]) + tau_t, abs(s[2]) + tau_t, abs(s[3]) + tau_t)
        bins = {}
        for s_ in sweep:
            k_ = int(s_[0] * 100)
            bins[k_] = min(bins.get(k_, 9e9), util(s_))
        reach_all = None
        for k_ in sorted(bins):
            if bins[k_] > allow:
                break
            reach_all = (k_ + 1) / 100
        first_bad = next((k_ / 100 for k_ in sorted(bins) if bins[k_] > allow), None)
        mm_budget = (allow - abs(arm_only["shoulder_lift"])) / G  # kg*m about shoulder_lift, full extension
        mm_budget_t = (allow - abs(arm_only["shoulder_lift"]) - tau_t) / G
        kits[kit] = {
            "stall_Nm": r(Ts), "source": src, "hold_allow_Nm": r(allow),
            "full_ext_gravity_only_ok_no_camera": abs(res["no_camera"]["gravity_full_ext_Nm"]["shoulder_lift"]) <= allow,
            "full_ext_gravity_only_ok_with_camera": abs(res["with_camera"]["gravity_full_ext_Nm"]["shoulder_lift"]) <= allow,
            "full_ext_gravity_plus_tension_ok_no_camera": abs(res["no_camera"]["gravity_full_ext_Nm"]["shoulder_lift"]) + tau_t <= allow,
            "mass_moment_budget_gmm_full_ext": r(mm_budget * 1e6, 0),
            "mass_moment_budget_gmm_full_ext_with_tension": r(mm_budget_t * 1e6, 0),
            "max_mass_g_at_40mm_gravity_only": r(mm_budget * 1e6 / (lever_H * 1000 + 40), 1),
            "max_mass_g_at_40mm_with_tension": r(mm_budget_t * 1e6 / (lever_H * 1000 + 40), 1),
            "feed_pose_ok_up_to_reach_m": r(reach_all, 3),
            "feed_pose_first_failing_bin_m": r(first_bad, 3),
            "dynamic_full_ext_ok": (abs(res["no_camera"]["gravity_full_ext_Nm"]["shoulder_lift"]) * (1 + V["dyn_accel_g"]) <= V["dyn_limit_fraction"] * Ts),
        }
    # new gripper mass-moment about shoulder_lift (full extension)
    for cname, its in cases.items():
        res[cname]["mass_moment_gmm"] = r(sum(g * (lever_H * 1000 + d) for _, g, d, _ in its), 0)
    res["tension_moment_Nm"] = r(tau_t)
    # worst-direction tension at full extension, for contrast
    set_gripper(items)
    data.qpos[:] = zero
    mujoco.mj_forward(model, data)
    tipw = data.xpos[bg] + (-data.xmat[bg].reshape(3, 3)[:, 2]) * tip_d
    jacp = np.zeros((3, model.nv))
    mujoco.mj_jac(model, data, jacp, None, tipw, bg)
    col = jacp[:, model.jnt_dofadr[jid["shoulder_lift"]]]
    res["tension_worst_direction_full_ext_Nm"] = r(V["tension_N"] * float(np.linalg.norm(col)))
    res["kits"] = kits
    res["sweep_sample"] = [dict(zip(["reach_m", "tau_sl", "tau_el", "tau_wf", "tip_z", "q_sl", "q_el", "q_wf", "tilt_deg"],
                                    [r(x, 4) for x in s])) for s in sweep[:: max(1, len(sweep) // 12)]]
    return res


# ---------------------------------------------------------------- duty cycle
def duty():
    ph = {"approach_touchdown": 4.0, "close": 0.5, "lift_move_to_needle": 5.0,
          "feed_hold": 20.0, "release": 0.5, "return": 5.0}  # s, A
    seam_mm, feed_mm_s = 200.0, 10.0  # A
    cyc = sum(ph.values())
    hold = ph["lift_move_to_needle"] + ph["feed_hold"] + ph["close"]
    spm_max, stitch_mm = 1100, 2.5  # S Singer 4423; A stitch length
    return {"phases_s": ph, "cycle_s": cyc, "cycles_per_hour": r(3600 / cyc, 1),
            "hold_fraction": r(hold / cyc), "seam_mm": seam_mm, "feed_mm_s": feed_mm_s,
            "feed_time_check_s": seam_mm / feed_mm_s,
            "machine_max_feed_mm_s": r(spm_max * stitch_mm / 60, 1),
            "demo_spm_at_feed": r(feed_mm_s * 60 / stitch_mm, 0),
            "servo_I2R_mean_fraction_of_stall": r(V["hold_fraction"] ** 2 * hold / cyc),
            "hours_to_N_design": r(V["N_design"] / (3600 / cyc), 0)}


def main():
    P = json.loads(PARAMS.read_text(encoding="utf-8"))
    gr = grip(P)
    act = actuators(gr)
    ge = gears(gr, act)
    ar = arm(P, gr, act)
    du = duty()
    out = {"inputs": {k: {"value": v[0], "tag": v[1], "note": v[2]} for k, v in INPUT.items()},
           "grip": gr, "actuators": act, "gears": ge, "arm": ar, "duty_cycle": du}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"grip": gr, "n_pass": [act["n_pass_current"], act["n_pass_design"], act["pass_design_ids"]],
                      "ratio": act["gearmotor_extra_reduction"], "gears": ge, "duty": du,
                      "arm": {k: v for k, v in ar.items() if k not in ("sweep_sample", "mass_items")}}, indent=1))
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
