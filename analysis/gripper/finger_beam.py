#!/usr/bin/env python3
"""Hand calcs for the cloth-feed gripper fingers (ME102B).

Each TPU Fin Ray finger is treated as a cantilever clamped at the PLA root plate:
  1. Euler-Bernoulli + Timoshenko solid wedge (the finger with no cells cut out),
  2. Fin Ray as a two-flank truss: flanks = sandwich chords (axial), ribs = Vierendeel
     verticals (shear), with the tapered-chord shear relief V_web = V - M tan(phi)/c.
It also sizes the PLA knuckle arm / root plate, the contact force the actuator torque
can make, and the over-travel needed to reach the grip target.

Two geometries are run: the design-basis finger (DESIGN-BASIS.md D3/R17: L = 45 mm,
r_c = 65 mm) and the current CAD finger from params.json as a reference.

    uv run --with numpy --with matplotlib python analysis/gripper/finger_beam.py
    uv run --with numpy --with matplotlib python analysis/gripper/finger_beam.py --check

Writes analysis/gripper/results/finger_beam.json and docs/gripper/figures/finger_beam.png.
finger_fea.py imports INPUTS, load_geometry() and finger_profile() from here, so every
design input lives in the one block below.
"""
from __future__ import annotations

import json
import math
import argparse
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RESULTS = HERE / "results"
FIGS = REPO / "docs" / "gripper" / "figures"

# =====================================================================================
# DESIGN INPUTS -- the single constants block.  docs/gripper/DESIGN-BASIS.md (2026-09-22)
# governs; its machine-readable copy in cad/gripper/params.json (blocks grip and
# materials.allowables) is mapped over these values by apply_overrides() below, and the
# mapping actually used is written into every output JSON.
# Tags: [S] sourced (URL), [D] derived, [A] assumed.
# =====================================================================================
INPUTS = {
    "params_json": "cad/gripper/params.json",  # geometry [S: repo CAD]
    "grip": {
        "target_N": 5.0,     # [D] DESIGN-BASIS R14 / LC1 (params grip.F_target_N)
        "cap_N": 10.0,       # [A] DESIGN-BASIS R15 / LC2 (params grip.F_cap_N)
        "mu_pad_cloth": 0.4,  # [A] DESIGN-BASIS M2 (params grip.mu_pad_cloth)
        "cloth_thickness_mm": 0.3,  # [A] DESIGN-BASIS section 6 (one ply)
        "k_tip_min_N_per_mm": 0.88,  # [D] DESIGN-BASIS R12 (params grip.k_tip_min_N_per_mm)
        "k_tip_max_N_per_mm": 1.63,  # [D] DESIGN-BASIS R12
        "k_tip_default_N_per_mm": 1.0,  # [D] DESIGN-BASIS R12
        "theta_min_deg": -11.0,  # [D] DESIGN-BASIS R18
        "theta_open_max_deg": 20.0,  # [D] DESIGN-BASIS R18
    },
    "geometry": {
        "length_design_mm": 45.0,  # [D] DESIGN-BASIS D3/R17 (params grip.finger_length_design_mm)
        "pad_centroid_from_tip_mm": 5.0,  # [D] DESIGN-BASIS section 3 (params grip.pad_centroid_from_tip_mm)
        # current CAD length comes from params.json finger.length (60 mm) [S repo CAD]
    },
    "contact": {
        "patch_mid_mm": 10.0,  # [A] cloth-contact patch length at mid-length (s = L/2)
        "patch_tip_mm": 6.0,   # [A] tip pad; equals the 6 mm FSR puck of DESIGN-BASIS section 8
    },
    "TPU": {  # Ultimaker TPU 95A, printed 100 % infill (DESIGN-BASIS section 4; params materials.allowables.TPU95A)
        "E_nominal_MPa": 67.0,  # [S] X-Y 67 +/- 6 MPa, ASTM D3039: https://um-support-files.ultimaker.com/materials/2.85mm/tds/TPU-95A/Ultimaker-TPU95A-TDS-v5.00.pdf
        "E_low_MPa": 56.0,      # [S] same TDS, Z 56 +/- 3 MPa (lower bound of the design band)
        "E_sensitivity_MPa": {  # other grades, sensitivity only (superseded as design values)
            "NinjaTek Cheetah 95A": 26.0,  # [S] ASTM D638: https://ninjatek.com/wp-content/uploads/Cheetah-TDS.pdf
            "Bambu TPU 95A HF": 9.8,       # [S] ISO 527 X-Y: https://store.bblcdn.eu/s8/default/16df21baf482453999b3dbb61cc110e7/Bambu_TPU_95A_HF_Technical_Data_Sheet.pdf
        },
        "nu": 0.45,             # [A] DESIGN-BASIS section 4
        "strain_limit_LC1": 0.10,  # [A] DESIGN-BASIS LC1: finger strain <= 10 % at F_target (params design_strain_max_pct)
        "stress_allow_cap_MPa": 4.5,  # [A] p99 von Mises at F_cap (linear model); ~ the Ultimaker flexural
                                      # strength 4.1 MPa at 9.4 % strain [S TDS]; was Cheetah yield 9 / SF 2
        "break_XY_MPa": 23.7,   # [S] Ultimaker TDS
        "break_Z_MPa": 6.4,     # [S] Ultimaker TDS (across layers)
        "flex_strength_MPa_at_9p4pct": 4.1,  # [S] Ultimaker TDS, ISO 178
        "density": 1.22,        # [S] Ultimaker TDS (params materials.allowables.TPU95A.density)
    },
    "PLA": {  # Bambu PLA Basic TDS (DESIGN-BASIS section 4; params materials.allowables.PLA)
        "E_MPa": 2580.0,         # [S] X-Y: https://wiki.bambulab.com/filament-acc/abs-asa-pc/bambu_pla_basic_technical_data_sheet.pdf
        "nu": 0.35,              # [A] gears.md
        "tensile_XY_MPa": 35.0,  # [S] same TDS
        "allow_LC1_MPa": 15.0,   # [D] DESIGN-BASIS section 4 (fatigue 1e5 / 1.5)
        "allow_LC2_MPa": 23.33,  # [D] DESIGN-BASIS section 4 (tensile X-Y / 1.5)
        "Kt_arm_root": 1.5,      # [A] sharp arm-to-hub junction, no fillet modelled
        "density": 1.24,         # [S] TDS
    },
    "drive": {
        "eta_mesh_pivot": 0.85,    # [A] DESIGN-BASIS section 2 (params grip.eta_mesh_pivot), whole path
        "torque_convention": "design_basis",  # [D] DESIGN-BASIS section 2: T_servo = 2 F r_c / eta
        "backlash_jt_mm": 0.25,    # [D] tolerancing.md s5: plan jt0 ~ 0.2-0.3 mm at m 1
        "lag_convention": "calibrated",  # [A] theta = 0 is defined after the R21 CALIBRATE state, which closes
                                         # in the grip direction, so backlash is already taken up (lag 0).
                                         # Sensitivity: 'centred' (theta 0 = centred mesh, lag = jt/2 at pitch).
        "hold_fraction": 0.4,      # [A] DESIGN-BASIS R16 (params grip.hold_fraction_of_stall)
    },
    "nail": {  # DESIGN-BASIS D7, finger A (driven)
        "thickness_mm": 1.0,  # [A] DESIGN-BASIS D7 / params grip.finger_roles.A
        "length_mm": 12.0,    # [A] from the tip up the pad face; covers the 6 mm tip-pad patch
    },
    "fsr_backing": {  # DESIGN-BASIS D7 / section 8, finger B (idler)
        "thickness_mm": 1.0,  # [A] DESIGN-BASIS section 8 (params grip.fsr.backing)
        "length_mm": 14.0,    # [A] covers an FSR 402-class round sensor; check against the part drawing
        "puck_mm": 6.0,       # [A] DESIGN-BASIS section 8: 6 mm puck over the active area (= load patch)
    },
    # Candidate PWM actuators, stall torque at the stated voltage (docs/gripper/research/actuators.csv)
    "actuators": {
        "A13 FS5115M-FB 15.5 kgcm": 15.5,  # [S] csv row A13 (6 V)
        "A12 FS5106B-FB 6.0 kgcm": 6.0,    # [S] csv row A12 (6 V)
        "A17 DS3218MG @6.8V 21.5 kgcm": 21.5,  # [S] csv row A17 (6.8 V)
    },
}
KGCM_TO_NMM = 98.0665  # [D] 1 kg-cm = 9.80665 N x 10 mm

