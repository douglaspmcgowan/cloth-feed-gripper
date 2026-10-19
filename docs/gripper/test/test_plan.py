"""Verification test plan calculator for the ME102B cloth-feed gripper.

Owner of every number in `docs/gripper/test/`. It reads the analysis outputs
already in the repository, works out what each bench test should read, sizes the
instruments (uncertainty budgets), picks sample sizes, totals the equipment list,
and writes:

- `test_plan_out.json` and `test_plan_stdout.txt` (this folder)
- `verification_matrix.csv` and the generated table in `VERIFICATION-MATRIX.md`
- the generated tables in `MEASUREMENT-SIZING.md`, `EQUIPMENT.md` and `README.md`
- `datasheets/<TP-id>.csv` and `datasheets/<TP-id>.html` (one-page data sheets)
- `datasheets/SIGNOFF.csv` and `datasheets/SIGNOFF.html` (one line per requirement)

Run from the repository root (about 2 s, deterministic, no network):

    python docs/gripper/test/test_plan.py

Needs numpy and scipy (`uv run --with numpy --with scipy python docs/gripper/test/test_plan.py`).
Tags follow the analysis notes: [S] sourced (URL + retrieval date), [D] derived here
or by the script named, [A] assumed with the reason.
"""
from __future__ import annotations

import csv
import argparse
import hashlib
import html
import io
import json
import math
import re
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE / "tools"))
from analyze_log import decide  # noqa: E402  one PASS / FAIL / INDETERMINATE rule for every limit
RETRIEVED = "2026-10-11"
SEED = 20261011  # used only by the Monte Carlo cross-check of the tolerance factor
R10_RULING_DATE = "2026-10-11"

# ---------------------------------------------------------------------------
# Inputs read from the repository
# ---------------------------------------------------------------------------
INPUT_FILES = {
    "design_basis": ROOT / "docs/gripper/DESIGN-BASIS.md",
    "design_basis_out": ROOT / "docs/gripper/design_basis_out.json",
    "fw_sim": ROOT / "analysis/gripper/firmware_sim/results/fw_sim.json",
    "dyno": ROOT / "analysis/gripper/results/dyno.json",
    "fea_summary": ROOT / "analysis/gripper/results/fea_summary.json",
    "payload_torque": ROOT / "analysis/gripper/results/payload_torque.json",
    "config_h": ROOT / "firmware/gripper/config.h",
    "bom": ROOT / "cad/gripper/drawings/BOM.md",
    "cad_fitcheck": ROOT / "cad/gripper/out/fitcheck.json",
}


def configure_root(root: Path) -> None:
    """Point generation at a repository copy (used by mutation tests)."""
    global ROOT, HERE, INPUT_FILES
    ROOT = root.resolve()
    HERE = ROOT / "docs/gripper/test"
    INPUT_FILES = {
        "design_basis": ROOT / "docs/gripper/DESIGN-BASIS.md",
        "design_basis_out": ROOT / "docs/gripper/design_basis_out.json",
        "fw_sim": ROOT / "analysis/gripper/firmware_sim/results/fw_sim.json",
        "dyno": ROOT / "analysis/gripper/results/dyno.json",
        "fea_summary": ROOT / "analysis/gripper/results/fea_summary.json",
        "payload_torque": ROOT / "analysis/gripper/results/payload_torque.json",
        "config_h": ROOT / "firmware/gripper/config.h",
        "bom": ROOT / "cad/gripper/drawings/BOM.md",
        "cad_fitcheck": ROOT / "cad/gripper/out/fitcheck.json",
    }


def r10_work_cell_rule(cad_mass: dict) -> dict:
    """Derive the ruled R10 reach limits from the current CAD mass record."""
    required = ("total_g_incl_cloth", "com_u_past_H", "mass_moment_gmm", "budget_gmm",
                "stock_loading_gmm", "revision", "items")
    missing = [key for key in required if key not in cad_mass]
    if missing:
        raise ValueError("CAD fit check mass object missing key(s): " + ", ".join(missing))
    try:
        fingertip_u = next(item["u_past_H"] for item in cad_mass["items"]
                           if item["name"] == "cloth at the pad [D DB]")
    except (KeyError, StopIteration, TypeError) as exc:
        raise ValueError("CAD fit check mass object missing cloth-at-pad fingertip position") from exc
    mass_g = cad_mass["total_g_incl_cloth"]
    com_past_h_mm = cad_mass["com_u_past_H"]
    com_limit_mm = cad_mass["budget_gmm"] / mass_g
    fingertip_past_com_mm = fingertip_u - com_past_h_mm
    full_extension_lever_mm = cad_mass["mass_moment_gmm"] / mass_g
    mass_moment_gmm = mass_g * full_extension_lever_mm
    budget_use_pct = 100 * mass_moment_gmm / cad_mass["budget_gmm"]
    max_mass_at_full_extension_g = cad_mass["budget_gmm"] / full_extension_lever_mm
    return {
        "ruling_date": R10_RULING_DATE,
        "revision": cad_mass["revision"],
        "budget_gmm": cad_mass["budget_gmm"],
        "mass_g": mass_g,
        "mass_moment_gmm": mass_moment_gmm,
        "budget_use_pct": budget_use_pct,
        "max_mass_at_full_extension_g": max_mass_at_full_extension_g,
        "stock_loading_gmm": cad_mass["stock_loading_gmm"],
        "com_past_h_mm": com_past_h_mm,
        "pad_past_h_mm": fingertip_u,
        "fingertip_past_com_mm": fingertip_past_com_mm,
        "com_limit_mm": com_limit_mm,
        "fingertip_limit_mm": com_limit_mm + fingertip_past_com_mm,
    }

# R15 and R19 were open with Douglas; he ruled 2026-10-12 for the "proposed" values (8 N, 0.75 s). "written" is the
# superseded history column. Every result is still reported at both.
OPEN = {
    "R15_cap_N": {"written": 10.0, "proposed": 8.0},
    "R19_close_s": {"written": 0.50, "proposed": 0.75},
}

# One hardware-scope source for every procedure. ``arm`` is absent, off, or gated;
# ``gripper`` is none, bench, or on-arm. The checker consumes this table too.
HARDWARE_SCOPES = {
    "TP-01": ("off", "bench"), "TP-02": ("off", "bench"),
    "TP-03": ("off", "bench"), "TP-04": ("off", "bench"),
    "TP-05": ("off", "bench"), "TP-06": ("off", "bench"),
    "TP-07": ("off", "on-arm"), "TP-08": ("off", "bench"),
    "TP-09": ("absent", "none"), "TP-10": ("absent", "bench"),
    "TP-11": ("absent", "none"), "TP-12": ("absent", "none"),
    "TP-13": ("absent", "bench"), "TP-14": ("gated", "on-arm"),
    "TP-15": ("absent", "bench"), "TP-16": ("off", "bench"),
}

SCOPE_SENTENCES = {
    "absent": "The arm is not used in this procedure.",
    "off": "The arm is off and its power supply is disconnected for this whole procedure.",
    "gated": "The arm may be powered only by generated steps after their generated measurement gates pass.",
}
GRIPPER_SENTENCES = {
    "none": "The gripper is not powered or commanded in this procedure.",
    "bench": "The gripper is fixed in the bench fixture; the arm is not powered.",
    "on-arm": "The gripper is installed on the arm; obey the arm scope above before applying power.",
}


def sha16(path: Path) -> str:
    """First 16 hex digits of the SHA-256 of the file with line endings normalised to \\n, so the
    hash is the same on Windows (CRLF checkout) and Linux."""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:16]


def rule(limit: float, U: float, unit: str, side: str = "upper", digits: int = 3) -> str:
    """The three-outcome rule as text, so the matrix and the procedures print the same numbers
    the tools use. side = 'upper': the value must stay at or under the limit."""
    f = lambda x: ("%." + str(digits) + "g") % x
    if side == "upper":
        return ("PASS if value ≤ %s %s (limit − U); FAIL if value ≥ %s %s (limit + U); INDETERMINATE in between"
                % (f(limit - U), unit, f(limit + U), unit))
    return ("PASS if value ≥ %s %s (limit + U); FAIL if value ≤ %s %s (limit − U); INDETERMINATE in between"
            % (f(limit + U), unit, f(limit - U), unit))


def load_json(key: str) -> dict:
    return json.loads(INPUT_FILES[key].read_text(encoding="utf-8"))


