"""Gripper thermal lane: servo heat in the hold, lumped network, limits, creep, sensitivity.

Run from the repository root (about 1 min):
    python analysis/gripper/thermal/thermal.py           # text outputs only
    python analysis/gripper/thermal/thermal.py --figures # text outputs and PNGs
    python analysis/gripper/thermal/thermal.py --check   # verify committed outputs; write nothing
Deterministic (no random draws).

Inputs read at run time (sha256 recorded in the JSON):
    cad/gripper/params.json                 servo, housing, wrist mount, duty cycle, grip
    analysis/gripper/results/dyno.json      DS3218MG comparison inputs and shared thermal assumptions
    firmware/gripper/config.h               force setpoints, trip, cap
    docs/gripper/DESIGN-BASIS.md            R19 full-close timing requirement
Tags: [S] sourced (SOURCES below), [D] derived here, [A] assumed with the reason.
Notes: docs/gripper/analysis/thermal.md.
"""
from __future__ import annotations

import copy
import argparse
import contextlib
import hashlib
import io
import json
import math
import re
import sys
from functools import lru_cache
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import network as nw  # noqa: E402

ROOT = HERE.parents[2]
P_PARAMS = ROOT / "cad" / "gripper" / "params.json"
P_DYNO = ROOT / "analysis" / "gripper" / "results" / "dyno.json"
P_CONFIG = ROOT / "firmware" / "gripper" / "config.h"
P_DESIGN_BASIS = ROOT / "docs" / "gripper" / "DESIGN-BASIS.md"
P_NOTE = ROOT / "docs" / "gripper" / "analysis" / "thermal.md"
P_TEST_PLAN_RESULTS = ROOT / "docs" / "gripper" / "test" / "test_plan_out.json"
P_TP07 = ROOT / "docs" / "gripper" / "test" / "procedures" / "TP-07-thermal-soak.md"
OUT_DIR = HERE / "results"
FIG_DIR = HERE / "figures"

PARAMS = json.loads(P_PARAMS.read_text(encoding="utf-8"))
DYNO = json.loads(P_DYNO.read_text(encoding="utf-8"))
TEST_PLAN_RESULTS = json.loads(P_TEST_PLAN_RESULTS.read_text(encoding="utf-8"))
CASE_TEMPERATURE_U_C = TEST_PLAN_RESULTS["budgets"]["case_temp_C"]["U_k2"]
AMBIENT_CALIBRATION_U_C = 1.0 / math.sqrt(3.0)
AMBIENT_RESOLUTION_U_C = 0.125 / math.sqrt(3.0)
AMBIENT_REPRESENTATIVENESS_LIMIT_C = 0.9  # assumed, not sourced: shaded air can vary across the bench
AMBIENT_REPRESENTATIVENESS_U_C = AMBIENT_REPRESENTATIVENESS_LIMIT_C / math.sqrt(3.0)
AMBIENT_TEMPERATURE_U_C = 2.0 * math.sqrt(
    AMBIENT_CALIBRATION_U_C ** 2
    + AMBIENT_RESOLUTION_U_C ** 2
    + AMBIENT_REPRESENTATIVENESS_U_C ** 2
)
AMBIENT_MODEL_RANGE_C = (20.0, 40.0)
AMBIENT_RANGE_C = (
    AMBIENT_MODEL_RANGE_C[0] + AMBIENT_TEMPERATURE_U_C,
    AMBIENT_MODEL_RANGE_C[1] - AMBIENT_TEMPERATURE_U_C,
)
AMBIENT_REPRESENTATIVENESS_LABEL = "assumed, unmeasured, until TP-07's third ambient channel measures it"
R26_LIMIT_C = 60.0


def accepted_ambient_range_text() -> str:
    """The accepted ambient range; the CLI and section 0 both print this text."""
    return f"{AMBIENT_RANGE_C[0]:.3f}–{AMBIENT_RANGE_C[1]:.3f} °C"


def r26_thresholds(u_case: float = CASE_TEMPERATURE_U_C) -> dict:
    """Governing R26 thresholds: exact limits 60 °C ∓ U, rounded inward to 0.1 °C. The CLI and the note both use this."""
    exact_pass = R26_LIMIT_C - u_case
    exact_fail = R26_LIMIT_C + u_case
    return {
        "exact_pass_limit_C": exact_pass,
        "exact_fail_limit_C": exact_fail,
        "pass_at_or_below_C": math.floor(exact_pass * 10.0) / 10.0,
        "fail_at_or_above_C": math.ceil(exact_fail * 10.0) / 10.0,
    }


def r26_band(reading_C: float, thresholds: dict | None = None) -> str:
    limits = r26_thresholds() if thresholds is None else thresholds
    if reading_C <= limits["pass_at_or_below_C"]:
        return "PASS"
    if reading_C >= limits["fail_at_or_above_C"]:
        return "FAIL"
    return "INDETERMINATE"

CONFIG = {m.group(1): float(m.group(2)) for m in re.finditer(
    r"^#define\s+(\w+)\s+(-?[0-9.]+)", P_CONFIG.read_text(encoding="utf-8"), re.M)}


def design_basis_seconds(requirement: str) -> float:
    """Read a seconds-valued requirement from its DESIGN-BASIS table row."""
    row = next((line for line in P_DESIGN_BASIS.read_text(encoding="utf-8").splitlines()
                if line.startswith(f"| {requirement} |")), None)
    if row is None:
        raise ValueError(f"missing {requirement} in {P_DESIGN_BASIS}")
    match = re.search(r"≤\s*\*\*([0-9.]+)\s*s\*\*", row)
    if match is None:
        raise ValueError(f"missing seconds limit in {requirement}: {row}")
    return float(match.group(1))


R19_CLOSE_S = design_basis_seconds("R19")

SOURCES = {
    "petg_tds": "Bambu Lab PETG Basic Technical Data Sheet V2.0 (copy hosted by Additive-X): "
                "https://www.additive-x.com/shop/mpattachments/file/viewonline/id/580/product_id/2330 (retrieved 2026-10-11)",
    "petg_k": "Tychanicz-Kwiecien, Grosicki, Markowicz, 'Experimental Investigation of Thermal Conductivity of "
              "Selected 3D-Printed Materials', Materials 18 (2025) 3950, doi 10.3390/ma18173950: "
              "https://pmc.ncbi.nlm.nih.gov/articles/PMC12428860/ (retrieved 2026-10-11)",
    "petg_creep": "Romeijn, Singh, Behrens, Paul, 'Effect of accelerated weathering on the creep behaviour of "
                  "additively manufactured PETG', J. Polymer Research 28 (2021) 352, doi 10.1007/s10965-021-02707-7; "
                  "accepted manuscript https://opus.lib.uts.edu.au/handle/10453/151771 (retrieved 2026-10-11)",
    "air": "Engineering ToolBox, Dry Air - Thermodynamic and Physical Properties (300 K and 350 K rows): "
           "https://engineeringtoolbox.com/dry-air-properties-d_973.html (retrieved 2026-10-11)",
    "churchill_chu": "Churchill & Chu, Int. J. Heat Mass Transfer 18 (1975) 1323-1329, "
                     "doi 10.1016/0017-9310(75)90243-4; form as given in https://en.wikipedia.org/wiki/Nusselt_number "
                     "(retrieved 2026-10-11)",
    "horizontal": "Horizontal-plate correlations 0.54 Ra^1/4 (hot face up) and 0.27 Ra^1/4 (hot face down), "
                  "L = A/P, after Incropera & DeWitt (2007), as given in https://en.wikipedia.org/wiki/Nusselt_number "
                  "(retrieved 2026-10-11)",
    "emissivity": "Engineering ToolBox, Emissivity Coefficients (anodized aluminium 0.77, black anodize 0.88): "
                  "https://www.engineeringtoolbox.com/emissivity-coefficients-d_447.html; black plastics 0.85-0.92: "
                  "https://www.design1st.com/Design-Resource-Library/engineering_data/ThermalEmissivityValues.pdf "
                  "(both retrieved 2026-10-11)",
    "servo_temp": "ServoDatabase, Miuzei DS3218: operating temperature -15 to 70 C, aluminium case: "
                  "https://servodatabase.com/servo/miuzei/ds3218 (retrieved 2026-10-11)",
    "tpu_tds": "Ultimaker TPU 95A TDS (HDT 50.3 C at 0.45 MPa): "
               "https://um-support-files.ultimaker.com/materials/2.85mm/tds/TPU-95A/Ultimaker-TPU95A-TDS-v5.00.pdf "
               "(cited in DESIGN-BASIS 4)",
    "asa_tds": "Bambu ASA Technical Data Sheet V3.0 (HDT 100 C at 0.45 MPa, 92 C at 1.8 MPa, Vicat 106 C), copy: "
               "https://polyalkemi.no/wp-content/uploads/2024/01/Bambu_ASA_Technical_Data_Sheet.pdf (retrieved 2026-10-11)",
    "maxon": "maxon 'DC motor and EC motor Key information' (two-resistance winding/housing structure): "
             "https://people.ece.ubc.ca/leos/pdf/datasheets/Maxon/MaxonSpecs.pdf (via dyno.md)",
    "ds3218": "DS3218MG comparison data via dyno.json",
    "ds3230": "DS3230 MG vendor listing and actuation_trade.md T1; claims are unmeasured",
}

LOG: list[str] = []


def say(s: str = "") -> None:
    print(s)
    LOG.append(s)


def sha16(p: Path) -> str:
    """sha256 (first 16 hex) with CRLF folded to LF, so a Windows checkout hashes like a Linux one."""
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]


def val(v, tag, note):
    return {"value": v, "tag": tag, "note": note}


# ----------------------------------------------------------------------------------------------
# Inputs
# ----------------------------------------------------------------------------------------------
SV = PARAMS["servo"]
HS = PARAMS["housing"]
WM = PARAMS["wrist_mount"]
GRIP = PARAMS["grip"]
DUTY = PARAMS["duty_cycle"]
TH_DYNO = DYNO["inputs"]["thermal"]["value"]
ETA_G = DYNO["inputs"]["eta_gearbox"]["value"]
ALPHA_CU = TH_DYNO["alpha_Cu"]

R_C = GRIP["r_c_design_mm"] / 1000.0
ETA_MP = GRIP["eta_mesh_pivot"]

K_PETG = 0.20  # W/m/K [S petg_k: 0.198-0.211 at 100 % infill, 22-60 C]
K_AIR_GAP = 0.028  # W/m/K, air at about 50 C film [S air, interpolated]
K_PA6CF = 0.40  # W/m/K [A] printed PA6-CF, no public through-thickness value found; range 0.25-0.8
CP_PETG = 1200.0  # J/kg/K [A] typical amorphous PET-family value
HOT_HOURS_SEMESTER = 84.0  # [A] 14 weeks x 2 lab sessions x 3 h with the gripper powered and gripping

LIMITS = {
    "case_R26_C": val(60.0, "A", "DESIGN-BASIS R26: servo case <= 60 C after 30 min of the duty cycle"),
    "case_servo_rating_C": val(70.0, "S", "DS3218 operating temperature upper limit 70 C (servo_temp); applied to the "
                                          "case, which is conservative because the rating is an ambient"),
    "winding_C": val(TH_DYNO["T_winding_max_C"], "A", "dyno.md winding limit 125 C (enamel and brush life)"),
    "petg_Tg_C": val(68.0, "S", "Bambu PETG Basic DSC glass transition (petg_tds)"),
    "petg_HDT_1p8_C": val(65.0, "S", "Bambu PETG Basic HDT ISO 75 at 1.8 MPa (petg_tds)"),
    "petg_HDT_0p45_C": val(69.0, "S", "Bambu PETG Basic HDT ISO 75 at 0.45 MPa (petg_tds)"),
    "petg_creep_onset_C": val(50.0, "A", "judgement: Romeijn 2021 (petg_creep) saw stress-dependent (non-linear) flexural "
                                         "creep at 50 C under 17.6 MPa [D from an assumed 48 mm span]; the mount screw "
                                         "clamp stress is 14-28 MPa (section 3 of thermal.md), so 50 C is taken as the "
                                         "temperature above which the clamped PETG creeps measurably"),
    "tpu_HDT_C": val(50.3, "S", "Ultimaker TPU 95A HDT at 0.45 MPa (tpu_tds)"),
}