# params.json keys (owner DESIGN-BASIS.md) mapped onto INPUTS.  Present key wins.
PARAMS_OVERRIDES = {
    ("grip", "F_target_N"): ("grip", "target_N"),
    ("grip", "F_cap_N"): ("grip", "cap_N"),
    ("grip", "mu_pad_cloth"): ("grip", "mu_pad_cloth"),
    ("grip", "eta_mesh_pivot"): ("drive", "eta_mesh_pivot"),
    ("grip", "k_tip_min_N_per_mm"): ("grip", "k_tip_min_N_per_mm"),
    ("grip", "k_tip_max_N_per_mm"): ("grip", "k_tip_max_N_per_mm"),
    ("grip", "k_tip_default_N_per_mm"): ("grip", "k_tip_default_N_per_mm"),
    ("grip", "theta_min_deg"): ("grip", "theta_min_deg"),
    ("grip", "theta_open_max_deg"): ("grip", "theta_open_max_deg"),
    ("grip", "hold_fraction_of_stall"): ("drive", "hold_fraction"),
    ("grip", "finger_length_design_mm"): ("geometry", "length_design_mm"),
    ("grip", "pad_centroid_from_tip_mm"): ("geometry", "pad_centroid_from_tip_mm"),
    ("materials", "allowables", "TPU95A", "E_xy"): ("TPU", "E_nominal_MPa"),
    ("materials", "allowables", "TPU95A", "E_z"): ("TPU", "E_low_MPa"),
    ("materials", "allowables", "TPU95A", "poisson"): ("TPU", "nu"),
    ("materials", "allowables", "TPU95A", "density"): ("TPU", "density"),
    ("materials", "allowables", "TPU95A", "break_xy"): ("TPU", "break_XY_MPa"),
    ("materials", "allowables", "TPU95A", "break_z"): ("TPU", "break_Z_MPa"),
    ("materials", "allowables", "TPU95A", "flex_strength_xy_at_9p4pct"): ("TPU", "flex_strength_MPa_at_9p4pct"),
    ("materials", "allowables", "PLA", "E_xy"): ("PLA", "E_MPa"),
    ("materials", "allowables", "PLA", "tensile_xy"): ("PLA", "tensile_XY_MPa"),
    ("materials", "allowables", "PLA", "allow_LC1"): ("PLA", "allow_LC1_MPa"),
    ("materials", "allowables", "PLA", "allow_LC2"): ("PLA", "allow_LC2_MPa"),
    ("materials", "allowables", "PLA", "density"): ("PLA", "density"),
}


