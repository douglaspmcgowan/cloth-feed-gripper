"""Actuation trade: every R7/R8 PWM servo and small gearmotor in actuators.csv, through the existing 1:1 train and
two alternative ratios, with the firmware close/hold model, a sensitivity study, a 2,000-sample Monte Carlo per
configuration and a weighted score with varied weights.

Run from the repository root (about 10 to 25 min, deterministic; --quick is a 200-sample smoke run):
    python analysis/gripper/actuation/actuation_trade.py
Writes analysis/gripper/actuation/results/actuation_trade.json and results/actuation_trade_stdout.txt.
"""
from __future__ import annotations

import io
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model as M  # noqa: E402
import extras as X  # noqa: E402

RES = HERE / "results"
QUICK = "--quick" in sys.argv  # smoke run (200 samples, results not written over the committed ones)
N_MC = 200 if QUICK else 2000
SEED = 20261011
CAPS = (10.0, 8.0)          # R15 as written / proposed (N)
TIMES = (0.5, 0.75)         # R19 as written / proposed (s)
PROFILES = ("fw", "fast")   # shipped close profile / fastest R19-compliant profile found by profile_search()
PROFILE_PARAMS = {"fw": None, "fast": None}  # "fast" is filled by profile_search()
HOLD_BIAS_SETPOINT_N = 6.0  # N: regulated hold force of the firmware (5 N setpoint + F_HOLD_BIAS_N 1.0 N, force_ctrl.cpp spReg)
SEL = ("A32@1:1", "A34@1:1", "A19@1:1", "A17@1:1", "A17@1.5:1")   # the options the note discusses
ORDER_TODAY, WAIT, FALLBACK = "A17@1.5:1", "A32@1:1", "A19@1:1"
F_HOLD_TOL = 0.1            # N: simulated hold mean may sit this far under 5.0 N and still count [A, FSR span]
GATE_P = 0.9                # recommendation gate on P(R14 and R16) at both requirement values [A]; 0.8 / 0.95 reported
V_TOUCH3_MAX = 21.5         # deg/s: jaw speed allowed at touch + 3 deg, the shipped profile's own value (controls.md 5.1)
SEARCH = {"v_fast": (120.0, 180.0, 240.0), "slow_zone": (3.0, 4.0, 5.0, 6.0), "a_dec": (0.0, 1000.0, 2000.0, 4000.0)}
K_CASES = {"R12 min": 0.88, "FEA E56": 2 * 0.523, "FEA E67": 2 * 0.621, "R12 max": 1.63}

WEIGHTS = {  # [A] written down; varied below
    "requirements": 0.30, "cost": 0.10, "mass": 0.15, "envelope": 0.15, "availability": 0.10,
    "interface": 0.10, "noise_life": 0.10,
}
UTIL_RULES = {
    "requirements": "mean of P(R14), P(R15), P(R19) from the Monte Carlo under the requirement set",
    "cost": "($50 - actuator, stage and driver cost) / $40, clipped 0..1",
    "mass": "(1.00 - SO-101 worst-pose hold utilisation) / 0.20, clipped 0..1; > 1.00 fails",
    "envelope": "drop-in 1.0, likely drop-in 0.7-0.8, unverified 0.6, pocket change 0.4, new bay 0.1; -0.2 for a non-25T output",
    "availability": "in stock 1.0, Pololu active/backorder 0.7, listed 0.5, backordered 0.4, UK-only 0.3, sold out 0.1-0.2",
    "interface": "PWM servo 1:1 1.0; PWM servo + stage 0.8 (pulse range and gains change); gearmotor 0.3 (H-bridge, "
                 "encoder, DC branch not yet written)",
    "noise_life": "0.5 x (0.40 - hold fraction of stall) / 0.30 + 0.5 x (gear SF at stall - 1.0) / 0.6, each clipped "
                  "0..1; -0.15 per printed stage; x 0.7 if stall exceeds the gearbox's published limit",
}


class Tee:
    def __init__(self):
        self.buf = io.StringIO()

    def __call__(self, *a):
        s = " ".join(str(x) for x in a)
        print(s)
        self.buf.write(s + "\n")


out = Tee()


def r(x, n=3):
    if x is None:
        return None
    if isinstance(x, (list, tuple)):
        return [r(v, n) for v in x]
    x = float(x)
    return None if not np.isfinite(x) else round(x, n)


# ------------------------------------------------------------------ vector helpers
def stall_vec(c, v):
    """Stall torque at the drive output (N*m) for an array of rail voltages."""
    v = np.asarray(v, float)
    if c["kind"] != "servo":
        return c["T_stall_Nm"] * v / M.V["V_dc_drive"]
    row = c["row"]
    pts = sorted({(M.fnum(row.get(vk)), M.fnum(row.get(tk))) for tk, vk in (("torque_low_kgcm", "torque_low_at_V"),
                                                                          ("torque_mid_kgcm", "torque_mid_at_V"),
                                                                          ("torque_high_kgcm", "torque_high_at_V"))
                  if M.fnum(row.get(vk)) and M.fnum(row.get(tk))})
    xs, ys = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
    y = np.interp(v, xs, ys)
    y = np.where(v < xs[0], ys[0] * np.minimum(1.0, v / xs[0]), y)
    return y * M.KGCM


def w0_vec(c, v):
    v = np.asarray(v, float)
    if c["kind"] != "servo":
        return c["w0_dps"] * v / M.V["V_dc_drive"]
    row = c["row"]
    a, b = M.fnum(row["speed_low_s_per_60deg"]), M.fnum(row["speed_high_s_per_60deg"])
    vl, vh = M.fnum(row["voltage_min_V"]) or 4.8, M.fnum(row["voltage_max_V"]) or 6.0
    if a and b:
        s = a + (b - a) * (np.clip(v, vl, vh) - vl) / max(vh - vl, 1e-9)
    else:
        s = np.full_like(v, a or b)
    return 60.0 / s


def hold_cap(c, Ts_motor):
    """Continuous hold torque at the drive input of the sector pair under the part's hold rule (N*m)."""
    cap_m = c["hold_rule"] * Ts_motor
    if c["gb_limit_Nm"]:
        cap_m = np.minimum(cap_m, c["gb_limit_Nm"])
    return cap_m * c["N"] * c["eta_stage"]


def lanes(c, n, rng=None, nominal=None):
    """Sample (or set) the uncertain inputs for configuration c. nominal: dict of overrides for OAT cases."""
    V = M.V
    if rng is not None:
        Vs = rng.uniform(c["V_rail"] - V["V_rail_tol"], c["V_rail"] + V["V_rail_tol"], n)
        Rw = rng.uniform(*V["R_wire_range"], n)
        sT = rng.uniform(1 - V["unit_spread"], 1 + V["unit_spread"], n)
        sw = rng.uniform(1 - V["unit_spread"], 1 + V["unit_spread"], n)
        claim = rng.uniform(*V["claim_factor_vendor"], n)
        if c.get("evidence", M.evidence(c["row"])) == "vendor claim":
            sT = sT * claim
        Tw = rng.uniform(*V["T_wind_range"], n)
        eta = rng.uniform(*V["eta_link_range"], n)
        es = rng.uniform(*V["stage_eta_range"], (max(c["n_stages"], 1), n)).prod(axis=0) if c["n_stages"] else np.ones(n)
        k = rng.uniform(*V["k_tip_FEA"], n)
        tau = rng.uniform(*V["tau_range"], n)
        ph = rng.integers(0, 20, n)
    else:
        o = nominal or {}
        Vs = np.full(n, c["V_rail"] + o.get("dV", 0.0))
        Rw = np.full(n, o.get("R_wire", float(np.mean(V["R_wire_range"]))))
        sT = np.full(n, o.get("sT", 1.0))
        sw = np.full(n, o.get("sw", 1.0))
        Tw = np.full(n, o.get("T_w", 25.0))
        eta = np.full(n, o.get("eta", V["eta_link"]))
        es = np.full(n, (o.get("eta_stage", V["stage_eta"]) ** c["n_stages"]) if c["n_stages"] else 1.0)
        k = np.full(n, o.get("k", K_CASES["FEA E56"]))
        tau = np.full(n, o.get("tau", M.CFG["SERVO_TAU_S"]))
        ph = np.arange(n) % 20
    cc = dict(c, eta_stage=1.0)
    I_id = M.idle_current(c)
    # rail sag at the hold current (one fixed-point pass)
    Ts0 = stall_vec(c, Vs) * sT * M.derate_T(Tw)
    Ist0 = np.array([M.stall_current(c, v)[0] for v in np.atleast_1d(Vs)])
    Ih = I_id + Ist0 * np.minimum(1.0, M.t_req(M.V["F_hold_N"], eta) / (Ts0 * c["N"] * es))
    Veff = Vs - Ih * Rw
    Ts_cold = stall_vec(c, Veff) * sT          # the R16 rule is written against the datasheet (cold) stall
    Ts = Ts_cold * M.derate_T(Tw)               # what the warm motor can actually push (simulation)
    w0 = w0_vec(c, Veff) * sw
    Ist = Ist0 * Veff / Vs
    del cc
    return {"N": np.full(n, c["N"]), "k_tip": k, "T_stall_motor": Ts, "w0_motor": w0, "eta_stage": es, "tau": tau,
            "eta_link": eta, "tension": np.full(n, M.V["tension_N"]), "I_stall": Ist, "I_idle": np.full(n, I_id),
            "phase": ph, "is_dc": np.full(n, c["kind"] != "servo"), "V_eff": Veff, "T_stall_cold": Ts_cold}