def motor_fit(fit: str, V: float) -> dict:
    """DS3230 output-referred bounds derived from vendor claims [D].

    Low reading uses the listed 3.8 A stall current; high reading uses T1's
    3.99 A rail-sizing value. Both use the 2.877 N m claim at 6.5 V.
    Gearbox efficiency remains the dyno study's unmeasured 0.65 [A].
    """
    if SV["model"] != "DSServo DS3230 MG":
        raise ValueError(f"thermal model requires DS3230 MG, got {SV['model']}")
    current = {"A_mech": 3.99, "B_elec": 3.8, "B_elec_Annimos1p8A": 3.8}[fit]
    torque = SV["stall_torque_kgcm"]["6.5V"] * 0.0980665
    return {"K_out_NmA": torque / current, "R_ohm": V / current,
            "I_stall_A": current, "stall_torque_Nm": torque}


def hold_torque(F_pad: float) -> float:
    """Pinch torque plus the 2 N cloth-tension moment from T1 [D]."""
    if F_pad <= 0:
        return 0.0
    cloth_moment = PARAMS["grip"]["tension_N"] * 11.5e-3
    return (2.0 * F_pad * R_C + cloth_moment) / ETA_MP


@dataclass(frozen=True)
class Scenario:
    T_amb: float = 25.0  # C [A] lab; DESIGN-BASIS 6 allows up to 40
    fit: str = "A_mech"  # dyno.md Fit A (3.75 A stall) or B_elec (2.1 A) or B_elec_Annimos1p8A
    V_rail: float = 6.5  # V, torque_and_actuator.md 6.5 +/- 0.15
    force_N: float = 5.0  # sustained pad force in the hold (R14 setpoint)
    t_close: float = R19_CLOSE_S  # s, DESIGN-BASIS R19 full-close limit
    hold_fraction: float | None = None  # None = from the duty-cycle phases
    conduction: str = "avg"  # 'avg' (continuous conduction) or 'pwm' (discontinuous bound, dyno.md 4)
    enclosure: str = "open"  # 'open' = CAD as drawn; 'enclosed' = closed PETG shroud
    hold_current_factor: float = 1.0  # 1 = motoring-side current; eta_g^2 = friction back-off hold
    eta_g: float | None = None  # gearbox efficiency; None = dyno.json value (0.65, assumed)
    R_wc: float = 10.0  # K/W winding -> case [A]: maxon-structure Rth1 8 (dyno) + 2 for motor can -> shell
    h_scale: float = 1.0  # multiplier on natural convection (correlation uncertainty)
    eps_case: float = 0.85  # [S emissivity] black anodised shell 0.88, plastic covers 0.85-0.92
    G_ch_scale: float = 1.0
    G_cf_scale: float = 1.0
    fin_area_m2: float = 0.0  # extra aluminium fin area on the case (both faces counted)
    al_strap: bool = False  # aluminium strap case -> wrist horn
    T_arm_offset_K: float = 5.0  # [A] wrist horn above ambient (STS3215 holding)
    idle_W: float = 0.0325  # servo board idle: 5 mA x 6.5 V [S ds3218]
    rds_W_per_A2: float = 0.1  # H-bridge conduction loss I^2 x 0.1 ohm (two FETs) [A]
    I_close_frac_stall: float = 0.5  # mean motor current in the close, fraction of stall [A]

    def phases(self) -> dict:
        p = dict(DUTY["phases_s"])
        p["close"] = self.t_close
        return p

    def cycle_s(self) -> float:
        return float(sum(self.phases().values()))

    def fractions(self) -> tuple[float, float]:
        """(hold, close) time fractions. Hold = lift + feed (the cloth is gripped)."""
        p = self.phases()
        cyc = self.cycle_s()
        f_close = p["close"] / cyc
        f_hold = (p["lift_move_to_needle"] + p["feed_hold"]) / cyc
        if self.hold_fraction is not None:
            f_hold = self.hold_fraction
        return f_hold, f_close


# ----------------------------------------------------------------------------------------------
# Heat sources
# ----------------------------------------------------------------------------------------------
def currents(sc: Scenario) -> dict:
    m = motor_fit(sc.fit, sc.V_rail)
    T = hold_torque(sc.force_N)
    eta = ETA_G if sc.eta_g is None else sc.eta_g
    I_hold = T / (m["K_out_NmA"] * eta) * sc.hold_current_factor
    return {"T_hold_Nm": T, "I_hold_A": I_hold, "I_close_A": sc.I_close_frac_stall * m["I_stall_A"],
            "R20_ohm": m["R_ohm"], "I_stall_A": m["I_stall_A"], "K_out": m["K_out_NmA"]}


def copper_W(sc: Scenario, I: float, Tw: float, R20: float) -> float:
    if sc.conduction == "pwm":
        return abs(I) * sc.V_rail  # dyno.md 4: fully discontinuous conduction bound
    return I * I * R20 * (1.0 + ALPHA_CU * (Tw - 20.0))


def heat_sources(sc: Scenario, Tw: float) -> dict:
    c = currents(sc)
    f_hold, f_close = sc.fractions()
    P_hold_w = copper_W(sc, c["I_hold_A"], Tw, c["R20_ohm"])
    P_close_w = copper_W(sc, c["I_close_A"], Tw, c["R20_ohm"])
    P_hold_case = sc.rds_W_per_A2 * c["I_hold_A"] ** 2 + sc.idle_W
    P_close_case = sc.rds_W_per_A2 * c["I_close_A"] ** 2 + sc.idle_W
    avg_w = f_hold * P_hold_w + f_close * P_close_w
    avg_case = f_hold * P_hold_case + f_close * P_close_case + (1 - f_hold - f_close) * sc.idle_W
    return {"P_hold_winding_W": P_hold_w, "P_hold_case_W": P_hold_case, "P_close_winding_W": P_close_w,
            "P_avg_winding_W": avg_w, "P_avg_case_W": avg_case, "P_avg_total_W": avg_w + avg_case,
            "P_peak_total_W": max(P_hold_w + P_hold_case, P_close_w + P_close_case),
            # what the INA219 on the rail sees in the hold (power balance at zero speed) [D]
            "I_rail_hold_A": (P_hold_w + P_hold_case) / sc.V_rail,
            "f_hold": f_hold, "f_close": f_close, **c}


# ----------------------------------------------------------------------------------------------
# Geometry [D from params.json unless tagged]
# ----------------------------------------------------------------------------------------------
def geometry() -> dict:
    mm = 1e-3
    Lx, Ly, Lz = SV["body_y"] * mm, SV["body_x"] * mm, SV["body_z"] * mm  # long axis X (README), 40 x 20 x 38
    z_in = SV["ear_from_top"] * mm
    t = HS["wall"] * mm
    z_out = SV["overall_h"] * mm - z_in - 2 * t  # revision B K4: 25.5 mm, open on four faces
    ear_ext = (SV["ear_span"] - SV["body_y"]) / 2 * mm
    clear = HS["cradle_pocket_clear"] * mm  # 0.2
    wall_h = (HS["deck_y_min"] + SV["body_x"] / 2 - 2.0) * mm  # end walls from y -8 to the deck at y 19 -> 27 mm
    wall_d = (17.0 - 2.5) * mm  # z -17 .. -2.5 (README)
    return {"Lx": Lx, "Ly": Ly, "Lz": Lz, "z_in": z_in, "z_out": z_out, "ear_ext": ear_ext, "t": t,
            "clear": clear, "wall_h": wall_h, "wall_d": wall_d,
            "gap_top": (7.0 - 2.5) * mm,  # case top z -7 to mid plate back face z -2.5 (README)
            "gap_end_walls": 0.5 * mm,  # [A] case band to end walls
            "horn_r": SV["horn_d"] / 2 * mm,
            "recess_d": WM["recess_d_cad"] * mm, "clamp_t": WM["clamp_t"] * mm}


GEO = geometry()


def case_faces(sc: Scenario) -> list[nw.Face]:
    g = GEO
    e = sc.eps_case
    faces = [
        nw.Face("top_exposed", g["Lx"] * g["z_out"], "up", g["Lx"] * g["z_out"] / (2 * (g["Lx"] + g["z_out"])), e, 0.8),
        nw.Face("bottom_exposed", g["Lx"] * g["z_out"], "down", g["Lx"] * g["z_out"] / (2 * (g["Lx"] + g["z_out"])), e, 0.8),
        nw.Face("ends_exposed", 2 * g["Ly"] * g["z_out"], "vertical", g["Ly"], e, 0.8),
        nw.Face("back", g["Lx"] * g["Ly"], "vertical", g["Ly"], e, 0.8),
        nw.Face("ears_back", 2 * g["ear_ext"] * g["Ly"], "vertical", g["Ly"], e, 0.8),
        # band inside the cradle (10 mm): top and bottom faces partly open (window above), half credit [A]
        nw.Face("band_top", 0.5 * g["Lx"] * g["z_in"], "up", g["Lx"] * g["z_in"] / (2 * (g["Lx"] + g["z_in"])), e, 0.5),
        nw.Face("band_bottom", 0.5 * g["Lx"] * g["z_in"], "down", g["Lx"] * g["z_in"] / (2 * (g["Lx"] + g["z_in"])), e, 0.5),
    ]
    if sc.fin_area_m2 > 0:
        # aluminium plate fins, 30 mm tall, fin efficiency ~1 for 1 mm Al at this size [D: m L < 0.3]
        faces.append(nw.Face("al_fin", sc.fin_area_m2, "vertical", 0.030, 0.85, 0.6))
    return faces


def shroud_faces(sc: Scenario) -> list[nw.Face]:
    """Closed PETG shroud: 3 mm air gap + 2 mm wall around the exposed part [A]."""
    g, d = GEO, (3.0 + 2.0) * 1e-3
    Lx, Ly, Lz = g["Lx"] + 2 * d, g["Ly"] + 2 * d, g["z_out"] + d
    eps = 0.9
    return [nw.Face("s_top", Lx * Lz, "up", Lx * Lz / (2 * (Lx + Lz)), eps, 0.8),
            nw.Face("s_bottom", Lx * Lz, "down", Lx * Lz / (2 * (Lx + Lz)), eps, 0.8),
            nw.Face("s_ends", 2 * Ly * Lz, "vertical", Ly, eps, 0.8),
            nw.Face("s_back", Lx * Ly, "vertical", Ly, eps, 0.8)]


def fin_eff(h: float, k: float, t: float, L: float) -> float:
    m = math.sqrt(2 * h / (k * t))
    return math.tanh(m * L) / (m * L)


def conductances(sc: Scenario) -> dict:
    """Fixed conductances (W/K) and their parts [D/A]."""
    g = GEO
    hc = 1000.0  # W/m^2/K [A] dry clamped contact, plastic/aluminium; range 300-3000
    A_ear = 2 * g["ear_ext"] * g["Ly"]
    R_ear = 1 / (hc * A_ear) + (g["t"] / 2) / (K_PETG * A_ear)
    A_pocket = 2 * (g["Lx"] + g["Ly"]) * g["t"]
    R_pocket = g["clear"] / (K_AIR_GAP * A_pocket) + (g["t"] / 2) / (K_PETG * A_pocket)
    A_band_ends = 2 * g["Ly"] * g["z_in"]
    R_band = g["gap_end_walls"] / (K_AIR_GAP * A_band_ends) + (g["t"] / 2) / (K_PETG * A_band_ends)
    A_top = g["Lx"] * g["Ly"] - math.pi * g["horn_r"] ** 2
    R_top = g["gap_top"] / (K_AIR_GAP * A_top) + (g["t"] / 2) / (K_PETG * A_top)
    G_ch = sum(1 / r for r in (R_ear, R_pocket, R_band, R_top)) * sc.G_ch_scale
    # housing -> wrist mount: end walls, deck, spider in series (PETG) [D]
    R_walls = g["wall_h"] / (K_PETG * 2 * g["t"] * g["wall_d"])
    R_deck = 0.007 / (K_PETG * HS["deck_t"] * 1e-3 * (HS["deck_z"][1] - HS["deck_z"][0]) * 1e-3)
    R_spider = 0.015 / (K_PETG * WM["bolt_count"] * WM["arm_w"] * WM["arm_t"] * 1e-6)
    G_hm = 1 / (R_walls + R_deck + R_spider)
    # wrist mount -> SO-101 horn: recess contact + half clamp thickness [D]
    A_rec = math.pi / 4 * g["recess_d"] ** 2
    G_m_arm = 1 / (1 / (hc * A_rec) + (g["clamp_t"] / 2) / (K_PETG * A_rec))
    # case -> knuckle A root via horn, 2 dog pins (line contact under hold torque), PA6-CF arm [A geometry]
    R_dog = 1 / (hc * 2 * 3.5e-3 * 0.5e-3)
    R_arm = 0.015 / (K_PA6CF * PARAMS["knuckle"]["arm_top_width"] * PARAMS["gear"]["face_width"] * 1e-6)
    G_cf = sc.G_cf_scale / (R_dog + R_arm)
    # aluminium strap 2 x 10 mm, 50 mm long, 6061 k 167 [S handbook], two contacts 1 K/W each [A]
    G_strap = 1 / (0.05 / (167 * 2e-3 * 10e-3) + 2.0) if sc.al_strap else 0.0
    return {"G_ch": G_ch, "R_ear": R_ear, "R_pocket": R_pocket, "R_band": R_band, "R_top": R_top,
            "G_hm": G_hm, "G_m_arm": G_m_arm, "G_cf": G_cf, "G_strap": G_strap}