def parse_config_h(path: Path) -> dict:
    """Numeric #defines from firmware/gripper/config.h."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*#define\s+(\w+)\s+(-?[0-9.]+)\b", line)
        if m:
            out[m.group(1)] = float(m.group(2))
    return out


def requirement_ids(design_basis_md: Path) -> list[str]:
    """Requirement ids R<n> from the table in DESIGN-BASIS section 1."""
    text = design_basis_md.read_text(encoding="utf-8")
    start = text.index("## 1. Requirements")
    end = text.index("## 2.", start)
    ids = re.findall(r"^\|\s*(R\d+)\s*\|", text[start:end], flags=re.M)
    return ids


def bom_total_mass_g(bom_md: Path) -> float:
    m = re.search(r"\*\*total on the arm[^|]*\*\*\s*\|[^|]*\|[^|]*\|[^|]*\|\s*\*\*([0-9.]+)\*\*", bom_md.read_text(encoding="utf-8"))
    if not m:
        raise ValueError("BOM total row not found in " + str(bom_md))
    return float(m.group(1))


# ---------------------------------------------------------------------------
# Small statistics helpers
# ---------------------------------------------------------------------------
def k_one_sided(n: int, coverage: float = 0.95, confidence: float = 0.90) -> float:
    """One-sided normal tolerance factor: mean + k*s bounds `coverage` of the
    population with `confidence`. Exact form via the noncentral t."""
    z_p = stats.norm.ppf(coverage)
    return float(stats.nct.ppf(confidence, df=n - 1, nc=z_p * math.sqrt(n)) / math.sqrt(n))


def success_run_n(reliability: float, confidence: float) -> int:
    """Zero-failure demonstration: n trials with no failure show reliability R at
    confidence C when R**n <= 1 - C."""
    return int(math.ceil(math.log(1.0 - confidence) / math.log(reliability)))


def rect_u(half_width: float) -> float:
    """Standard uncertainty of a rectangular distribution of half-width a."""
    return half_width / math.sqrt(3.0)


def budget(components: list[dict]) -> dict:
    """Root-sum-square of standard uncertainties; expanded with k = 2."""
    for c in components:
        if c["dist"] == "rect":
            c["u"] = rect_u(c["value"])
        elif c["dist"] == "normal":
            c["u"] = c["value"]
        else:
            raise ValueError(c["dist"])
    u_c = math.sqrt(sum(c["u"] ** 2 for c in components))
    dominant = max(components, key=lambda c: c["u"])["name"]
    return {"components": components, "u_c": u_c, "U_k2": 2.0 * u_c, "dominant": dominant}


def sample_size(mean: float, sigma: float, limit: float, side: str, n_max: int = 30) -> dict:
    """Smallest n (3..n_max) at which the predicted mean, with the one-sided 95 %/90 %
    tolerance bound, clears the limit. side = 'upper' (value must stay <= limit) or
    'lower' (value must stay >= limit)."""
    margin = (limit - mean) if side == "upper" else (mean - limit)
    for n in range(3, n_max + 1):
        if margin > 0 and k_one_sided(n) * sigma <= margin:
            return {"n": n, "margin": margin, "k": k_one_sided(n), "rule": "tolerance bound clears"}
    if margin <= 0:
        rule = "predicted to fail: 5 trials confirm the verdict"
    else:
        rule = "predicted to pass, but no n <= %d brings the 95/90 bound inside the margin: 5 trials give the estimate" % n_max
    return {"n": 5, "margin": margin, "k": k_one_sided(5), "rule": rule}


# ---------------------------------------------------------------------------
# Expected values from the analysis (what each test should read)
# ---------------------------------------------------------------------------
def first_time_at_or_above(t, F, level):
    for ti, fi in zip(t, F):
        if fi >= level:
            return ti
    return None


def expected_values(fw, dyno, fea, db_out, pay, cfg, bom_mass, cad_mass):
    e = {}
    # Close timing from the compiled-firmware simulation, one per R12 stiffness case.
    close = {}
    for name, case in fw["cases"].items():
        ser = fw["series"][name]
        close[name] = {
            "k_N_per_mm": case["k_tip"],
            "t_contact_s": case["t_contact_s"],
            "t_F4p5_s": case["t_F90_s"],
            "t_F5p0_s": first_time_at_or_above(ser["t"], ser["F"], 5.0),
            "t_HOLD_s": case["t_hold_s"],
            "hold_path": case.get("hold_path"),
            "F_peak_N": case["F_max_N"],
            "F_hold_mean_N": case["F_hold_mean_N"],
            "F_hold_min_N": case["F_hold_min_N"],
            "theta_c0_deg": case["c0_deg"],
        }
    e["close"] = close
    tc = [c["t_contact_s"] for c in close.values()]
    t45 = [c["t_F4p5_s"] for c in close.values()]
    t5 = [c["t_F5p0_s"] for c in close.values()]
    t5_d7 = [c["t_F5p0_s"] for c in close.values() if c["k_N_per_mm"] >= 1.0]
    th = [c["t_HOLD_s"] for c in close.values()]
    # 4.5 N is the bottom of the firmware's FSR_TARGET band (setpoint - F_BAND_N).
    e["close_range"] = {"t_contact_s": [min(tc), max(tc)], "t_F4p5_s": [min(t45), max(t45)],
                        "t_F5p0_s": [min(t5), max(t5)], "t_F5p0_s_k_ge_1": [min(t5_d7), max(t5_d7)],
                        "t_HOLD_s": [min(th), max(th)]}
    # Run-to-run scatter of one gripper: the servo reads the pulse once per 20 ms frame,
    # so the frame phase at the command is uniform over one period [D], plus servo
    # variation 5 ms [A: no data; replace with the TP-03 scatter].
    frame_s = cfg["CONTROL_PERIOD_MS"] / 1000.0
    sigma_frame = frame_s / math.sqrt(12.0)
    sigma_servo = 0.005
    e["close_sigma_s"] = {"frame_phase": sigma_frame, "servo_A": sigma_servo,
                          "total": math.hypot(sigma_frame, sigma_servo)}
    # Hold force
    hold = [c["F_hold_mean_N"] for c in close.values()]
    peak = [c["F_peak_N"] for c in close.values()]
    e["hold_range_N"] = [min(hold), max(hold)]
    e["peak_range_N"] = [min(peak), max(peak)]
    e["hold_sigma_noise_N"] = max(r["F_hold_std_N"] for r in fw["noise"])
    # Sensor-fault injection (FSR reads 50 %) on the stiffest finger: the cap case.
    e["fsr50_peak_N"] = {k: v["F_max_N"] for k, v in fw["sensor_faults"].items() if "50pct" in k}
    # Force cap: squeeze cap U_max = (cap - F_CAP_MARGIN_N - touch) / K_stiff, both cap values (force_ctrl.h
    # CTRL_U_MAX_DEG; the 0.5 N margin entered the firmware with the gain schedule, controls.md O4).
    k_stiff = fw["derived"]["K_STIFF_N_PER_DEG"]
    r_c = cfg["R_C_MM"]
    n_per_deg_per_n_per_mm = r_c * math.pi / 180.0  # K = k * r_c * pi/180 (controls.md 4.1)
    lag_deg = 0.64  # lag-compensation allowance kept at the soft end (W2b-1 controls.md 4.2 item 7; the current note no longer states it) [A]
    cap = {}
    for label, cap_N in OPEN["R15_cap_N"].items():
        u_max = (cap_N - cfg.get("F_CAP_MARGIN_N", 0.0) - cfg["F_TOUCH_N"]) / k_stiff
        k_min_reach5 = (cfg["F_TARGET_DEFAULT_N"] - cfg["F_TOUCH_N"]) / u_max / n_per_deg_per_n_per_mm
        k_min_reach5_lag = (cfg["F_TARGET_DEFAULT_N"] - cfg["F_TOUCH_N"]) / (u_max - lag_deg) / n_per_deg_per_n_per_mm
        f_at_kmin = cfg["F_TOUCH_N"] + u_max * cfg["FINGER_K_MIN_N_PER_MM"] * n_per_deg_per_n_per_mm
        cap[label] = {
            "cap_N": cap_N,
            "U_max_deg": u_max,
            "F_max_softest_R12_finger_N": f_at_kmin,
            "k_min_to_reach_5N_N_per_mm": k_min_reach5,
            "k_min_to_reach_5N_with_0p64deg_lag_N_per_mm": k_min_reach5_lag,
            "trip_N_now": cfg["F_TRIP_N"],
            "soft_limit_N_now": cfg["F_SOFT_LIMIT_N"],
            "trip_margin_to_cap_N": cap_N - cfg["F_TRIP_N"],
            "fold_E56_N": fea["recommended"]["nonlinear_check"]["rec_bare_tip_limit_E56_N"],
            "fold_E56_nailA_N": fea["recommended"]["nonlinear_check"]["rec_nailA_tip_limit_E56_N"],
            "fsr50_peak_stiff_N": e["fsr50_peak_N"].get("fsr_reads_50pct@1.63"),
            "fsr50_passes": e["fsr50_peak_N"].get("fsr_reads_50pct@1.63") <= cap_N,
        }
    # Suggested firmware set for the proposed cap: same 1 N trip-to-cap gap scaled, and
    # the same 0.5 N soft-limit-to-trip gap as config.h [D from config.h ratios].
    prop = cap["proposed"]
    prop["suggested_trip_N"] = prop["cap_N"] - (OPEN["R15_cap_N"]["written"] - cfg["F_TRIP_N"]) / 2.0
    prop["suggested_soft_limit_N"] = prop["suggested_trip_N"] - (cfg["F_TRIP_N"] - cfg["F_SOFT_LIMIT_N"])
    prop["suggested_F_SET_MAX_N"] = prop["suggested_trip_N"] - (cfg["F_TRIP_N"] - cfg["F_SET_MAX_N"])
    e["cap"] = cap
    e["stall_trip_A"] = {"motion": cfg["STALL_CURRENT_A"], "force_loop": cfg["STALL_CURRENT_HOLD_A"]}
    e["jaw_floor"] = {"below_c0_deg": cfg["JAW_FLOOR_BELOW_C0_DEG"], "min_deg": cfg["JAW_MIN_DEG"]}
    # Slip: two pads, friction mu on each face -> capacity 2 mu F [D, DB R14].
    mu = 0.4
    e["slip"] = {"mu_A": mu, "F_hold_N": 5.0, "capacity_N": 2 * mu * 5.0, "tension_N": 2.0,
                 "sf": 2 * mu * 5.0 / 2.0}
    # Stall (R16): stall needed for the 0.792 N m hold at 40 %; predicted stall at the rail low end.
    t_hold = pay["grip"]["T_hold_Nm"]
    rs = dyno["rail_sensitivity"]
    e["stall"] = {"T_hold_Nm": t_hold, "stall_needed_Nm": t_hold / 0.40,
                  "stall_needed_kgcm": t_hold / 0.40 / 0.0980665,
                  "predicted_6p5V_Nm": _rail_stall(rs, "6.5"),
                  "predicted_6p35V_Nm": _rail_stall(rs, "6.35"),
                  "I_stall_A_fitA_fitB_6p5V": [rs["6p5V"]["A_mech"]["fit"]["I_stall_A"], rs["6p5V"]["B_elec"]["fit"]["I_stall_A"]],
                  "t_winding_125C_s_fitA_25_40": [dyno["test2_stall"]["A_mech_amb25"]["t_to_winding_limit_s"],
                                                  dyno["test2_stall"]["A_mech_amb40"]["t_to_winding_limit_s"]],
                  "lever_mm": 50.0}
    e["stall"]["force_at_lever_N"] = e["stall"]["predicted_6p5V_Nm"] / (e["stall"]["lever_mm"] / 1000.0)
    # Thermal (R26)
    th30 = dyno["test3_duty_cycle"]["thermal_30min"]
    e["thermal"] = {k: round(v["T_case_30min_C"], 1) for k, v in th30.items()}
    e["thermal_range_C"] = [min(e["thermal"].values()), max(e["thermal"].values())]
    e["thermal_limits_C"] = {"case": 60.0, "bare_mount": 50.0}
    # Mass and mass-moment (R10): budget and the BOM-based prediction.
    lever = db_out["arm"]["lever_shoulder_lift_to_H_mm"]
    budget_gmm = 43720.0  # DB R10 [D, design_basis.py]
    db_no_cam = db_out["arm"]["no_camera"]
    cloth_g, wiring_g = 13.5, 5.0
    com_db = db_no_cam["com_past_H_mm"]
    m_bom = bom_mass + cloth_g + wiring_g
    required_cad_keys = ("mass_moment_gmm", "budget_use")
    missing = [key for key in required_cad_keys if key not in cad_mass]
    if missing:
        raise ValueError("CAD fit check mass object missing key(s): " + ", ".join(missing))
    reach_rule = r10_work_cell_rule(cad_mass)
    cad_total = reach_rule["mass_g"]
    cad_com = reach_rule["com_past_h_mm"]
    reach_limit_com = reach_rule["com_limit_mm"]
    fingertip_past_com = reach_rule["fingertip_past_com_mm"]
    e["mass"] = {
        "lever_mm": lever, "budget_gmm": budget_gmm,
        "db_estimate_g": db_no_cam["mass_g"], "db_com_mm": com_db, "db_mass_moment_gmm": db_no_cam["mass_moment_gmm"],
        "db_check_gmm": db_no_cam["mass_g"] * (lever + com_db),
        "bom_on_arm_g": bom_mass, "bom_plus_cloth_wiring_g": m_bom,
        "bom_mass_moment_at_db_com_gmm": m_bom * (lever + com_db),
        "bom_fraction_of_budget": m_bom * (lever + com_db) / budget_gmm,
        "max_mass_at_db_com_g": budget_gmm / (lever + com_db),
        "stretch_gmm": 33380.0,
        # Revision-qualified CAD prediction; the DB/BOM fields above remain as estimate history.
        "cad_total_g": cad_total, "cad_com_mm": cad_com,
        "cad_mass_moment_gmm": cad_mass["mass_moment_gmm"],
        "cad_fraction_of_budget": cad_mass["budget_use"], "cad_revision": cad_mass["revision"],
        "reach_limit_com_mm": reach_limit_com, "full_reach_com_mm": lever + cad_com,
        "fingertip_past_com_mm": fingertip_past_com,
        "reach_limit_fingertip_mm": reach_limit_com + fingertip_past_com,
        "work_cell_existing_fingertip_limit_mm": 300.0,
        "powered_pose_rules": [
            {"name": "feed pose", "commanded": True, "gate_step": 7, "command_step": 9,
             "max_fingertip_reach_mm": min(300.0, reach_limit_com + fingertip_past_com) - 1.0,
             "max_com_reach_mm": min(300.0, reach_limit_com + fingertip_past_com) - 1.0 - fingertip_past_com},
            {"name": "farthest measurement pose", "commanded": True, "gate_step": 8, "command_step": 9,
             "max_fingertip_reach_mm": min(300.0, reach_limit_com + fingertip_past_com) - 1.0,
             "max_com_reach_mm": min(300.0, reach_limit_com + fingertip_past_com) - 1.0 - fingertip_past_com},
            {"name": "full extension", "commanded": False, "gate_step": 8,
             "com_reach_mm": lever + cad_com},
        ],
        "history": {
            "design_basis_mass_g": db_no_cam["mass_g"],
            "design_basis_com_mm": com_db,
            "design_basis_moment_gmm": db_no_cam["mass_moment_gmm"],
            "intermediate_bom_mass_g": 144.4,
            "intermediate_bom_moment_gmm": 50511.0,
            "softest_hold_prediction_N": 5.02,
        },
    }
    gate_limit = min(300.0, reach_limit_com + fingertip_past_com)
    gate_uncertainty = 3.0
    gate_decision = ("PASS if largest fingertip reach ≤ %.1f mm; FAIL if largest fingertip reach ≥ %.1f mm; "
                     "INDETERMINATE in between or if spread > 4.0 mm"
                     % (gate_limit - gate_uncertainty, gate_limit + gate_uncertainty))
    e["gate_records"] = [
        {"id": "tp14-feed", "procedure": "TP-14", "pose": "feed pose", "step": 7,
         "datum": "shoulder_lift horn-screw centre", "measurement": "horizontal fingertip reach",
         "combination": "largest of three independent plumb-line placements", "limit_mm": gate_limit,
         "uncertainty_mm": gate_uncertainty, "decision": gate_decision},
        {"id": "tp14-farthest", "procedure": "TP-14", "pose": "farthest measurement pose", "step": 8,
         "datum": "shoulder_lift horn-screw centre", "measurement": "horizontal fingertip reach",
         "combination": "largest of three independent plumb-line placements", "limit_mm": gate_limit,
         "uncertainty_mm": gate_uncertainty, "decision": gate_decision},
    ]
    # Finger stiffness (R12)
    e["finger"] = {"window_N_per_mm": [cfg["FINGER_K_MIN_N_PER_MM"], cfg["FINGER_K_MAX_N_PER_MM"]],
                   "predicted_bare_N_per_mm": [0.922, 1.101], "predicted_D7_N_per_mm": [1.07, 1.29],
                   "fold_E56_N": fea["recommended"]["nonlinear_check"]["rec_bare_tip_limit_E56_N"]}
    # Jaw speed over the last 3 deg before contact (R19, second clause). The firmware commands
    # JAW_SPEED_NEAR_DPS; the servo trails it, so the modelled jaw runs 21 deg/s at contact + 3 deg
    # and <= 20 deg/s from contact + 2 deg [D controls.md 4.2]. The DB limit (20 deg/s) equals the
    # design speed, so a video fit cannot clear it by U. The video check is therefore judged against a
    # screening limit that a conforming gripper passes: expected jaw maximum + U + 1 deg/s, rounded up.
    cmd_dps = cfg["JAW_SPEED_NEAR_DPS"]
    sigma_deg = 0.5 / math.sqrt(3.0)          # one protractor reading, rectangular +-0.5 deg [A]
    n_frames = round(3.0 / cmd_dps * 240.0)   # frames inside the last 3 deg at 240 fps
    se_fit = sigma_deg * math.sqrt(12.0) / ((1.0 / 240.0) * n_frames ** 1.5)  # slope standard error, deg/s
    jaw_expected_max = 21.0
    e["jaw_speed"] = {"cmd_dps": cmd_dps, "db_limit_dps": 20.0, "jaw_expected_max_dps": jaw_expected_max,
                      "n_frames": n_frames, "sigma_deg": sigma_deg, "U_fit_dps": 2.0 * se_fit,
                      "screening_limit_dps": math.ceil(jaw_expected_max + 2.0 * se_fit + 1.0),
                      "verdict_command": decide(cmd_dps, 20.0, 0.0, "upper"),
                      "verdict_db_limit_on_jaw": decide(jaw_expected_max, 20.0, 2.0 * se_fit, "upper"),
                      "verdict_screening_on_jaw": decide(jaw_expected_max, math.ceil(jaw_expected_max + 2.0 * se_fit + 1.0), 2.0 * se_fit, "upper")}
    # Stall back-off (R20), from the host test (controls.md section 0)
    e["r20"] = {"backoff_begins_ms": 140, "backoff_at_target_ms": 200, "jaw_lag_ms": 50, "limit_ms": 200}
    return e


def _rail_stall(rs: dict, volts: str) -> float:
    """Stall torque at a rail voltage from dyno.json `rail_sensitivity` [D, dyno.py]."""
    return rs[volts.replace(".", "p") + "V"]["inputs"]["T_stall_Nm"]


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------
TAL220 = {"capacity_kg": 10.0, "combined_error_pctFS": 0.05, "repeatability_pctFS": 0.03,
          "creep_pctFS_3min": 0.05, "tc_span_pctFS_10C": 0.05, "rated_output_mV_V": 1.0,
          "src": "TAL220 datasheet (HT Sensor), https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/TAL220M4M5Update.pdf, retrieved " + RETRIEVED}
HX711 = {"noise_nV_rms_80sps": 90.0, "noise_nV_rms_10sps": 50.0,
         "src": "HX711 datasheet (Avia), https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/hx711_english.pdf, retrieved " + RETRIEVED}
G = 9.80665


def instrument_budgets(e, cfg) -> dict:
    fs_N = TAL220["capacity_kg"] * G
    exc_V = 3.3  # HX711 board powered from the ESP32 / Uno 3.3 V pin [A]
    sens_uV_per_N = TAL220["rated_output_mV_V"] * 1000.0 * exc_V / fs_N
    noise_N = HX711["noise_nV_rms_80sps"] / 1000.0 / sens_uV_per_N
    out = {"probe_sensitivity_uV_per_N": sens_uV_per_N, "probe_noise_N_rms": noise_N, "probe_fs_N": fs_N}

    def probe_budget(F):
        return budget([
            {"name": "load cell combined error ±0.05 % FS [S TAL220]", "value": TAL220["combined_error_pctFS"] / 100 * fs_N, "dist": "rect"},
            {"name": "repeatability ±0.03 % FS [S TAL220]", "value": TAL220["repeatability_pctFS"] / 100 * fs_N, "dist": "rect"},
            {"name": "creep ±0.05 % FS per 3 min, over a 25.5 s hold [S TAL220]", "value": TAL220["creep_pctFS_3min"] / 100 * fs_N, "dist": "rect"},
            {"name": "span drift ±0.05 % FS/10 °C, room ±5 °C [S TAL220, A room]", "value": TAL220["tc_span_pctFS_10C"] / 100 * fs_N * 0.5, "dist": "rect"},
            {"name": "HX711 noise 90 nV rms at 80 SPS, 3.3 V excitation [S HX711, D]", "value": noise_N, "dist": "normal"},
            {"name": "reference masses: lab balance ±0.2 g on 500 g, g = 9.80 ±0.1 % [A]", "value": F * 0.0014, "dist": "rect"},
            {"name": "contact point ±1 mm on the probe, 0.5 %/mm off-centre error [A, measured in TP-01 step 4]", "value": F * 0.005, "dist": "rect"},
        ])

    out["pad_force_5N"] = probe_budget(5.0)
    out["pad_force_8N"] = probe_budget(8.0)
    out["pad_force_10N"] = probe_budget(10.0)
    pull = probe_budget(4.0)
    pull["components"].append({"name": "pull line within 5° of the feed direction (cosine) [A]", "value": 4.0 * (1 - math.cos(math.radians(5))), "dist": "rect",
                               "u": rect_u(4.0 * (1 - math.cos(math.radians(5))))})
    pull["u_c"] = math.sqrt(sum(c["u"] ** 2 for c in pull["components"]))
    pull["U_k2"] = 2 * pull["u_c"]
    out["pull_force_4N"] = pull
    out["close_time_eventlog_s"] = budget([
        {"name": "millis() resolution 1 ms [D]", "value": 0.0005, "dist": "rect"},
        {"name": "FSR EMA lag 9.5 ms + 1 ms poll, corrected; residual ±3 ms [D controls.md 3, A residual]", "value": 0.003, "dist": "rect"},
        {"name": "host line to dispatch, one loop pass ≤ 1 ms [A]", "value": 0.0005, "dist": "rect"},
    ])
    # Both endpoints are first-observed ST records on the same controller millis() clock. Each true
    # event lies in the preceding 20 ms status interval, so subtracting the records has error in
    # [-20, +20] ms regardless of correlation. This is a 100 % quantisation bound, not k=2 RSS.
    out["fault_timing_s"] = {
        "components": [{"name": "difference of two 50 Hz first-observed endpoints: ± one 20 ms status period [D]",
                        "value": 0.020, "dist": "bounded", "u": 0.020}],
        "u_c": 0.020, "U_k2": 0.020,
        "dominant": "50 Hz interval bound (100 % coverage; no independence assumption)",
        "coverage": "bounded (100 % under uninterrupted STREAM 50)",
    }
    out["force_time_stream_s"] = budget([
        {"name": "`STREAM 50` status lines every 20 ms, crossing interpolated ±10 ms [D config.h]", "value": 0.010, "dist": "rect"},
        {"name": "FSR EMA lag 9.5 ms, corrected; residual ±3 ms [D, A]", "value": 0.003, "dist": "rect"},
        {"name": "FSR span error ±2 % at 5 N on a ~25 N/s rise, ±4 ms [A]", "value": 0.004, "dist": "rect"},
    ])
    out["close_time_video_s"] = budget([
        {"name": "start frame ±1 frame at 240 fps [D]", "value": 1 / 240, "dist": "rect"},
        {"name": "contact frame ±1 frame at 240 fps [D]", "value": 1 / 240, "dist": "rect"},
    ])
    out["case_temp_C"] = budget([
        {"name": "type K + MAX31855 after an ice-point check, residual ±1.0 °C [A; unchecked ±2 to ±6 °C S Adafruit 269]", "value": 1.0, "dist": "rect"},
        {"name": "MAX31855 resolution 0.25 °C [S Adafruit 269]", "value": 0.125, "dist": "rect"},
        {"name": "bead-to-case contact under Kapton tape and paste ±1.0 °C [A]", "value": 1.0, "dist": "rect"},
    ])
    m = e["mass"]["bom_plus_cloth_wiring_g"]
    lever = e["mass"]["lever_mm"] + e["mass"]["db_com_mm"]
    um = rect_u(0.2)
    ud = rect_u(1.0)
    out["mass_moment_gmm"] = budget([
        {"name": "mass: balance ±0.2 g [A]", "value": lever * 0.2, "dist": "rect"},
        {"name": "COM: knife-edge balance ±1.0 mm [A]", "value": m * 1.0, "dist": "rect"},
        {"name": "lever 309.1 mm from MuJoCo model, ±0.5 mm [D design_basis.py, A]", "value": m * 0.5, "dist": "rect"},
    ])
    k = 1.10
    F = 5.0
    out["finger_k_rel"] = budget([
        {"name": "deflection: dial indicator ±0.02 mm on ~4.5 mm [A]", "value": 0.02 / (F / k), "dist": "rect"},
        {"name": "load: hanger masses ±0.2 % [A]", "value": 0.002, "dist": "rect"},
        {"name": "load point ±0.5 mm at s = 40 mm, k ∝ s^-3 [D beam, A placement]", "value": 3 * 0.5 / 40.0, "dist": "rect"},
        {"name": "root clamp compliance, read off the zero-load dial [A]", "value": 0.01, "dist": "rect"},
    ])
    T = e["stall"]["predicted_6p5V_Nm"]
    Fl = e["stall"]["force_at_lever_N"]
    pf = probe_budget(Fl)
    out["stall_torque_rel"] = budget([
        {"name": "force at the lever (probe budget at %.0f N) [D]" % Fl, "value": pf["u_c"] / Fl, "dist": "normal"},
        {"name": "lever 50 mm: calipers ±0.05 mm and contact ±0.5 mm [A]", "value": 0.5 / 50.0, "dist": "rect"},
        {"name": "lever perpendicular within 3° (cosine) [A]", "value": 1 - math.cos(math.radians(3)), "dist": "rect"},
        {"name": "rail voltage ±0.05 V at 6.35 V; stall ∝ V [A DMM]", "value": 0.05 / 6.35, "dist": "rect"},
    ])
    out["current_A"] = budget([
        {"name": "INA219 shunt LSB 10 µV / 0.1 Ω = 0.1 mA [S config.h, TI]", "value": 0.00005, "dist": "rect"},
        {"name": "0.1 Ω shunt ±1 % at 1.8 A [A]", "value": 0.018, "dist": "rect"},
    ])
    out["rail_V"] = budget([
        {"name": "handheld DMM ±(0.5 % + 2 counts at 10 mV) at 6.5 V [A, check the meter's manual]", "value": 0.005 * 6.5 + 0.02, "dist": "rect"},
    ])
    out["pulse_us"] = budget([
        {"name": "logic analyser or scope at ≥ 1 MS/s: ±1 µs per edge, two edges [A]", "value": 1.0, "dist": "rect"},
        {"name": "second edge", "value": 1.0, "dist": "rect"},
    ])
    out["caliper_mm"] = budget([
        {"name": "digital calipers ±0.03 mm [A, typical 150 mm class]", "value": 0.03, "dist": "rect"},
        {"name": "printed surface, three readings ±0.03 mm [A]", "value": 0.03, "dist": "rect"},
    ])
    out["rc_mm"] = budget([
        {"name": "digital calipers ±0.03 mm [A, typical 150 mm class]", "value": 0.03, "dist": "rect"},
        {"name": "printed surface, three readings ±0.03 mm [A]", "value": 0.03, "dist": "rect"},
        {"name": "pad plane set by the steel-square blade, contact ±0.05 mm [A]", "value": 0.05, "dist": "rect"},
        {"name": "3 mm dowel diameter ±0.01 mm (the r_c = L1 − 1.5 − 5.0 offset uses its radius) [A]", "value": 0.01, "dist": "rect"},
    ])
    out["jaw_angle_deg"] = budget([
        {"name": "printed protractor on the knuckle, read off video ±0.5° [A]", "value": 0.5, "dist": "rect"},
    ])
    out["backlash_mm"] = budget([
        {"name": "dial indicator 0.01 mm, ±0.02 mm [A]", "value": 0.02, "dist": "rect"},
        {"name": "reversal load ±0.1 N on a 1.1 N/mm finger, measured on the rigid knuckle [A]", "value": 0.01, "dist": "rect"},
    ])
    out["slip_mm"] = budget([
        {"name": "ink mark against a 0.5 mm printed grid, macro photo ±0.2 mm [A]", "value": 0.2, "dist": "rect"},
    ])
    return out


def _r19_proposed_change(e, lim):
    late = [c for c in e["close"].values() if c["t_F5p0_s"] is None or c["t_F5p0_s"] > lim]
    if not late:
        worst = max(e["close"].values(), key=lambda c: c["t_F5p0_s"])
        return ("firmware as is (120 °/s, 6° slow zone): 4.5 N and 5.0 N arrive by %.2f s on every finger in the R12 window (latest 5.0 N %.3f s at k %.2f, %.0f ms margin)"
                % (lim, worst["t_F5p0_s"], worst["k_N_per_mm"], 1000 * (lim - worst["t_F5p0_s"])))
    k_ok = min((c["k_N_per_mm"] for c in e["close"].values() if c["t_F5p0_s"] is not None and c["t_F5p0_s"] <= lim), default=None)
    return ("firmware as is (120 °/s, 6° slow zone) if 4.5 N counts; if 5.0 N must arrive by %.2f s, the finger must be ≥ %s N/mm or the PI retuned for the soft end"
            % (lim, ("%.2f" % k_ok) if k_ok else "(none simulated)"))


def _r19_k1_note(e, lim, U):
    """Note for the latest 5.0 N arrival among fingers k >= 1.0 against the proposed R19."""
    c = max((c for c in e["close"].values() if c["k_N_per_mm"] >= 1.0), key=lambda c: c["t_F5p0_s"])
    m_ms = 1000 * (lim - c["t_F5p0_s"])
    return "k %.2f lands %.0f ms %s %.2f s: %s" % (c["k_N_per_mm"], abs(m_ms), "under" if m_ms >= 0 else "over", lim,
                                                  "decidable" if abs(m_ms) >= 1000 * U else "undecidable")


def resolvability(e, b) -> list[dict]:
    """Can the instrument resolve each pass criterion? limit/U (want >= 10) and
    |predicted margin|/U (>= 1 means the expected result lands outside the band)."""
    rows = []

    def add(test, req, quantity, limit, side, predicted, U, unit, note=""):
        margin = (limit - predicted) if side == "upper" else (predicted - limit)
        rows.append({"test": test, "req": req, "quantity": quantity, "limit": limit, "side": side,
                     "predicted": predicted, "U_k2": U, "unit": unit, "limit_over_U": abs(limit) / U if U else None,
                     "margin": margin, "margin_over_U": margin / U if U else None,
                     "resolves_limit": abs(limit) / U >= 10,
                     "verdict_decidable": abs(margin) >= U, "predicted_verdict": decide(predicted, limit, U, "upper" if side == "upper" else "lower"),
                     "note": note})

    lo, hi = e["hold_range_N"]
    U5 = b["pad_force_5N"]["U_k2"]
    k_lo = next(c["k_N_per_mm"] for c in e["close"].values() if c["F_hold_mean_N"] == lo)
    add("TP-01", "R14", "hold force, softest R12 finger", 5.0, "lower", lo, U5, "N",
        ("sim hold %.2f N at k %.2f: margin %.2f N is inside U; the FSR span (CALF) decides it" % (lo, k_lo, lo - 5.0)) if lo - 5.0 < U5 else
        ("sim hold %.2f N at k %.2f: margin %.2f N, outside U (F_HOLD_BIAS_N regulates 1 N above the setpoint)" % (lo, k_lo, lo - 5.0)))
    add("TP-01", "R14", "hold force, D7 finger (k 1.24)", 5.0, "lower", e["close"]["1.24 FEA E67+D7"]["F_hold_mean_N"],
        b["pad_force_5N"]["U_k2"], "N")
    for label, c in e["cap"].items():
        add("TP-04", "R15", "peak force, FSR reading 50 %%, k 1.63 (cap %s %.0f N)" % (label, c["cap_N"]), c["cap_N"], "upper",
            c["fsr50_peak_stiff_N"], b["pad_force_10N"]["U_k2"], "N")
        add("TP-04", "R15", "peak force, normal G 5, k 1.63 (cap %s %.0f N)" % (label, c["cap_N"]), c["cap_N"], "upper",
            e["peak_range_N"][1], b["pad_force_8N"]["U_k2"], "N")
    add("TP-02", "R14", "pull to slip (SF 2 at mu 0.4)", e["slip"]["capacity_N"], "lower", e["slip"]["capacity_N"],
        b["pull_force_4N"]["U_k2"], "N", "predicted equals the limit by construction; the measured mu (M2) decides")
    for label, lim in OPEN["R19_close_s"].items():
        add("TP-03", "R19", "contact time, event log (R19 %s %.2f s)" % (label, lim), lim, "upper",
            e["close_range"]["t_contact_s"][1], b["close_time_eventlog_s"]["U_k2"], "s")
        add("TP-03", "R19", "time to 4.5 N, stream (R19 %s %.2f s)" % (label, lim), lim, "upper",
            e["close_range"]["t_F4p5_s"][1], b["force_time_stream_s"]["U_k2"], "s")
        add("TP-03", "R19", "time to 5.0 N, k ≥ 1.0 (R19 %s %.2f s)" % (label, lim), lim, "upper",
            e["close_range"]["t_F5p0_s_k_ge_1"][1], b["force_time_stream_s"]["U_k2"], "s",
            _r19_k1_note(e, lim, b["force_time_stream_s"]["U_k2"]) if label == "proposed" else "")
        add("TP-03", "R19", "time to 5.0 N, k 0.88 (R19 %s %.2f s)" % (label, lim), lim, "upper",
            e["close_range"]["t_F5p0_s"][1], b["force_time_stream_s"]["U_k2"], "s")
    add("TP-07", "R26", "case temperature after 30 min (Fit B, 25 °C, Rth2 ×1)", 60.0, "upper",
        e["thermal"]["B_elec_amb25_Rth2x1.0"], b["case_temp_C"]["U_k2"], "°C", "model is an upper bound; spans 43-115 °C")
    add("TP-09", "R17", "moment arm r_c, both fingers (CAD nominal)", 65.0, "upper", 65.0, b["rc_mm"]["U_k2"], "mm",
        "CAD nominal sits on the limit: a perfect part reads INDETERMINATE; see Requested changes in the README")
    add("TP-09", "R10", "mass-moment, CAD revision %s" % e["mass"]["cad_revision"], e["mass"]["budget_gmm"], "upper",
        e["mass"]["cad_mass_moment_gmm"], b["mass_moment_gmm"]["U_k2"], "g·mm",
        "Predicted FAIL at full reach; disposition: prohibit holds beyond %.1f mm COM reach and enforce the tighter work-cell fingertip limit" % e["mass"]["reach_limit_com_mm"])
    add("TP-12", "R12", "finger tip stiffness, low end", 0.88, "lower", 1.07, b["finger_k_rel"]["U_k2"] * 1.07, "N/mm")
    add("TP-12", "R12", "finger tip stiffness, high end", 1.63, "upper", 1.29, b["finger_k_rel"]["U_k2"] * 1.29, "N/mm")
    add("TP-13", "R16", "stall torque at 6.35 V", e["stall"]["stall_needed_Nm"], "lower", e["stall"]["predicted_6p35V_Nm"],
        b["stall_torque_rel"]["U_k2"] * e["stall"]["predicted_6p35V_Nm"], "N·m", "1 % margin: run at 6.50 V too")
    add("TP-05", "R20", "back-off begins after over-current onset", 0.200, "upper", 0.140,
        b["fault_timing_s"]["U_k2"], "s")
    add("TP-13", "R27", "rail voltage band low end", 6.35, "lower", 6.5, b["rail_V"]["U_k2"], "V",
        "TUR about 3: set the rail to 6.50 V with the DMM")
    add("TP-13", "R27", "rail voltage band high end", 6.65, "upper", 6.5, b["rail_V"]["U_k2"], "V",
        "TUR about 3: set the rail to 6.50 V with the DMM")
    return rows


def _quantity(value, unit, digits, fixed=False):
    spec = ".%df" % digits if fixed else ".%dg" % digits
    return format(value, spec) + " " + unit


def _boundary(row, outcome, digits):
    pass_delta = row["U_k2"] if row["side"] == "lower" else -row["U_k2"]
    delta = pass_delta if outcome == "pass" else -pass_delta
    return _quantity(row["limit"] + delta, row["unit"], digits)


def _expanded(row):
    return row["U_k2"]


def _milliseconds(seconds):
    return seconds * 1000


def placeholder_values(e, b, res):
    """Procedure quantities derived from expected values, budgets, and criteria."""
    row = lambda start, word="": next(r for r in res if r["quantity"].startswith(start) and word in r["quantity"])
    hold = row("hold force, softest")
    pull = row("pull to slip")
    close_written = row("contact time", "written")
    close_proposed = row("contact time", "proposed")
    cap_written = row("peak force, FSR", "written")
    cap_proposed = row("peak force, FSR", "proposed")
    backoff = row("back-off begins")
    case = row("case temperature")
    arm = row("moment arm")
    moment = row("mass-moment")
    stiffness_low = row("finger tip stiffness, low")
    stiffness_high = row("finger tip stiffness, high")
    torque = row("stall torque")
    rail = row("rail voltage")
    rail_high = row("rail voltage band high")
    prefix = lambda r: r["test"].lower().replace("-", "")
    return {
        prefix(hold) + ".hold_limit": _quantity(hold["limit"], hold["unit"], digits=1),
        prefix(pull) + ".pull_limit": _quantity(pull["limit"], pull["unit"], digits=2),
        prefix(close_written) + ".written_limit": _quantity(close_written["limit"], close_written["unit"], digits=1, fixed=True),
        prefix(close_proposed) + ".proposed_limit": _quantity(close_proposed["limit"], close_proposed["unit"], digits=2, fixed=True),
        prefix(cap_written) + ".written_cap": _quantity(cap_written["limit"], cap_written["unit"], digits=2),
        prefix(cap_proposed) + ".proposed_cap": _quantity(cap_proposed["limit"], cap_proposed["unit"], digits=1),
        prefix(backoff) + ".backoff_limit": _quantity(_milliseconds(backoff["limit"]), "ms", digits=3),
        prefix(case) + ".case_limit": _quantity(case["limit"], case["unit"], digits=2),
        prefix(arm) + ".moment_arm_limit": _quantity(arm["limit"], arm["unit"], digits=2),
        prefix(stiffness_high) + ".stiffness_high_limit": _quantity(stiffness_high["limit"], stiffness_high["unit"], digits=3),
        prefix(stiffness_low) + ".stiffness_low_limit": _quantity(stiffness_low["limit"], stiffness_low["unit"], digits=2),
        prefix(torque) + ".torque_limit": _quantity(torque["limit"], torque["unit"], digits=3),
        prefix(rail) + ".rail_low_limit": _quantity(rail["limit"], rail["unit"], digits=3),
        prefix(hold) + ".limit_display": _quantity(hold["limit"], hold["unit"], digits=1, fixed=True),
        prefix(hold) + ".pass_bound": _boundary(hold, "pass", digits=3),
        prefix(hold) + ".fail_bound": _boundary(hold, "fail", digits=3),
        prefix(hold) + ".probe_u": _quantity(_expanded(hold), hold["unit"], digits=2),
        prefix(hold) + ".predicted_low": _quantity(hold["predicted"], hold["unit"], digits=3),
        prefix(pull) + ".limit_display": _quantity(pull["limit"], pull["unit"], digits=1, fixed=True),
        prefix(pull) + ".limit_two_decimals": _quantity(pull["limit"], pull["unit"], digits=2, fixed=True),
        prefix(pull) + ".pass_bound": _boundary(pull, "pass", digits=3),
        prefix(cap_written) + ".predicted_peak": _quantity(cap_written["predicted"], cap_written["unit"], digits=3),
        prefix(cap_written) + ".screen_low": _quantity(e["cap"]["written"]["soft_limit_N_now"], cap_written["unit"], digits=2),
        prefix(cap_written) + ".written_fail": _boundary(cap_written, "fail", digits=3),
        prefix(cap_written) + ".written_pass": _boundary(cap_written, "pass", digits=3),
        prefix(case) + ".stop_high": _boundary(case, "fail", digits=3),
        prefix(case) + ".stop_low": _quantity(e["thermal_limits_C"]["bare_mount"] + _expanded(case), case["unit"], digits=3),
        prefix(moment) + ".moment_u": _quantity(_expanded(moment), moment["unit"], digits=7),
        prefix(moment) + ".moment_pass": _boundary(moment, "pass", digits=5),
        prefix(moment) + ".moment_fail": _boundary(moment, "fail", digits=5),
        prefix(arm) + ".rc_u": _quantity(_expanded(arm), arm["unit"], digits=2),
        prefix(arm) + ".rc_pass": _boundary(arm, "pass", digits=4),
        prefix(arm) + ".rc_limit_display": _quantity(arm["limit"], arm["unit"], digits=1, fixed=True),
        prefix(arm) + ".rc_fail": _boundary(arm, "fail", digits=4),
        prefix(arm) + ".rc_example": _quantity(arm["limit"] + _expanded(arm) + _expanded(arm) + _expanded(arm), arm["unit"], digits=3),
        prefix(stiffness_high) + ".pass_high": _boundary(stiffness_high, "pass", digits=3),
        prefix(stiffness_high) + ".fail_high": _boundary(stiffness_high, "fail", digits=3),
        prefix(torque) + ".torque_pass": _boundary(torque, "pass", digits=4),
        prefix(rail) + ".rail_pass": _boundary(rail_high, "pass", digits=3),
        prefix(rail) + ".rail_fail": _boundary(rail_high, "fail", digits=3),
        prefix(rail) + ".rail_u": _quantity(_expanded(rail), rail["unit"], digits=2),
    }


# ---------------------------------------------------------------------------
# Procedures, equipment, requirement matrix
# ---------------------------------------------------------------------------
PROCEDURES = [
    # id, file, title, requirements, minutes, owner, columns of the data sheet
    ("TP-01", "TP-01-pad-force.md", "Pad force against command and FSR calibration", ["R14", "R3", "M11", "M18"], 62, "controls / firmware",
     ["trial", "finger_pair", "command_N", "fsr_reading_N", "probe_peak_N", "probe_hold_mean_N", "probe_hold_min_N", "state_at_end", "notes"]),
    ("TP-02", "TP-02-hold-and-slip.md", "Hold under tension with cloth slip detection", ["R14", "M2", "M3"], 45, "grip / design basis",
     ["part_incline_hold_pull", "trial", "fabric", "incline_slip_deg", "hold_N_probe", "tension_N", "slip_at_2N_mm_after_25p5s", "pull_to_slip_N", "fsr_min_N", "slip_event_logged", "notes"]),
    ("TP-03", "TP-03-close-time.md", "Close time and approach speed", ["R19", "R6"], 25, "firmware (R19 owner: Douglas)",
     ["trial", "start_state", "t_cmd_ms", "t_contact_ms", "t_F4p5_ms", "t_F5_ms", "t_hold_ms", "video_start_frame", "video_contact_frame", "speed_last3deg_dps", "theta_c0_bare_deg", "finger_k_N_per_mm", "event_order_ok", "notes"]),
    ("TP-04", "TP-04-force-cap-and-trip.md", "Force cap and over-force trip", ["R15", "R18"], 45, "controls (R15 owner: Douglas)",
     ["trial", "case", "spacer_mm", "fsr_span_set", "probe_peak_N", "fsr_at_trip_N", "t_cross_8N_ms", "t_fsr_over_ms", "t_enter_fault_ms", "backoff_deg", "fault_event", "theta_min_reached_deg", "notes"]),
    ("TP-05", "TP-05-stall-backoff.md", "Stall detection and back-off", ["R20"], 40, "firmware / electrical",
     ["trial", "part", "blocked_at_deg", "t_overcurrent_onset_ms", "t_fault_ms", "t_backoff_begin_ms", "t_unloaded_ms", "peak_rail_A", "case_C", "relax_event", "notes"]),
    ("TP-06", "TP-06-endurance.md", "Endurance cycling screen", ["R25", "R13", "M22"], 30, "mechanical (gears, finger)",
     ["checkpoint_cycles", "backlash_tip_mm", "theta_c0_deg", "hold_N_probe", "finger_k_N_per_mm", "visible_damage", "faults_since_last", "peak_case_C", "cutoff_checks_1to4_ok", "notes"]),
    ("TP-07", "TP-07-thermal-soak.md", "Thermal soak over the duty cycle", ["R26", "M7"], 50, "electrical / actuator",
     ["t_min", "case_C", "mount_C", "ambient_C", "ir_check_C", "rail_V", "rail_mean_A", "cycles_done", "hold_I_A", "hold_Ih_A", "drive_regime", "sleeves_fitted", "stopped_by_rig", "notes"]),
    ("TP-08", "TP-08-backlash-repeatability.md", "Backlash, calibration repeatability and motion range", ["R18", "R21", "M8"], 25, "mechanical / firmware",
     ["trial", "theta_c0_deg", "tip_gap_open_mm", "r_d_mm", "backlash_B_tip_mm", "backlash_A_tip_mm", "angle_open_deg", "deadband_us", "notes"]),
    ("TP-09", "TP-09-mass-envelope.md", "Mass, centre of mass, envelope and moment arm", ["R9", "R10", "R17", "M13", "M14"], 25, "CAD / design basis",
     ["item", "measured", "unit", "limit", "pass", "notes"]),
    ("TP-10", "TP-10-course-rules.md", "Course rules and firmware inspection", ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R11", "M16", "M20"], 40, "team lead",
     ["item", "requirement", "evidence", "result", "checked_by", "notes"]),
    ("TP-11", "TP-11-printed-fit.md", "Fit of the printed parts and the wrist interface", ["R22", "R23", "M12", "M15"], 55, "CAD / tolerancing",
     ["feature", "cad_mm", "measured_mm", "gauge_result", "limit", "pass", "notes"]),
    ("TP-12", "TP-12-finger-stiffness.md", "Finger tip stiffness and fold load", ["R12", "M10"], 40, "finger / FEA",
     ["finger", "run", "branch_load_or_unload", "load_N", "deflection_mm", "k_secant_N_per_mm", "folded", "notes"]),
    ("TP-13", "TP-13-servo-and-rail.md", "Servo stall torque, hold current and power rail", ["R16", "R27", "M6", "M16"], 35, "actuator / electrical",
     ["trial", "rail_set_V", "lever_mm", "peak_force_N", "plateau_force_N", "torque_Nm", "rail_A", "hold_A_from_TP01", "rail_min_V", "pulse_us", "notes"]),
    ("TP-14", "TP-14-work-cell.md", "Work cell layout and arm load", ["R24", "M1", "M3", "M5", "M5b", "M19"], 40, "integration",
     ["item", "measured", "unit", "limit", "pass", "notes"]),
    ("TP-16", "TP-16-fault-detection.md", "Sensor and limit-switch fault detection", ["R15", "R18", "R20"], 45, "firmware / electrical",
     ["trial", "injected_fault", "fault_event_seen", "t_enter_fault_ms", "st_fault_field", "th_before_deg", "th_after_deg", "I_end_of_search_A", "build", "notes"]),
    ("TP-15", "TP-15-gear-step-load.md", "Gear sector step-load test (destructive, spare pair)", ["R13", "M17", "M21"], 60, "gears",
     ["step", "torque_Nm", "hanger_kg", "lever_own_moment_Nm", "held_60s", "backlash_after_mm", "contact_pattern", "damage", "notes"]),
]


# Run order. Parts-level tests come first because a failure there changes what gets built;
# the core afternoon decides R14, R15, R19 and R20; the soak and the work cell need the
# gripper on the arm; the endurance run is unattended. Minutes per procedure are [A].
PHASES = [
    ("0 Desk checks and first power-up", ["TP-10"]),
    ("1 Parts, before assembly", ["TP-11", "TP-12", "TP-13", "TP-15"]),
    ("2 Core afternoon (R14, R15, R19, R20)", ["TP-09", "TP-08", "TP-01", "TP-04", "TP-05", "TP-16", "TP-03", "TP-02"]),
    ("3 On the arm", ["TP-07", "TP-14"]),
    ("4 Unattended", ["TP-06"]),
]


# Work in a session that no procedure owns. Session 1 must include building the probe: the pinch
# probe (TP-01 "The pinch probe", about 30 min plus printing), the probe board with two thermocouple
# channels and the cutoff relay (wiring, flashing `probe.ino`, an ice-point check), and its load
# calibration (TP-01 part A). Minutes are [A].
PHASE_EXTRA = [("1 Parts, before assembly", "Build and calibrate the probe board: pinch probe, load-cell and two-thermocouple reader, cutoff relay, TP-01 part A", 90)]


def procedure_by_id(procs=None):
    return {p[0]: p for p in (procs or PROCEDURES)}


# Data-sheet rows per procedure: one per trial the procedure runs (TP-01 comes from the R14 sizing, in main).
# TP-05: 22 blocked closes (A) + 3 near contact (B) + 1 open-stop relax (C) + 3 stalls after contact (D).
# TP-07: 5-min rows of the soak and 2-min rows of the cool-down. TP-16: faults A-H, 3 trials each.
DATASHEET_ROWS = {"TP-05": 22 + 3 + 1 + 3, "TP-07": 32, "TP-16": 8 * 3}
DATASHEET_ROWS_DEFAULT = 12
# TP-01 bench time: 62 min [A] was sized for 12 holds; each further hold adds the DB section 7 hold (25.5 s), the
# RETRACT wait before the next `G` (TIMEOUT_RETRACT_MS) and about 1 s to close and reach HOLD [A].
TP01_BASE = (12, 62)
HOLD_S = 25.5      # [DB section 7]
CLOSE_TO_HOLD_S = 1.0


def equipment():
    """Instrument and supply list. Prices are listed prices on the retrieval date [S]
    unless tagged [A]. 'borrow' = expected in an ME teaching lab or the student shop [A]."""
    S = lambda url: "[S] %s, retrieved %s" % (url, RETRIEVED)
    items = [
        # name, qty, unit_usd, buy_or_borrow, source, used_in, resolution
        ("Load cell, 10 kg straight bar (TAL220), SparkFun SEN-13329", 1, 12.95, "buy", S("https://www.sparkfun.com/load-cell-10kg-straight-bar-tal220.html"), "TP-01 02 04 05 13 14", "see budget; ±0.05 % FS combined error"),
        ("Load cell amplifier HX711, SparkFun SEN-13879", 1, 4.95, "buy", S("https://www.sparkfun.com/sparkfun-load-cell-amplifier-hx711.html"), "TP-01 02 04 05 13 14", "24 bit, 80 SPS, 90 nV rms"),
        ("Thermocouple amplifier MAX31855, Adafruit 269 (two: servo case and printed mount)", 2, 14.95, "buy", S("https://www.adafruit.com/product/269"), "TP-06 07", "0.25 °C"),
        ("Thermocouple type K, glass braid, Adafruit 270 (two: servo case and printed mount)", 2, 9.95, "buy", S("https://www.adafruit.com/product/270"), "TP-06 07", "bead probe"),
        ("Relay module, 5 V coil, 10 A contacts, normally open (thermal cutoff in the servo's +6.5 V line)", 1, 3.00, "buy", "[A] typical hobby relay board price; not looked up", "TP-06 07", "-"),
        ("Spare FSR, Adafruit 166 (now listed as Alpha MF01A, 0.3-10 N)", 1, 3.95, "buy", S("https://www.adafruit.com/product/166"), "TP-01 04 (fault cases), spare", "-"),
        ("Spare DS3218MG servo (stall and step-load tests are hard on it)", 1, 12.99, "buy", "[S] docs/gripper/research/actuators.csv row A17 (SpeedyFPV, 2026-09-22)", "TP-13 15", "-"),
        ("Probe hardware: 2 × 40 × 15 × 3 mm aluminium flat or printed PETG plates, 4 × M4/M5 screws per TAL220 thread", 1, 5.00, "buy", "[A] hardware-store estimate", "TP-01 02 04", "-"),
        ("Filament for fixtures (probe yoke, lever arm, load saddle, protractor, coupons), about 60 g PETG", 1, 1.50, "buy", "[A] $25/kg as in BOM.md", "TP-01 06 11 12 13 15", "-"),
        ("Spare printed parts for the destructive tests: one PA6-CF gear sector pair, two TPU fingers with D7 parts, two M3 heat-set inserts", 1, 4.00, "buy", "[A] PA6-CF at $60/kg and TPU at $35/kg (BOM.md) plus inserts", "TP-04 11 12 15", "-"),
        ("Two more microcontrollers: the probe reader (Uno or ESP32) and a test ESP32 for the TP-08/TP-13 sketches", 2, 0.0, "borrow", "[A] ME102B kit or lab", "TP-01 02 04 07 08 13", "-"),
        ("Soldering iron, hook-up wire, header pins (HX711, MAX31855)", 1, 0.0, "borrow", "[A] lab bench", "probe build", "-"),
        ("Lab balance, 0.1 g or better, ≥ 500 g", 1, 0.0, "borrow", "[A] teaching lab", "TP-01 09 12", "0.1 g"),
        ("Digital calipers 150 mm", 1, 0.0, "borrow", "[A] student shop", "TP-09 11 13", "0.01 mm"),
        ("Dial indicator 0.01 mm with magnetic or clamp base", 1, 0.0, "borrow", "[A] student shop", "TP-06 08 12 15", "0.01 mm"),
        ("Feeler gauge set 0.05-1.0 mm", 1, 0.0, "borrow", "[A] student shop", "TP-08 11", "0.05 mm steps"),
        ("Bench power supply with current readout, ≥ 7 V 5 A (a Fit A stall draws 3.75 A, dyno.md)", 1, 0.0, "borrow", "[A] ME102B lab bench", "TP-05 07 13", "10 mA"),
        ("Handheld digital multimeter", 1, 0.0, "borrow", "[A] ME102B lab bench", "TP-07 13", "10 mV"),
        ("Oscilloscope or USB logic analyser", 1, 0.0, "borrow", "[A] ME102B lab bench", "TP-10 13", "1 µs"),
        ("Handheld IR thermometer (cross-check only)", 1, 0.0, "borrow", "[A] lab", "TP-07", "0.1 °C display"),
        ("Phone with 240 fps slow motion", 1, 0.0, "borrow", "[A] a teammate's phone; check its frame rate", "TP-03 08", "4.2 ms"),
        ("Slotted masses or water bottles weighed on the balance, 50 g to 4.5 kg (TP-15 needs about 4.2 kg)", 1, 0.0, "borrow", "[A] lab, or tap water in bottles", "TP-01 12 15", "-"),
        ("Demo fabric, 300 × 300 mm, and a spare strip", 1, 0.0, "borrow", "[A] the team's demo cloth", "TP-02 03 07", "-"),
        ("Tape measure, plumb line, steel square, luggage scale (cross-check)", 1, 0.0, "borrow", "[A] student shop", "TP-09 11 14 15", "1 mm"),
        ("Labelled fault-injection breakout: shrouded test points and insulated latching switches for FSR 3V3 short/open, limit open/closed and INA219 SDA open", 1, 0.0, "build", "[A] perfboard and keyed connectors", "TP-16", "install only with rail off"),
        ("Kapton tape, thermal paste, cable ties, marker, painter's tape", 1, 0.0, "borrow", "[A] lab consumables", "all", "-"),
    ]
    rows = []
    for name, qty, price, mode, src, used, res in items:
        rows.append({"item": name, "qty": qty, "unit_usd": price, "mode": mode, "subtotal_usd": qty * price,
                     "source": src, "used_in": used, "resolution": res})
    buy = [r for r in rows if r["mode"] == "buy"]
    total = round(sum(r["subtotal_usd"] for r in buy), 2)
    must = [r for r in buy if not r["item"].startswith("Spare")]
    minimum = round(sum(r["subtotal_usd"] for r in must), 2)
    fallback = [
        ("Lab balance (if none to borrow): 500 g × 0.01 g pocket scale", 15.0),
        ("Digital calipers (if none to borrow)", 20.0),
        ("Dial indicator with base (if none to borrow)", 25.0),
    ]
    return {"rows": rows, "total_buy_usd": total, "minimum_buy_usd": minimum,
            "budget_usd": 100.0,
            "budget_reason": "[A] About three times the gripper's own BOM cost (US$30.35, BOM.md) and two "
                             "actuator caps (R8, US$50 each). It buys only what a teaching lab will not lend, plus a "
                             "spare servo and FSR for the destructive tests. It leaves almost nothing for the borrowed "
                             "items if the lab cannot lend them: drop the spares first.",
            "fallback_if_not_borrowed": [{"item": a, "usd_A": b} for a, b in fallback],
            "total_with_fallbacks_usd": round(total + sum(b for _, b in fallback), 2)}


def alternatives(e, b, cfg) -> list[dict]:
    """Instruments a Berkeley ME student may not be able to borrow, with a substitute and the
    change in U that the substitute causes (all numbers printed by this script)."""
    # Pulse timing: second ESP32 with micros() capture instead of a scope / logic analyser.
    u_edge_esp = math.hypot(rect_u(0.5), rect_u(2.0))   # 1 us resolution, +-2 us interrupt latency [A]
    U_pulse_esp = 2.0 * math.sqrt(2.0) * u_edge_esp
    U_pulse_scope = b["pulse_us"]["U_k2"]
    # Camera frame rate: close time (two frame edges) and the jaw-speed least-squares slope.
    def cam(fps):
        u_t = math.sqrt(2.0) * rect_u(1.0 / fps)
        n = round(3.0 / cfg["JAW_SPEED_NEAR_DPS"] * fps)
        se = (0.5 / math.sqrt(3.0)) * math.sqrt(12.0) / ((1.0 / fps) * n ** 1.5)
        return 2.0 * u_t, 2.0 * se, n
    c240, c120, c60 = cam(240), cam(120), cam(60)
    lim = e["jaw_speed"]["screening_limit_dps"]
    jaw_v = e["jaw_speed"]["jaw_expected_max_dps"]
    # Rail current: the INA219 already on the gripper (logged in every ST line) against a bench-supply readout.
    U_supply_readout = 2.0 * rect_u(0.01 * 1.8 + 0.010)   # +-(1 % of 1.8 A + 10 mA) [A]
    U_ina = b["current_A"]["U_k2"]
    ina_range = 0.32 / cfg["INA219_SHUNT_OHM"]             # +-320 mV full scale across the shunt [A: INA219 gain /8 range, not looked up]
    # IR thermometer against a second contact bead.
    U_ir = 2.0 * rect_u(max(2.0, 0.02 * 60.0))            # +-2 C or +-2 % of reading at 60 C [A], plus an emissivity error not counted here
    U_bead = b["case_temp_C"]["U_k2"]
    rows = [
        {"item": "Bench supply with current readout, ≥ 7 V 5 A", "used": "TP-05 07 13 current and rail",
         "alt": "(a) another lab's supply; or (b) a 2S LiPo or 12 V adapter into a 6.5 V 5 A buck module (about US$8 [A]) with a 4 A fuse, current from the gripper's own INA219 (`I=` in every `ST` line), voltage from the DMM",
         "u_before": "supply readout U = %.3f A [A: ±(1 %% + 10 mA)] at 1.8 A" % U_supply_readout,
         "u_after": "INA219 U = %.3f A (budget `current_A`); DMM U = %.3f V. The INA219 saturates above %.1f A (±320 mV / %.1f Ω), so it cannot log a 3.75 A Fit A stall: in TP-13 read that peak on the DMM in series, U ≈ 0.04 A [A]" % (U_ina, b["rail_V"]["U_k2"], ina_range, cfg["INA219_SHUNT_OHM"])},
        {"item": "Oscilloscope or USB logic analyser", "used": "TP-10 13 (R7 pulse and frame)",
         "alt": "A second ESP32 timing the servo signal with `micros()` and an input-capture interrupt (the TP-08/TP-13 board), or a US$10 24 MHz USB logic-analyser clone [A]",
         "u_before": "scope / analyser at ≥ 1 MS/s: U = %.1f µs" % U_pulse_scope,
         "u_after": "ESP32 micros(): U = %.1f µs [A: 1 µs resolution, ±2 µs interrupt latency]. The R7 open-stop check (1722 ± 3 µs) becomes INDETERMINATE with this U; check the frame (19.61-20.41 ms) and the 1200-1900 µs clamp with it and take the 1722 µs reading on a borrowed scope" % U_pulse_esp},
        {"item": "Handheld IR thermometer (cross-check only)", "used": "TP-07 case cross-check",
         "alt": "A second type K bead on the case face next to the first, on the second MAX31855 channel (a contact thermocouple)",
         "u_before": "IR on a plastic or anodised case: U ≈ %.1f °C [A] plus an emissivity error (`thermal.md` section 6: anodised shell 0.77-0.88 reads low)" % U_ir,
         "u_after": "contact bead U = %.1f °C. The R26 verdict uses the bead in both cases, so the verdict's U does not change" % U_bead},
        {"item": "Phone with 240 fps slow motion", "used": "TP-03 08 (independent close time, jaw speed)",
         "alt": "A 120 fps or 60 fps phone camera (most phones), same procedure",
         "u_before": "240 fps: close time U = %.1f ms; jaw-speed fit U = %.1f °/s over %d frames" % (1000 * c240[0], c240[1], c240[2]),
         "u_after": "120 fps: %.1f ms, %.1f °/s (%d frames); 60 fps: %.1f ms, %.1f °/s (%d frames). A conforming jaw (%.0f °/s) against the %d °/s screening limit is %s at 120 fps and %s at 60 fps. The R19 verdict does not use the video (event log U = %.1f ms), so the video only cross-checks it" %
                   (1000 * c120[0], c120[1], c120[2], 1000 * c60[0], c60[1], c60[2], jaw_v, lim, decide(jaw_v, lim, c120[1], "upper"),
                    decide(jaw_v, lim, c60[1], "upper"), 1000 * b["close_time_eventlog_s"]["U_k2"])},
    ]
    return rows


def matrix_rows(e, b, ss):
    """One row per requirement R1..R27. Fields: method, procedure, criterion (number and
    tolerance; both values for R15 and R19), instrument (resolution), n and why, status."""
    cap_w, cap_p = OPEN["R15_cap_N"]["written"], OPEN["R15_cap_N"]["proposed"]
    t_w, t_p = OPEN["R19_close_s"]["written"], OPEN["R19_close_s"]["proposed"]
    attr = success_run_n(0.80, 0.90)
    attr_safety = success_run_n(0.90, 0.90)
    U5 = b["pad_force_5N"]["U_k2"]
    Ut = b["close_time_eventlog_s"]["U_k2"]
    m = e["mass"]
    rows = [
        ("R1", "≥ 1 moving transmission DOF", "Demonstration + inspection", "TP-10",
         "Jaw opens and closes through the 1:1 sector pair; GSI confirms a 1:1 pair counts (M20). Pass/fail", "Eyes; assembly drawing", "1 demo; a rule is checked once", "not started"),
        ("R2", "≥ 1 DC motor", "Inspection", "TP-10",
         "GSI answer that a PWM hobby servo counts as the DC motor, recorded in LOG.md (M20). Pass/fail", "Written answer", "1; documentary", "analysed only"),
        ("R3", "≥ 1 analog input", "Demonstration", "TP-10, TP-01",
         "`analogRead` trace of the FSR changes by ≥ 300 mV between 0 and 5 N during a grip [A threshold]", "Host log, 1 mV", "1 trace; a function either works or not", "simulated"),
        ("R4", "≥ 1 digital button", "Demonstration", "TP-10",
         "Each of 5 presses logs one `EVT BUTTON_PRESS`; a 0.8 s hold logs `BUTTON_LONG`", "Event log, 1 ms", "5 presses: catches bounce", "simulated"),
        ("R5", "Microcontroller", "Inspection + test", "TP-10",
         "`arduino-cli compile --fqbn esp32:esp32:esp32` exits 0 on the tested commit; the board boots to IDLE", "Compiler exit code", "1; deterministic", "simulated"),
        ("R6", "State machine, event-driven, no blocking delay()", "Inspection + demonstration", "TP-10, TP-03",
         "No `delay(` in `firmware/gripper/`; the event log of one full cycle shows ENTER_ events in the section 8 order", "grep; event log", "1 full cycle; deterministic code", "simulated"),
        ("R7", "PWM actuator, not the STS3215 bus", "Inspection + test", "TP-10, TP-13",
         "Signal is 50 ± 1 Hz, pulse 500-2500 µs range, clamped 1200-1900 µs by the firmware", "Scope or logic analyser, U = %.1f µs (k = 2)" % b["pulse_us"]["U_k2"], "1 sweep; deterministic", "analysed only"),
        ("R8", "≤ $50 per actuator", "Inspection", "TP-10",
         "Receipt or vendor page price ≤ US$50.00 (BOM: DS3218MG US$12.99)", "Receipt", "1", "analysed only"),
        ("R9", "Compact (rolling envelope)", "Inspection + analysis", "TP-09, TP-11",
         "Hub ≤ Ø23.2 mm to H+1 and ≤ Ø29.2 mm to H+4.5 (tolerance_stacks.md fix 5; DB R9 says Ø24 / Ø30); full wrist roll and flex sweep with no contact", "Calipers ±%.2f mm (k = 2)" % b["caliper_mm"]["U_k2"], "3 readings per diameter; one sweep", "analysed only"),
        ("R10", "Light: mass-moment ≤ 43,720 g·mm", "Test (measurement) + analysis", "TP-09",
         "m × (309.1 mm + COM past H) ≤ 43,720 g·mm with cloth and wiring; stretch ≤ 33,380 (PASS needs ≤ %.0f g·mm after U). CAD revision %s predicts %.0f g·mm (%.1f %%): FAIL at full reach; %s. Disposition: no holds beyond %.1f mm COM reach, enforced by TP-14. The DB and BOM estimates are retained as history" % (m["stretch_gmm"] - b["mass_moment_gmm"]["U_k2"], m["cad_revision"], m["cad_mass_moment_gmm"], 100 * m["cad_fraction_of_budget"], rule(m["budget_gmm"], b["mass_moment_gmm"]["U_k2"], "g·mm", "upper", 5), m["reach_limit_com_mm"]),
         "Balance 0.1 g; knife edge ±1 mm; U = %.0f g·mm" % b["mass_moment_gmm"]["U_k2"], "3 weighings, 3 balance points: averages out placement", "analysed only"),
        ("R11", "Public, cited sources only", "Inspection", "TP-10",
         "Every [S] in docs/gripper has a public URL; none is a course file or pirated PDF", "Reviewer checklist", "1 pass over the source lists", "not started"),
        ("R12", "Compliant fingers, 0.88 ≤ k ≤ 1.63 N/mm", "Test", "TP-12",
         "Secant tip-pad stiffness 0.5-5 N inside 0.88-1.63 N/mm for both fingers with their D7 parts; at the %.0f N proposed cap k ≥ %.2f N/mm" % (cap_p, e["cap"]["proposed"]["k_min_to_reach_5N_N_per_mm"]),
         "Dial 0.01 mm + masses; U = %.1f %% of k" % (100 * b["finger_k_rel"]["U_k2"]), "3 load-unload runs per finger: hysteresis and repeatability of printed TPU", "analysed only (FEA)"),
        ("R13", "Strong gear profile", "Analysis + test", "TP-15, TP-06",
         "Spare sector pair holds LC1 0.38 N·m (DB; gears.md 0.399 with the tension moment) to LC3 2.11 N·m in +20 % steps for 60 s each with no crack and backlash growth ≤ 0.1 mm at the pad [A]", "Lever + hanger masses, ±1 %", "1 destructive pair (2 if PETG is still a candidate): the cost of a pair", "analysed only"),
        ("R14", "Hold ≥ 5.0 N per pad through the 25.5 s hold", "Test", "TP-01, TP-02",
         "Probe force ≥ 5.0 N at every sample of a 25.5 s hold; no slip > 0.5 mm at 2 N tension; pull-to-slip ≥ 4.0 N (SF 2 at μ 0.4)",
         "Pinch probe, U = %.2f N (k = 2) at 5 N" % U5, "%d holds on the softest finger pair and %d on the stiffest (by TP-12): %s; %d pulls: zero-failure run R 0.8 / C 0.9" % (ss["R14_hold_per_finger"]["n_softest"], ss["R14_hold_per_finger"]["n_stiffest"], {"attribute": "softest judged hold by hold as a zero-failure run (each F_min clears 5.0 N + U; the 95/90 bound cannot clear at a bench-sized n), stiffest by the 95/90 bound", "bound": "both judged by the 95/90 bound", "indeterminate": "sized on the softest, lowest-FSR case, where the 95/90 bound cannot clear and the F_min rules decide"}[ss["R14_hold_per_finger"]["softest_mode"]], attr), "simulated"),
        ("R15", "Force cap", "Test + analysis", "TP-04, TP-16",
         "Peak probe force ≤ %.0f N (written) and ≤ %.0f N (proposed) in: G 7, contact 6-10° early, FSR reading 50 %%, pushed finger; FSR_OVER → FAULT within 20 ms of crossing the trip; a shorted, open or frozen FSR or a bad FSR zero ends in FAULT_FSR_SHORT / FAULT_FSR_OPEN (or a miss under 0.60 A) / FAULT_FSR_STUCK / FAULT_ZERO_BAD in 3 of 3 trials (TP-16)" % (cap_w, cap_p),
         "Pinch probe, U = %.2f N at 10 N" % b["pad_force_10N"]["U_k2"], "3 per deterministic case (G 7, early contact, FSR at 50 %%); %d pushed-finger trips: zero-failure run R 0.9 / C 0.9 (safety)" % attr_safety, "simulated"),
        ("R16", "Servo hold ≤ 40 % of stall", "Test", "TP-13",
         "Stall torque ≥ %.2f N·m (%.1f kg·cm) at the 6.35 V rail low end; hold current ≤ 40 %% of stall current" % (e["stall"]["stall_needed_Nm"], e["stall"]["stall_needed_kgcm"]),
         "Lever + probe; U = %.1f %% of T" % (100 * b["stall_torque_rel"]["U_k2"]), "3 stalls of ≤ 2 s: winding heats 3 K per 0.2 s", "analysed only"),
        ("R17", "Moment arm r_c ≤ 65 mm", "Inspection", "TP-09",
         "Pivot-to-pad-normal distance r_c on both fingers, one-sided (the requirement is a maximum, so a short arm is not a fail): %s. U = %.3f mm" %
         (rule(65.0, b["rc_mm"]["U_k2"], "mm", "upper", 4), b["rc_mm"]["U_k2"]),
         "Calipers and square, U = %.3f mm (the r_c method, not the caliper alone)" % b["rc_mm"]["U_k2"], "3 readings per finger", "analysed only"),
        ("R18", "Motion range", "Test + inspection", "TP-08, TP-10",
         "Open stop +20 ± 1° (TP-08). Floor θ ≥ θ_c0 − %.1f° in the force loop (config.h JAW_FLOOR_BELOW_C0_DEG) and θ ≥ %.1f° absolute (JAW_MIN_DEG, inside DB R18's −11°) checked by inspection of the firmware clamp in TP-10; the bench closes never reach it (squeeze cap about −3°), so it is not exercised" % (e["jaw_floor"]["below_c0_deg"], e["jaw_floor"]["min_deg"]), "Protractor on video ±%.1f°" % b["jaw_angle_deg"]["U_k2"], "3 sweeps", "simulated"),
        ("R19", "Close time", "Test", "TP-03",
         "From `G 5` at the open stop (+20°): written, full close (contact) ≤ %.2f s; proposed, 4.5 N and 5.0 N each ≤ %.2f s. Both: last 3° before contact: commanded speed JAW_SPEED_NEAR_DPS = %.0f °/s (DB limit 20, inspected, U = 0) and the video fit v + U ≤ %.0f °/s (U = %.1f °/s). Each time: %s, on the upper 95 %%/90 %% tolerance bound of the closes" % (t_w, t_p, e["jaw_speed"]["cmd_dps"], e["jaw_speed"]["screening_limit_dps"], e["jaw_speed"]["U_fit_dps"], rule(0.5, Ut, "s", "upper", 4).replace("value", "bound")),
         "Event log U = %.1f ms; video 240 fps U = %.1f ms" % (1000 * Ut, 1000 * b["close_time_video_s"]["U_k2"]),
         "%d closes: the 95/90 tolerance bound clears 0.75 s at n = %d on the predicted %.0f ms scatter; 10 gives a scatter estimate" % (10, ss["R19_proposed_F4p5"]["n"], 1000 * e["close_sigma_s"]["total"]), "simulated"),
        ("R20", "Stall back-off ≤ 200 ms", "Test", "TP-05, TP-16",
         "Back-off command begins ≤ 200 ms after over-current onset (host test 140 ms); %s. The reading 'unloaded within 200 ms' is also logged (O11). A stall after contact trips the force-loop limit (%.1f A) in 3 of 3 (TP-05 part D); a current sensor lost after boot ends in FAULT_I_SENSOR in 3 of 3 (TP-16)" % (rule(200.0, 1000 * b["fault_timing_s"]["U_k2"], "ms", "upper", 4), e["stall_trip_A"]["force_loop"]), "50 Hz ST lines + INA219 (20 ms tick), U = %.1f ms" % (1000 * b["fault_timing_s"]["U_k2"]), "%d blocked closes: zero-failure run R 0.9 / C 0.9 (safety); 3 stalls after contact" % attr_safety, "simulated"),
        ("R21", "Calibration stores θ_c0", "Demonstration + test", "TP-08",
         "Boot log shows `EVT CAL_THETA_C0` inside −4…+4°; 10 recalibrations scatter ≤ ±0.27° (one deadband) [A]", "Event log, 0.01°", "10: estimates the scatter itself", "simulated"),
        ("R22", "Wrist interface", "Inspection + test", "TP-11",
         "Coupon slides onto the real horn pilot by hand; BC Ø14.0 and pilot Ø19.2 (M15) measured; 4 × M3 seat with ≥ 1.5 mm engagement. Rev B gate (TP-11 part F): servo body width W and shaft offset s on 3 servos, pocket chosen so printed P − W_max is 0.10-0.30 mm (PASS), ≤ 0.00 mm (FAIL), else INDETERMINATE", "Calipers; coupon", "1 coupon per CAD size tried", "analysed only"),
        ("R23", "Camera provision", "Inspection", "TP-11",
         "2 × M3 insert bores on the front plate accept an M3 screw; camera allowance 10 g counted in R10", "Eyes; an M3 screw", "1", "analysed only"),
        ("R24", "Work cell", "Inspection + test", "TP-14",
         "Shoulder_lift axis within ±50 mm of the cloth tension line; COM reach ≤ %.1f mm (R10 budget / CAD mass), equivalent fingertip reach ≤ %.1f mm; existing feed-pose fingertip reach ≤ 300 mm is tighter; arm shoulder load ≤ 50 %% of stall (M19)" % (m["reach_limit_com_mm"], m["reach_limit_fingertip_mm"]), "Tape ±1 mm; STS3215 load register", "1 layout; 3 load readings", "analysed only"),
        ("R25", "Life 1e5 grips", "Analysis + test (screen)", "TP-06",
         "Analysis (dyno.md) carries the 1e5 claim. Bench screen: 1e4 fast cycles with no fault, no crack, backlash growth ≤ 0.1 mm, hold still ≥ 5.0 N", "Dial 0.01 mm; probe", "1 unit, 1e4 cycles: a zero-failure demo of 1e5 needs about 2.6e5 cycles (β 2, C 0.5) — not affordable", "analysed only"),
        ("R26", "Servo case ≤ 60 °C after 30 min", "Test", "TP-07",
         "Case thermocouple: %s, at 30 min of the section 7 duty cycle at 5 N. Printed mount (thermocouple in the C3 hole under a servo ear), thermal.md section 3: %s with bare PETG (limit 50 °C), %s with the C1 metal sleeves (limit 60 °C). Report ambient" % (rule(60.0, b["case_temp_C"]["U_k2"], "°C", "upper", 3), rule(50.0, b["case_temp_C"]["U_k2"], "°C", "upper", 3), rule(60.0, b["case_temp_C"]["U_k2"], "°C", "upper", 3)), "Type K + MAX31855 on case and mount, U = %.1f °C" % b["case_temp_C"]["U_k2"], "1 soak (30 min) + 1 repeat if within 5 °C of the limit", "analysed only (model fails 9 of 12)"),
        ("R27", "Power rail", "Test + inspection", "TP-13",
         "Rail 6.5 ± 0.15 V (DB says 6.0 V, superseded) and ≥ 6.35 V during a stall; supply rated ≥ 3 A (4 A until M6, dyno.md); 1000 µF at the servo; common ground", "DMM U = %.2f V; scope" % b["rail_V"]["U_k2"], "3 stalls", "analysed only"),
    ]
    out = []
    for r in rows:
        out.append({"id": r[0], "requirement": r[1], "method": r[2], "procedure": r[3], "pass_criterion": r[4],
                    "instrument": r[5], "sample_size": r[6], "status": r[7]})
    return out


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------
def write_csv(path: Path, rows: list[dict], fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def write_text_lf(path: Path, text: str) -> None:
    """UTF-8 with LF line endings on every platform (Path.write_text would write CRLF on Windows)."""
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def round_floats(o, sig: int = 10):
    """Round every float to `sig` significant digits so a last-bit difference between machines
    (numpy / scipy builds) cannot change a committed byte."""
    if isinstance(o, float):
        return float("%.*g" % (sig, o))
    if isinstance(o, dict):
        return {k: round_floats(v, sig) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [round_floats(v, sig) for v in o]
    return o


def md_table(rows: list[dict], fields: list[str], headers: list[str] | None = None) -> str:
    headers = headers or fields
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(k, "")).replace("|", "/") for k in fields) + " |")
    return "\n".join(out)


def replace_block(path: Path, name: str, content: str):
    text = path.read_text(encoding="utf-8")
    begin, end = "<!-- %s:begin -->" % name, "<!-- %s:end -->" % name
    if begin not in text or end not in text:
        raise ValueError("markers %s missing in %s" % (name, path))
    pre = text.split(begin)[0]
    post = text.split(end)[1]
    write_text_lf(path, pre + begin + "\n" + content.rstrip() + "\n" + end + post)


# One session header for every data sheet (CSV lines starting with "#", and the top block of the HTML).
SESSION_FIELDS = [
    ("date", "Date (yyyy-mm-dd)"),
    ("tester", "Tester"),
    ("unit_serial", "Unit serial"),
    ("firmware", "Firmware version or commit"),
    ("ambient_C", "Ambient temperature, °C"),
    ("supply_V_at_servo", "Supply voltage measured at the servo, V"),
    ("instruments", "Instrument ids with calibration date"),
    ("fsr_cal_id", "FSR calibration id (FSR-CAL.csv)"),
]


def session_header_html() -> str:
    cells = "".join("<tr><td>%s</td><td>____________________</td></tr>" % html.escape(label) for _, label in SESSION_FIELDS)
    return "<table class='meta' data-block='session-header'>%s</table>" % cells


FSR_CAL_FIELDS = ["fsr_cal_id", "date", "tester", "unit_serial", "probe_cal_id", "cal_force_N", "span", "trigger",
                  "e_1N", "e_2N", "e_3N", "e_4N", "e_5N", "e_6N", "e_7N", "max_abs_e_N", "verdict"]

PAGE_CSS = ("body{font-family:Arial,Helvetica,sans-serif;font-size:10pt;margin:12mm;color:#000;background:#fff}"
            "h1{font-size:14pt;margin:0 0 4px}table{border-collapse:collapse;width:100%;margin-top:6px}"
            "td,th{border:1px solid #444;padding:3px 4px;vertical-align:top}th{background:#eee;text-align:left}"
            ".row td{height:20px}.meta td{border:none;padding:1px 4px}@page{size:letter;margin:10mm}")


def datasheet_html(pid, title, reqs, criteria, cols, nrows):
    head = "".join("<th>%s</th>" % html.escape(c) for c in cols)
    body = "".join("<tr class='row'>" + "".join("<td></td>" for _ in cols) + "</tr>" for _ in range(nrows))
    crit = "".join("<li>%s</li>" % html.escape(c) for c in criteria)
    return ("<!doctype html><html><head><meta charset='utf-8'><title>%s data sheet</title><style>%s</style></head><body>"
            "<h1>%s: %s</h1>"
            "%s"
            "<p><b>Requirements:</b> %s. <b>Pass criteria</b> (from VERIFICATION-MATRIX.md):</p><ul>%s</ul>"
            "<table><tr>%s</tr>%s</table>"
            "<p><b>Result:</b> PASS / FAIL / INDETERMINATE / NOT RUN (R15, R19: one result per value) &nbsp; <b>Signed:</b> ____________ &nbsp; Copy the result to SIGNOFF.</p>"
            "</body></html>") % (pid, PAGE_CSS, pid, html.escape(title), session_header_html(), ", ".join(reqs), crit, head, body)


def main():
    # The report prints ∝, ±, ° and ≤: a Windows console (cp1252) cannot encode them, so write UTF-8 everywhere.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    out_buf = io.StringIO()

    def say(*a):
        print(*a)
        print(*a, file=out_buf)

    np.random.seed(SEED)
    for k, p in INPUT_FILES.items():
        if not p.exists():
            raise SystemExit("missing input %s: %s" % (k, p))
    fw, dyno, fea = load_json("fw_sim"), load_json("dyno"), load_json("fea_summary")
    db_out, pay = load_json("design_basis_out"), load_json("payload_torque")
    fitcheck = load_json("cad_fitcheck")
    if "mass" not in fitcheck:
        raise SystemExit("CAD fit check input has no mass object: %s" % INPUT_FILES["cad_fitcheck"])
    cfg = parse_config_h(INPUT_FILES["config_h"])
    bom_mass = bom_total_mass_g(INPUT_FILES["bom"])
    req_ids = requirement_ids(INPUT_FILES["design_basis"])

    e = expected_values(fw, dyno, fea, db_out, pay, cfg, bom_mass, fitcheck["mass"])
    b = instrument_budgets(e, cfg)

    # Sample sizes from the predicted scatter.
    sig_t = math.hypot(e["close_sigma_s"]["total"], b["force_time_stream_s"]["u_c"])
    ss = {}
    for label, lim in OPEN["R19_close_s"].items():
        ss["R19_%s_contact" % label] = sample_size(e["close_range"]["t_contact_s"][1], sig_t, lim, "upper")
        ss["R19_%s_F4p5" % label] = sample_size(e["close_range"]["t_F4p5_s"][1], sig_t, lim, "upper")
        ss["R19_%s_F5_k_ge_1" % label] = sample_size(e["close_range"]["t_F5p0_s_k_ge_1"][1], sig_t, lim, "upper")
    # Hold force: FSR span error dominates the run-to-run scatter of the true force. A
    # 2 % span repeatability [A] on 5 N plus the probe u.
    sig_F = math.hypot(0.02 * 5.0, b["pad_force_5N"]["u_c"])
    ss["R14_hold"] = sample_size(e["close"]["1.24 FEA E67+D7"]["F_hold_mean_N"], sig_F, 5.0, "lower")
    ss["R14_hold_softest"] = sample_size(e["hold_range_N"][0], sig_F, 5.0, "lower")
    # R14 is judged on the unfavourable finger as well as the favourable one, and both pairs
    # (softest and stiffest by TP-12) are held. How the softest pair is sized depends on where
    # its predicted hold lands against the probe U and the 95/90 bound.
    soft, stiff = ss["R14_hold_softest"], ss["R14_hold"]
    U5 = b["pad_force_5N"]["U_k2"]
    n_bound = next((n for n in range(3, 201) if k_one_sided(n) * sig_F <= soft["margin"]), None) if soft["margin"] > 0 else None
    if soft["rule"] == "tolerance bound clears":
        mode, n_soft = "bound", soft["n"]
        why = "the 95/90 bound clears 5.0 N at n %d" % n_soft
    elif soft["margin"] >= U5:
        # Every hold is decidable on its own (margin >= U) but the bound is not reachable at a
        # bench-sized n: judge the pair as a zero-failure run on the per-hold minimums.
        mode, n_soft = "attribute", success_run_n(0.80, 0.90)
        p_hold = float(stats.norm.cdf((soft["margin"] - U5) / sig_F))
        soft_path = next(c["hold_path"] for c in e["close"].values() if c["F_hold_mean_N"] == e["hold_range_N"][0])
        why = ("predicted hold %.3f N, margin %.3f N = %.1f U, so each hold's F_min is decidable on its own; the 95/90 bound needs n %s "
               "(k <= %.2f at sigma %.3f N), so the pair is a zero-failure run on F_min: %d holds, every F_min PASS shows R 0.80 at C 0.90; "
               "its bound L is reported, not judged. Risk: at that sigma one hold clears 5.0 N + U with p %.2f and %d clean holds with p %.2f; "
               "the sigma is the FSR-span loop scatter%s, so TP-01's measured scatter decides whether the run is realistic" %
               (e["hold_range_N"][0], soft["margin"], soft["margin"] / U5, n_bound if n_bound else "> 200", soft["margin"] / sig_F, sig_F, n_soft,
                p_hold, n_soft, p_hold ** n_soft,
                ", and this finger holds at the squeeze cap (FORCE_SAT), where position, not the FSR, sets the force" if soft_path == "FORCE_SAT" else ""))
    else:
        mode, n_soft = "indeterminate", max(stiff["n"], soft["n"])
        why = ("predicted hold %.3f N, margin %.3f N is inside U %.3f N: the verdict is expected INDETERMINATE and comes from the F_min rules; "
               "the n only gives the estimate" % (e["hold_range_N"][0], soft["margin"], U5))
    n_stiff = stiff["n"]
    ss["R14_hold_per_finger"] = {"n": max(n_soft, n_stiff), "n_softest": n_soft, "n_stiffest": n_stiff, "n_total": n_soft + n_stiff,
                                 "fingers": 2, "softest_mode": mode, "n_bound_softest": n_bound,
                                 "rule": "%d holds on the softest pair and %d on the stiffest (k from TP-12) = %d holds. Softest: %s. Stiffest: the 95/90 bound clears 5.0 N at n %d (margin %.3f N)" %
                                         (n_soft, n_stiff, n_soft + n_stiff, why, n_stiff, stiff["margin"])}
    # TP-01 runs every R14 hold: its data sheet has one row per hold and its bench time follows the hold count.
    n_holds = ss["R14_hold_per_finger"]["n_total"]
    per_hold_s = HOLD_S + cfg["TIMEOUT_RETRACT_MS"] / 1000.0 + CLOSE_TO_HOLD_S
    tp01_min = int(math.ceil(TP01_BASE[1] + (n_holds - TP01_BASE[0]) * per_hold_s / 60.0))
    procs = [p[:4] + ((tp01_min if p[0] == "TP-01" else p[4]),) + p[5:] for p in PROCEDURES]
    ds_rows = dict(DATASHEET_ROWS, **{"TP-01": n_holds})
    for label, c in e["cap"].items():
        ss["R15_%s_peak_normal" % label] = sample_size(e["peak_range_N"][1], sig_F * 6.2 / 5.0, c["cap_N"], "upper")
    ss["R26_temp"] = {"n": 1, "rule": "one 30 min soak; repeat once if within 5 °C of 60 °C [A]"}
    ss["attribute_function"] = {"n": success_run_n(0.80, 0.90), "rule": "zero failures shows R 0.80 at C 0.90"}
    ss["attribute_safety"] = {"n": success_run_n(0.90, 0.90), "rule": "zero failures shows R 0.90 at C 0.90"}
    beta, C, R = 2.0, 0.5, 0.9
    life_ratio = (math.log(1 - C) / math.log(R)) ** (1 / beta)
    ss["R25_life"] = {"cycles_needed_one_unit": life_ratio * 1e5, "beta_A": beta, "C": C, "R": R,
                      "rule": "Lipson single-unit zero-failure test: (t/T)^beta = ln(1-C)/ln(R)"}
    # Cross-check the tolerance factor by Monte Carlo (seeded).
    rng = np.random.default_rng(SEED)
    n_mc, n = 20000, 10
    x = rng.standard_normal((n_mc, n))
    kf = k_one_sided(n)
    bound = x.mean(1) + kf * x.std(1, ddof=1)
    mc_conf = float(np.mean(bound >= stats.norm.ppf(0.95)))

    res = resolvability(e, b)
    eq = equipment()
    alts = alternatives(e, b, cfg)
    mx = matrix_rows(e, b, ss)

    # -------- stdout summary --------
    say("Gripper verification plan calculator (docs/gripper/test/test_plan.py)")
    say("Requirements found in DESIGN-BASIS section 1: %d (%s ... %s)" % (len(req_ids), req_ids[0], req_ids[-1]))
    say("Matrix rows: %d" % len(mx))
    say("")
    say("Open requirements, reported at both values")
    for label, c in e["cap"].items():
        say("  R15 cap %-8s %4.1f N: U_max %.2f deg; squeeze-cap reach of the softest R12 finger %.2f N (the firmware sim holds less, see Expected values); k for 5 N >= %.3f N/mm (%.3f with 0.64 deg lag); FSR-50%% peak %.2f N -> %s"
            % (label, c["cap_N"], c["U_max_deg"], c["F_max_softest_R12_finger_N"], c["k_min_to_reach_5N_N_per_mm"],
               c["k_min_to_reach_5N_with_0p64deg_lag_N_per_mm"], c["fsr50_peak_stiff_N"], "pass" if c["fsr50_passes"] else "FAIL"))
    p = e["cap"]["proposed"]
    say("  For the 8 N cap the firmware would need: trip %.1f N, soft limit %.1f N, F_SET_MAX %.1f N, U_max %.2f deg" %
        (p["suggested_trip_N"], p["suggested_soft_limit_N"], p["suggested_F_SET_MAX_N"], p["U_max_deg"]))
    cr = e["close_range"]
    for label, lim in OPEN["R19_close_s"].items():
        pf = lambda x: "pass" if x <= lim else "FAIL"
        say("  R19 %-8s %.2f s: contact %.3f-%.3f s (%s); 4.5 N %.3f-%.3f s (%s); 5.0 N %.3f-%.3f s at k >= 1.0 (%s), %.3f s at k 0.88 (%s); HOLD %.3f-%.3f s" %
            (label, lim, cr["t_contact_s"][0], cr["t_contact_s"][1], pf(cr["t_contact_s"][1]),
             cr["t_F4p5_s"][0], cr["t_F4p5_s"][1], pf(cr["t_F4p5_s"][1]),
             cr["t_F5p0_s_k_ge_1"][0], cr["t_F5p0_s_k_ge_1"][1], pf(cr["t_F5p0_s_k_ge_1"][1]),
             cr["t_F5p0_s"][1], pf(cr["t_F5p0_s"][1]), cr["t_HOLD_s"][0], cr["t_HOLD_s"][1]))
    js = e["jaw_speed"]
    say("  Jaw speed, last 3 deg: command %.0f deg/s (DB limit 20 -> %s); video fit U %.2f deg/s over %d frames; a conforming jaw (%.0f deg/s) against the DB limit is %s, against the %.0f deg/s screening limit %s" %
        (js["cmd_dps"], js["verdict_command"], js["U_fit_dps"], js["n_frames"], js["jaw_expected_max_dps"], js["verdict_db_limit_on_jaw"],
         js["screening_limit_dps"], js["verdict_screening_on_jaw"]))
    say("  Close-time scatter per gripper: frame phase %.1f ms, servo %.1f ms [A], total %.1f ms" %
        (1000 * e["close_sigma_s"]["frame_phase"], 1000 * e["close_sigma_s"]["servo_A"], 1000 * e["close_sigma_s"]["total"]))
    say("")
    say("Expected values")
    say("  Hold force (sim, R12 window): %.2f-%.2f N; peak %.2f-%.2f N" % (*e["hold_range_N"], *e["peak_range_N"]))
    say("  Slip capacity 2*mu*F = %.2f N at mu %.1f, F %.1f N; SF %.1f against %.1f N" %
        (e["slip"]["capacity_N"], e["slip"]["mu_A"], e["slip"]["F_hold_N"], e["slip"]["sf"], e["slip"]["tension_N"]))
    st = e["stall"]
    say("  Stall needed %.3f N m (%.2f kg cm); predicted %.3f N m at 6.5 V, %.3f at 6.35 V; %.1f N on a %.0f mm lever; winding 125 C in %.1f-%.1f s" %
        (st["stall_needed_Nm"], st["stall_needed_kgcm"], st["predicted_6p5V_Nm"], st["predicted_6p35V_Nm"], st["force_at_lever_N"], st["lever_mm"],
         min(st["t_winding_125C_s_fitA_25_40"]), max(st["t_winding_125C_s_fitA_25_40"])))
    say("  Case temperature at 30 min (dyno model, upper bound): %.1f-%.1f C" % tuple(e["thermal_range_C"]))
    mm = e["mass"]
    say("  History only (superseded by CAD revision B): DB %.0f g (check %.0f g mm = %.0f); BOM %.1f g + cloth + wiring = %.1f g -> %.0f g mm = %.0f %% of %.0f; max mass at COM %.1f mm: %.1f g" %
        (mm["db_estimate_g"], mm["db_mass_moment_gmm"], mm["db_check_gmm"], mm["bom_on_arm_g"], mm["bom_plus_cloth_wiring_g"],
         mm["bom_mass_moment_at_db_com_gmm"], 100 * mm["bom_fraction_of_budget"], mm["budget_gmm"], mm["db_com_mm"], mm["max_mass_at_db_com_g"]))
    say("")
    say("Instrument budgets (expanded, k = 2)")
    say("  Probe sensitivity %.2f uV/N, noise %.4f N rms, full scale %.1f N" %
        (b["probe_sensitivity_uV_per_N"], b["probe_noise_N_rms"], b["probe_fs_N"]))
    for key, unit, scale in [("pad_force_5N", "N", 1), ("pad_force_8N", "N", 1), ("pad_force_10N", "N", 1), ("pull_force_4N", "N", 1),
                             ("close_time_eventlog_s", "ms", 1000), ("force_time_stream_s", "ms", 1000), ("close_time_video_s", "ms", 1000), ("case_temp_C", "C", 1),
                             ("mass_moment_gmm", "g mm", 1), ("finger_k_rel", "%", 100), ("stall_torque_rel", "%", 100),
                             ("current_A", "A", 1), ("rail_V", "V", 1), ("pulse_us", "us", 1), ("caliper_mm", "mm", 1), ("rc_mm", "mm", 1),
                             ("jaw_angle_deg", "deg", 1), ("backlash_mm", "mm", 1), ("slip_mm", "mm", 1)]:
        say("  %-22s U = %8.4f %-4s (dominant: %s)" % (key, b[key]["U_k2"] * scale, unit, b[key]["dominant"]))
    say("")
    say("Can each instrument resolve its criterion? (limit/U >= 10; |margin|/U >= 1 = verdict decidable at the predicted value)")
    for r in res:
        say("  %-5s %-4s %-58s limit %9.3f pred %9.3f U %7.4f %-4s limit/U %7.1f margin/U %6.2f" %
            (r["test"], r["req"], r["quantity"][:58], r["limit"], r["predicted"], r["U_k2"], r["unit"], r["limit_over_U"], r["margin_over_U"]))
    say("")
    say("Sample sizes")
    for k, v in ss.items():
        say("  %-26s %s" % (k, json.dumps({kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()})))
    say("  tolerance factor k(10, 95 %%, 90 %%) = %.4f; Monte Carlo confidence %.4f (n_mc %d, seed %d)" % (kf, mc_conf, n_mc, SEED))
    say("")
    for a in alts:
        say("Alternative for %s: %s -> %s" % (a["item"], a["u_before"], a["u_after"]))
    say("Equipment: buy total US$%.2f (minimum without spares US$%.2f) against a US$%.0f budget; with fallbacks US$%.2f" %
        (eq["total_buy_usd"], eq["minimum_buy_usd"], eq["budget_usd"], eq["total_with_fallbacks_usd"]))
    say("TP-01: %d holds, %d data-sheet rows, %d min (%d min for %d holds + %.1f s per further hold: %.1f s hold, %.1f s RETRACT, %.1f s close)" %
        (n_holds, ds_rows["TP-01"], tp01_min, TP01_BASE[1], TP01_BASE[0], per_hold_s, HOLD_S, cfg["TIMEOUT_RETRACT_MS"] / 1000.0, CLOSE_TO_HOLD_S))
    total_min = sum(p[4] for p in procs)
    say("Procedures: %d; bench time %d min (%.1f h) excluding the TP-06 unattended run" % (len(procs), total_min, total_min / 60))

    # -------- files --------
    write_csv(HERE / "verification_matrix.csv", mx, ["id", "requirement", "method", "procedure", "pass_criterion", "instrument", "sample_size", "status"])
    replace_block(HERE / "VERIFICATION-MATRIX.md", "matrix",
                  md_table(mx, ["id", "requirement", "method", "procedure", "pass_criterion", "instrument", "sample_size", "status"],
                           ["ID", "Requirement", "Method", "Procedure", "Pass criterion", "Instrument (resolution or U)", "Sample size and why", "Status"]))
    open_rows = []
    for label, c in e["cap"].items():
        open_rows.append({"item": "R15 cap, %s" % label, "value": "%.0f N" % c["cap_N"],
                          "procedure": "TP-04", "instrument": "Pinch probe, U %.2f N" % b["pad_force_10N"]["U_k2"],
                          "pass": "Peak ≤ %.0f N in every case" % c["cap_N"],
                          "predicted": "Normal grip peak %.2f N; FSR-50 %% fault %.2f N (%s)" % (e["peak_range_N"][1], c["fsr50_peak_stiff_N"], "pass" if c["fsr50_passes"] else "FAIL"),
                          "changes": ("none: config.h as is (trip 8 N, soft 7.5 N, U_max %.2f°)" % c["U_max_deg"]) if label == "written" else
                          ("trip %.1f N, soft %.1f N, F_SET_MAX %.1f N, U_max %.2f°; R12 lower bound ≥ %.2f N/mm (%.2f with lag margin); finger fold %.1f N becomes above the cap"
                           % (c["suggested_trip_N"], c["suggested_soft_limit_N"], c["suggested_F_SET_MAX_N"], c["U_max_deg"],
                              c["k_min_to_reach_5N_N_per_mm"], c["k_min_to_reach_5N_with_0p64deg_lag_N_per_mm"], c["fold_E56_N"]))})
    for label, lim in OPEN["R19_close_s"].items():
        open_rows.append({"item": "R19 close, %s" % label, "value": "%.2f s" % lim, "procedure": "TP-03",
                          "instrument": "Event log U %.1f ms; video U %.1f ms" % (1000 * b["close_time_eventlog_s"]["U_k2"], 1000 * b["close_time_video_s"]["U_k2"]),
                          "pass": ("contact ≤ %.2f s; 4.5 N arrives %.2f-%.2f s after the limit" % (lim, cr["t_F4p5_s"][0] - lim, cr["t_F4p5_s"][1] - lim)) if label == "written"
                          else ("4.5 N (target band) ≤ %.2f s and 5.0 N ≤ %.2f s" % (lim, lim)),
                          "predicted": "contact %.3f-%.3f s; 4.5 N %.3f-%.3f s; 5.0 N %.3f-%.3f s (k ≥ 1.0), %.3f s (k 0.88)" %
                                       (cr["t_contact_s"][0], cr["t_contact_s"][1], cr["t_F4p5_s"][0], cr["t_F4p5_s"][1],
                                        cr["t_F5p0_s_k_ge_1"][0], cr["t_F5p0_s_k_ge_1"][1], cr["t_F5p0_s"][1]),
                          "changes": ("the 3° slow zone of controls.md 6.3 (contact by 0.5 s; the last-3° rule restated as a jaw-speed limit, controls.md O1); or R19 is read as contact only"
                                      if label == "written" else _r19_proposed_change(e, lim))})
    replace_block(HERE / "VERIFICATION-MATRIX.md", "open",
                  md_table(open_rows, ["item", "value", "procedure", "instrument", "pass", "predicted", "changes"],
                           ["Open item", "Value", "Procedure", "Instrument", "Pass", "Predicted [D]", "What changes in the design"]))
    # Sizing
    srows = []
    for key in ["pad_force_5N", "pad_force_10N", "pull_force_4N", "close_time_eventlog_s", "force_time_stream_s", "close_time_video_s", "case_temp_C",
                "mass_moment_gmm", "finger_k_rel", "stall_torque_rel"]:
        for c in b[key]["components"]:
            srows.append({"budget": key, "component": c["name"], "half_width_or_sigma": "%.4g" % c["value"], "dist": c["dist"], "u": "%.4g" % c["u"]})
        srows.append({"budget": key, "component": "**combined u_c / expanded U (k = 2)**", "half_width_or_sigma": "", "dist": "",
                      "u": "**%.4g / %.4g**" % (b[key]["u_c"], b[key]["U_k2"])})
    replace_block(HERE / "MEASUREMENT-SIZING.md", "budgets",
                  md_table(srows, ["budget", "component", "half_width_or_sigma", "dist", "u"],
                           ["Budget", "Component", "Half-width (rect) or σ (normal)", "Distribution", "Standard uncertainty u"]))
    rrows = [{"test": r["test"], "req": r["req"], "quantity": r["quantity"], "limit": "%.3g %s" % (r["limit"], r["unit"]),
              "pred": "%.3g" % r["predicted"], "U": "%.3g" % r["U_k2"], "lu": "%.0f" % r["limit_over_U"],
              "mu": "%.2f" % r["margin_over_U"], "pv": r["predicted_verdict"], "ok": ("yes" if r["resolves_limit"] else "no") + " / " + ("yes" if r["verdict_decidable"] else "**no**"),
              "note": r["note"]} for r in res]
    replace_block(HERE / "MEASUREMENT-SIZING.md", "resolve",
                  md_table(rrows, ["test", "req", "quantity", "limit", "pred", "U", "lu", "mu", "pv", "ok", "note"],
                           ["Test", "Req", "Quantity", "Limit", "Predicted", "U (k = 2)", "Limit / U", "Margin / U", "Predicted outcome", "Resolves limit / verdict decidable", "Note"]))
    sz = [{"case": k, "n": v.get("n", round(v.get("cycles_needed_one_unit", 0))), "rule": v["rule"],
           "margin": ("%.4g" % v["margin"]) if "margin" in v else ""} for k, v in ss.items()]
    replace_block(HERE / "MEASUREMENT-SIZING.md", "samples", md_table(sz, ["case", "n", "margin", "rule"], ["Case", "n", "Predicted margin", "Rule"]))
    # Equipment
    erows = [{"item": r["item"], "qty": r["qty"], "usd": ("%.2f" % r["unit_usd"]) if r["mode"] == "buy" else "borrow",
              "used": r["used_in"], "res": r["resolution"], "src": r["source"]} for r in eq["rows"]]
    erows.append({"item": "**Total to buy**", "qty": "", "usd": "**%.2f**" % eq["total_buy_usd"], "used": "", "res": "", "src": "[D]"})
    replace_block(HERE / "EQUIPMENT.md", "equipment", md_table(erows, ["item", "qty", "usd", "used", "res", "src"],
                                                               ["Item", "Qty", "US$", "Used in", "Resolution", "Source"]))
    frows = [{"item": f["item"], "usd": "%.2f [A]" % f["usd_A"]} for f in eq["fallback_if_not_borrowed"]]
    replace_block(HERE / "EQUIPMENT.md", "alternatives",
                  md_table(alts, ["item", "used", "alt", "u_before", "u_after"],
                           ["Item the lab may not lend", "Used for", "Alternative a student can get", "U with the original", "U with the alternative"]))
    replace_block(HERE / "EQUIPMENT.md", "fallback", md_table(frows, ["item", "usd"], ["If the lab cannot lend it", "US$"]))
    # README order table
    pb = procedure_by_id(procs)
    ordrows = []
    phase_min = {}
    i = 0
    for phase, pids in PHASES:
        for extra_phase, extra_title, extra_min in PHASE_EXTRA:
            if extra_phase == phase:
                i += 1
                phase_min[phase] = phase_min.get(phase, 0) + extra_min
                ordrows.append({"n": i, "phase": phase,
                                "pid": "[TP-01 probe build](procedures/TP-01-pad-force.md)", "title": extra_title,
                                "reqs": "(needed by TP-01, 02, 04, 05, 06, 07, 13)", "min": extra_min, "owner": "controls / firmware"})
        for pid in pids:
            i += 1
            pr = pb[pid]
            phase_min[phase] = phase_min.get(phase, 0) + pr[4]
            ordrows.append({"n": i, "phase": phase, "pid": "[%s](procedures/%s)" % (pid, pr[1]), "title": pr[2],
                            "reqs": ", ".join(pr[3]), "min": pr[4], "owner": pr[5]})
    assert sorted(p for _, ps in PHASES for p in ps) == sorted(pb), "every procedure must be in one phase"
    replace_block(HERE / "README.md", "order", md_table(ordrows, ["n", "phase", "pid", "title", "reqs", "min", "owner"],
                                                        ["#", "Session", "Procedure", "What", "Requirements and measurements", "Minutes", "Tell if it fails"]))
    replace_block(HERE / "README.md", "phases", md_table([{"phase": k, "min": v, "h": "%.1f" % (v / 60)} for k, v in phase_min.items()],
                                                         ["phase", "min", "h"], ["Session", "Minutes [A]", "Hours"]))
    placeholders = placeholder_values(e, b, res)

    def expand_template(template):
        def replace(match):
            key = match.group(1)
            if key not in placeholders:
                raise SystemExit("unknown procedure template placeholder: %s" % key)
            return placeholders[key]
        return re.sub(r"\{\{([a-z0-9_.-]+)\}\}", replace, template)

    for pid, filename, *_ in procs:
        template = HERE / "procedure_templates" / filename
        replace_block(HERE / "procedures" / filename, "procedure-body", expand_template(template.read_text(encoding="utf-8")))
        arm, gripper = HARDWARE_SCOPES[pid]
        replace_block(HERE / "procedures" / filename, "hardware-scope",
                      "**Hardware scope — arm: `%s`; gripper: `%s`.** %s %s"
                      % (arm, gripper, SCOPE_SENTENCES[arm], GRIPPER_SENTENCES[gripper]))
    m = e["mass"]
    r10 = r10_work_cell_rule(load_json("cad_fitcheck")["mass"])
    r10_rule = (f"no holds with the gripper COM farther than r_limit = {r10['com_limit_mm']:.1f} mm "
                f"from the shoulder_lift axis ({r10['budget_gmm']:,.0f} g·mm / {r10['mass_g']:.1f} g); "
                f"the equivalent fingertip limit is {r10['fingertip_limit_mm']:.1f} mm")
    replace_block(ROOT / "docs/gripper/DESIGN-BASIS.md", "r10-work-cell-rule",
                  "| R10 | Light | **Keep R10 at {:,.0f} g·mm**, cloth included. That equals ≤ 125 g at 40 mm "
                  "past H. Current estimate: **{:,.0f} g·mm** ({:.1f} %, {:.1f} g, rev B.1 CAD, "
                  "`cad/gripper/out/fitcheck.json`) [D]; the budget is exceeded at full reach. "
                  "*Superseded 2026-10-16: the earlier estimate 40,507 g·mm (93 %, 115.8 g) was the pre-CAD "
                  "number; rev A as built was 50,131.* Stretch goal: ≤ {:,.0f} g·mm, the stock loading [D]. "
                  "Work-cell rule: {}. Douglas ruled this disposition on {}. [D `cad/gripper/out/fitcheck.json`; "
                  "owner ruling] | team / derived | Weigh the part and balance it for the COM; enforce the reach "
                  "gate in TP-14 |"
                  .format(r10["budget_gmm"], r10["mass_moment_gmm"], r10["budget_use_pct"], r10["mass_g"],
                          r10["stock_loading_gmm"], r10_rule, r10["ruling_date"]))
    replace_block(ROOT / "docs/gripper/RISK.md", "r10-work-cell-rule",
                  "| F52 | R10 | Use: arm payload | Stay within the arm's mass-moment budget (R10) | Gripper too "
                  "heavy for shoulder_lift | Arm droops, overheats, or stalls | Current CAD mass {:.1f} g gives a "
                  "full-extension mass-moment of {:,.0f} g·mm ({:.1f} %), above the {:,.0f} g·mm budget; R10 "
                  "remains FAIL at full extension. With the 10 g camera, mass would be {:.1f} g and the overload "
                  "would be worse. Do not fly the camera [D `cad/gripper/out/fitcheck.json`] | TP-14 reach gate "
                  "[D] | 7 | 5 | 3 | 105 | Douglas's {} ruling keeps R10 at {:,.0f} g·mm. Enforce {}. M14 weighs "
                  "the current build and TP-14 measures reach; never command or hold full extension. The old "
                  "103.9 g threshold no longer follows from the current inputs: at the current full-extension lever, "
                  "fail above {:.1f} g or load above 50 % of stall | `cad/gripper/out/fitcheck.json`; DB R10; TP-14 |"
                  .format(r10["mass_g"], r10["mass_moment_gmm"], r10["budget_use_pct"], r10["budget_gmm"],
                          r10["mass_g"] + 10, r10["ruling_date"], r10["budget_gmm"], r10_rule,
                          r10["max_mass_at_full_extension_g"]))
    replace_block(ROOT / "cad/gripper/README.md", "r10-work-cell-rule",
                  "Douglas's {} ruling keeps R10 at **{:,.0f} g·mm**. No option closes R10, and R10 honestly remains "
                  "**FAIL at full extension**. The required work-cell rule is {}. The values come from the current "
                  "CAD mass in `out/fitcheck.json`; TP-14 enforces the reach gate."
                  .format(r10["ruling_date"], r10["budget_gmm"], r10_rule))
    gates = {g["id"]: g for g in e["gate_records"]}
    reach_u = 3.0  # repeated plumb-line/table marks do not support a 1 mm expanded uncertainty
    fingertip_limit = min(m["work_cell_existing_fingertip_limit_mm"], m["reach_limit_fingertip_mm"])
    commanded_fingertip_limit = fingertip_limit - reach_u
    commanded_com_limit = commanded_fingertip_limit - m["fingertip_past_com_mm"]
    def gate_step(record):
        setup = ("Turn the arm motor rail off. Put a rigid prop under the wrist link so the arm cannot drop, "
                 "then place it by hand in the %s." % record["pose"])
        return ("%d. %s Datum: %s. Measure %s using %s. %s. Do not energize or command this pose unless it passes. "
                "<!-- gate-record:%s -->" % (record["step"], setup, record["datum"], record["measurement"],
                                              record["combination"], record["decision"], record["id"]))
    replace_block(HERE / "procedures/TP-14-work-cell.md", "feed-gate", gate_step(gates["tp14-feed"]))
    replace_block(HERE / "procedures/TP-14-work-cell.md", "reach-rule",
                  "The revision %s R10 rule limits horizontal reach to **%.1f mm from the shoulder_lift axis to the gripper COM**. "
                  "The fingertip is %.1f mm beyond that COM (`fitcheck.json` pad position %.1f minus COM %.1f), so the equivalent fingertip limit is %.1f mm. "
                  "The existing 300.0 mm fingertip rule is tighter. Step 7 measures to the **fingertip** with the arm unpowered, then records COM reach = fingertip reach − %.1f mm."
                  % (m["cad_revision"], m["reach_limit_com_mm"], m["fingertip_past_com_mm"],
                     m["cad_com_mm"] + m["fingertip_past_com_mm"], m["cad_com_mm"],
                     m["reach_limit_fingertip_mm"], m["fingertip_past_com_mm"]))
    replace_block(HERE / "procedures/TP-14-work-cell.md", "current-prediction",
                  "| Gripper, cloth and wiring: CAD revision %s | %.1f g | [D] `fitcheck.json` |\n"
                  "| COM past H: CAD revision %s | %.1f mm | [D] `fitcheck.json` |\n"
                  "| Full-extension mass-moment | %.0f g·mm = %.1f %% of the R10 budget (predicted FAIL) | [D] `fitcheck.json` |\n"
                  "| Full-extension shoulder torque | Not predicted here: the repository has no validated mapping from revision %s mass-moment to total shoulder torque; measure at the safe pose and extrapolate as steps 8–10 specify | [A] explicit linear gravity scaling |"
                  % (m["cad_revision"], m["cad_total_g"], m["cad_revision"], m["cad_com_mm"],
                     m["cad_mass_moment_gmm"], 100 * m["cad_fraction_of_budget"], m["cad_revision"]))
    replace_block(HERE / "procedures/TP-14-work-cell.md", "powered-poses",
                  gate_step(gates["tp14-farthest"]) + " The revision %s full-extension pose (COM reach %.1f mm) is therefore **not commanded or held with the rail on**.\n"
                  "9. Only after the feed pose gate and farthest measurement pose gate passed, turn the motor rail on. Command only the feed pose and the farthest measurement pose (target fingertip reach %.1f mm), with gripper and cloth installed. Read shoulder load and current 3 times at each; hold each ≤ 10 s. No other powered pose is permitted by this procedure. <!-- poses:feed pose|farthest measurement pose gate-records:tp14-feed|tp14-farthest -->\n"
                  "10. Calculate the analysed full-extension torque as `T_full = T_arm,full + (T_meas − T_arm,meas) × r_g,full / r_g,meas`. `T_meas` is the step-9 reading converted using the documented servo-load calibration. `T_arm,meas` and `T_arm,full` are model assumptions from `docs/gripper/research/so101.md`: arm-only torque is 0.527 N·m at full extension and is scaled linearly by horizontal reach. `r_g,meas` is the measured horizontal shoulder_lift-to-COM reach; `r_g,full` is %.1f mm. This is analysis only; full extension is not commanded."
                  % (m["cad_revision"], m["full_reach_com_mm"], commanded_fingertip_limit,
                     m["full_reach_com_mm"]))
    replace_block(HERE / "procedures/TP-14-work-cell.md", "reach-pass",
                  "- **R24 layout / R10 reach rule** (tape and repeated plumb-line placement U = %.0f mm; use the largest of three reaches; spread over 4.0 mm is INDETERMINATE): **pass** if |h_off| ≤ 47 mm, "
                  "computed COM reach ≤ %.1f mm, and measured fingertip reach ≤ %.1f mm. The fingertip criterion is tighter than the R10-equivalent %.1f mm. "
                  "**Fail** if |h_off| ≥ 53 mm, COM reach ≥ %.1f mm, or fingertip reach ≥ %.1f mm; **indeterminate** otherwise."
                  % (reach_u, m["reach_limit_com_mm"] - reach_u, fingertip_limit - reach_u,
                     m["reach_limit_fingertip_mm"], m["reach_limit_com_mm"] + reach_u,
                     fingertip_limit + reach_u))
    replace_block(HERE / "procedures/TP-09-mass-envelope.md", "current-mass",
                  "| Gripper, cloth and wiring: CAD revision %s | %.1f g | [D] `fitcheck.json` |\n"
                  "| COM past H: CAD revision %s | %.1f mm | [D] `fitcheck.json` |\n"
                  "| **Mass-moment: CAD revision %s** | **%.0f g·mm (%.1f %%, predicted FAIL at full reach)** | [D] `fitcheck.json` |"
                  % (m["cad_revision"], m["cad_total_g"], m["cad_revision"], m["cad_com_mm"],
                     m["cad_revision"], m["cad_mass_moment_gmm"], 100 * m["cad_fraction_of_budget"]))
    h = m["history"]
    replace_block(HERE / "procedures/TP-09-mass-envelope.md", "history",
                  "Revision A history: the design-basis estimate was %.1f g including cloth at %.1f mm past H, or %s g·mm. "
                  "The intermediate BOM estimate was %.1f g and %s g·mm. These values are not inputs or verdict criteria for this procedure."
                  % (h["design_basis_mass_g"], h["design_basis_com_mm"], f"{h['design_basis_moment_gmm']:,.0f}",
                     h["intermediate_bom_mass_g"], f"{h['intermediate_bom_moment_gmm']:,.0f}"))
    replace_block(HERE / "procedures/TP-01-pad-force.md", "prediction-history",
                  "History: before the firmware regulated its FSR reading 1 N above the setpoint (`F_HOLD_BIAS_N`, `controls.md` 4.1), "
                  "the softest hold prediction was %.2f N, inside U, and was expected INDETERMINATE (`MEASUREMENT-SIZING.md` section 3)"
                  % h["softest_hold_prediction_N"])
    replace_block(HERE / "procedures/TP-09-mass-envelope.md", "mass-verdict",
                  "- **R10:** U = %.4f g·mm. %s. Stretch-goal PASS threshold: %.0f g·mm. "
                  "CAD revision %s predicts FAIL at full reach. The ruled disposition prohibits holds beyond measured `r_limit`; TP-14 enforces it."
                  % (b["mass_moment_gmm"]["U_k2"],
                     rule(m["budget_gmm"], b["mass_moment_gmm"]["U_k2"], "g·mm", "upper", 5),
                     m["stretch_gmm"] - b["mass_moment_gmm"]["U_k2"], m["cad_revision"]))
    replace_block(HERE / "procedures/TP-05-stall-backoff.md", "timing-verdict",
                  "- For each onset-to-back-off run, `analyze_log.py` prints the largest status gap and uses U equal to the larger gap bracketing onset or back-off begin. PASS if value ≤ limit − U; FAIL if value ≥ limit + U; INDETERMINATE in between. A bracketing gap over 40 ms voids the run as INDETERMINATE with a non-zero exit; repeat it. The ceiling allows one delayed nominal period but rejects lost timing resolution. Use the largest run U for the 95 %%/90 %% upper bound.")
    replace_block(HERE / "procedures/TP-16-fault-detection.md", "breakout", r"""### Fault-injection breakout build