# ------------------------------------------------------------------ geometry
def load_params(path=None):
    p = Path(path) if path else REPO / INPUTS["params_json"]
    return json.loads(p.read_text(encoding="utf-8"))


def _get(P, keys):
    v = P
    for k in keys:
        if not isinstance(v, dict) or k not in v:
            return None
        v = v[k]
    return v


def apply_overrides(P):
    used = {}
    for keys, (iblk, ikey) in PARAMS_OVERRIDES.items():
        v = _get(P, keys)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            INPUTS[iblk][ikey] = float(v)
            used[f"{iblk}.{ikey}"] = "params.json " + ".".join(keys)
    v = _get(P, ("materials", "allowables", "TPU95A", "design_strain_max_pct"))
    if isinstance(v, (int, float)):
        INPUTS["TPU"]["strain_limit_LC1"] = float(v) / 100
        used["TPU.strain_limit_LC1"] = "params.json materials.allowables.TPU95A.design_strain_max_pct / 100"
    sdp = _get(P, ("grip", "servo_design_point"))
    if isinstance(sdp, dict) and isinstance(sdp.get("stall_kgcm"), (int, float)):
        name = f"{sdp.get('id', '')} {sdp.get('model', '')} @{sdp.get('supply_V', '')}V {sdp['stall_kgcm']} kgcm (design point)"
        INPUTS["actuators"] = {name: float(sdp["stall_kgcm"]), **{k: v for k, v in INPUTS["actuators"].items() if "(design point)" not in k}}
        used["actuators.design_point"] = "params.json grip.servo_design_point"
    return used


def load_geometry(P=None, design=True, **over):
    """Finger-A local frame (pivot at origin), mm.  design=True sets L to the design-basis
    length (45 mm); design=False keeps the CAD length.  over= replaces finger.* keys (sweep)."""
    P = P or load_params()
    g, k, f = P["gear"], P["knuckle"], dict(P["finger"])
    if design:
        f["length"] = INPUTS["geometry"]["length_design_mm"]
    f.update(over)
    m, z = g["module"], g["teeth"]
    r = m * z / 2
    a = m * z
    rf = r - 1.25 * m
    w_arm = k["arm_top_width"]
    G = dict(
        m=m, z=z, r=r, a=a, rf=rf, rb=r * math.cos(math.radians(g["pressure_angle"])),
        b=g["face_width"], alpha=math.radians(g["pressure_angle"]),
        xf=a / 2 - f["closed_gap"] / 2, R0=k["root_offset"], t_root=k["root_thickness"],
        y0=-k["root_offset"] - k["root_thickness"] - k["root_tab"], w_arm=w_arm,
        h_arm_top=math.sqrt(rf ** 2 - w_arm ** 2 / 4),
        L=f["length"], W=f["base_width"], D=f["depth"], t=f["wall"], tr=f["rib_thickness"],
        n=int(f["ribs"]), beta=f["rib_angle"], gap=f["closed_gap"], lattice=f["lattice"],
        tip_width=float(f.get("tip_width", 0.0)),  # sweep-only option: truncated (blunt) tip, 0 = CAD spec
        rho_tpu=INPUTS["TPU"]["density"], rho_pla=INPUTS["PLA"]["density"], fill=P["materials"]["print_fill"],
    )
    G["s_tip"] = G["L"] - INPUTS["geometry"]["pad_centroid_from_tip_mm"]  # tip-pad centroid, from the root line
    G["s_mid"] = G["L"] / 2
    G["rc_tip"] = -G["y0"] + G["s_tip"]  # DESIGN-BASIS D2: perpendicular pivot -> pad-normal line (65 / 80 mm)
    G["phi_back"] = math.atan(G["W"] / G["L"])  # back-flank angle from the finger axis
    return G


def _area(p):
    return sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p))) / 2