def housing_face_G(T: float, Ta: float, h_scale: float) -> float:
    """Cradle seat (one face, 100 % effective) + end walls (outer faces, fin efficiency) [D]."""
    g = GEO
    A_seat = (g["Lx"] + 2 * g["clear"] + 2 * g["t"]) * (g["Ly"] + 2 * g["clear"] + 2 * g["t"]) \
        - (g["Lx"] + 2 * g["clear"]) * (g["Ly"] + 2 * g["clear"])
    f = nw.Face("h", 1.0, "vertical", 0.020, 0.9, 0.8)
    h = f.h_conv(T, Ta, h_scale) + f.h_rad(T, Ta)
    A_walls = 2 * g["wall_h"] * g["wall_d"]
    return h * (A_seat + fin_eff(h, K_PETG, g["t"], g["wall_h"]) * A_walls)


def simple_face_G(A: float, L: float, T: float, Ta: float, h_scale: float, eps: float = 0.9) -> float:
    return nw.Face("x", A, "vertical", L, eps, 0.8).conductance(T, Ta, h_scale)


A_MOUNT = math.pi / 4 * (2 * WM["hub_r_band"] * 1e-3) ** 2 * 2 + 4 * WM["arm_w"] * 15 * 1e-6  # [D] hub disc 2 faces + arms
A_FINGER_ROOT = 2 * (math.pi * (PARAMS["knuckle"]["hub_r"] * 1e-3) ** 2 + 0.015 * 0.010) + 0.016 * 0.020  # [D]


def build_model(sc: Scenario) -> dict:
    g = conductances(sc)
    names = ["winding", "case", "housing", "mount", "finger_root"]
    C = [TH_DYNO["tau_w_s"] / TH_DYNO["Rth1_K_W"],  # 1.5 J/K (dyno.md)
         50.7,  # J/K [A]: prior 49 J/K scaled by params mass 60/58
         (GEO["t"] * (2 * GEO["wall_h"] * GEO["wall_d"] + 0.000329)) * 1250 * CP_PETG,  # local PETG [D]
         6.0,  # J/K wrist mount plate ~5 g PETG [A]
         10.0]  # J/K knuckle A ~3 g PA6-CF + finger root [A]
    if sc.enclosure == "enclosed":
        names.append("shroud")
        C.append(12.0)  # ~10 g PETG [A]
    net = nw.Network(names, np.array(C, dtype=float))
    iw, ic, ih, im, ifr = (net.idx(n) for n in names[:5])
    Ta, Tarm = sc.T_amb, sc.T_amb + sc.T_arm_offset_K
    net.links += [(iw, ic, 1.0 / sc.R_wc), (ic, ih, g["G_ch"]), (ih, im, g["G_hm"]), (ic, ifr, g["G_cf"])]
    faces = case_faces(sc)
    if sc.enclosure == "enclosed":
        isr = net.idx("shroud")
        g_exp = GEO["Lx"] * GEO["z_out"] * 2 + 2 * GEO["Ly"] * GEO["z_out"] + GEO["Lx"] * GEO["Ly"]
        gap = 3e-3
        eps_eff = 1 / (1 / sc.eps_case + 1 / 0.9 - 1)

        def G_case_shroud(T, A=g_exp):
            a, b = T[ic] + 273.15, T[isr] + 273.15
            h_r = eps_eff * nw.SIGMA * (a * a + b * b) * (a + b)
            return 1 / (1 / (A * (K_AIR_GAP / gap + h_r)) + 2e-3 / (K_PETG * A))
        net.links.append((ic, isr, G_case_shroud))
        inner = [f for f in faces if f.name.startswith(("band", "ears", "al_fin"))]
        net.bounds.append((ic, Ta, lambda T: sum(f.conductance(T[ic], Ta, sc.h_scale) for f in inner)))
        sfaces = shroud_faces(sc)
        net.bounds.append((isr, Ta, lambda T: sum(f.conductance(T[isr], Ta, sc.h_scale) for f in sfaces)))
    else:
        net.bounds.append((ic, Ta, lambda T: sum(f.conductance(T[ic], Ta, sc.h_scale) for f in faces)))
    net.bounds += [
        (ih, Ta, lambda T: housing_face_G(T[ih], Ta, sc.h_scale)),
        (im, Ta, lambda T: simple_face_G(A_MOUNT, 0.03, T[im], Ta, sc.h_scale)),
        (im, Tarm, g["G_m_arm"]),
        (ifr, Ta, lambda T: simple_face_G(A_FINGER_ROOT, 0.02, T[ifr], Ta, sc.h_scale)),
    ]
    if g["G_strap"] > 0:
        net.bounds.append((ic, Tarm, g["G_strap"]))

    def power_avg(t, T):
        hs = heat_sources(sc, T[iw])
        P = np.zeros(len(names))
        P[iw], P[ic] = hs["P_avg_winding_W"], hs["P_avg_case_W"]
        return P

    p = sc.phases()
    order = ["approach_touchdown", "close", "lift_move_to_needle", "feed_hold", "release", "return"]
    edges = np.cumsum([0.0] + [p[k] for k in order])
    cyc = edges[-1]

    def power_time(t, T, continuous=False):
        c = currents(sc)
        P = np.zeros(len(names))
        if continuous:
            phase = "feed_hold"
        else:
            tc = t % cyc
            phase = order[int(np.searchsorted(edges, tc, side="right") - 1)]
        if phase == "close":
            I = c["I_close_A"]
        elif phase in ("lift_move_to_needle", "feed_hold"):
            I = c["I_hold_A"]
        else:
            I = 0.0
        P[iw] = copper_W(sc, I, T[iw], c["R20_ohm"]) if I > 0 else 0.0
        P[ic] = sc.rds_W_per_A2 * I * I + sc.idle_W
        return P

    return {"sc": sc, "net": net, "G": g, "power_avg": power_avg, "power_time": power_time, "cycle_s": cyc}


# ----------------------------------------------------------------------------------------------
# Solutions
# ----------------------------------------------------------------------------------------------
def winding_peak(sc: Scenario, T_case: float) -> float:
    """Quasi-steady winding at the end of a hold: tau_w ~ 15 s < 25 s hold, so the winding reaches
    T_case + P_hold R_wc. Closed form with R(T). Returns inf on electro-thermal runaway."""
    c = currents(sc)
    if sc.conduction == "pwm":
        return T_case + c["I_hold_A"] * sc.V_rail * sc.R_wc
    a = c["I_hold_A"] ** 2 * c["R20_ohm"]
    den = 1 - a * ALPHA_CU * sc.R_wc
    return math.inf if den <= 0 else (T_case + a * (1 - 20 * ALPHA_CU) * sc.R_wc) / den


def solve_steady(m: dict) -> dict:
    net, sc = m["net"], m["sc"]
    T0 = np.full(len(net.names), sc.T_amb + 20.0)
    try:
        T, ok = net.steady(m["power_avg"], T0)
    except (ValueError, OverflowError):
        return {"converged": False, "T": T0, "runaway": True}
    # every source is a heat input, so a physical steady state has no node below the coldest boundary;
    # past the electro-thermal runaway point fsolve can land on a non-physical root with R(T) < 0
    if not ok or T[net.idx("winding")] > 400 or np.min(T) < sc.T_amb - 1e-6:
        return {"converged": False, "T": T, "runaway": True}
    n = {k: float(T[net.idx(k)]) for k in net.names}
    hs = heat_sources(sc, n["winding"])
    Tw_pk = winding_peak(sc, n["case"])
    return {"converged": True, "runaway": False, "T": T, "nodes": n, "winding_peak_C": Tw_pk, "heat": hs}


def margins(n: dict, Tw_pk: float) -> dict:
    L = {k: v["value"] for k, v in LIMITS.items()}
    return {"case_vs_R26_K": L["case_R26_C"] - n["case"],
            "case_vs_servo_rating_K": L["case_servo_rating_C"] - n["case"],
            "winding_peak_vs_limit_K": L["winding_C"] - Tw_pk,
            "housing_vs_petg_creep_onset_K": L["petg_creep_onset_C"] - n["housing"],
            "housing_vs_petg_Tg_K": L["petg_Tg_C"] - n["housing"],
            "finger_root_vs_tpu_HDT_K": L["tpu_HDT_C"] - n["finger_root"]}


def summary(sc: Scenario) -> dict:
    m = build_model(sc)
    r = solve_steady(m)
    if not r["converged"]:
        return {"scenario": asdict(sc), "converged": False, "runaway": True}
    mg = margins(r["nodes"], r["winding_peak_C"])
    h = r["heat"]
    return {"scenario": asdict(sc), "converged": True, "runaway": False,
            "T_C": {**{k: round(v, 2) for k, v in r["nodes"].items()}, "winding_peak": round(r["winding_peak_C"], 2)},
            "margins_K": {k: round(v, 2) for k, v in mg.items()},
            "min_margin_K": round(min(mg.values()), 2), "binding": min(mg, key=mg.get),
            "heat_W": {k: round(h[k], 4) for k in ("P_hold_winding_W", "P_hold_case_W", "P_avg_winding_W",
                                                    "P_avg_case_W", "P_avg_total_W", "P_peak_total_W")},
            "I_hold_A": round(h["I_hold_A"], 4), "T_hold_Nm": round(h["T_hold_Nm"], 4),
            "f_hold": round(h["f_hold"], 4), "f_close": round(h["f_close"], 4)}


def transient(sc: Scenario, t_end: float, continuous: bool = False, T0=None, dt: float = 0.05):
    m = build_model(sc)
    net = m["net"]
    T0 = np.full(len(net.names), sc.T_amb) if T0 is None else np.asarray(T0, float)
    ts, Ts = net.transient(lambda t, T: m["power_time"](t, T, continuous), T0, t_end, dt)
    return m, ts, Ts


def max_sustainable_force(base: Scenario, limit_key: str, hold_fraction: float | None) -> float:
    """Largest hold force (N) whose steady state keeps every limit in limit_key's set >= 0 margin."""
    keys = {"strict": ("case_vs_R26_K", "winding_peak_vs_limit_K", "housing_vs_petg_creep_onset_K"),
            "rating": ("case_vs_servo_rating_K", "winding_peak_vs_limit_K", "housing_vs_petg_Tg_K")}[limit_key]

    def ok(F):
        s = summary(replace(base, force_N=F, hold_fraction=hold_fraction))
        return s["converged"] and all(s["margins_K"][k] >= 0 for k in keys)
    lo, hi = 0.0, 12.0
    if not ok(lo):
        return 0.0
    if ok(hi):
        return hi
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    return lo



@lru_cache(maxsize=None)
def case_temperature_at(sc: Scenario, duration_s: float | None) -> tuple[float, float]:
    """Return case and winding temperature for a cold-start duration, or at steady state."""
    if duration_s is None:
        result = solve_steady(build_model(sc))
        if not result["converged"]:
            return math.inf, math.inf
        return result["nodes"]["case"], result["nodes"]["winding"]
    model, _, temperatures = transient(sc, duration_s, continuous=False, dt=1.0)
    return (float(temperatures[-1, model["net"].idx("case")]),
            float(temperatures[-1, model["net"].idx("winding")]))