Repository names the ESP32 pins but does not name physical connector families or connector pin numbers; label the harness ends with the signal names below and record the chosen connector/pin mapping on the enclosure. Do not invent or rely on an unrecorded pin number.

| Interrupted/injected line | Firmware name and endpoint | Switch | NORMAL circuit | Path voltage/current; minimum rating |
|---|---|---|---|---|
| FSR signal | `PIN_FSR_ADC`, GPIO34, FSR-divider node | One break-before-make SPDT, centre-off: common to GPIO34; throws to the FSR node and 3V3; centre = OPEN | GPIO34 connected to FSR node | 0-3.3 V, ADC leakage only; ≥5 VDC, ≥10 mA |
| Jaw-open limit | `PIN_LIMIT_OPEN`, GPIO26, switch-to-GND input | One break-before-make SPDT, centre-off: common to GPIO26; throws to the real limit switch and GND; centre = OPEN | GPIO26 connected to the real normally-open limit switch, which closes to GND at open stop | 3.3 V pull-up, <1 mA; ≥5 VDC, ≥10 mA |
| INA219 data | `PIN_I2C_SDA`, GPIO21, INA219 SDA | One SPST, normally closed, in series | GPIO21 connected to INA219 SDA | 3.3 V I2C, <1 mA; ≥5 VDC, ≥10 mA |