def fw_lanes(c, prof, cap, n):
    w0_jaw = c["w0_dps"] / c["N"]
    d = M.fw_profile(PROFILE_PARAMS[prof], cap, w0_jaw)
    return {k: np.full(n, v) for k, v in d.items()}


def ref_lanes(k, n=20):
    """The rev A fw_sim plant: A17 1:1 at 6.5 V (rev A config.h, rev_a/config.json), no tension, phases 0..19."""
    return {"N": np.ones(n), "k_tip": np.full(n, k), "T_stall_motor": np.full(n, M.CFG["SERVO_STALL_NM"]),
            "w0_motor": np.full(n, M.CFG["SERVO_SPEED_DPS"]), "eta_stage": np.ones(n), "tau": np.full(n, M.CFG["SERVO_TAU_S"]),
            "eta_link": np.full(n, 0.85), "tension": np.zeros(n), "I_stall": np.full(n, M.CFG["SERVO_STALL_A"]),
            "I_idle": np.full(n, M.V["I_idle_fwsim"]), "phase": np.arange(n) % 20, "is_dc": np.zeros(n, bool)}


def profile_search():
    """Grid over the close profile (fast speed, slow-zone length, command deceleration) on the reference servo, every
    finger case and every control-tick phase. Keeps profiles whose jaw speed at touch + 3 deg stays within the
    shipped profile's own value, and returns the one with the shortest worst-finger time to F >= 4.5 N, plus the
    fastest profile with the speed clause dropped."""
    grid = [{"v_fast": v, "slow_zone": z, "a_dec": a} for v in SEARCH["v_fast"] for z in SEARCH["slow_zone"]
            for a in SEARCH["a_dec"]]
    jobs = []
    for gi, g in enumerate(grid):
        for kl, k in K_CASES.items():
            d = ref_lanes(k)
            d.update({kk: np.full(20, vv) for kk, vv in M.fw_profile(g, 10.0).items()})
            jobs.append(((gi, kl), d))
    rows = {}
    for (gi, kl), d, res in run_batch(jobs, ms=1200):
        t45 = np.nan_to_num(res["t_45"], nan=9.0)
        row = rows.setdefault(gi, dict(grid[gi], t45_worst=0.0, contact_worst=0.0, v3_worst=0.0, F_peak=0.0))
        row["t45_worst"] = max(row["t45_worst"], float(t45.mean()))
        row["contact_worst"] = max(row["contact_worst"], float(np.nan_to_num(res["t_contact"], nan=9.0).mean()))
        row["v3_worst"] = max(row["v3_worst"], float(np.nanmax(res["v_jaw_touch3"])))
        row["F_peak"] = max(row["F_peak"], float(res["F_peak"].max()))
    table = [dict({k: r(v) for k, v in x.items()}, compliant=x["v3_worst"] <= V_TOUCH3_MAX) for x in rows.values()]
    ok = [x for x in table if x["compliant"]]
    best = min(ok, key=lambda x: x["t45_worst"])
    free = min(table, key=lambda x: x["t45_worst"])
    return best, free, table


def run_batch(jobs, ms=2000):
    """jobs: list of (key, lane dict). Concatenate, simulate once, split back."""
    keys = sorted({k for _, d in jobs for k in d})
    sizes = [len(d["N"]) for _, d in jobs]
    p = {k: np.concatenate([d[k] if k in d else np.zeros(len(d["N"])) for _, d in jobs]) for k in keys if k != "V_eff"}
    res = M.sim(p, ms=ms)
    outl, i = [], 0
    for (key, d), s in zip(jobs, sizes):
        outl.append((key, d, {k: v[i:i + s] for k, v in res.items()}))
        i += s
    return outl


def static(c):
    V = M.V
    vlo, vhi = c["V_rail"] - V["V_rail_tol"], c["V_rail"] + V["V_rail_tol"]
    Ts_lo, Ts_hi = float(stall_vec(c, vlo)), float(stall_vec(c, vhi))
    Treq = M.t_req(V["F_hold_N"], V["eta_link"])
    cap = float(hold_cap(c, Ts_lo))
    cap25 = float(hold_cap(dict(c, hold_rule=min(c["hold_rule"], V["hold_frac_vendor_pololu"])), Ts_lo))
    T_mesh = Ts_hi * c["N"] * c["eta_stage"]
    sf = float(M.gear_sf(T_mesh))
    jam = T_mesh * V["jam_factor"]
    F_stall = (T_mesh * V["eta_link"] * 1000 - V["tension_N"] * V["x_f_mm"]) / (2 * M.R_C)
    I_st, I_tag = M.stall_current(c, c["V_rail"])
    Ts_nom = float(stall_vec(c, c["V_rail"]))
    Tjaw = Ts_nom * c["N"] * c["eta_stage"]
    I_hold = M.idle_current(c) + I_st * min(1.0, Treq / Tjaw)
    lo_us = 1500 + c["N"] * M.US_PER_DEG * M.CFG["JAW_MIN_DEG"]
    hi_us = 1500 + c["N"] * M.US_PER_DEG * M.CFG["JAW_OPEN_DEG"]
    return {
        "V_rail_V": c["V_rail"], "V_band_V": [r(vlo, 2), r(vhi, 2)],
        "stall_drive_Nm_at_V_lo": r(Ts_lo), "stall_drive_Nm_at_V_hi": r(Ts_hi),
        "T_hold_req_Nm": r(Treq), "hold_capacity_Nm": r(cap), "hold_margin": r(cap / Treq),
        "hold_margin_25pct_rule": r(cap25 / Treq), "hold_fraction_of_stall": r(Treq / (Ts_lo * c["N"] * c["eta_stage"])),
        "T_mesh_LC3_Nm": r(T_mesh), "gear_SF_LC3": r(sf), "T_jam_Nm": r(jam), "gear_SF_jam": r(float(M.gear_sf(jam))),
        "gearbox_overload": bool(c["gb_limit_Nm"] and Ts_hi > c["gb_limit_Nm"]),
        "pad_force_at_stall_N": r(F_stall, 2), "stall_exceeds_cap_10N": F_stall > 10.0, "stall_exceeds_cap_8N": F_stall > 8.0,
        "w0_jaw_dps": r(c["w0_dps"] / c["N"], 1), "I_stall_A": r(I_st, 2), "I_stall_tag": I_tag,
        "I_stall_sizing_A": r(M.stall_current_sizing(c, vhi), 2), "I_hold_A": r(I_hold), "P_hold_W": r(I_hold * c["V_rail"], 2),
        "pulse_range_us": [r(lo_us, 0), r(hi_us, 0)],
        "pulse_inside_1200_1900": bool(lo_us >= M.CFG["SERVO_US_LIMIT_MIN"] and hi_us <= M.CFG["SERVO_US_LIMIT_MAX"]),
        "mass_total_g": r(c["mass_total_g"], 1), "stage_mass_g": r(c["stage_mass_g"], 1),
        "arm_util_C001_7p4V": r(M.arm_util(c["mass_total_g"])),
    }