def acceptance_limit(sc: Scenario, duration_s: float | None, case_limit_C: float | None = None) -> dict:
    """Solve the model for the largest hold command and its F4 rail-current reading."""
    limit = LIMITS["case_R26_C"]["value"] if case_limit_C is None else case_limit_C

    def residual(factor: float) -> float:
        return case_temperature_at(replace(sc, hold_current_factor=factor), duration_s)[0] - limit

    lo, hi = 0.0, 1.5
    if residual(lo) > 0:
        raise ValueError("R26 cannot be met even at zero hold current")
    while residual(hi) <= 0:
        hi *= 1.5
    root = brentq(residual, lo, hi, xtol=1e-5, rtol=1e-8)
    solved = replace(sc, hold_current_factor=root)
    case_C, winding_C = case_temperature_at(solved, duration_s)
    rail_limit = heat_sources(solved, winding_C)["I_rail_hold_A"]
    predicted = {}
    for name, factor in (("backoff", ETA_G ** 2), ("no_backoff", 1.0)):
        pred_sc = replace(sc, hold_current_factor=factor)
        _, pred_winding = case_temperature_at(pred_sc, duration_s)
        predicted[name] = heat_sources(pred_sc, pred_winding)["I_rail_hold_A"]
    return {"hold_current_factor": root, "rail_limit_A": rail_limit, "case_C": case_C,
            "predicted_rail_A": predicted}


def washer_minimum_protrusion_mm(preload_N: float, od_mm: float = 6.0) -> float:
    """Elastic compression of the PETG annulus at 23 C using petg_E_short [D from S]."""
    area_mm2 = math.pi / 4 * (od_mm ** 2 - HS["limiter"]["od"] ** 2)
    return preload_N * HS["wall"] / (area_mm2 * petg_E_short(23.0))


# ----------------------------------------------------------------------------------------------
# Creep at the servo mount and the finger root (modelled stresses, judgement creep law)
# ----------------------------------------------------------------------------------------------
def petg_E_short(T: float) -> float:
    """Short-time apparent flexural modulus of Bambu PETG Basic (MPa) vs temperature [D from S]:
    23 C -> 1790 (TDS bending modulus X-Y); 65 C -> 900 (HDT at 1.8 MPa; ISO 75 deflection taken as
    0.2 % strain [A], so E = 1.8/0.002); 69 C -> 225 (HDT at 0.45 MPa). Log-linear between points,
    held at 1790 below 23 C, and falling at the 65-69 C slope above 69 C."""
    pts = [(23.0, 1790.0), (65.0, 900.0), (69.0, 225.0)]
    if T <= pts[0][0]:
        return pts[0][1]
    for (t0, e0), (t1, e1) in zip(pts, pts[1:]):
        if T <= t1:
            return math.exp(math.log(e0) + (T - t0) / (t1 - t0) * (math.log(e1) - math.log(e0)))
    (t0, e0), (t1, e1) = pts[-2], pts[-1]
    return math.exp(math.log(e1) + (T - t1) / (t1 - t0) * (math.log(e1) - math.log(e0)))


def findley_n(T: float, Tg: float = 68.0) -> float:
    """Power-law creep exponent [A, judgement]: 0.05 at or below Tg - 30, rising linearly to 0.20 at Tg - 5."""
    x = (T - (Tg - 30.0)) / 25.0
    return 0.05 + 0.15 * min(max(x, 0.0), 1.0)


def preload_retained(T: float, hours: float, t0_h: float = 0.1) -> float:
    """Fraction of the room-temperature screw preload left in a PETG clamp held at T for `hours`
    [judgement]. Stiff steel screw -> clamp is displacement-controlled -> preload tracks the
    relaxation modulus: E_short(T)/E(23) x (t/t0)^-n(T). t0 = 6 min, the time scale of an HDT ramp [A]."""
    return petg_E_short(T) / petg_E_short(23.0) * (max(hours, t0_h) / t0_h) ** (-findley_n(T))


def mount_stresses(sc: Scenario) -> dict:
    """Stresses on the PETG cradle at the 4 servo ear screws [D from A preload]."""
    A_nut = math.pi / 4 * ((5.5e-3) ** 2 - (HS["clearance_hole_cad"] * 1e-3) ** 2)  # M3 nut face on PETG
    A_washer = math.pi / 4 * ((7.0e-3) ** 2 - (HS["clearance_hole_cad"] * 1e-3) ** 2)  # M3 washer OD 7
    out = {}
    for T_tight in (0.15, 0.30):  # N m, snug for screws into plastic [A]
        F = T_tight / (0.2 * 3e-3)  # nut factor K 0.2 [A]
        out[f"preload_N_at_{T_tight}Nm"] = F
        out[f"bearing_MPa_nut_{T_tight}Nm"] = F / A_nut / 1e6
        out[f"bearing_MPa_washer_{T_tight}Nm"] = F / A_washer / 1e6
    T = hold_torque(sc.force_N)
    pitch = SV["ear_hole_pitch_y"] * 1e-3
    out["hold_reaction_per_screw_N"] = T / pitch / 2  # couple across the ear pairs
    A_ear = (SV["ear_span"] - SV["body_y"]) / 2 * SV["body_x"] * 1e-6
    out["hold_reaction_bearing_MPa"] = out["hold_reaction_per_screw_N"] * 2 / A_ear / 1e6
    out["romeijn_flexural_MPa_1p4_2p8_4p2kg"] = [3 * m * 9.80665 * 48.0 / (2 * 12.5 * 3.0 ** 2) for m in (1.4, 2.8, 4.2)]
    return out


def creep_limit_temperature(hours: float, keep: float = 0.5) -> float:
    lo, hi = 23.0, 80.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if preload_retained(mid, hours) >= keep else (lo, mid)
    return lo


def verdict_class(margin_fitA: float, margin_fitB: float, margin_fitA_backoff: float) -> str:
    """Legacy analytical margin class; exported operational verdict uses the acceptance renderer."""
    if margin_fitA >= 0:
        return "safe"
    if margin_fitA_backoff >= 0 or margin_fitB >= 0:
        return "safe with a limit"
    return "not safe"


def classify_30min_regime(
    observed_case_C: float,
    ambient_C: float,
    backoff: bool,
    continuous_prediction_C: float | tuple[float, float],
    discontinuous_prediction_C: float | tuple[float, float],
    instrument_U_C: float,
) -> dict:
    """Classify a reading against model spans and expanded instrument uncertainty."""
    continuous_span = prediction_span(continuous_prediction_C)
    discontinuous_span = prediction_span(discontinuous_prediction_C)
    continuous_distance = distance_to_span(observed_case_C, continuous_span)
    discontinuous_distance = distance_to_span(observed_case_C, discontinuous_span)
    distances = (
        f"continuous distance {continuous_distance:.1f} K; "
        f"discontinuous distance {discontinuous_distance:.1f} K"
    )
    if not AMBIENT_RANGE_C[0] <= ambient_C <= AMBIENT_RANGE_C[1]:
        reason = (
            f"measured ambient {ambient_C:.3f} °C ± {AMBIENT_TEMPERATURE_U_C:.3f} °C "
            f"exceeds the {AMBIENT_MODEL_RANGE_C[0]:.0f}–{AMBIENT_MODEL_RANGE_C[1]:.0f} °C model domain"
        )
        return {"outcome": "refused", "reason": reason}
    if not isinstance(backoff, bool):
        return {"outcome": "indeterminate", "reason": f"back-off state is invalid; {distances}"}
    reading_span = (observed_case_C - instrument_U_C, observed_case_C + instrument_U_C)
    contains_continuous = spans_overlap(reading_span, continuous_span)
    contains_discontinuous = spans_overlap(reading_span, discontinuous_span)
    if contains_continuous and not contains_discontinuous:
        return {"outcome": "continuous", "reason": distances}
    if contains_discontinuous and not contains_continuous:
        return {"outcome": "discontinuous", "reason": distances}
    reason = f"{distances}; model prediction uncertainty is not quantified; do not operate"
    return {"outcome": "indeterminate", "reason": reason}


def prediction_span(value: float | tuple[float, float]) -> tuple[float, float]:
    values = (float(value),) if isinstance(value, (int, float)) else value
    return min(values), max(values)


def distance_to_span(value: float, span: tuple[float, float]) -> float:
    return max(span[0] - value, value - span[1], 0.0)