`PIN_I2C_SCL` is GPIO22 and remains uninterrupted. The breakout never carries the 6.5 V servo rail or either INA219 shunt/current path. Use latching switches whose position is visible. Put all conductors and terminals in a rigid, non-conductive enclosure; use keyed connectors, captive covers over test points, and clamp strain relief on both cable entries so a 20 N hand pull cannot load a solder joint or expose conductor.

**Pre-use inspection, USB and motor rail off:**

1. Covers fitted: PASS only when no bare conductor or probe-accessible live metal is visible; cable clamps resist a 20 N hand pull without movement.
2. NORMAL continuity: meter resistance is <1 Ω from each harness input to output for FSR, limit and SDA; record all three readings.
3. With the rail and USB off, select each path position before placing meter probes; never move a selector while taking a reading. Record this generated table:

| Pair | Selector state | Expected resistance | Tolerance |
|---|---|---:|---:|
| FSR node–GND | FSR NORMAL | 2.7 kΩ plus the FSR parallel path | 2.43–2.97 kΩ when the FSR is open/unloaded |
| FSR node–3V3 | FSR SHORT | continuity | <1 Ω |
| FSR node–3V3 | FSR OPEN | isolation | >1 MΩ |
| Limit–GND | LIMIT CLOSED | continuity | <1 Ω |
| Limit–GND | LIMIT OPEN | isolation | >1 MΩ |
| SDA input–SDA output | SDA NORMAL | continuity | <1 Ω |
| SDA input–SDA output | SDA OPEN | isolation | >1 MΩ |
| Any unrelated signal pair (FSR/limit/SDA) | all NORMAL, limit not at stop | isolation | >1 MΩ |