def nominal_jobs(c):
    jobs = []
    for kl, k in K_CASES.items():
        for prof in PROFILES:
            for cap in CAPS:
                d = lanes(c, 20, nominal={"k": k})
                d.update(fw_lanes(c, prof, cap, 20))
                jobs.append(((c["cfg"], "nom", kl, prof, cap), d))
    return jobs


OAT = {  # name -> overrides (sensitivity study, one at a time, FEA E56 finger, 10 N cap, shipped profile)
    "base": {},
    "rail -0.15 V": {"dV": -0.15}, "rail +0.15 V": {"dV": 0.15}, "rail -0.5 V": {"dV": -0.5},
    "wire 0.10 ohm": {"R_wire": 0.10},
    "eta_link 0.70": {"eta": 0.70}, "eta_link 0.95": {"eta": 0.95},
    "eta_stage 0.85": {"eta_stage": 0.85}, "eta_stage 0.95": {"eta_stage": 0.95},
    "stall -15 %": {"sT": 0.85}, "stall -20 %": {"sT": 0.80}, "stall -30 %": {"sT": 0.70}, "stall +15 %": {"sT": 1.15}, "speed -15 %": {"sw": 0.85}, "speed +15 %": {"sw": 1.15},
    "winding 80 C": {"T_w": 80.0}, "winding 120 C": {"T_w": 120.0},
    "tau 30 ms": {"tau": 0.030}, "tau 60 ms": {"tau": 0.060},
    "k R12 min": {"k": 0.88}, "k R12 max": {"k": 1.63},
}


def oat_jobs(c):
    jobs = []
    for name, o in OAT.items():
        d = lanes(c, 20, nominal=o)
        d.update(fw_lanes(c, "fw", 10.0, 20))
        jobs.append(((c["cfg"], "oat", name), d))
    return jobs


def mc_jobs(c, idx):
    rng = np.random.default_rng(SEED + idx)
    base = lanes(c, N_MC, rng=rng)
    jobs = []
    for prof in PROFILES:
        for cap in CAPS:
            d = dict(base)
            d.update(fw_lanes(c, prof, cap, N_MC))
            jobs.append(((c["cfg"], "mc", prof, cap), d))
    return jobs


def pct(a, q):
    a = a[np.isfinite(a)]
    return r(np.percentile(a, q)) if len(a) else None


def passes(c, d, res):
    """Per-sample pass flags. R14: the jaw reaches and holds >= 5.0 N (minus F_HOLD_TOL) with no over-force fault.
    R16: the hold torque is within the part's hold rule (40 % of stall, 25 % for Pololu gearmotors) at the sampled
    datasheet (cold) stall, unit spread, efficiency and rail; winding heat acts on the simulated force instead."""
    cap = hold_cap(dict(c, eta_stage=1.0), d["T_stall_cold"]) * d["eta_stage"]
    need = M.t_req(M.V["F_hold_N"], d["eta_link"])
    r14 = (res["F_final"] >= M.V["F_hold_N"] - F_HOLD_TOL) & ~res["fault"]
    return r14, cap >= need