def _clip(poly, nx, ny, c):
    out = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        fa, fb = nx * a[0] + ny * a[1] - c, nx * b[0] + ny * b[1] - c
        if fa >= 0:
            out.append(a)
        if (fa >= 0) != (fb >= 0):
            t = fa / (fa - fb)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def _inset(poly, d):
    r = poly
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        nx, ny = -(q[1] - p[1]) / L, (q[0] - p[0]) / L
        r = _clip(r, nx, ny, nx * p[0] + ny * p[1] + d)
        if len(r) < 3:
            return []
    return r


def _clean(p):
    o = []
    for q in p:
        if not o or math.hypot(q[0] - o[-1][0], q[1] - o[-1][1]) > 1e-4:
            o.append(q)
    if len(o) > 2 and math.hypot(o[0][0] - o[-1][0], o[0][1] - o[-1][1]) < 1e-4:
        o.pop()
    return o


def finger_profile(G):
    """Port of cad/gripper/gripper_concept.py finger_profile (finray lattice).
    Returns (outer polygon CCW, list of cell polygons to cut out)."""
    xf, y0, L, W = G["xf"], G["y0"], G["L"], G["W"]
    tw = G.get("tip_width", 0.0)
    outer = [(xf, y0), (xf - W, y0), (xf - tw, y0 - L), (xf, y0 - L)] if tw > 0 else [(xf, y0), (xf - W, y0), (xf, y0 - L)]
    if _area(outer) < 0:
        outer.reverse()
    inner = _inset(outer, G["t"])
    cells = []
    if len(inner) >= 3:
        be = math.radians(G["beta"])
        nx, ny, N, t = math.sin(be), math.cos(be), G["n"], G["tr"]
        cs = [nx * xf + ny * (y0 - i * L / (N + 1)) for i in range(1, N + 1)]
        for k in range(N + 1):
            poly = inner
            if k >= 1:
                poly = _clip(poly, -nx, -ny, -(cs[k - 1] - t / 2))
            if k < N and len(poly) >= 3:
                poly = _clip(poly, nx, ny, cs[k] + t / 2)
            cells.append(poly)
    cells = [c for c in (_clean(c) for c in cells) if len(c) >= 3 and abs(_area(c)) > 1.2]
    return outer, cells


def finger_area(G):
    outer, cells = finger_profile(G)
    return abs(_area(outer)) - sum(abs(_area(c)) for c in cells)


# ------------------------------------------------------------------ beam models
def section(G, s):
    """Horizontal cut at distance s below the root. Returns dict of section props (mm)."""
    L, W, D, t = G["L"], G["W"], G["D"], G["t"]
    w = W * (1 - s / L)
    th = t / math.cos(G["phi_back"])  # back-flank horizontal thickness
    c = w - t / 2 - th / 2
    A1, A2 = t * D, th * D
    solid = w <= t + th
    I_solid = D * w ** 3 / 12
    I_sand = I_solid if solid else A1 * A2 / (A1 + A2) * c ** 2 + D * t ** 3 / 12 + D * th ** 3 / 12
    return dict(w=w, c=max(c, 1e-9), A1=A1, A2=A2, solid=solid, I_solid=I_solid, I_sand=I_sand, A_solid=D * w)


def compliance(G, E, nu, a, model, npts=4000):
    """Unit-load compliance, mm/N: (delta at load point a, delta at tip) for a lateral
    load at distance a below the root.  model = 'solid' (EB + Timoshenko) or 'finray'
    (sandwich chords + Vierendeel ribs with tapered-chord shear relief)."""
    L = G["L"]
    Gs = E / (2 * (1 + nu))
    kap = 5 / 6
    p = L / (G["n"] + 1)
    Ic = G["D"] * G["t"] ** 3 / 12
    Iv = G["D"] * G["tr"] ** 3 / 12
    tanp = math.tan(G["phi_back"])

    def terms(s, x_load):
        sec = [section(G, si) for si in s]
        m = np.clip(x_load - s, 0, None)  # moment per unit load at s
        if model == "solid":
            EI = np.array([E * q["I_solid"] for q in sec])
            GA = np.array([kap * Gs * q["A_solid"] for q in sec])
            v = np.where(s < x_load, 1.0, 0.0)
            return m, EI, GA, v
        EI = np.array([E * q["I_sand"] for q in sec])
        c = np.array([q["c"] for q in sec])
        solid = np.array([q["solid"] for q in sec])
        lr = c / math.cos(math.radians(G["beta"]))
        flex = p ** 2 / (24 * E * Ic) + p * lr / (12 * E * Iv)  # Vierendeel shear flexibility per length
        GA = np.where(solid, kap * Gs * np.array([q["A_solid"] for q in sec]), 1 / flex)
        v = np.where(s < x_load, 1.0, 0.0) - np.where(solid, 0.0, m * tanp / c)
        return m, EI, GA, v

    s = np.linspace(0, min(a, L - 1e-6), npts)
    mA, EI, GA, vA = terms(s, a)
    dA = np.trapezoid(mA * mA / EI + vA * vA / GA, s)
    mT, _, _, vT = terms(s, L)
    dT = np.trapezoid(mA * mT / EI + vA * vT / GA, s)
    return dA, dT