def spans_overlap(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return left[0] <= right[1] and right[0] <= left[1]


def model_30min_prediction(ambient_C: float, conduction: str, backoff: bool = True) -> float:
    """Evaluate the committed high-reading transient model for one bench condition."""
    factor = ETA_G ** 2 if backoff else 1.0
    mode = {"continuous": "avg", "discontinuous": "pwm"}[conduction]
    scenario = Scenario(
        fit="A_mech", conduction=mode, T_amb=ambient_C, hold_current_factor=factor
    )
    network, _, temperatures = transient(scenario, 1800.0, continuous=False, dt=0.1)
    return float(temperatures[-1, network["net"].idx("case")])


def ambient_prediction_spans(
    ambient_C: float, backoff: bool = True
) -> dict[str, tuple[float, float]]:
    """Evaluate both regimes at the limits of the measured ambient interval."""
    ambient_limits = (
        ambient_C - AMBIENT_TEMPERATURE_U_C,
        ambient_C + AMBIENT_TEMPERATURE_U_C,
    )
    return {
        conduction: prediction_span(tuple(
            model_30min_prediction(value, conduction, backoff) for value in ambient_limits
        ))
        for conduction in ("continuous", "discontinuous")
    }


def regime_prediction_row(ambient_C: float, backoff: bool = True) -> dict:
    """Return central predictions and uncertainty spans for one table/command row."""
    spans = ambient_prediction_spans(ambient_C, backoff)
    centers = {
        name: model_30min_prediction(ambient_C, name, backoff) for name in spans
    }
    separable = abs(centers["continuous"] - centers["discontinuous"]) >= (
        2 * CASE_TEMPERATURE_U_C
    )
    return {
        "ambient_C": ambient_C,
        "predictions": centers,
        "spans": spans,
        "separable": separable,
    }


def classify_command(ambient_C: float, reading_C: float, backoff: bool) -> int:
    """Print the bench classification without mutating generated artifacts."""
    if not AMBIENT_RANGE_C[0] <= ambient_C <= AMBIENT_RANGE_C[1]:
        verdict = classify_30min_regime(
            reading_C, ambient_C, backoff, 0.0, 0.0, CASE_TEMPERATURE_U_C
        )
        print(f"outcome: refused (outside supported range: {verdict['reason']})")
        return 4
    row = regime_prediction_row(ambient_C, backoff)
    spans = row["spans"]
    verdict = classify_30min_regime(
        reading_C, ambient_C, backoff, spans["continuous"], spans["discontinuous"],
        CASE_TEMPERATURE_U_C,
    )
    reading = (reading_C - CASE_TEMPERATURE_U_C, reading_C + CASE_TEMPERATURE_U_C)
    print(f"ambient: {ambient_C:.1f} °C ± {AMBIENT_TEMPERATURE_U_C:.3f} °C (includes "
          f"{AMBIENT_REPRESENTATIVENESS_LIMIT_C:.1f} °C shaded-air representativeness term, "
          f"{AMBIENT_REPRESENTATIVENESS_LABEL})")
    print(f"accepted ambient range: {accepted_ambient_range_text()}")
    for name in ("continuous", "discontinuous"):
        print(f"{name} prediction: {spans[name][0]:.1f}–{spans[name][1]:.1f} °C")
    print(f"reading interval: {reading[0]:.1f}–{reading[1]:.1f} °C")
    print(f"outcome: {verdict['outcome']}")
    print(f"R26 band: {r26_band(reading_C)}")
    return {"continuous": 0, "discontinuous": 2, "indeterminate": 3}[verdict["outcome"]]


def render_acceptance_verdict(rows: list[dict]) -> str:
    """Render the single operational headline from every acceptance row."""
    continuous = [row for row in rows if row["conduction"] == "continuous"]
    discontinuous = [row for row in rows if row["conduction"] == "discontinuous"]
    backoff_passes = all(row["backoff_margin_A"] >= 0 for row in continuous)
    every_row_passes = all(row["backoff_margin_A"] >= 0 for row in rows)
    if every_row_passes:
        qualification = "with back-off, all eight acceptance rows pass when every section-0 condition holds"
    elif backoff_passes:
        qualification = "with back-off, acceptable only when every section-0 condition holds"
    else:
        qualification = "with back-off, not acceptable because one or more continuous-conduction rows fail"
    discontinuous_instruction = ("discontinuous conduction: acceptable under every section-0 condition"
                                 if discontinuous and all(row["backoff_margin_A"] >= 0 for row in discontinuous)
                                 else "discontinuous conduction: do not operate")
    return f"not safe without back-off; {qualification}; {discontinuous_instruction}."


# ----------------------------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------------------------
def main(*, write_outputs: bool = True, figures: bool = False,
         out_dir: Path = OUT_DIR, note_path: Path = P_NOTE) -> dict:
    LOG.clear()
    np.random.seed(0)  # nothing random; kept for the lane rule
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    R = {"_doc": "Thermal lane results. See docs/gripper/analysis/thermal.md. Tags in 'inputs' and 'limits'.",
         "inputs": {
             "input_file_sha256_16": val({str(p.relative_to(ROOT).as_posix()): sha16(p)
                                           for p in (P_PARAMS, P_DYNO, P_CONFIG, P_DESIGN_BASIS)},
                                         "D", "sha256 (first 16 hex) of every input file"),
             "hold_torque_Nm_at_5N": val(hold_torque(5.0), "D", "(2 F r_c + T x_f) / eta = 0.792 N m, T1"),
             "hold_torque_Nm_at_6N": val(hold_torque(6.0), "D", "regulated hold with cloth tension = 0.944 N m, T1"),
             "servo_model": val(SV["model"], "S", "cad/gripper/params.json selector"),
             "servo_mass_g": val(SV["mass_g"], "S", "params.json from vendor listing"),
             "servo_body_mm": val([SV["body_y"], SV["body_x"], SV["overall_h"]], "S/A", "params.json; listing dimensions rounded"),
             "exposed_case_length_mm": val(GEO["z_out"] * 1000, "D", "overall_h - ear_from_top - 2*housing.wall; revision B K4"),
             "T1_simulated_hold_current_A": val({"median": 1.62, "p95": 2.12}, "D", "actuation_trade.md T1, 10 N cap"),
             "eta_gearbox": val(ETA_G, "A", "dyno.json; motor current = T / (K_out eta_g), motoring side, conservative"),
             "alpha_Cu": val(ALPHA_CU, "S", "maxon key information via dyno.json"),
             "k_PETG": val(K_PETG, "S", SOURCES["petg_k"]),
             "k_PA6CF": val(K_PA6CF, "A", "no public value found; range 0.25-0.8 W/m/K"),
             "contact_conductance_W_m2K": val(1000.0, "A", "dry clamped contact, range 300-3000"),
             "hot_hours_semester": val(HOT_HOURS_SEMESTER, "A", "14 weeks x 2 sessions x 3 h"),
             "firmware": val({k: CONFIG.get(k) for k in ("F_TARGET_DEFAULT_N", "F_SET_MAX_N", "F_SOFT_LIMIT_N",
                                                          "F_TRIP_N", "F_CAP_N", "STALL_CURRENT_A", "JAW_MIN_DEG")},
                             "S", "firmware/gripper/config.h"),
             "scenario_defaults": val(asdict(Scenario()), "A", "baseline scenario; see Scenario docstrings"),
         },
         "limits": LIMITS, "sources": SOURCES}

    base = Scenario()
    say("=== Thermal lane: DS3230 MG in revision B printed PETG housing ===")
    say(f"Hold torque at 5 N per pad: {hold_torque(5.0):.4f} N m; cycle {base.cycle_s():.2f} s; "
        f"hold fraction {base.fractions()[0]:.4f}, close fraction {base.fractions()[1]:.4f}")
    G = conductances(base)
    say(f"Conductances (W/K): case->housing {G['G_ch']:.4f} (ears {1/G['R_ear']:.4f}, pocket {1/G['R_pocket']:.4f}, "
        f"band {1/G['R_band']:.4f}, top gap {1/G['R_top']:.4f}); housing->mount {G['G_hm']:.2e}; "
        f"mount->arm {G['G_m_arm']:.4f}; case->finger root {G['G_cf']:.2e}")
    R["conductances_W_per_K"] = {k: v for k, v in G.items()}

    # ---- Step 1: heat sources ------------------------------------------------------------
    say("\n--- 1. Heat sources (6.5 V rail, average-value conduction, winding at 100 C for the table) ---")
    src = {}
    for fit in ("A_mech", "B_elec", "B_elec_Annimos1p8A"):
        for F in (5.0, CONFIG["F_SET_MAX_N"], 8.0, 10.0):
            for cond in ("avg", "pwm"):
                sc = Scenario(fit=fit, force_N=F, conduction=cond)
                h = heat_sources(sc, 100.0)
                key = f"{fit}|F{F:g}|{cond}"
                src[key] = {k: round(v, 4) for k, v in h.items() if isinstance(v, float)}
                if cond == "avg" or F == 5.0:
                    say(f"{fit:20s} F {F:4.1f} N {cond:3s}: I_hold {h['I_hold_A']:.3f} A, hold {h['P_hold_winding_W'] + h['P_hold_case_W']:.2f} W "
                        f"peak {h['P_peak_total_W']:.2f} W, cycle-average {h['P_avg_total_W']:.2f} W, rail current in hold "
                        f"{h['I_rail_hold_A']:.2f} A (trip {CONFIG['STALL_CURRENT_A']:.1f} A)")
    R["step1_heat_sources"] = src
    R["step1_note"] = (f"Hold = lift + feed (25 s of {base.cycle_s():g} s). Close = {base.t_close:g} s (DESIGN-BASIS R19) "
                       "at 0.5 x stall current [A]. Electronics inside the servo: "
                       "idle 5 mA x 6.5 V [S] + H-bridge I^2 x 0.1 ohm [A]. ESP32, INA219 and buck are off the "
                       "gripper [A]; a gripper-mounted buck would add (1 - eff) x rail power.")

    # ---- Step 2: network, steady and transient -------------------------------------------
    say("\n--- 2. Steady state (cycle-averaged power), ambient 25 C, open cradle as drawn ---")
    steady = {}
    for fit in ("A_mech", "B_elec", "B_elec_Annimos1p8A"):
        for cond in ("avg", "pwm"):
            for F in (5.0, 8.0, 10.0):
                s = summary(Scenario(fit=fit, conduction=cond, force_N=F))
                steady[f"{fit}|{cond}|F{F:g}"] = s
                if s["converged"]:
                    t = s["T_C"]
                    say(f"{fit:20s} {cond:3s} F {F:4.1f}: winding pk {t['winding_peak']:6.1f}  case {t['case']:5.1f}  "
                        f"housing {t['housing']:5.1f}  mount {t['mount']:5.1f}  finger root {t['finger_root']:5.1f} C; "
                        f"min margin {s['min_margin_K']:+.1f} K ({s['binding']})")
                else:
                    say(f"{fit:20s} {cond:3s} F {F:4.1f}: no steady state (electro-thermal runaway)")
    R["step2_steady"] = steady

    # effective case-to-surroundings resistance and the per-face film coefficients at the Fit A / B steady state
    faces_out = {}
    for fit in ("A_mech", "B_elec"):
        s = steady[f"{fit}|avg|F5"]
        Tc = s["T_C"]["case"]
        R_eff = (Tc - 25.0) / s["heat_W"]["P_avg_total_W"]
        faces_out[fit] = {"R_case_to_ambient_effective_K_per_W": round(R_eff, 2), "faces": {}}
        for f in case_faces(Scenario(fit=fit)):
            faces_out[fit]["faces"][f.name] = {"area_mm2": round(f.area * 1e6, 1), "L_mm": round(f.L_char * 1e3, 2),
                                               "Ra": round(nw.rayleigh(Tc, 25.0, f.L_char), 1),
                                               "h_conv": round(f.h_conv(Tc, 25.0), 2), "h_rad": round(f.h_rad(Tc, 25.0), 2),
                                               "Ra_in_stated_range": f.ra_in_range(Tc, 25.0)}
        say(f"{fit}: effective case-to-ambient resistance {R_eff:.2f} K/W (all heat paths, P_avg {s['heat_W']['P_avg_total_W']:.2f} W)")
    for name, d in faces_out["A_mech"]["faces"].items():
        say(f"   face {name:15s}: {d['area_mm2']:7.1f} mm2, L {d['L_mm']:5.2f} mm, Ra {d['Ra']:9.1f}, h_conv {d['h_conv']:5.2f}, "
            f"h_rad {d['h_rad']:5.2f} W/m2K, Ra in stated range: {d['Ra_in_stated_range']}")
    R["step2_faces"] = faces_out

    say("\n--- 2b. Transients, 1 h from cold at 25 C ---")
    tr = {}
    traces = {}
    for fit in ("A_mech", "B_elec"):
        for cont in (False, True):
            m, ts, Ts = transient(Scenario(fit=fit), 3600.0, continuous=cont)
            net = m["net"]
            ic, ih, iw = net.idx("case"), net.idx("housing"), net.idx("winding")
            last = ts >= 3600.0 - m["cycle_s"]
            k30 = int(round(1800 / 0.05))
            key = f"{fit}|{'continuous' if cont else 'duty'}"
            tr[key] = {"case_30min_C": round(float(Ts[k30, ic]), 2), "case_60min_C": round(float(Ts[-1, ic]), 2),
                       "housing_60min_C": round(float(Ts[-1, ih]), 2),
                       "winding_peak_last_cycle_C": round(float(Ts[last, iw].max()), 2),
                       "t_case_to_60C_s": nw.first_crossing(ts, Ts[:, ic], 60.0),
                       "t_case_63pct_s": nw.first_crossing(ts, Ts[:, ic] - 25.0, 0.632 * (Ts[-1, ic] - 25.0))}
            traces[key] = (ts[::200], Ts[::200, :])
            say(f"{key:20s}: case 30 min {tr[key]['case_30min_C']:.1f} C, 60 min {tr[key]['case_60min_C']:.1f} C; "
                f"housing 60 min {tr[key]['housing_60min_C']:.1f} C; winding peak (last cycle) "
                f"{tr[key]['winding_peak_last_cycle_C']:.1f} C; case 63 % time {tr[key]['t_case_63pct_s']} s")
        ss = steady[f"{fit}|avg|F5"]
        tr[f"{fit}|duty"]["steady_case_C"] = ss["T_C"]["case"]
        tr[f"{fit}|duty"]["steady_vs_60min_case_K"] = round(ss["T_C"]["case"] - tr[f"{fit}|duty"]["case_60min_C"], 2)
        tr[f"{fit}|duty"]["steady_vs_lastcycle_winding_K"] = round(ss["T_C"]["winding_peak"] - tr[f"{fit}|duty"]["winding_peak_last_cycle_C"], 2)
        say(f"  check {fit}: steady case {ss['T_C']['case']:.2f} vs 60 min transient {tr[f'{fit}|duty']['case_60min_C']:.2f} C; "
            f"steady winding peak {ss['T_C']['winding_peak']:.1f} vs transient {tr[f'{fit}|duty']['winding_peak_last_cycle_C']:.1f} C")
    R["step2_transient"] = tr

    # time to limits for a sustained hold at each cap value, starting from the duty-cycle steady state
    say("\n--- 2c. Sustained hold at the cap, from the duty-cycle steady state, 25 C ---")
    caps = {}
    for fit in ("A_mech", "B_elec"):
        m0 = build_model(Scenario(fit=fit))
        r0 = solve_steady(m0)
        for F in (CONFIG["F_SET_MAX_N"], 8.0, 10.0):
            m, ts, Ts = transient(Scenario(fit=fit, force_N=F), 1800.0, continuous=True, T0=r0["T"])
            net = m["net"]
            ic, ih, iw = net.idx("case"), net.idx("housing"), net.idx("winding")
            caps[f"{fit}|F{F:g}"] = {
                "t_case_60C_s": nw.first_crossing(ts, Ts[:, ic], 60.0),
                "t_case_70C_s": nw.first_crossing(ts, Ts[:, ic], 70.0),
                "t_winding_125C_s": nw.first_crossing(ts, Ts[:, iw], 125.0),
                "t_housing_50C_s": nw.first_crossing(ts, Ts[:, ih], 50.0),
                "case_after_30min_C": round(float(Ts[-1, ic]), 1), "winding_after_30min_C": round(float(Ts[-1, iw]), 1)}
            c = caps[f"{fit}|F{F:g}"]
            say(f"{fit:8s} F {F:4.1f} N continuous: case 60 C at {c['t_case_60C_s']} s, 70 C at {c['t_case_70C_s']} s, "
                f"winding 125 C at {c['t_winding_125C_s']} s, housing 50 C at {c['t_housing_50C_s']} s")
    R["step2_cap_holds"] = caps

    # ---- Step 3: limits and creep --------------------------------------------------------
    say("\n--- 3. Limits and creep ---")
    ms = mount_stresses(base)
    say("Mount clamp: preload {:.0f}-{:.0f} N; bearing under an M3 nut {:.1f}-{:.1f} MPa, under a 7 mm washer {:.1f}-{:.1f} MPa; "
        "hold reaction {:.1f} N per screw ({:.2f} MPa on the ear face)".format(
            ms["preload_N_at_0.15Nm"], ms["preload_N_at_0.3Nm"], ms["bearing_MPa_nut_0.15Nm"], ms["bearing_MPa_nut_0.3Nm"],
            ms["bearing_MPa_washer_0.15Nm"], ms["bearing_MPa_washer_0.3Nm"], ms["hold_reaction_per_screw_N"],
            ms["hold_reaction_bearing_MPa"]))
    say("Romeijn 2021 flexural creep stresses (48 mm span assumed): " + ", ".join(f"{x:.1f}" for x in ms["romeijn_flexural_MPa_1p4_2p8_4p2kg"]) + " MPa")
    creep = {"mount_stresses": ms, "E_short_MPa": {str(T): round(petg_E_short(T), 1) for T in (23, 40, 50, 55, 60, 65, 69)}}
    for T in (25, 35, 40, 45, 50, 55, 60, 65):
        creep[f"preload_retained_{T}C_semester"] = round(preload_retained(T, HOT_HOURS_SEMESTER), 3)
    creep["T_half_preload_semester_C"] = round(creep_limit_temperature(HOT_HOURS_SEMESTER), 1)
    creep["T_half_preload_1e5_grips_C"] = round(creep_limit_temperature(DUTY["hours_to_N_design"]), 1)
    say("Preload retained after a semester (84 h hot) [judgement]: " + ", ".join(
        f"{T} C {creep[f'preload_retained_{T}C_semester']:.2f}" for T in (25, 40, 50, 60, 65)))
    say(f"Temperature at which half the preload is gone in a semester: {creep['T_half_preload_semester_C']:.1f} C "
        f"(972 h design life: {creep['T_half_preload_1e5_grips_C']:.1f} C)")
    for key in ("A_mech|avg|F5", "B_elec|avg|F5"):
        s = steady[key]
        Th = s["T_C"]["housing"]
        creep[f"{key}|housing_C"] = Th
        creep[f"{key}|preload_retained_semester"] = round(preload_retained(Th, HOT_HOURS_SEMESTER), 3)
        say(f"{key}: housing at the mount {Th:.1f} C -> preload retained {creep[f'{key}|preload_retained_semester']:.2f}; "
            f"finger root {s['T_C']['finger_root']:.1f} C vs TPU HDT 50.3 C")
    R["step3_creep"] = creep

    # ---- Step 4: sensitivity and options ---------------------------------------------------
    say("\n--- 4. Sensitivity (steady, Fit A and Fit B, 5 N hold unless stated) ---")
    sens = {}
    variants = {
        "baseline": {},
        "ambient_20": {"T_amb": 20.0}, "ambient_30": {"T_amb": 30.0}, "ambient_35": {"T_amb": 35.0}, "ambient_40": {"T_amb": 40.0},
        "enclosed_shroud": {"enclosure": "enclosed"},
        "duty_0p5": {"hold_fraction": 0.5}, "duty_0p9": {"hold_fraction": 0.9}, "duty_1p0_continuous": {"hold_fraction": 1.0},
        "V_6p35": {"V_rail": 6.35}, "V_6p8": {"V_rail": 6.8},
        "pwm_bound": {"conduction": "pwm"},
        "R19_close_0p75s": {"t_close": 0.75},
        "R_wc_6": {"R_wc": 6.0}, "R_wc_15": {"R_wc": 15.0},
        "h_conv_x0p75": {"h_scale": 0.75}, "h_conv_x1p25": {"h_scale": 1.25},
        "eps_0p77": {"eps_case": 0.77}, "eps_0p92": {"eps_case": 0.92},
        "G_ch_x0p5": {"G_ch_scale": 0.5}, "G_ch_x2": {"G_ch_scale": 2.0},
        "G_cf_x3": {"G_cf_scale": 3.0},
        "arm_offset_0": {"T_arm_offset_K": 0.0}, "arm_offset_15": {"T_arm_offset_K": 15.0},
        "force_7N_hold": {"force_N": CONFIG["F_SET_MAX_N"]},
        # options that buy margin
        "opt_backoff_hold_eta2": {"hold_current_factor": ETA_G ** 2},
        "opt_duty_limit_0p5": {"hold_fraction": 0.5},
        "opt_al_fin_40cm2": {"fin_area_m2": 40e-4},
        "opt_al_strap_to_arm": {"al_strap": True},
    }
    for fit in ("A_mech", "B_elec"):
        for name, kw in variants.items():
            if fit == "B_elec" and name == "V_6p8":
                pass
            s = summary(replace(Scenario(fit=fit), **kw))
            sens[f"{fit}|{name}"] = s
    for fit in ("A_mech", "B_elec"):
        b = sens[f"{fit}|baseline"]
        say(f"{fit}: baseline case {b['T_C']['case']:.1f} C, housing {b['T_C']['housing']:.1f} C, winding pk {b['T_C']['winding_peak']:.1f} C")
        for name in variants:
            s = sens[f"{fit}|{name}"]
            if not s["converged"]:
                say(f"   {name:24s}: runaway")
                continue
            say(f"   {name:24s}: case {s['T_C']['case']:6.1f} ({s['T_C']['case'] - b['T_C']['case']:+6.1f})  housing "
                f"{s['T_C']['housing']:6.1f}  winding pk {s['T_C']['winding_peak']:6.1f}  min margin {s['min_margin_K']:+6.1f} K")
    R["step4_sensitivity"] = sens

    # material option: ASA housing moves the housing limits, not the temperatures
    R["step4_material_option"] = {"PETG_Tg_C": 68.0, "PETG_HDT_0p45_C": 69.0, "ASA_HDT_0p45_C": 100.0, "ASA_HDT_1p8_C": 92.0,
                                  "ASA_Vicat_C": 106.0, "note": "ASA raises the housing limits by about 30 K (HDT at 0.45 MPa "
                                  "100 vs 69 C) [S asa_tds]; it changes no temperature and no servo limit"}

    # which single change buys the most margin on the binding limits (Fit A, the pessimistic fit)
    opts = {}
    for fit in ("A_mech", "B_elec"):
        b = sens[f"{fit}|baseline"]
        for name in ("opt_backoff_hold_eta2", "opt_duty_limit_0p5", "opt_al_fin_40cm2", "opt_al_strap_to_arm"):
            s = sens[f"{fit}|{name}"]
            opts[f"{fit}|{name}"] = {"case_drop_K": round(b["T_C"]["case"] - s["T_C"]["case"], 2),
                                     "housing_drop_K": round(b["T_C"]["housing"] - s["T_C"]["housing"], 2),
                                     "min_margin_gain_K": round(s["min_margin_K"] - b["min_margin_K"], 2),
                                     "min_margin_K": s["min_margin_K"]}
        opts[f"{fit}|opt_vent_vs_enclosed"] = {"case_rise_if_enclosed_K": round(sens[f"{fit}|enclosed_shroud"]["T_C"]["case"] - b["T_C"]["case"], 2)}
        opts[f"{fit}|opt_ASA_housing"] = {"housing_limit_gain_K": 31.0}
    R["step4_options"] = opts
    say("\nOptions (case drop K / housing drop K / min-margin gain K):")
    for k, v in opts.items():
        say(f"   {k:32s}: {v}")

    # sensitivity ranking: absolute case shift per variant (Fit A)
    rank = []
    for name in variants:
        if name.startswith("opt_") or name == "baseline":
            continue
        s = sens[f"A_mech|{name}"]
        d = (s["T_C"]["case"] - sens["A_mech|baseline"]["T_C"]["case"]) if s["converged"] else math.inf
        rank.append((name, d))
    fit_shift = sens["B_elec|baseline"]["T_C"]["case"] - sens["A_mech|baseline"]["T_C"]["case"]
    rank.append(("motor_fit_A_to_B", fit_shift))
    rank.sort(key=lambda x: -abs(x[1]))
    R["step4_rank_case_shift_K_fitA"] = [(n, round(d, 2)) for n, d in rank]
    say("Largest case shifts (Fit A baseline): " + "; ".join(f"{n} {d:+.1f} K" for n, d in rank[:6]))

    # max sustainable hold force
    msf = {}
    for fit in ("A_mech", "B_elec"):
        for hf_name, hf in (("duty", None), ("continuous", 1.0)):
            for lk in ("strict", "rating"):
                for opt_name, kw in (("as_is", {}), ("backoff", {"hold_current_factor": ETA_G ** 2})):
                    msf[f"{fit}|{hf_name}|{lk}|{opt_name}"] = round(max_sustainable_force(replace(Scenario(fit=fit), **kw), lk, hf), 2)
    R["max_sustainable_force_N"] = msf
    say("\nMax sustainable hold force, steady, 25 C (strict = R26 60 C + winding 125 + PETG creep 50; rating = 70 C + 125 + Tg 68):")
    for k, v in msf.items():
        say(f"   {k:40s}: {v:.2f} N")

    # ---- mitigated-case matrix: fit x conduction x ambient x back-off ------------------------
    say("\n--- 4b. Mitigated-case matrix (5 N hold, 6.5 V; back-off factor = eta_g^2 = 0.4225, the friction threshold) ---")
    BO = ETA_G ** 2
    matrix = {}
    for fit in ("A_mech", "B_elec"):
        for cond in ("avg", "pwm"):
            for amb in (25.0, 40.0):
                for bo_name, f in (("none", 1.0), (f"{BO:.4f}", BO)):
                    s = summary(Scenario(fit=fit, conduction=cond, T_amb=amb, hold_current_factor=f))
                    key = f"{fit}|{cond}|amb{amb:g}|backoff_{bo_name}"
                    if s["converged"]:
                        matrix[key] = {"case_C": s["T_C"]["case"], "mount_C": s["T_C"]["housing"],
                                       "winding_peak_C": s["T_C"]["winding_peak"], "min_margin_K": s["min_margin_K"],
                                       "binding": s["binding"], "case_vs_R26_K": s["margins_K"]["case_vs_R26_K"],
                                       # with the C1 sleeves the mount limit is 60 C [A], not the 50 C bare-PETG creep onset
                                       "min_margin_with_sleeves_K": round(min(
                                           s["margins_K"]["case_vs_R26_K"], 60.0 - s["T_C"]["housing"],
                                           s["margins_K"]["winding_peak_vs_limit_K"]), 2)}
                        say(f"{key:42s}: case {s['T_C']['case']:6.1f}  mount {s['T_C']['housing']:6.1f}  winding pk "
                            f"{s['T_C']['winding_peak']:6.1f}  min margin {s['min_margin_K']:+7.1f} K ({s['binding']})")
                    else:
                        matrix[key] = {"runaway": True}
                        say(f"{key:42s}: runaway")
    R["step4b_mitigated_matrix"] = matrix

    # largest back-off factor that still keeps the case <= 60 C (R26, steady = upper bound on the 30 min value),
    # and the hold rail current (what the INA219 reads, F4) at 0.4225 and at that limit
    def r26_ok(fit, cond, amb, f):
        s = summary(Scenario(fit=fit, conduction=cond, T_amb=amb, hold_current_factor=f))
        return s["converged"] and s["margins_K"]["case_vs_R26_K"] >= 0
    fmax = {}
    for fit in ("A_mech", "B_elec"):
        for cond in ("avg", "pwm"):
            for amb in (25.0, 40.0):
                lo, hi = 0.05, 1.0
                if not r26_ok(fit, cond, amb, lo):
                    best = None
                elif r26_ok(fit, cond, amb, hi):
                    best = hi
                else:
                    for _ in range(30):
                        mid = 0.5 * (lo + hi)
                        lo, hi = (mid, hi) if r26_ok(fit, cond, amb, mid) else (lo, mid)
                    best = lo
                rail_bo = heat_sources(Scenario(fit=fit, conduction=cond, hold_current_factor=BO), 100.0)["I_rail_hold_A"]
                rail_no = heat_sources(Scenario(fit=fit, conduction=cond), 100.0)["I_rail_hold_A"]
                rail_max = None if best is None else heat_sources(
                    Scenario(fit=fit, conduction=cond, hold_current_factor=best), 100.0)["I_rail_hold_A"]
                key = f"{fit}|{cond}|amb{amb:g}"
                fmax[key] = {"max_backoff_factor_for_R26": None if best is None else round(best, 3),
                             "factor_is_implementable": best is not None and best >= BO - 1e-9,
                             "rail_hold_A_no_backoff": round(rail_no, 3), "rail_hold_A_backoff_0p4225": round(rail_bo, 3),
                             "rail_hold_A_at_max_factor": None if rail_max is None else round(rail_max, 3)}
                say(f"{key:24s}: largest back-off factor with case <= 60 C = {fmax[key]['max_backoff_factor_for_R26']}; "
                    f"hold rail current {rail_no:.2f} A none / {rail_bo:.2f} A at 0.4225 / {rail_max if rail_max is None else round(rail_max, 2)} A at the limit")
    R["step4b_max_backoff_factor_R26"] = fmax
    R["step4b_note"] = ("Back-off 0.4225 = eta_g^2 is the BEST case: the command sits exactly at the gearbox friction "
                        "threshold, zero margin. Any real back-off stays above it. 'pwm' = discontinuous-conduction bound.")

    # back-off factor and gearbox efficiency sensitivity (Fit A and B, avg and pwm, 25 and 40 C)
    say("\n--- 4c. Back-off factor and gearbox-efficiency sensitivity (case C / mount C / min margin K) ---")
    bo_sens = {}
    cases = ([(f"factor_{f:g}", {"hold_current_factor": f}) for f in (0.42, 0.6, 0.8)]
             + [(f"eta_{e:g}_no_backoff", {"eta_g": e}) for e in (0.5, 0.65, 0.8)]
             + [(f"eta_{e:g}_backoff_at_threshold", {"eta_g": e, "hold_current_factor": e * e}) for e in (0.5, 0.65, 0.8)]
             + [(f"eta_{e:g}_backoff_0p4225", {"eta_g": e, "hold_current_factor": BO}) for e in (0.5, 0.65, 0.8)])
    for fit in ("A_mech", "B_elec"):
        for cond in ("avg", "pwm"):
            for amb in (25.0, 40.0):
                for name, kw in cases:
                    s = summary(Scenario(fit=fit, conduction=cond, T_amb=amb, **kw))
                    key = f"{fit}|{cond}|amb{amb:g}|{name}"
                    e = kw.get("eta_g", ETA_G)
                    below = kw.get("hold_current_factor", 1.0) < e * e - 1e-9
                    if s["converged"]:
                        bo_sens[key] = {"case_C": s["T_C"]["case"], "mount_C": s["T_C"]["housing"],
                                        "min_margin_K": s["min_margin_K"], "binding": s["binding"],
                                        "factor_below_friction_threshold": below}
                    else:
                        bo_sens[key] = {"runaway": True, "factor_below_friction_threshold": below}
                    r = bo_sens[key]
                    say(f"{key:56s}: " + ("runaway" if "runaway" in r else
                        f"case {r['case_C']:6.1f}  mount {r['mount_C']:6.1f}  min margin {r['min_margin_K']:+7.1f} K"
                        + ("  [below friction threshold: hold not kept]" if below else "")))
    R["step4c_backoff_sensitivity"] = bo_sens

    # R26 table owned by this script: 30-minute transient and steady state.
    r26_table = []
    for fit in ("A_mech", "B_elec"):
        for cond in ("avg", "pwm"):
            for amb in (25.0, 40.0):
                for bo_name, factor in (("off", 1.0), ("on", ETA_G ** 2)):
                    sc = Scenario(fit=fit, conduction=cond, T_amb=amb, hold_current_factor=factor)
                    m, ts, Ts = transient(sc, 1800.0, continuous=False, dt=0.1)
                    case30 = float(Ts[-1, m["net"].idx("case")])
                    ss = summary(sc)
                    r26_table.append({"reading": "high" if fit == "A_mech" else "low",
                                      "conduction": "continuous" if cond == "avg" else "discontinuous",
                                      "backoff": bo_name, "ambient_C": int(amb),
                                      "case_30min_C": round(case30, 1),
                                      "case_steady_C": ss["T_C"]["case"],
                                      "mount_steady_C": ss["T_C"]["housing"],
                                      "R26": "PASS" if case30 <= 60 else "FAIL"})
    R["r26_verdict_table"] = r26_table

    # Acceptance is the conservative high-reading fit. F4 is the INA219 in the 6.5 V rail, upstream of the servo.
    acceptance_rows = []
    for cond in ("avg", "pwm"):
        for amb in (25.0, 40.0):
            for duration_name, duration_s in (("30_min", 1800.0), ("steady", None)):
                sc = Scenario(fit="A_mech", conduction=cond, T_amb=amb)
                solved = acceptance_limit(sc, duration_s)
                limit_A = solved["rail_limit_A"]
                pred = solved["predicted_rail_A"]
                acceptance_rows.append({
                    "ambient_C": int(amb),
                    "conduction": "continuous" if cond == "avg" else "discontinuous",
                    "duration": duration_name,
                    "case_limit_C": LIMITS["case_R26_C"]["value"],
                    "hold_current_factor": round(solved["hold_current_factor"], 6),
                    "rail_limit_A": round(limit_A, 3),
                    "predicted_rail_A_backoff": round(pred["backoff"], 3),
                    "predicted_rail_A_no_backoff": round(pred["no_backoff"], 3),
                    "backoff_margin_A": round(limit_A - pred["backoff"], 3),
                    "backoff_margin_percent": round(100 * (limit_A - pred["backoff"]) / limit_A, 1),
                })
    R["acceptance"] = {
        "instrument": "INA219 bench current reading at F4 in the 6.5 V rail upstream of the servo",
        "basis": "high-reading motor fit, 5 N per pad, stated 35 s duty cycle; limits solved from the thermal model",
        "case_temperature_expanded_uncertainty_C": CASE_TEMPERATURE_U_C,
        "ambient_temperature_expanded_uncertainty_C": AMBIENT_TEMPERATURE_U_C,
        "ambient_uncertainty_budget_C": {
            "calibration_standard_u": AMBIENT_CALIBRATION_U_C,
            "resolution_standard_u": AMBIENT_RESOLUTION_U_C,
            "shaded_air_representativeness_limit": AMBIENT_REPRESENTATIVENESS_LIMIT_C,
            "shaded_air_representativeness_standard_u": AMBIENT_REPRESENTATIVENESS_U_C,
            "shaded_air_representativeness_status": AMBIENT_REPRESENTATIVENESS_LABEL,
        },
        "ambient_model_range_C": list(AMBIENT_MODEL_RANGE_C),
        "ambient_range_C": list(AMBIENT_RANGE_C),
        "r26_thresholds": {
            "derivation": "exact limits = 60 C -/+ case_temperature_expanded_uncertainty_C; "
                          "governing thresholds = exact limits rounded inward to 0.1 C (CLI and note)",
            **r26_thresholds(),
        },
        "ambient_instrument": "shaded type K bead on MAX31855, 20 cm from the gripper",
        "instrument_config": {
            "shunt_ohm": CONFIG["INA219_SHUNT_OHM"],
            "shunt_lsb_uV": CONFIG["INA219_SHUNT_LSB_UV"],
            "current_resolution_A": CONFIG["INA219_SHUNT_LSB_UV"] * 1e-6 / CONFIG["INA219_SHUNT_OHM"],
            "sample_period_ms": CONFIG["INA219_PERIOD_MS"],
            "averaging_window_ms": CONFIG["HOLD_I_AVG_MS"],
            "samples_per_average": CONFIG["HOLD_I_AVG_MS"] // CONFIG["INA219_PERIOD_MS"],
        },
        "rows": acceptance_rows,
    }
    regime_ambients = (AMBIENT_RANGE_C[0], 25.0, 30.0, 35.0, AMBIENT_RANGE_C[1])
    R["acceptance"]["regime_table"] = [
        regime_prediction_row(float(ambient))
        for ambient in regime_ambients
    ]
    passing_margins = [row["backoff_margin_A"] for row in acceptance_rows if row["backoff_margin_A"] >= 0]
    R["acceptance"]["minimum_passing_margin_A"] = min(passing_margins)
    R["acceptance"]["maximum_total_instrument_error_A"] = min(passing_margins) / 2
    acceptance_verdict = render_acceptance_verdict(acceptance_rows)
    R["acceptance"]["verdict"] = acceptance_verdict

    # Revision-B limiter/washer bearing pressures. Preload is 250--500 N.
    washers = {}
    for od in (7.0, 6.0):
        petg_A = math.pi / 4 * ((od * 1e-3) ** 2 - (HS["limiter"]["od"] * 1e-3) ** 2)
        sleeve_A = math.pi / 4 * ((HS["limiter"]["od"] * 1e-3) ** 2 - (HS["limiter"]["id"] * 1e-3) ** 2)
        washers[f"OD{od:g}_mm"] = {"PETG_bearing_MPa": [round(F / petg_A / 1e6, 1) for F in (250, 500)],
                                      "sleeve_bearing_MPa": [round(F / sleeve_A / 1e6, 1) for F in (250, 500)]}
    washer_protrusions = [washer_minimum_protrusion_mm(F) for F in (250, 500)]
    R["washer_ruling"] = {"preload_N": [250, 500], "washer": washers,
                           "PETG_modulus_MPa": {"value": petg_E_short(23.0), "tag": "D from S"},
                           "elastic_compression_mm": [round(x, 4) for x in washer_protrusions],
                           "minimum_protrusion_mm": round(max(washer_protrusions), 3),
                           "ruling": "Keep the 7 mm washer. Permit a 6 mm washer only when the installed sleeve stands above the compressed PETG seat by at least the computed minimum; reject flush."}

    # verdict
    a = steady["A_mech|avg|F5"]
    b = steady["B_elec|avg|F5"]
    ab = sens["A_mech|opt_backoff_hold_eta2"]
    verdict = {
        "fitA_case_C": a["T_C"]["case"], "fitB_case_C": b["T_C"]["case"],
        "fitA_housing_C": a["T_C"]["housing"], "fitB_housing_C": b["T_C"]["housing"],
        "fitA_backoff_case_C": ab["T_C"]["case"], "fitA_backoff_housing_C": ab["T_C"]["housing"],
        "fitA_min_margin_K": a["min_margin_K"], "fitB_min_margin_K": b["min_margin_K"],
        "fitA_backoff_min_margin_K": ab["min_margin_K"],
        "class": acceptance_verdict,
        # the mitigated design (back-off 0.4225) passes R26 only under the stated conditions (matrix 4b)
        "mitigated_R26_pass_at_40C": {k: matrix[k]["case_vs_R26_K"] >= 0 for k in matrix
                                      if k.endswith("amb40|backoff_0.4225")},
    }
    R["verdict"] = verdict
    say(f"\nVERDICT: {acceptance_verdict}")

    # ---- figures (opt-in because renderer bytes vary across platforms) ----------------------
    if figures:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
        for j, cont in enumerate(("duty", "continuous")):
            for fit, col in (("A_mech", "tab:red"), ("B_elec", "tab:blue")):
                ts, Ts = traces[f"{fit}|{cont}"]
                ax[j].plot(ts / 60, Ts[:, 1], color=col, label=f"{fit} case")
                ax[j].plot(ts / 60, Ts[:, 2], color=col, ls="--", label=f"{fit} housing at mount")
                ax[j].plot(ts / 60, Ts[:, 0], color=col, lw=0.5, alpha=0.5, label=f"{fit} winding")
            for y, lab in ((60, "R26 60 C"), (50, "PETG creep onset 50 C [A]"), (68, "PETG Tg 68 C")):
                ax[j].axhline(y, color="k", lw=0.6, ls=":")
                ax[j].text(1, y + 0.8, lab, fontsize=7)
            ax[j].set_title(f"1 h from cold, 25 C ambient, 5 N hold, {'35 s duty cycle' if cont == 'duty' else 'continuous hold'}")
            ax[j].set_xlabel("time (min)")
            ax[j].set_ylim(20, 140)
            ax[j].grid(alpha=0.3)
        ax[0].set_ylabel("temperature (C)")
        ax[1].legend(fontsize=7, loc="upper left")
        fig.tight_layout()
        FIG_DIR.mkdir(parents=True, exist_ok=True)
        fig.savefig(FIG_DIR / "thermal_transient_1h.png", dpi=120, metadata={"Software": None})
        plt.close(fig)

        names = [n for n, _ in rank if math.isfinite(_)][:14]
        vals = [dict(rank)[n] for n in names]
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.barh(range(len(names)), vals, color=["tab:red" if v > 0 else "tab:green" for v in vals])
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=8)
        ax.invert_yaxis()
        ax.axvline(0, color="k", lw=0.6)
        ax.set_xlabel("steady case temperature shift from the Fit A baseline (K)")
        ax.set_title(f"Sensitivity, Fit A baseline case {sens['A_mech|baseline']['T_C']['case']:.1f} C")
        fig.tight_layout()
        fig.savefig(FIG_DIR / "thermal_sensitivity.png", dpi=120, metadata={"Software": None})
        plt.close(fig)

    washer_begin = "<!-- THERMAL-WASHER:BEGIN -->"
    washer_end = "<!-- THERMAL-WASHER:END -->"
    washer_replacement = (f"{washer_begin}\nComputed minimum sleeve protrusion: "
                          f"**{R['washer_ruling']['minimum_protrusion_mm']:.3f} mm** at 500 N; "
                          f"elastic compression is {R['washer_ruling']['elastic_compression_mm'][0]:.4f}–"
                          f"{R['washer_ruling']['elastic_compression_mm'][1]:.4f} mm over 250–500 N, "
                          f"using **{R['washer_ruling']['PETG_modulus_MPa']['value']:.0f} MPa [D from S]**.\n{washer_end}")

    accept_begin = "<!-- THERMAL-ACCEPT:BEGIN -->"
    accept_end = "<!-- THERMAL-ACCEPT:END -->"
    accept_replacement = render_acceptance_table(acceptance_rows, R["acceptance"], r26_table)

    begin = "<!-- THERMAL-R26:BEGIN -->"
    end = "<!-- THERMAL-R26:END -->"
    lines = [begin, "| Reading | Conduction | Back-off | Ambient (°C) | Case 30 min (°C) | Case steady (°C) | R26 |",
             "|---|---|---:|---:|---:|---:|---|"]
    for row in r26_table:
        lines.append(f"| {row['reading']} | {row['conduction']} | {row['backoff']} | {row['ambient_C']} | {row['case_30min_C']:.1f} | {row['case_steady_C']:.1f} | {row['R26']} |")
    lines.append(end)
    replacement = "\n".join(lines)
    if write_outputs:
        note = note_path.read_text(encoding="utf-8")
        if washer_begin in note and washer_end in note:
            note = note[:note.index(washer_begin)] + washer_replacement + note[note.index(washer_end) + len(washer_end):]
        if accept_begin in note and accept_end in note:
            note = note[:note.index(accept_begin)] + accept_replacement + note[note.index(accept_end) + len(accept_end):]
        if begin in note and end in note:
            note = note[:note.index(begin)] + replacement + note[note.index(end) + len(end):]
        note_path.write_text(note, encoding="utf-8", newline="\n")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "thermal.json").write_text(
            json.dumps(R, indent=1, sort_keys=True, default=float) + "\n", encoding="utf-8", newline="\n")
        (out_dir / "thermal_stdout.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8", newline="\n")
    R["_generated_note_table"] = replacement
    R["_generated_acceptance_table"] = accept_replacement
    R["_generated_washer_block"] = washer_replacement
    return R