def main():
    best, free, table = profile_search()
    PROFILE_PARAMS["fast"] = {k: best[k] for k in ("v_fast", "slow_zone", "a_dec")}
    out("close-profile search on the reference servo (A17 1:1, fw_sim plant), worst finger of four:")
    out(f"  shipped  v_fast 120 zone 6 step: " + str(next({k: x[k] for k in ("t45_worst", "contact_worst", "v3_worst")}
                                                       for x in table if x["v_fast"] == 120 and x["slow_zone"] == 6
                                                       and x["a_dec"] == 0)))
    out(f"  fastest with jaw <= {V_TOUCH3_MAX} deg/s at touch + 3 deg: {best}")
    out(f"  fastest with that clause dropped: {free}")

    configs, screened = M.build_configs()
    out(f"\nactuation trade: {len(configs)} configurations from {len({c['id'] for c in configs})} parts; "
        f"{len(screened)} rows screened out")
    for s in screened:
        out(f"  screened {s['id']:4s} {s['model'][:48]:48s} {'; '.join(s['reasons'])}")
    for c in configs:
        c["static"] = static(c)

    # ---------------- nominal + OAT sensitivity (one batch)
    jobs = [j for c in configs for j in nominal_jobs(c) + oat_jobs(c)]
    nom = {key: (d, res) for key, d, res in run_batch(jobs)}

    def mean_metrics(c, d, res):
        need = M.t_req(M.V["F_hold_N"], d["eta_link"])
        hm = hold_cap(dict(c, eta_stage=1.0), d["T_stall_cold"]) * d["eta_stage"] / need
        hot = need / (d["T_stall_motor"] * d["N"] * d["eta_stage"])
        t45 = res["t_45"]
        return {"t_contact_s": r(np.nanmean(res["t_contact"])) if np.isfinite(res["t_contact"]).any() else None,
                "t_close_F45_s": r(np.nanmean(t45)) if np.isfinite(t45).all() else None,
                "t_hold_s": r(np.nanmean(res["t_hold"])) if np.isfinite(res["t_hold"]).all() else None,
                "F_peak_N": r(res["F_peak"].max(), 2), "F_hold_N": r(res["F_final"].mean(), 2),
                "I_hold_A": r(res["I_hold"].mean()),
                "v_jaw_touch3_dps": r(np.nanmax(res["v_jaw_touch3"]), 1) if np.isfinite(res["v_jaw_touch3"]).any() else None,
                "fault": bool(res["fault"].any()), "hold_margin": r(float(np.mean(hm))),
                "hold_fraction_of_warm_stall": r(float(np.mean(hot)))}

    for c in configs:
        c["nominal"] = {f"{kl} | {prof} | cap {cap:g} N": mean_metrics(c, *nom[(c["cfg"], "nom", kl, prof, cap)])
                        for kl in K_CASES for prof in PROFILES for cap in CAPS}
        c["sensitivity"] = {name: mean_metrics(c, *nom[(c["cfg"], "oat", name)]) for name in OAT}

    # ---------------- Monte Carlo, in chunks of configurations
    chunk = 6
    for i0 in range(0, len(configs), chunk):
        part = configs[i0:i0 + chunk]
        jobs = [j for i, c in enumerate(part) for j in mc_jobs(c, i0 + i)]
        res_all = {key: (d, res) for key, d, res in run_batch(jobs)}
        for c in part:
            mc = {}
            for prof in PROFILES:
                for cap in CAPS:
                    d, res = res_all[(c["cfg"], "mc", prof, cap)]
                    p14, p16 = passes(c, d, res)
                    tag = f"{prof}_cap{cap:g}"
                    mc[f"P_sim_force_{tag}"] = r(p14.mean())
                    mc[f"P_R16_{tag}"] = r(p16.mean())
                    mc[f"P_R16_sim_force_{tag}"] = r((p14 & p16).mean())
                    mc[f"P_R15_{tag}"] = r((res["F_peak"] <= cap).mean())
                    for tl in TIMES:
                        mc[f"P_R19_{tl:g}s_{tag}"] = r((np.nan_to_num(res["t_45"], nan=9.0) <= tl).mean())
                        mc[f"P_contact_{tl:g}s_{tag}"] = r((np.nan_to_num(res["t_contact"], nan=9.0) <= tl).mean())
                    mc[f"t_close_p50_{tag}"] = pct(res["t_45"], 50)
                    mc[f"t_close_p95_{tag}"] = pct(res["t_45"], 95)
                    mc[f"F_peak_p99_{tag}"] = pct(res["F_peak"], 99)
                    mc[f"F_peak_max_{tag}"] = r(res["F_peak"].max(), 2)
                    mc[f"I_hold_p50_{tag}"] = pct(res["I_hold"], 50)
                    mc[f"I_hold_p95_{tag}"] = pct(res["I_hold"], 95)
                    mc[f"fault_rate_{tag}"] = r(res["fault"].mean())
            d, res = res_all[(c["cfg"], "mc", "fw", 10.0)]
            hm = hold_cap(dict(c, eta_stage=1.0), d["T_stall_cold"]) * d["eta_stage"] / M.t_req(M.V["F_hold_N"], d["eta_link"])
            mc["hold_margin_p05"] = pct(hm, 5)
            mc["hold_margin_p50"] = pct(hm, 50)
            # hold setpoint 6 N (firmware study's 1.0 N hold bias): torque rule and current at the higher setpoint
            need6 = M.t_req(HOLD_BIAS_SETPOINT_N, d["eta_link"])
            cap_ = hold_cap(dict(c, eta_stage=1.0), d["T_stall_cold"]) * d["eta_stage"]
            mc["hold_margin_6N_p50"] = pct(cap_ / need6, 50)
            mc["P_R16_hold6N"] = r((cap_ >= need6).mean())
            # The simulation regulates setpoint + F_HOLD_BIAS_N (model.sim), so its hold current is already the 6 N
            # one; scale only when the firmware has no hold bias (the pre-PR-20 model scaled 5 N currents by ~1.19).
            ratio6 = 1.0 if M.CFG.get("F_HOLD_BIAS_N", 0.0) else \
                M.t_req(HOLD_BIAS_SETPOINT_N, M.V["eta_link"]) / M.t_req(M.V["F_hold_N"], M.V["eta_link"])
            mc["I_hold_p50_hold6N_scaled"] = r(mc["I_hold_p50_fw_cap10"] * ratio6)
            mc["I_hold_p95_hold6N_scaled"] = r(mc["I_hold_p95_fw_cap10"] * ratio6)
            mc["n"] = N_MC
            c["mc"] = mc
            # requirement sets: as written = 10 N, 0.5 s with the fastest compliant profile; proposed = 8 N, 0.75 s, shipped
            c["req_sets"] = {
                "as_written": {"P_R16_sim_force": mc["P_R16_sim_force_fast_cap10"], "P_R15": mc["P_R15_fast_cap10"],
                               "P_R19": mc["P_R19_0.5s_fast_cap10"], "profile": "fast", "cap_N": 10, "t_s": 0.5},
                "proposed": {"P_R16_sim_force": mc["P_R16_sim_force_fw_cap8"], "P_R15": mc["P_R15_fw_cap8"],
                             "P_R19": mc["P_R19_0.75s_fw_cap8"], "profile": "fw", "cap_N": 8, "t_s": 0.75},
            }
        out(f"  MC done {i0 + len(part)}/{len(configs)}")

    # ---------------- utilities and scores
    for c in configs:
        s = c["static"]
        life = 0.5 * np.clip((0.40 - s["hold_fraction_of_stall"]) / 0.30, 0, 1) + 0.5 * np.clip((s["gear_SF_LC3"] - 1.0) / 0.6, 0, 1)
        life = max(0.0, life - 0.15 * c["n_stages"]) * (0.7 if s["gearbox_overload"] else 1.0)
        iface = 1.0 if (c["kind"] == "servo" and c["N"] == 1.0) else (0.8 if c["kind"] == "servo" else 0.3)
        base_u = {"cost": float(np.clip((50 - c["price_total"]) / 40, 0, 1)),
                  "mass": float(np.clip((1.0 - s["arm_util_C001_7p4V"]) / 0.20, 0, 1)),
                  "envelope": float(max(0.0, c["u_envelope"])), "availability": c["avail"], "interface": iface,
                  "noise_life": float(life)}
        c["utilities"] = {}
        for rs, q in c["req_sets"].items():
            u = dict(base_u, requirements=float(np.mean([q["P_R16_sim_force"], q["P_R15"], q["P_R19"]])))
            c["utilities"][rs] = {k: r(v) for k, v in u.items()}
        c["arm"] = X.arm_gate(c)
        c["gates"] = gates(c, GATE_P)
        c["eligible"] = all(c["gates"].values())
        c["eligible_clear"] = c["eligible"] and c["arm"]["status"] == "pass"

    ranking, stability = {}, {}
    rng = np.random.default_rng(SEED)
    for rs in ("as_written", "proposed"):
        sc = scores(configs, WEIGHTS, rs)
        elig = [c["cfg"] for c in configs if c["eligible"]]
        order = sorted(sc, key=lambda k: (-sc[k], k))
        ranking[rs] = [{"cfg": k, "score": r(sc[k]), "eligible": k in elig} for k in order]
        best_c = top(elig, sc)
        oat = {}
        for crit in WEIGHTS:
            for f in (0.5, 1.5):
                w = dict(WEIGHTS)
                w[crit] *= f
                s2 = scores(configs, w, rs)
                oat[f"{crit} x{f:g}"] = top(elig, s2)
        wins, rec_wins = {}, {}
        evid = {c["cfg"]: c["evidence"] for c in configs}
        avail = {c["cfg"]: c["avail"] for c in configs}
        for _ in range(4000):
            w = {k: v * rng.uniform(0.5, 1.5) for k, v in WEIGHTS.items()}
            s2 = scores(configs, w, rs)
            b = top(elig, s2)
            wins[b] = wins.get(b, 0) + 1
            rl = [{"cfg": k, "score": s2[k], "eligible": True} for k in sorted(elig, key=lambda k: (-s2[k], k))]
            tp = tie_pick(rl, evid, avail)
            rec_wins[tp] = rec_wins.get(tp, 0) + 1
        gate_alt = {}
        for g in (0.8, 0.95):
            el = [c["cfg"] for c in configs if all(gates(c, g).values())]
            gate_alt[f"gate {g:g}"] = top(el, sc)
        no_gate = top(sc, sc)
        stability[rs] = {"winner": best_c, "oat_winners": oat,
                         "oat_changes": {k: v for k, v in oat.items() if v != best_c},
                         "mc_weights_win_share": {str(k): r(v / 4000) for k, v in sorted(wins.items(), key=lambda kv: (-kv[1], str(kv[0])))},
                         "mc_weights_recommendation_share": {str(k): r(v / 4000) for k, v in
                                                             sorted(rec_wins.items(), key=lambda kv: (-kv[1], str(kv[0])))},
                         "n_weight_samples": 4000, "winner_at_other_gates": gate_alt,
                         "top_score_without_gates": no_gate}

    # ---------------- validation against the shipped firmware simulation (A17 1:1, no tension, fw_sim plant)
    fw = json.loads(M.FW_JSON.read_text(encoding="utf-8"))
    labs = {"R12 min": "0.88 R12 min", "FEA E56": "1.05 FEA E56+D7", "FEA E67": "1.24 FEA E67+D7", "R12 max": "1.63 R12 max"}
    vjobs = []
    for kl, k in K_CASES.items():
        d = ref_lanes(k)
        d.update({kk: np.full(20, vv) for kk, vv in M.fw_profile().items()})
        vjobs.append((kl, d))
    validation = {}
    for kl, d, res in run_batch(vjobs, ms=1500):
        ref = fw["cases"][labs[kl]]
        validation[kl] = {"model": {"c0_deg": r(res["c0"].mean()), "t_contact_s": r(np.nanmean(res["t_contact"])),
                                    "t_F45_s": r(np.nanmean(res["t_45"])), "F_peak_N": r(res["F_peak"].mean(), 2),
                                    "F_hold_N": r(res["F_final"].mean(), 2)},
                          "fw_sim": {"c0_deg": r(ref["c0_deg"]), "t_contact_s": r(ref["t_contact_s"]), "t_F45_s": r(ref["t_F90_s"]),
                                     "F_peak_N": r(ref["F_max_N"], 2), "F_hold_N": r(ref["F_hold_mean_N"], 2)}}

    rec = recommend(configs, ranking, stability)
    studies = extra_studies(configs)
    clear = {c["cfg"] for c in configs if c["eligible_clear"]}
    rl = [dict(x, eligible=x["cfg"] in clear) for x in ranking["proposed"]]
    rec["winner_if_marginal_excluded"] = tie_pick(rl, {c["cfg"]: c["evidence"] for c in configs},
                                                  {c["cfg"]: c["avail"] for c in configs})
    studies["decision"] = decision(configs)
    extra = {**studies, "profile_search": {"best_compliant": best, "fastest_without_speed_clause": free, "table": table,
                                "speed_clause_dps": V_TOUCH3_MAX},
             "cap8_stiffness_floor": cap8_floor()}
    write(configs, screened, ranking, stability, validation, rec, extra)