# ------------------------------------------------------------------ stresses
def tpu_root_stress(G, F, a):
    """Root-panel stresses in the TPU for lateral load F at distance a (Fin Ray truss model)."""
    sec = section(G, 0.0)
    p = G["L"] / (G["n"] + 1)
    M = F * a
    Vweb = max(F - M * math.tan(G["phi_back"]) / sec["c"], 0.0)
    sig_chord = M / (sec["c"] * G["t"] * G["D"])  # axial, front flank
    sig_chord_b = 6 * (Vweb / 2) * (p / 2) / (G["D"] * G["t"] ** 2)  # chord local (Vierendeel) bending
    sig_rib = 6 * (Vweb * p / 2) / (G["D"] * G["tr"] ** 2)  # first rib end moment
    sig_solid = 6 * M / (G["D"] * G["W"] ** 2)
    return dict(M_root_Nmm=M, V_web_N=Vweb, sigma_chord_axial=sig_chord,
                sigma_chord_axial_plus_bending=sig_chord + sig_chord_b,
                sigma_rib_bending=sig_rib, sigma_solid_wedge_root=sig_solid)


def back_flank_buckling(G, E, a):
    """Back-flank panels between rib nodes as Euler columns under the chord compression from a
    lateral load at s = a (load toward -x puts the back flank in compression).  Chord force per N
    of load: N(s) = (a - s) / c(s) / cos(phi_back), c = flank centre distance.  Panel ends are the
    rib-centreline intersections with the back flank; pinned (K = 1) is the lower bound, fixed
    (K = 0.5) the upper.  Returns the first-panel buckling load F_cr (N) for both, and the panel."""
    xf, y0, L, W, tw = G["xf"], G["y0"], G["L"], G["W"], G.get("tip_width", 0.0)
    be = math.radians(G["beta"])
    nx, ny, N = math.sin(be), math.cos(be), G["n"]
    cs = [nx * xf + ny * (y0 - i * L / (N + 1)) for i in range(1, N + 1)]
    # back flank P(tau) = (xf - W + (W - tw) tau, y0 - L tau), tau in [0, 1]
    taus = [0.0]
    for c in cs:
        den = nx * (W - tw) - ny * L
        tau = (c - nx * (xf - W) - ny * y0) / den
        if 0 < tau < 1:
            taus.append(tau)
    taus = sorted(taus)
    phi = math.atan((W - tw) / L)
    I = G["D"] * G["t"] ** 3 / 12
    best = None
    for t0, t1 in zip(taus[:-1], taus[1:]):
        s0, s1 = L * t0, L * t1
        if s0 >= a:
            break
        lp = (s1 - s0) / math.cos(phi)
        s_m = 0.5 * (s0 + min(s1, a))
        w = W - (W - tw) * s_m / L
        c = max(w - G["t"] / 2 - G["t"] / math.cos(phi) / 2, 1e-6)
        n_per_F = max(a - s_m, 0.0) / c / math.cos(phi)
        if n_per_F <= 0:
            continue
        P_pin = math.pi ** 2 * E * I / lp ** 2
        cand = dict(s0_mm=s0, s1_mm=s1, panel_len_mm=lp, chord_force_per_N=n_per_F,
                    P_cr_pinned_N=P_pin, F_cr_pinned_N=P_pin / n_per_F, F_cr_fixed_N=4 * P_pin / n_per_F)
        if best is None or cand["F_cr_pinned_N"] < best["F_cr_pinned_N"]:
            best = cand
    return best


def pad_local_stress(G, F, patch):
    """Front flank between two ribs as a fixed-fixed strip under the patch pressure."""
    p = G["L"] / (G["n"] + 1)
    q = F / patch  # N/mm along the face
    lq = min(patch, p)
    M = q * lq * p / 12 if patch >= p else q * lq * p / 8
    return 6 * M / (G["D"] * G["t"] ** 2)


def pla_stresses(G, F, s_contact):
    """PLA knuckle arm (z-thickness = gear face width b) and root-plate overhang."""
    rc = -G["y0"] + s_contact
    b = G["b"]
    M_top = F * (rc - G["h_arm_top"])
    S_top = b * G["w_arm"] ** 2 / 6
    M_bot = F * (rc - G["R0"])
    S_bot = b * G["W"] ** 2 / 6
    sec = section(G, 0.0)
    M_f = F * s_contact
    n = M_f / (sec["c"] * G["D"])
    c_z = (G["D"] - b) / 2
    b_eff = G["W"] / 2  # [A] half the plate width carries each flank line
    M_ov = n * c_z ** 2 / 2
    sig_ov = 6 * M_ov / (b_eff * G["t_root"] ** 2)
    return dict(M_arm_top_Nmm=M_top, sigma_arm_top=M_top / S_top,
                sigma_arm_top_Kt=M_top / S_top * INPUTS["PLA"]["Kt_arm_root"],
                M_arm_bottom_Nmm=M_bot, sigma_arm_bottom=M_bot / S_bot,
                sigma_root_plate_overhang=sig_ov, overhang_mm=c_z)