def render_acceptance_table(
    rows: list[dict],
    acceptance: dict | None = None,
    r26_rows: list[dict] | None = None,
) -> str:
    begin, end = "<!-- THERMAL-ACCEPT:BEGIN -->", "<!-- THERMAL-ACCEPT:END -->"
    if acceptance is None:
        committed = json.loads((OUT_DIR / "thermal.json").read_text(encoding="utf-8"))
        acceptance = committed["acceptance"]
    if r26_rows is None:
        committed = json.loads((OUT_DIR / "thermal.json").read_text(encoding="utf-8"))
        r26_rows = committed["r26_verdict_table"]
    u_case = acceptance.get("case_temperature_expanded_uncertainty_C", CASE_TEMPERATURE_U_C)
    limits = r26_thresholds(u_case)
    passing = [row["backoff_margin_A"] for row in rows if row["backoff_margin_A"] >= 0]
    error_bound = acceptance.get("maximum_total_instrument_error_A", min(passing) / 2)
    regime_rows = acceptance["regime_table"]
    prediction_lines = [
        "| Ambient (°C) | Continuous prediction (°C) | Discontinuous prediction (°C) "
        "| Separable at U? |",
        "|---:|---:|---:|---|",
    ]
    for row in regime_rows:
        predictions = row["predictions"]
        prediction_lines.append(
            f"| {row['ambient_C']:.0f} | {predictions['continuous']:.1f} | "
            f"{predictions['discontinuous']:.1f} | {'yes' if row['separable'] else 'no'} |"
        )
    continuous_limits = {
        row["ambient_C"]: row["rail_limit_A"]
        for row in rows
        if row["conduction"] == "continuous" and row["duration"] == "steady"
    }
    lines = [begin, f"**Verdict: {render_acceptance_verdict(rows)}**", "",
        "**Regime classifier:** Bond the type K case bead with paste and Kapton to the exposed "
        "aluminium shell "
        "per [TP-07](../test/procedures/TP-07-thermal-soak.md). The C3 Ø1 hole measures the "
        "PETG mount; it is "
        "not the classifier. Commissioning needs a third, calibrated ambient channel in TP-07, "
        "pending in the test plan. Measure ambient with the shaded type K/MAX31855 bead 20 cm away; its "
        f"expanded uncertainty is ±{AMBIENT_TEMPERATURE_U_C:.3f} °C, including a "
        f"{AMBIENT_REPRESENTATIVENESS_LIMIT_C:.1f} °C shaded-air representativeness term "
        f"({AMBIENT_REPRESENTATIVENESS_LABEL}). The accepted ambient range is "
        f"{accepted_ambient_range_text()}, so ambient ± uncertainty stays "
        f"inside the model's {AMBIENT_MODEL_RANGE_C[0]:.0f}–{AMBIENT_MODEL_RANGE_C[1]:.0f} °C domain. "
        "At 30 minutes, the reading ± expanded instrument uncertainty "
        f"U = {u_case:.3f} °C is continuous only when that interval contains only the continuous prediction, "
        "and discontinuous only when it contains only the discontinuous prediction; otherwise it is "
        "indeterminate. "
        "The model's prediction uncertainty is not quantified, so any indeterminate outcome means "
        "do not operate. The command evaluates each regime at ambient ± its uncertainty and uses "
        "the widest prediction span. Rows marked not separable have predictions closer than 2U.", "",
        "`python analysis/gripper/thermal/thermal.py --classify --ambient <°C> --reading <°C>` "
        "uses back-off on; add `--no-backoff` to select back-off off. Exit codes: continuous 0, "
        "discontinuous 2, indeterminate 3, refused ambient 4.", "",
        *prediction_lines, "",
        "Worked example: at 22 °C ambient and a 35.0 °C case reading, run "
        "`python analysis/gripper/thermal/thermal.py --classify --ambient 22 --reading 35.0`; "
        "the generated model classifies the result as continuous.", "",
        f"**Separate R26 safety check:** PASS at or below {limits['pass_at_or_below_C']:.1f} °C; "
        f"FAIL at or above {limits['fail_at_or_above_C']:.1f} °C; indeterminate between. Derivation: "
        f"the exact limits 60 °C ∓ {u_case:.3f} °C are {limits['exact_pass_limit_C']:.9f} °C and "
        f"{limits['exact_fail_limit_C']:.9f} °C; the governing thresholds round them inward to 0.1 °C. "
        "Any indeterminate outcome means do not operate.", "",
        "Commissioning gates:",
        "1. Back-off is enabled.",
        "2. At least 5.0 N per pad is proven throughout the hold.",
        f"3. Stop at 30 minutes unless the steady-state F4 current limit for the row is met "
        f"(continuous: {continuous_limits[25]:.3f} A at 25 °C; {continuous_limits[40]:.3f} A at 40 °C).", "",
        f"For acceptance, the combined expanded uncertainty must be ≤{error_bound:.3f} A for the "
        "reference chain at each applicable threshold. Firmware trips read the same INA219; its gain, "
        "offset, drift, "
        "and shunt tolerance are not established in firmware/gripper/config.h, so calibrate trips "
        "against the "
        "reference and apply a guard band before operation.", "",
        "| Ambient (°C) | Conduction | Duration | F4 limit (A) | Predicted back-off (A) "
        "| Margin (A / %) | Predicted no back-off (A) |",
        "|---:|---|---|---:|---:|---:|---:|"]
    for row in rows:
        duration = "30 min" if row["duration"] == "30_min" else "steady state"
        lines.append(
            f"| {row['ambient_C']} | {row['conduction']} | {duration} | {row['rail_limit_A']:.3f} | "
            f"{row['predicted_rail_A_backoff']:.3f} | {row['backoff_margin_A']:+.3f} / "
            f"{row['backoff_margin_percent']:+.1f}% | {row['predicted_rail_A_no_backoff']:.3f} |"
        )
    lines.append(end)
    return "\n".join(lines)