# ------------------------------------------------------------------ review follow-up studies
DEFINITIONS = {
    "P_sim_force": "Share of samples whose simulated settled pad force is at least 4.9 N with no over-force trip. The "
                   "sensor is ideal (the firmware's filtered true force; no FSR span error, creep or droop) and 0.1 N is "
                   "allowed [A]. This is NOT the closed-loop true-force R14.",
    "P_R16": "Share of samples whose hold torque is within the part's hold rule (40 % of the sampled cold stall torque). "
             "This is the R16 margin: the actuator can supply the hold torque. It does not test the firmware.",
    "P_R16_sim_force": "Both of the above at once.",
    "R14_true_force_closed_loop": "True pad force at least 5.0 N through the hold with the shipped firmware. Not modelled "
                                  "here; measured by the firmware study (see firmware_study).",
    "t_contact": "First millisecond at which the filtered force reaches F_TOUCH (0.5 N). R19 does not name this event.",
    "t_45": "First millisecond at which the true pad force reaches 4.5 N (90 % of the 5 N setpoint). Every close-time "
            "number in the note (t_close, P_R19) ends on this event.",
    "R19_words": "Full close in <= 0.5 s. The last 3 deg before contact at <= 20 deg/s to limit impact [A] "
                 "(DESIGN-BASIS R19, verbatim)",
    "hold_margin": "Capacity at the rail low end divided by the hold torque (2 F r_c + T x_f) / eta, capacity = hold rule x stall.",
}
FIRMWARE_STUDY = {
    "source": "pull request 20 (branch agent/gripper-firmware-controls), docs/gripper/analysis/controls.md; not merged, as of 2026-10-11",
    "tag": "S",
    "R14_true_force_met_share_present_servo": 0.451,
    "R19_5N_within_0.75s_share_present_servo": 0.493,
    "causes": ["finger stiffness (squeeze cap sized for the stiffest finger)", "droop", "force-sensor span error"],
    "in_this_model": ["hold bias F_HOLD_BIAS_N 1.0 N (regulated hold about 6 N)", "stiffness estimate and gain schedule",
                      "squeeze cap less F_CAP_MARGIN_N 0.5 N", "FSR power law with the voltage-domain EMA"],
    "constants_this_model_lacks": {"hold_current_trip_A": 2.0, "other_states_trip_A": 1.8,
                                   "fsr_span_error_creep_droop": "not modelled (ideal sensor)"},
    "rerun_status": "Rerun 2026-10-11 on pull request 20 merged with master: the model reproduces fw_sim.json for the four "
                    "R12/FEA fingers (test_sim_reproduces_firmware_sim); the recommendation and purchase gate did not change.",
}
R10 = {"limit_g_mm": 43720.0, "estimate_g_mm": 40507.0, "lever_mm_A": 43720.0 / 125.0,
       "note": "R10: 43,720 g*mm equals 125 g at 40 mm past H, so the gripper lever is 349.8 mm [D from R10]; an added "
               "servo-station mass is taken at that lever [A]"}


def hold_current_reconciliation(c):
    """Median hold motor current of c as each sampled input is switched on, nominal to fully sampled (same draws as the
    Monte Carlo seed). Explains why the nominal 1.00 A and the Monte Carlo median differ."""
    rng = np.random.default_rng(SEED + 5000)
    full = lanes(c, N_MC, rng=rng)
    nom = lanes(c, N_MC, nominal={})
    F = M.V["F_hold_N"]

    def cur(Ts, eta, es, Ist, Iid):
        need = M.t_req(F, eta)
        return Iid + Ist * np.minimum(1.0, need / (Ts * c["N"] * es))
    steps = [("nominal unit, 6.5 V, 25 C, eta 0.85", nom, nom, nom, nom),
             ("+ sampled stall torque (+/-15 % spread, vendor-claim factor, 25-80 C winding, rail and wire drop)", full, nom, nom, nom),
             ("+ sampled link efficiency 0.70-0.95", full, full, nom, nom),
             ("+ sampled stage efficiency and stall current (rail sag)", full, full, full, full)]
    rows = []
    for lab, a, b, d, e in steps:
        i = cur(a["T_stall_motor"], b["eta_link"], d["eta_stage"], e["I_stall"], full["I_idle"])
        rows.append({"step": lab, "median_A": r(np.median(i)), "p95_A": r(np.percentile(i, 95))})
    return rows


def thermal_block(configs):
    by = {c["cfg"]: c for c in configs}
    ref = X.thermal_reference()
    est = {cfg: X.thermal_estimate(by[cfg], ref) for cfg in SEL}
    # same, with each unit's Monte Carlo median hold current instead of the nominal one (relative to the present servo)
    k = {cfg: by[cfg]["mc"]["I_hold_p50_fw_cap8"] / by[cfg]["static"]["I_hold_A"] for cfg in SEL}
    est_med = {cfg: X.thermal_estimate(by[cfg], ref, current_scale=k[cfg] / k["A17@1:1"]) for cfg in SEL}
    est_abs = {cfg: X.thermal_estimate(by[cfg], ref, current_scale=k[cfg]) for cfg in ("A32@1:1", "A19@1:1", "A17@1.5:1")}
    cmp_ = {}
    for key in est["A17@1:1"]:
        cmp_[key] = {cfg: est[cfg][key]["case_C"] for cfg in SEL}
    return {"tag": "D scaling estimate, not a thermal model",
            "method": X.thermal_estimate.__doc__.split("\n\n")[0] if False else " ".join(X.thermal_estimate.__doc__.split()),
            "K_per_W_from_thermal_json": {f"{f} | {cd}": {str(a): {k: r(v, 3) for k, v in kk.items()} for a, kk in v["K_per_W"].items()}
                                                   for (f, cd), v in ref.items()},
            "present_servo_reference": {f"{f} | {cd}": {k: r(v, 4) for k, v in v.items() if k != "K_per_W"}
                                        for (f, cd), v in ref.items()},
            "median_current_scale_vs_present": {cfg: r(k[cfg] / k["A17@1:1"], 3) for cfg in SEL},
            "estimates_at_median_hold_current": est_med,
            "estimates_median_current_vs_present_at_nominal": est_abs, "backoff_factor": X.BACKOFF, "R26_case_limit_C": X.R26_C, "estimates": est, "case_C_by_config": cmp_}


def ideal_actuator_case():
    """R19 demonstration: an ideal actuator (5000 deg/s, 2 ms lag, 20 N*m) against the shipped servo on the fw_sim plant,
    shipped and fastest-compliant profiles, every finger."""
    jobs = []
    for kl, k in K_CASES.items():
        for lab in ("shipped servo", "ideal actuator"):
            for prof in PROFILES:
                d = ref_lanes(k)
                if lab == "ideal actuator":
                    d["w0_motor"], d["tau"], d["T_stall_motor"] = np.full(20, 5000.0), np.full(20, 0.002), np.full(20, 20.0)
                d.update({kk: np.full(20, vv) for kk, vv in M.fw_profile(PROFILE_PARAMS[prof]).items()})
                jobs.append(((kl, lab, prof), d))
    out_ = {}
    for (kl, lab, prof), d, res in run_batch(jobs, ms=1500):
        out_.setdefault(f"{lab} | {prof} profile", {})[kl] = {
            "t_contact_s": r(np.nanmean(res["t_contact"])), "t_45_s": r(np.nanmean(res["t_45"])),
            "F_at_0p5s": None, "F_peak_N": r(res["F_peak"].max(), 2)}
    return {"actuator": "ideal: 5000 deg/s no-load, 2 ms lag, 20 N*m stall [A]", "plant": "fw_sim (A17 1:1 plant, no tension)",
            "events": {"t_contact_s": DEFINITIONS["t_contact"], "t_45_s": DEFINITIONS["t_45"]}, "R19": DEFINITIONS["R19_words"],
            "cases": out_}


def mc_at_r12_limits(configs):
    by = {c["cfg"]: c for c in configs}
    out_ = {}
    for idx, cfg in enumerate(SEL):
        c = by[cfg]
        jobs = []
        for kl in ("R12 min", "R12 max"):
            base = lanes(c, N_MC, rng=np.random.default_rng(SEED + 1000 + idx))
            base["k_tip"] = np.full(N_MC, K_CASES[kl])
            for cap in CAPS:
                d = dict(base)
                d.update(fw_lanes(c, "fw", cap, N_MC))
                jobs.append(((kl, cap), d))
        for (kl, cap), d, res in run_batch(jobs):
            p14, p16 = passes(c, d, res)
            out_.setdefault(cfg, {})[f"{kl} ({K_CASES[kl]} N/mm) | cap {cap:g} N"] = {
                "P_sim_force": r(p14.mean()), "P_R16": r(p16.mean()), "P_R16_sim_force": r((p14 & p16).mean()),
                "F_hold_p05_N": pct(res["F_final"], 5), "F_peak_p99_N": pct(res["F_peak"], 99)}
    return out_