def arm_compliance(G, s_contact, npts=2000):
    """PLA arm + root plate as a tapered cantilever from the hub (y = -h_top) to y0,
    finger rigid below; lateral deflection at the contact point per N (mm/N)."""
    E = INPUTS["PLA"]["E_MPa"]
    rc = -G["y0"] + s_contact
    y = np.linspace(G["h_arm_top"], -G["y0"], npts)
    w = np.where(y <= G["R0"], G["w_arm"] + (G["W"] - G["w_arm"]) * (y - G["h_arm_top"]) / (G["R0"] - G["h_arm_top"]), G["W"])
    zdepth = np.where(y <= G["R0"], G["b"], G["D"])
    I = zdepth * w ** 3 / 12
    m = rc - y
    return float(np.trapezoid(m * m / (E * I), y))


def mesh_compliance(G, s_contact):
    """VDI 2736 tooth-pair deflection (gears.md s5) seen at finger B's contact point, mm/N."""
    E = INPUTS["PLA"]["E_MPa"]
    rc = -G["y0"] + s_contact
    Ft_per_N = rc / G["r"]
    lam = 7.5 * (Ft_per_N / G["b"]) * (2 / E)
    return lam * rc / G["r"]


# ------------------------------------------------------------------ drive / kinematics
def force_from_torque(T_Nmm, rc, convention=None):
    """Per-finger pad force from servo torque T.  r_c is invariant with jaw angle (DESIGN-BASIS D2).
    design_basis: T = 2 F r_c / eta (eta on the whole path, DESIGN-BASIS section 2) -- governing.
    lane:         T = F r_c (1 + 1/eta) (loss on finger B only) -- less conservative, reported for comparison."""
    eta = INPUTS["drive"]["eta_mesh_pivot"]
    conv = convention or INPUTS["drive"]["torque_convention"]
    if conv == "design_basis":
        return T_Nmm * eta / (2 * rc)
    return T_Nmm / (rc * (1 + 1 / eta))


def torque_for_force(F, rc, convention=None):
    return F / force_from_torque(1.0, rc, convention)


def backlash_lag_mm(G, rc, convention=None):
    """Pad lag of finger B behind A [A]: 'calibrated' (R21 CALIBRATE, theta 0 after closing, lag 0)
    or 'centred' (theta 0 = centred mesh, lag = jt/2 at the pitch circle, scaled to r_c)."""
    conv = convention or INPUTS["drive"]["lag_convention"]
    return 0.0 if conv == "calibrated" else INPUTS["drive"]["backlash_jt_mm"] / 2 * rc / G["r"]


def overtravel_deg(G, F, k_pair, rc, lag=None):
    """Commanded jaw angle below theta 0 (pads 1 mm apart) to squeeze one ply to force F."""
    lag = backlash_lag_mm(G, rc) if lag is None else lag
    closure = F / k_pair + G["gap"] - INPUTS["grip"]["cloth_thickness_mm"] + lag
    return -math.degrees(closure / (2 * rc))