4. PASS the breakout only if every row passes and the enclosure labels match the recorded connector/pin mapping. Do not power a failed or uninspected breakout.
""")
    say("Sessions: " + "; ".join("%s %d min" % (k, v) for k, v in phase_min.items()))
    # Data sheets
    crit_by_proc = {}
    for r in mx:
        for pid in re.findall(r"TP-\d\d", r["procedure"]):
            crit_by_proc.setdefault(pid, []).append("%s: %s" % (r["id"], r["pass_criterion"]))
    ds = HERE / "datasheets"
    ds.mkdir(exist_ok=True)
    for pid, fname, title, reqs, minutes, owner, cols in procs:
        nrows = ds_rows.get(pid, DATASHEET_ROWS_DEFAULT)
        with (ds / ("%s.csv" % pid)).open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            for key, label in SESSION_FIELDS:  # session header block: "#key,value" lines, value left empty
                w.writerow(["#" + key, ""])
            w.writerow(cols)
        crit = crit_by_proc.get(pid, ["See the procedure for M-measurement outputs (no R-requirement pass number)"])
        write_text_lf(ds / ("%s.html" % pid), datasheet_html(pid, title, reqs, crit, cols, nrows))
    # Calibration log, header only: one row per FSR calibration (TP-01 part C2).
    write_csv(ds / "FSR-CAL.csv", [], FSR_CAL_FIELDS)
    write_csv(ds / "SIGNOFF.csv", [{"id": r["id"], "requirement": r["requirement"], "procedure": r["procedure"],
                                    "pass_criterion": r["pass_criterion"]} for r in mx],
              ["id", "requirement", "procedure", "pass_criterion", "measured", "result_PASS_FAIL_INDETERMINATE_NOT_RUN", "result_at_proposed_value_R15_8N_R19_0p75s", "date", "initials", "data_sheet_ref"])
    srow = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td></td><td></td><td>%s</td><td></td></tr>" %
                   (html.escape(r["id"]), html.escape(r["requirement"]), html.escape(r["procedure"]), html.escape(r["pass_criterion"]),
                    "" if r["id"] in ("R15", "R19") else "n/a") for r in mx)
    write_text_lf(ds / "SIGNOFF.html",
        "<!doctype html><html><head><meta charset='utf-8'><title>Requirement sign-off</title><style>%s td{font-size:8.5pt}</style></head><body>"
        "<h1>Cloth-feed gripper: requirement sign-off</h1>%s<p>Result: PASS / FAIL / INDETERMINATE (inside ± U of the limit) / NOT RUN. Douglas ruled R15 and R19 on 2026-10-12: the requirement is the proposed value (8 N, 0.75 s), recorded in the second result column. The first column keeps the superseded written value (10 N, 0.50 s) for history only.</p>"
        "<table><tr><th>ID</th><th>Requirement</th><th>Procedure</th><th>Pass criterion</th><th>Measured</th><th>Result (written value)</th><th>Result at proposed value</th><th>Initials</th></tr>%s</table></body></html>"
        % (PAGE_CSS, session_header_html(), srow))

    result = {
        "_doc": "Generated by docs/gripper/test/test_plan.py. Do not hand-edit.",
        "seed": SEED, "retrieved": RETRIEVED,
        "inputs_sha256_16": {k: sha16(p) for k, p in INPUT_FILES.items()},
        "open_requirements": OPEN,
        "requirement_ids": req_ids,
        "expected": e, "budgets": b, "resolvability": res, "sample_sizes": ss,
        "tolerance_factor_check": {"n": n, "k": kf, "mc_confidence": mc_conf, "n_mc": n_mc},
        "equipment": eq, "matrix": mx,
        "procedures": [{"id": p[0], "file": p[1], "title": p[2], "requirements": p[3], "minutes": p[4], "owner": p[5], "datasheet_columns": p[6], "datasheet_rows": ds_rows.get(p[0], DATASHEET_ROWS_DEFAULT)} for p in procs],
    }
    write_text_lf(HERE / "test_plan_out.json", json.dumps(round_floats(result), indent=1, ensure_ascii=False, default=float) + "\n")
    write_text_lf(HERE / "test_plan_stdout.txt", out_buf.getvalue())
    return result


def check_generated(root: Path) -> None:
    """Regenerate in a disposable copy and fail if task-owned outputs drift."""
    relative_outputs = tuple(Path(path) for path in (
        "docs/gripper/DESIGN-BASIS.md",
        "docs/gripper/RISK.md",
        "cad/gripper/README.md",
        "docs/gripper/test/procedures/TP-14-work-cell.md",
        "docs/gripper/test/procedures/TP-09-mass-envelope.md",
        "docs/gripper/test/test_plan_out.json",
    ))
    source_root = root.resolve()
    with tempfile.TemporaryDirectory(prefix="gripper-test-plan-") as temp_dir:
        generated_root = Path(temp_dir) / "repo"
        shutil.copytree(source_root, generated_root, ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__"))
        configure_root(generated_root)
        main()
        drift = [path for path in relative_outputs
                 if (source_root / path).read_bytes() != (generated_root / path).read_bytes()]
    configure_root(source_root)
    if drift:
        raise SystemExit("generated-file drift: " + ", ".join(path.as_posix() for path in drift))
    print("generated files are current")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true", help="regenerate in a temporary copy and report drift")
    args = parser.parse_args()
    configure_root(args.root)
    if args.check:
        check_generated(args.root)
    else:
        main()