def extra_studies(configs):
    by = {c["cfg"]: c for c in configs}
    out("\nfollow-up studies: thermal scaling, gears, bench floors, R12-limit Monte Carlo, ideal actuator")
    gear = X.gear_width_table(configs)
    bench = {cfg: {"floor_Nm_eta_0.85": r(X.bench_stall_floor(by[cfg])), "floor_Nm_eta_0.70": r(X.bench_stall_floor(by[cfg], 0.70)),
                   "listing_Nm_at_V_lo": r(by[cfg]["static"]["stall_drive_Nm_at_V_lo"]),
                   "derivation": "T_req(5 N, eta) / (hold_rule x N x eta_stage); T_req = (2 x 5 x 65 + 2 x 11.5) / 1000 / eta"}
             for cfg in SEL}
    mass = {cfg: X.arm_gate(by[cfg]) for cfg in SEL}
    eligible = {"including_marginal": sorted(c["cfg"] for c in configs if c["eligible"]),
                "clear_pass_only": sorted(c["cfg"] for c in configs if c["eligible_clear"]),
                "marginal": sorted(c["cfg"] for c in configs if c["eligible"] and not c["eligible_clear"])}
    st = by[ORDER_TODAY]
    z_p, z_g = 16, 24
    stage = {"pair": f"m1.25 z{z_p}/z{z_g}, b 8 mm, PA6-CF printed", "centre_distance_mm": 1.25 * (z_p + z_g) / 2,
             "mass_model_g": r(st["stage_mass_g"], 2),
             "mass_z16_z24_g": r(M.stage_gear_mass(1.5, 1.25, z_p, 8.0, 1.20, 0.6) + M.V["servo_stage_hw_g"], 2),
             "backlash_stage_deg": r(math.degrees(0.25 / (1.25 * z_g / 2)), 2),
             "backlash_stage_pad_lag_mm": r(0.25 / (1.25 * z_g / 2) * M.R_C, 2),
             "backlash_sector_pair_deg": 1.005, "backlash_sector_pair_pad_lag_mm": 1.14,
             "backlash_tag": "stage: jt 0.25 mm printed [S tolerance_stacks T07] at the output gear's pitch radius [D]; "
                             "sector pair from gears.json recommendation.printed.backlash",
             "R10_added_g_mm": r(st["stage_mass_g"] * R10["lever_mm_A"], 0),
             "R10_percent_of_limit_after": r(100 * (R10["estimate_g_mm"] + st["stage_mass_g"] * R10["lever_mm_A"]) / R10["limit_g_mm"], 1),
             "R10_percent_after_z16_z24_mass": r(100 * (R10["estimate_g_mm"] + (M.stage_gear_mass(1.5, 1.25, z_p, 8.0, 1.20, 0.6)
                                                                                 + M.V["servo_stage_hw_g"]) * R10["lever_mm_A"]) / R10["limit_g_mm"], 1),
             "R10_percent_after_stage_mass_plus25pct": r(100 * (R10["estimate_g_mm"] + 1.25 * st["stage_mass_g"] * R10["lever_mm_A"]) / R10["limit_g_mm"], 1),
             "R10_headroom_g_mm": R10["limit_g_mm"] - R10["estimate_g_mm"], "R10": R10["note"],
             "parts": "2 printed PA6-CF gears, one 4 mm shaft, two 4x8x3 bearings, bracket screws [A, $1 in the price]"}
    return {"definitions": DEFINITIONS, "firmware_study": FIRMWARE_STUDY, "thermal_scaling_estimate": thermal_block(configs),
            "hold_current_reconciliation_A32": hold_current_reconciliation(by[WAIT]),
            "gear_width_table": gear, "bench_stall_floor": bench, "arm_gate_options": mass, "eligible_sets": eligible,
            "order_today_stage": stage, "mc_at_R12_limits": mc_at_r12_limits(configs), "ideal_actuator_R19": ideal_actuator_case(),
            "servo_lag_note": "Servo lag tau is drawn U(30, 60) ms for every candidate. No candidate row publishes a lag, so a "
                              "per-candidate lag from listed speed would be invented; the listed speed already limits the slew "
                              "in the model (w0). What the common draw can hide is bounded by ideal_actuator_R19: a zero-lag, "
                              "infinite-speed actuator moves first contact by the difference between its row and the shipped servo's.",
            "R12_window_note": "Finger stiffness is drawn over the FEA range 1.05-1.24 N/mm, not the R12 window 0.88-1.63 N/mm; "
                               "mc_at_R12_limits holds one Monte Carlo at each R12 limit."}


def decision(configs):
    """Three-row decision table (order today / wait / fallback): every number comes from the configs."""
    by = {c["cfg"]: c for c in configs}
    rows = {}
    for role, cfg in (("order_today", ORDER_TODAY), ("wait_for_backordered", WAIT), ("fallback", FALLBACK)):
        c = by[cfg]
        s, mc = c["static"], c["mc"]
        rows[role] = {
            "cfg": cfg, "model": c["model"], "price_total_usd": c["price_total"], "V_rail_V": c["V_rail"],
            "availability": c["avail_note"], "envelope": c["envelope"], "envelope_note": c["envelope_note"],
            "evidence": c["evidence"], "hold_margin": s["hold_margin"], "hold_margin_p05": mc["hold_margin_p05"],
            "hold_margin_hold6N_p50": mc["hold_margin_6N_p50"], "P_R16_hold6N": mc["P_R16_hold6N"],
            "P_R16_fw_cap10": mc["P_R16_fw_cap10"], "P_R16_fw_cap8": mc["P_R16_fw_cap8"],
            "P_R16_sim_force_fw_cap10": mc["P_R16_sim_force_fw_cap10"], "P_R16_sim_force_fw_cap8": mc["P_R16_sim_force_fw_cap8"],
            "P_R15_fw_cap10": mc["P_R15_fw_cap10"], "P_R15_fw_cap8": mc["P_R15_fw_cap8"],
            "P_R19_0.75s_fw_cap8": mc["P_R19_0.75s_fw_cap8"], "P_R19_0.5s_fw_cap8": mc["P_R19_0.5s_fw_cap8"],
            "t_close_p50_fw_cap8_s": mc["t_close_p50_fw_cap8"], "t_close_p95_fw_cap8_s": mc["t_close_p95_fw_cap8"],
            "gear_SF_LC3": s["gear_SF_LC3"], "gear_SF_jam": s["gear_SF_jam"],
            "I_hold_A_nominal": s["I_hold_A"], "I_hold_p50_fw_cap8_A": mc["I_hold_p50_fw_cap8"],
            "I_hold_p95_fw_cap8_A": mc["I_hold_p95_fw_cap8"], "P_hold_W_nominal": s["P_hold_W"],
            "I_stall_sizing_A": s["I_stall_sizing_A"], "arm": c["arm"], "mass_total_g": s["mass_total_g"],
            "bench_floor_Nm_at_servo": r(X.bench_stall_floor(c)),
            "F_peak_max_fw_cap10_N": mc["F_peak_max_fw_cap10"]}
    return {"rows": rows, "recommended": "wait_for_backordered",
            "recommended_reason": "no CAD bay change beyond revision B, arm gate passes (not marginal), best hold margin per "
                                  "dollar of redesign; its weakness is one vendor's unverified torque and a backorder with no date",
            "measurement_that_changes_it": "first delivered A32 unit: bench stall below 1.98 N*m at 6.35 V (bench_stall_floor) or mass above 64.6 g "
                                           "(arm gate crosses 1.00) -> switch to fallback; no ship date from the vendor -> order today"}