def analyse(G, label):
    T, D = INPUTS["TPU"], INPUTS["PLA"]
    C = INPUTS["contact"]
    E_set = {"Z_56": T["E_low_MPa"], "XY_67": T["E_nominal_MPa"], **{f"sens_{v:g}": v for v in T["E_sensitivity_MPa"].values()}}
    out = {"label": label, "geometry": {k: v for k, v in G.items()}}
    out["geometry"]["phi_back_deg"] = math.degrees(G["phi_back"])
    out["geometry"]["finger_area_mm2"] = finger_area(G)
    out["geometry"]["finger_mass_g"] = finger_area(G) * G["D"] * G["rho_tpu"] / 1000
    stiff = {}
    for lc, a in (("mid", G["s_mid"]), ("tip", G["s_tip"])):
        for model in ("solid", "finray"):
            for en, E in E_set.items():
                dA, dT = compliance(G, E, T["nu"], a, model)
                stiff[f"{lc}_{model}_{en}"] = dict(a_mm=a, E_MPa=E, compliance_load_mm_per_N=dA,
                                                   k_load_N_per_mm=1 / dA, tip_per_N_mm=dT)
    out["stiffness"] = stiff
    st = {}
    for Fn, F in (("LC1_target", INPUTS["grip"]["target_N"]), ("LC2_cap", INPUTS["grip"]["cap_N"])):
        for lc, a, patch in (("mid", G["s_mid"], C["patch_mid_mm"]), ("tip", G["s_tip"], C["patch_tip_mm"])):
            st[f"{Fn}_{lc}"] = dict(F_N=F, tpu=tpu_root_stress(G, F, a), tpu_pad_local=pad_local_stress(G, F, patch),
                                    pla=pla_stresses(G, F, a))
    out["stresses_MPa"] = st
    out["back_flank_buckling_tip_load"] = {en: back_flank_buckling(G, E, G["s_tip"]) for en, E in E_set.items()}
    out["allowables_MPa"] = dict(tpu_stress_cap=T["stress_allow_cap_MPa"], tpu_strain_LC1=T["strain_limit_LC1"],
                                 pla_LC1=D["allow_LC1_MPa"], pla_LC2=D["allow_LC2_MPa"])
    ser = {}
    for lc, a in (("mid", G["s_mid"]), ("tip", G["s_tip"])):
        rc = -G["y0"] + a
        c_arm, c_mesh = arm_compliance(G, a), mesh_compliance(G, a)
        for en in E_set:
            c_f = stiff[f"{lc}_finray_{en}"]["compliance_load_mm_per_N"]
            k_pair = 1 / (2 * c_f + 2 * c_arm + c_mesh)
            ser[f"{lc}_{en}"] = dict(c_finger=c_f, c_arm=c_arm, c_mesh_B=c_mesh,
                                     arm_plus_mesh_fraction_of_pair=(2 * c_arm + c_mesh) / (2 * c_f + 2 * c_arm + c_mesh),
                                     k_pair_N_per_mm=k_pair,
                                     theta_target_deg=overtravel_deg(G, INPUTS["grip"]["target_N"], k_pair, rc),
                                     theta_cap_deg=overtravel_deg(G, INPUTS["grip"]["cap_N"], k_pair, rc),
                                     dF_dtheta_N_per_deg=k_pair * 2 * rc * math.pi / 180)
    out["series_and_overtravel_truss_model"] = ser
    rc = G["rc_tip"]
    act = {}
    hf = INPUTS["drive"]["hold_fraction"]
    for name, kgcm in INPUTS["actuators"].items():
        Tst = kgcm * KGCM_TO_NMM
        act[name] = dict(stall_Nmm=Tst,
                         F_tip_hold_N_design_basis=force_from_torque(Tst * hf, rc, "design_basis"),
                         F_tip_hold_N_lane_less_conservative=force_from_torque(Tst * hf, rc, "lane"),
                         F_mid_hold_N_design_basis=force_from_torque(Tst * hf, -G["y0"] + G["s_mid"], "design_basis"),
                         F_tip_stall_N_design_basis=force_from_torque(Tst, rc, "design_basis"))
    out["actuator_force_hold_fraction"] = hf
    out["actuator_force"] = act
    req = {}
    for Fn, F in (("LC1_target", INPUTS["grip"]["target_N"]), ("LC2_cap", INPUTS["grip"]["cap_N"])):
        for conv in ("design_basis", "lane"):
            Treq = torque_for_force(F, rc, conv)
            req[f"tip_{Fn}_{conv}"] = dict(T_Nmm=Treq, T_kgcm=Treq / KGCM_TO_NMM, stall_needed_kgcm=Treq / KGCM_TO_NMM / hf)
    out["torque_required_tip"] = req
    return out


_MISSING = object()


def differing_keys(expected, actual, path=""):
    """Return paths of leaves that differ between a stored result and a fresh one."""
    if expected is _MISSING or actual is _MISSING:
        return [path]
    if isinstance(expected, dict) and isinstance(actual, dict):
        return [key for name in sorted(expected.keys() | actual.keys())
                for key in differing_keys(expected.get(name, _MISSING), actual.get(name, _MISSING),
                                          f"{path}.{name}" if path else name)]
    if isinstance(expected, list) and isinstance(actual, list):
        return [key for index in range(max(len(expected), len(actual)))
                for key in differing_keys(expected[index] if index < len(expected) else _MISSING,
                                          actual[index] if index < len(actual) else _MISSING,
                                          f"{path}[{index}]")]
    return [path] if expected != actual else []


def main(check=False):
    P = load_params()
    used = apply_overrides(P)
    out = {"inputs": INPUTS, "overrides_from_params": used,
           "governing": "docs/gripper/DESIGN-BASIS.md (2026-09-22); E_TPU 67 (X-Y) / 56 (Z) MPa [S Ultimaker TDS]",
           "cases": {}}
    Gd = load_geometry(P, design=True)
    Gc = load_geometry(P, design=False)
    out["cases"]["design_L45"] = analyse(Gd, f"design basis: L {Gd['L']:g}, r_c {Gd['rc_tip']:g} mm, CAD section")
    out["cases"]["cad_L60"] = analyse(Gc, f"current CAD: L {Gc['L']:g}, r_c {Gc['rc_tip']:g} mm (reference)")
    out["ejection_limit_deg"] = math.degrees(math.atan(INPUTS["grip"]["mu_pad_cloth"]))
    result_path = RESULTS / "finger_beam.json"
    serialized = json.dumps(out, indent=1, default=float, allow_nan=False)
    if check:
        try:
            committed = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"STALE: {result_path.name}: {exc}")
            return 1
        differences = differing_keys(committed, json.loads(serialized))
        if differences:
            print(f"STALE: {result_path.name} differs at {len(differences)} keys:")
            for key in differences:
                print(f"  {key}")
            return 1
        print(f"FRESH: {result_path.name} matches recomputed values")
        return 0
    RESULTS.mkdir(parents=True, exist_ok=True)
    result_path.write_text(serialized, encoding="utf-8")
    plot(Gd, Gc, out)
    summary(out)
    return out