def differences(expected, actual, key="") -> list[str]:
    """Return stable, leaf-level differences using the check-mode comparison rules."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        result = []
        for child in sorted(set(expected) | set(actual)):
            child_key = f"{key}.{child}" if key else child
            if child not in expected or child not in actual:
                result.append(f"{child_key}: {expected.get(child)!r} != {actual.get(child)!r}")
            else:
                result.extend(differences(expected[child], actual[child], child_key))
        return result
    if isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)):
        if len(expected) != len(actual):
            return [f"{key}.length: {len(expected)} != {len(actual)}"]
        return [d for i, pair in enumerate(zip(expected, actual))
                for d in differences(pair[0], pair[1], f"{key}[{i}]")]
    if isinstance(expected, float) or isinstance(actual, float):
        same = isinstance(expected, (int, float)) and isinstance(actual, (int, float)) and math.isclose(
            float(expected), float(actual), rel_tol=1e-9, abs_tol=0.0)
    else:
        same = type(expected) is type(actual) and expected == actual
    return [] if same else [f"{key}: {expected!r} != {actual!r}"]


def check_outputs(result: dict, out_dir: Path, note_path: Path) -> list[str]:
    table = result.pop("_generated_note_table")
    acceptance_table = result.pop("_generated_acceptance_table")
    washer_block = result.pop("_generated_washer_block")
    expected = json.loads((out_dir / "thermal.json").read_text(encoding="utf-8"))
    found = differences(expected, result)
    note = note_path.read_text(encoding="utf-8")
    begin, end = "<!-- THERMAL-R26:BEGIN -->", "<!-- THERMAL-R26:END -->"
    committed = note[note.index(begin):note.index(end) + len(end)]
    if committed != table:
        found.append("note.THERMAL-R26: generated table differs")
    accept_begin, accept_end = "<!-- THERMAL-ACCEPT:BEGIN -->", "<!-- THERMAL-ACCEPT:END -->"
    accept_committed = note[note.index(accept_begin):note.index(accept_end) + len(accept_end)]
    if accept_committed != acceptance_table:
        found.append("note.THERMAL-ACCEPT: generated table differs")
    washer_begin, washer_end = "<!-- THERMAL-WASHER:BEGIN -->", "<!-- THERMAL-WASHER:END -->"
    washer_committed = note[note.index(washer_begin):note.index(washer_end) + len(washer_end)]
    if washer_committed != washer_block:
        found.append("note.THERMAL-WASHER: generated block differs")
    return found


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--figures", action="store_true", help="also render platform-dependent PNG figures")
    parser.add_argument("--check", action="store_true", help="compare generated values without writing files")
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR, help=argparse.SUPPRESS)
    parser.add_argument("--note", type=Path, default=P_NOTE, help=argparse.SUPPRESS)
    parser.add_argument("--classify", action="store_true", help="classify a 30-minute case reading")
    parser.add_argument("--ambient", type=float, help="measured ambient temperature in °C")
    parser.add_argument("--reading", type=float, help="measured 30-minute case temperature in °C")
    parser.add_argument(
        "--no-backoff", action="store_true", help="evaluate commissioning without back-off"
    )
    args = parser.parse_args()
    if args.classify:
        if args.ambient is None or args.reading is None:
            parser.error("--classify requires --ambient and --reading")
        raise SystemExit(classify_command(args.ambient, args.reading, not args.no_backoff))
    if args.check:
        with contextlib.redirect_stdout(io.StringIO()):
            generated = main(write_outputs=False, figures=False, out_dir=args.output_dir, note_path=args.note)
    else:
        generated = main(write_outputs=True, figures=args.figures, out_dir=args.output_dir, note_path=args.note)
    if args.check:
        problems = check_outputs(generated, args.output_dir, args.note)
        for problem in problems:
            print(problem)
        raise SystemExit(bool(problems))