def cap8_floor():
    """Position cap U_MAX = (cap - F_CAP_MARGIN_N - F_touch) / K_STIFF bounds the softest finger's reachable force to
    F_touch + K_soft U_MAX. Smallest tip stiffness that still reaches the R14 hold (5.0 N true force), per cap."""
    outd = {}
    for cap in CAPS:
        u_max = (cap - M.CFG.get("F_CAP_MARGIN_N", 0.0) - M.CFG["F_TOUCH_N"]) / M.K_STIFF  # force_ctrl.h CTRL_U_MAX_DEG
        need = M.V["F_hold_N"] - M.CFG["F_TOUCH_N"]
        K_min = need / u_max
        outd[f"cap {cap:g} N"] = {"U_MAX_deg": r(u_max), "K_min_N_per_deg": r(K_min),
                                  "k_tip_min_N_per_mm": r(K_min / (M.R_C * M.DEG)),
                                  "F_reachable_at_R12_min_N": r(M.CFG["F_TOUCH_N"] + 0.88 * M.R_C * M.DEG * u_max, 2),
                                  "max_stiffness_ratio": r(u_max * M.K_STIFF / need, 3)}
    return outd


def gates(c, g):
    s = c["static"]
    w, p = c["req_sets"]["as_written"], c["req_sets"]["proposed"]
    return {"arm_util_not_clearly_over_1": c["arm"]["status"] != "fail",
            "gear_SF_LC3_ge_1": s["gear_SF_LC3"] >= 1.0,
            f"P_R16_sim_force_ge_{g:g}_both": min(w["P_R16_sim_force"], p["P_R16_sim_force"]) >= g,
            "P_R15_8N_ge_0.9": p["P_R15"] >= 0.9,
            "available_ge_0.3": c["avail"] >= 0.3}


SCORE_DP = 9  # scores are rounded to this many places before any comparison, so last-bit float differences between
             # machines cannot reorder near-ties (a Windows rerun once swapped two and printed 0.469 for 0.468)


def scores(configs, w, rs):
    tot = sum(w.values())
    return {c["cfg"]: round(sum(w[k] * c["utilities"][rs][k] for k in sorted(w)) / tot, SCORE_DP) for c in configs}


def top(keys, sc):
    """Highest score; ties go to the lower configuration id (deterministic on every machine)."""
    keys = list(keys)
    return min(keys, key=lambda k: (-sc[k], k)) if keys else None


TIE_BAND = 0.02  # [A] score gap treated as a tie: the weight study moves scores by more than this
EVIDENCE_RANK = {"datasheet": 0, "corroborated": 0, "mixed": 1, "vendor claim": 2, "not recorded": 3}


def tie_pick(rank_list, evid, avail):
    """Among eligible configurations within TIE_BAND of the top eligible score, pick the best torque evidence, then
    the best availability, then the score."""
    el = [x for x in rank_list if x["eligible"]]
    if not el:
        return None
    band = [x for x in el if x["score"] >= el[0]["score"] - TIE_BAND]
    return min(band, key=lambda x: (EVIDENCE_RANK.get(evid[x["cfg"]], 3), -avail[x["cfg"]], -x["score"], x["cfg"]))["cfg"]


def recommend(configs, ranking, stability):
    by = {c["cfg"]: c for c in configs}
    evid = {k: c["evidence"] for k, c in by.items()}
    avail = {k: c["avail"] for k, c in by.items()}
    w_p, w_w = (tie_pick(ranking[rs], evid, avail) for rs in ("proposed", "as_written"))
    top3 = [w_p] + [x["cfg"] for x in ranking["proposed"] if x["eligible"] and x["cfg"] != w_p][:2]
    return {"rule": f"eligible (arm util <= 1.00, gear SF at stall >= 1.0, P(R14 and R16) >= {GATE_P} at both values, "
                    "P(R15 at 8 N) >= 0.9, availability >= 0.3); top weighted score; within "
                    f"{TIE_BAND} of the top, best torque evidence (datasheet or corroborated > mixed > vendor claim), "
                    "then availability",
            "score_winner_proposed": stability["proposed"]["winner"],
            "score_winner_as_written": stability["as_written"]["winner"],
            "winner_proposed": w_p, "winner_as_written": w_w, "same_winner": w_p == w_w,
            "top3_proposed": top3,
            "near_miss_proposed": [{"cfg": x["cfg"], "score": x["score"],
                                    "fails": [k for k, v in by[x["cfg"]]["gates"].items() if not v]}
                                   for x in ranking["proposed"]
                                   if sum(not v for v in by[x["cfg"]]["gates"].values()) == 1][:5],
            "winner_summary": summary(by[w_p]) if w_p else None,
            "top3_summary": [summary(by[k]) for k in top3],
            "reference_A17": summary(by["A17@1:1"]) if "A17@1:1" in by else None,
            "reference_A19": summary(by["A19@1:1"]) if "A19@1:1" in by else None}


def summary(c):
    s, mc = c["static"], c["mc"]
    return {"cfg": c["cfg"], "model": c["model"], "price_total_usd": c["price_total"], "price_tag": c["price_tag"],
            "V_rail_V": c["V_rail"], "hold_margin": s["hold_margin"], "hold_margin_25pct_rule": s["hold_margin_25pct_rule"],
            "hold_margin_p05": mc["hold_margin_p05"], "gear_SF_LC3": s["gear_SF_LC3"], "gear_SF_jam": s["gear_SF_jam"],
            "T_mesh_LC3_Nm": s["T_mesh_LC3_Nm"], "arm_util": s["arm_util_C001_7p4V"], "mass_total_g": s["mass_total_g"],
            "envelope": c["envelope"], "envelope_note": c["envelope_note"], "spec_basis": c["spec_basis"],
            "evidence": c["evidence"], "P_R16_sim_force_all": {k: mc[k] for k in mc if k.startswith("P_R16_sim_force_")},
            "P_R15_all": {k: mc[k] for k in mc if k.startswith("P_R15_")},
            "P_R19_all": {k: mc[k] for k in mc if k.startswith("P_R19_")},
            "t_close_p50_fast_cap8_s": mc["t_close_p50_fast_cap8"], "gearbox_overload": s["gearbox_overload"],
            "availability": c["avail_note"], "as_written": c["req_sets"]["as_written"], "proposed": c["req_sets"]["proposed"],
            "P_sim_force_fw_cap8": mc["P_sim_force_fw_cap8"], "P_R16_fw_cap8": mc["P_R16_fw_cap8"],
            "P_R19_0.75s_fw_cap10": mc["P_R19_0.75s_fw_cap10"], "P_R19_0.5s_fw_cap10": mc["P_R19_0.5s_fw_cap10"],
            "P_contact_0.5s_fast_cap10": mc["P_contact_0.5s_fast_cap10"],
            "t_close_p50_fw_s": mc["t_close_p50_fw_cap8"], "t_close_p95_fw_s": mc["t_close_p95_fw_cap8"],
            "t_close_p50_fast_s": mc["t_close_p50_fast_cap10"], "F_peak_max_fw_cap8_N": mc["F_peak_max_fw_cap8"],
            "F_peak_max_fw_cap10_N": mc["F_peak_max_fw_cap10"],
            "I_hold_A": s["I_hold_A"], "I_hold_p95_A": mc["I_hold_p95_fw_cap8"], "P_hold_W": s["P_hold_W"],
            "I_stall_A": s["I_stall_A"], "I_stall_sizing_A": s["I_stall_sizing_A"], "pad_force_at_stall_N": s["pad_force_at_stall_N"],
            "pulse_range_us": s["pulse_range_us"], "w0_jaw_dps": s["w0_jaw_dps"],
            "stall_drive_Nm_at_V_lo": s["stall_drive_Nm_at_V_lo"], "stall_drive_Nm_at_V_rail": r(float(stall_vec(c, c["V_rail"]))),
            "bench_stall_min_Nm_at_V_lo": r(s["T_hold_req_Nm"] / c["hold_rule"]),
            "contact_s_fast_profile_by_finger": [c["nominal"][f"{kl} | fast | cap 10 N"]["t_contact_s"] for kl in K_CASES],
            "F_peak_N_shipped_by_finger": {kl: c["nominal"][f"{kl} | fw | cap 10 N"]["F_peak_N"] for kl in K_CASES},
            "F_hold_N_cap8_by_finger": {kl: c["nominal"][f"{kl} | fw | cap 8 N"]["F_hold_N"] for kl in K_CASES}}