def plot(Gd, Gc, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIGS.mkdir(parents=True, exist_ok=True)
    T = INPUTS["TPU"]
    g = INPUTS["grip"]
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
    Es = np.linspace(8, 75, 30)
    for G, col in ((Gd, "#c8553d"), (Gc, "#2a6f97")):
        for model, ls in (("solid", "--"), ("finray", "-")):
            k = [1 / compliance(G, E, T["nu"], G["s_tip"], model, npts=800)[0] for E in Es]
            ax[0].plot(Es, k, ls, color=col, label=f"L {G['L']:g}, tip pad s {G['s_tip']:g}, {model}")
    ax[0].axvspan(T["E_low_MPa"], T["E_nominal_MPa"], color="0.85", label="Ultimaker Z-XY band")
    ax[0].axhspan(g["k_tip_min_N_per_mm"], g["k_tip_max_N_per_mm"], color="#2a9d8f", alpha=0.2, label="R12 window")
    ax[0].set_yscale("log")
    ax[0].set_xlabel("TPU 95A modulus E, MPa")
    ax[0].set_ylabel("finger stiffness at tip pad, N/mm")
    ax[0].set_title("Hand-calc stiffness (CAD section)")
    ax[0].legend(fontsize=7)
    names = list(out["cases"]["design_L45"]["actuator_force"].keys())
    x = np.arange(len(names))
    for i, (case, col) in enumerate((("design_L45", "#c8553d"), ("cad_L60", "#2a6f97"))):
        a = out["cases"][case]["actuator_force"]
        ax[1].bar(x + (i - 0.5) * 0.38, [a[n]["F_tip_hold_N_design_basis"] for n in names], 0.38, color=col,
                  label=f"{case}: r_c {out['cases'][case]['geometry']['rc_tip']:g} mm")
    ax[1].axhline(g["target_N"], color="k", ls="--", lw=0.8, label="F_target")
    ax[1].set_xticks(x, [n.split(" (")[0] for n in names], rotation=15, fontsize=7)
    ax[1].set_ylabel("tip-pad force per finger at hold, N")
    ax[1].set_title(f"Hold force, T = 2 F r_c / eta, {INPUTS['drive']['hold_fraction']:.0%} of stall")
    ax[1].legend(fontsize=7)
    F = np.linspace(0, g["cap_N"], 40)
    for en, col in (("Z_56", "#8d99ae"), ("XY_67", "#2b2d42")):
        for case, ls in (("design_L45", "-"), ("cad_L60", "--")):
            s = out["cases"][case]["series_and_overtravel_truss_model"][f"tip_{en}"]
            G = Gd if case == "design_L45" else Gc
            ax[2].plot([overtravel_deg(G, f, s["k_pair_N_per_mm"], G["rc_tip"]) for f in F], F, ls, color=col,
                       label=f"{case} E {en}: k_pair {s['k_pair_N_per_mm']:.2f}")
    ax[2].axhline(g["target_N"], color="k", ls="--", lw=0.8)
    ax[2].axvline(g["theta_min_deg"], color="r", ls=":", lw=0.8, label="theta_min")
    ax[2].set_xlabel("commanded jaw angle theta, deg (0 = pads 1 mm apart)")
    ax[2].set_ylabel("pinch force, N")
    ax[2].set_title("Truss-model pinch of one 0.3 mm ply (tip pad)")
    ax[2].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIGS / "finger_beam.png", dpi=130)
    plt.close(fig)


def summary(out):
    for case, c in out["cases"].items():
        print("==", case, c["label"], "mass g", round(c["geometry"]["finger_mass_g"], 2))
        s = c["stiffness"]
        for k in ("tip_solid_XY_67", "tip_finray_XY_67", "tip_finray_Z_56", "mid_finray_XY_67"):
            print(" ", k, "k N/mm", round(s[k]["k_load_N_per_mm"], 3))
        for k in ("LC1_target_tip", "LC2_cap_tip"):
            v = c["stresses_MPa"][k]
            print(" ", k, {kk: round(vv, 2) for kk, vv in v["tpu"].items()}, {kk: round(vv, 2) for kk, vv in v["pla"].items()})
        for k in ("tip_XY_67", "tip_Z_56"):
            v = c["series_and_overtravel_truss_model"][k]
            print(" ", k, {kk: round(vv, 4) for kk, vv in v.items()})
        for k, v in c["torque_required_tip"].items():
            print(" ", k, {kk: round(vv, 2) for kk, vv in v.items()})
        for k, v in c["actuator_force"].items():
            print(" ", k, {kk: round(vv, 2) for kk, vv in v.items()})
        for k in ("Z_56", "XY_67"):
            v = c["back_flank_buckling_tip_load"][k]
            if v:
                print("  back-flank buckling, tip load,", k, {kk: round(vv, 3) for kk, vv in v.items()})
    print("ejection limit deg", round(out["ejection_limit_deg"], 1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare computed values with the committed JSON without writing")
    args = parser.parse_args()
    result = main(check=args.check)
    if args.check:
        raise SystemExit(result)