def write(configs, screened, ranking, stability, validation, rec, extra):
    res_dir = RES
    if QUICK:
        import tempfile
        res_dir = Path(tempfile.gettempdir()) / "actuation_trade_quick"
    res_dir.mkdir(exist_ok=True)
    clean = [{k: v for k, v in c.items() if k != "row"} for c in configs]
    data = {"inputs": {k: {"value": v[0], "tag": v[1], "note": v[2]} for k, v in M.INPUT.items()},
            "arm_fit": {"util = a + b * mass_g": [r(M.ARM_A, 4), r(M.ARM_B, 5)], "max_residual": r(M.ARM_RESID, 4)},
            "settings": {"n_mc": N_MC, "seed": SEED, "caps_N": CAPS, "times_s": TIMES, "profiles": PROFILE_PARAMS,
                         "F_hold_tol_N": F_HOLD_TOL, "gate_P": GATE_P, "k_cases": K_CASES, "weights": WEIGHTS,
                         "utility_rules": UTIL_RULES, "fw_profile_10N": M.fw_profile(), "fw_profile_8N": M.fw_profile(None, 8.0),
                         "screen_hold_margin": M.SCREEN_HOLD_MARGIN},
            "validation_vs_fw_sim": validation, **extra, "screened_out": screened, "configs": clean,
            "ranking": ranking, "stability": stability, "recommendation": rec}
    (res_dir / "actuation_trade.json").write_text(
        json.dumps(data, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8", newline="\n")
    report(configs, ranking, stability, validation, rec, extra)
    (res_dir / "actuation_trade_stdout.txt").write_text(out.buf.getvalue(), encoding="utf-8", newline="\n")  # LF on Windows too


def report(configs, ranking, stability, validation, rec, extra):
    out("\nvalidation vs firmware sim (A17 1:1):  model / fw_sim")
    for kl, v in validation.items():
        m, f = v["model"], v["fw_sim"]
        out(f"  {kl:8s} c0 {m['c0_deg']:+.2f}/{f['c0_deg']:+.2f}  contact {m['t_contact_s']:.3f}/{f['t_contact_s']:.3f} s"
            f"  F>=4.5 {m['t_F45_s']:.3f}/{f['t_F45_s']:.3f} s  peak {m['F_peak_N']:.2f}/{f['F_peak_N']:.2f} N"
            f"  hold {m['F_hold_N']:.2f}/{f['F_hold_N']:.2f} N")
    out(f"\narm fit: util = {M.ARM_A:.4f} + {M.ARM_B:.5f} x mass_g (max residual {M.ARM_RESID:.4f})")
    out(f"8 N cap stiffness floor: {extra['cap8_stiffness_floor']}")
    hdr = (f"{'config':12s} {'$':>6s} {'V':>5s} {'hold':>5s} {'p05':>5s} {'SF3':>5s} {'arm':>5s} {'g':>6s} {'w0jaw':>6s}"
           f" {'Ihold':>6s} {'Isz':>5s} {'Fstl':>5s} | {'P14w':>5s} {'P15w':>5s} {'P19w':>5s} | {'P14p':>5s} {'P15p':>5s}"
           f" {'P19p':>5s} | {'tc50':>5s} {'tc95':>5s} | {'env':14s} {'evidence':14s} gates")
    out("\nall configurations. hold = 40 % rule margin at the rail low end; p05 = MC 5th percentile; SF3 = gear SF at stall;"
        "\narm = SO-101 hold utilisation; Isz = stall current for rail sizing; Fstl = pad force at stall;"
        "\nP14 = P(R14 and R16); w = as written (10 N, 0.5 s, fastest compliant profile); p = proposed (8 N, 0.75 s, shipped"
        " profile); tc = close time to F >= 4.5 N, shipped profile, 8 N")
    out(hdr)
    for c in sorted(configs, key=lambda c: (-c["utilities"]["proposed"]["requirements"], c["cfg"])):
        s, mc, w, p = c["static"], c["mc"], c["req_sets"]["as_written"], c["req_sets"]["proposed"]
        out(f"{c['cfg']:12s} {c['price_total']:6.2f} {c['V_rail']:5.2f} {s['hold_margin']:5.2f} {mc['hold_margin_p05']:5.2f}"
            f" {s['gear_SF_LC3']:5.2f} {s['arm_util_C001_7p4V']:5.3f} {s['mass_total_g']:6.1f} {s['w0_jaw_dps']:6.0f}"
            f" {s['I_hold_A']:6.2f} {s['I_stall_sizing_A']:5.2f} {s['pad_force_at_stall_N']:5.1f} | {w['P_R16_sim_force']:5.2f} {w['P_R15']:5.2f}"
            f" {w['P_R19']:5.2f} | {p['P_R16_sim_force']:5.2f} {p['P_R15']:5.2f} {p['P_R19']:5.2f} |"
            f" {fmt(mc['t_close_p50_fw_cap8'])} {fmt(mc['t_close_p95_fw_cap8'])} | {c['envelope']:14s} {c['evidence'][:14]:14s}"
            f" {'eligible' if c['eligible'] else 'fails ' + ','.join(k for k, v in c['gates'].items() if not v)}")
    for rs in ("as_written", "proposed"):
        out(f"\nranking ({rs}), top 6 eligible, then top 3 overall:")
        for x in [x for x in ranking[rs] if x["eligible"]][:6] + ranking[rs][:3]:
            c = next(c for c in configs if c["cfg"] == x["cfg"])
            u = c["utilities"][rs]
            out(f"  {x['cfg']:12s} score {x['score']:.3f} {'eligible' if x['eligible'] else 'GATED  '}  "
                + "  ".join(f"{k} {v:.2f}" for k, v in u.items()))
        st = stability[rs]
        out(f"  winner {st['winner']}; single-weight x0.5/x1.5 changes that move it: {st['oat_changes'] or 'none'}")
        out(f"  random weights (each x U(0.5, 1.5), 4000 draws) win share: {st['mc_weights_win_share']}")
        out(f"  same draws, recommendation after the {TIE_BAND} tie rule: {st['mc_weights_recommendation_share']}")
        out(f"  winner with the P(R14 and R16) gate at 0.8 / 0.95: {st['winner_at_other_gates']}; "
            f"top score with no gates: {st['top_score_without_gates']}")
    out("\nsensitivity (one at a time; FEA E56 finger, 10 N cap, shipped profile):")
    keys = list(dict.fromkeys(rec["top3_proposed"] + ["A17@1:1"]))
    for k in keys:
        c = next(c for c in configs if c["cfg"] == k)
        out(f"  {k}")
        for name, m in c["sensitivity"].items():
            out(f"    {name:16s} hold margin {m['hold_margin']:.2f}  warm-stall fraction {m['hold_fraction_of_warm_stall']:.2f}"
                f"  close {fmt(m['t_close_F45_s'])} s  peak {m['F_peak_N']:.2f} N  hold {m['F_hold_N']:.2f} N  I {m['I_hold_A']:.2f} A")
    out("\nnominal close per finger (shipped / fastest compliant profile, 10 N cap; and 8 N cap shipped):")
    for k in keys:
        c = next(c for c in configs if c["cfg"] == k)
        for kl in K_CASES:
            a, b, e = (c["nominal"][f"{kl} | fw | cap 10 N"], c["nominal"][f"{kl} | fast | cap 10 N"],
                       c["nominal"][f"{kl} | fw | cap 8 N"])
            out(f"  {k:12s} {kl:8s} contact {fmt(a['t_contact_s'])}/{fmt(b['t_contact_s'])}  F>=4.5 {fmt(a['t_close_F45_s'])}/"
                f"{fmt(b['t_close_F45_s'])} s  peak {a['F_peak_N']:.2f}/{b['F_peak_N']:.2f} N  v@+3 {a['v_jaw_touch3_dps']}/"
                f"{b['v_jaw_touch3_dps']} deg/s | 8 N: hold {e['F_hold_N']:.2f} N peak {e['F_peak_N']:.2f} N")
    out("\nrecommendation: " + json.dumps({k: rec[k] for k in ("score_winner_proposed", "score_winner_as_written",
                                                              "winner_proposed", "winner_as_written", "same_winner",
                                                              "top3_proposed")}))
    out("  rule: " + rec["rule"])
    for sm in ([rec["winner_summary"]] if rec["winner_summary"] else []) + rec["top3_summary"][1:] + [rec["reference_A17"],
                                                                                              rec["reference_A19"]]:
        out("  " + json.dumps(sm))


def fmt(x):
    return " n/a " if x is None else f"{x:5.3f}"


if __name__ == "__main__":
    main()
