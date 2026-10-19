"""Force-loop simulation of the cloth-feed gripper, running the shipped firmware core (fsm/force_ctrl/motion
through shim.cpp) against a servo + finger + FSR plant at 1 kHz.

Run from the repository root (about 20 s):
    python analysis/gripper/firmware_sim/sim.py
Writes analysis/gripper/firmware_sim/results/fw_sim.json and results/figures/controls_*.png.

Plant (every value tagged; controls.md section 3 cites each):
  servo   DS3230 MG at 6.5 V: stall 2.876 N*m, no-load 327 deg/s (config.h [D from S]); first-order position
          loop SERVO_TAU_S 40 ms [A]; reads the pulse once per 20 ms frame, half a frame after the control tick,
          plus SERVO_INT_DELAY_S 10 ms [A]; deadband 3 us = +/-0.135 deg [S A17]; 1 us pulse quantisation;
          speed falls linearly with load torque to zero at stall [A, DC-motor line].
  linkage T_servo = 2 F r_c / eta, r_c 65 mm, eta 0.85 [DB section 2].
  finger  F = k_tip * r_c * (theta_touch - theta) [TA 2.5]; k_tip over the R12 window 0.88-1.63 N/mm and the
          finger.md 6.2 D7 pair (k_pair 0.523 / 0.621 -> 1.05 / 1.24 N/mm per finger); linear (the FEA fold at
          8.9 N only lowers force, so linear is the conservative case for the cap).
  contact no-cloth touch at -0.44 deg (1 mm gap at theta = 0 [DB R18]); one 0.3 mm ply at -0.31 deg [TA 2.1].
  FSR     fsr_model.h power law; 20 mV unloaded offset [A]; Gaussian ADC noise FSR_NOISE_MV_RMS 8 mV [A, M11];
          1 mV quantisation (analogReadMilliVolts); firmware EMA alpha 0.10 at 1 kHz (inputs.cpp).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402
import fwconfig  # noqa: E402

ROOT = HERE.parents[2]
FIG = HERE / "results/figures"   # owned by this lane; docs/gripper/figures is not
RES = HERE / "results"
CFG = fwconfig.load()
DER = fwconfig.derived(CFG)

ETA = 0.85            # [DB section 2]
R_C = CFG["R_C_MM"]   # mm
T_STALL = CFG["SERVO_STALL_NM"]
W0 = CFG["SERVO_SPEED_DPS"]
I_STALL = CFG["SERVO_STALL_A"]
I_IDLE = 0.15         # A, servo electronics + no-load [A]
TH_TOUCH_NOCLOTH = -0.44   # deg: 1 mm gap / (2 r_c) [DB R18]
TH_TOUCH_PLY = -0.31       # deg [TA 2.1]
ZERO_MV = 20.0             # unloaded FSR node offset [A]

K_CASES = [  # (label, k_tip N/mm, source)
    ("0.88 R12 min", 0.88, "DB R12"),
    ("1.05 FEA E56+D7", 2 * 0.523, "finger.md 6.2"),
    ("1.24 FEA E67+D7", 2 * 0.621, "finger.md 6.2"),
    ("1.63 R12 max", 1.63, "DB R12"),
]
COLORS = ["#1c5bb8", "#c9601a", "#008a63", "#9c3a8a"]  # validated categorical order (dataviz validator, light)
INK, INK2, GRID = "#141d27", "#3f4b58", "#e2e6eb"

EV = {}  # event name -> id, filled at load


class Plant:
    def __init__(self, k_tip, noise_mv=CFG["FSR_NOISE_MV_RMS"], span=1.0, fsr_dead=False, seed=1):
        self.k = k_tip
        self.noise = noise_mv
        self.span = span            # FSR reads span x true force (M11 error)
        self.dead = fsr_dead        # FSR open circuit: reads only the offset
        self.rng = np.random.default_rng(seed)
        self.theta = CFG["JAW_OPEN_DEG"]
        self.tgt = self.theta
        self.pending = []           # (t_apply, target)
        self.touch = TH_TOUCH_NOCLOTH
        self.ema = ZERO_MV
        self.F = 0.0

    def force(self):
        d = self.touch - self.theta
        return self.k * R_C * math.radians(d) if d > 0 else 0.0

    def step(self, t_ms, us, lib):
        # Servo samples the pulse once per frame, 10 ms after the control tick, then decodes for 10 ms.
        if t_ms % 20 == 10:
            tgt = (us - 1500) / DER["US_PER_DEG"] - 0.0  # pulse -> jaw angle (SERVO_DEG_AT_JAW0 = 90, dir +1)
            self.pending.append((t_ms + int(CFG["SERVO_INT_DELAY_S"] * 1000), tgt))
        while self.pending and self.pending[0][0] <= t_ms:
            self.tgt = self.pending.pop(0)[1]
        F = self.force()
        T = 2 * F * R_C / 1000 / ETA
        e = self.tgt - self.theta
        db = DER["DEADBAND_DEG"] / 2
        if abs(e) <= db:
            w = 0.0
        else:
            w = (e - math.copysign(db, e)) / CFG["SERVO_TAU_S"]
        wmax = W0 * max(0.0, 1 - T / T_STALL) if w < 0 else W0
        w = max(-wmax, min(W0, w))
        self.theta += w * 0.001
        self.F = self.force()
        amps = I_IDLE + I_STALL * min(1.0, 2 * self.F * R_C / 1000 / ETA / T_STALL)
        mv = 0.0 if self.dead else lib.sim_fsr_mv_from_force(self.F * self.span)
        raw = round(min(3300.0, max(0.0, mv + ZERO_MV + self.rng.normal(0, self.noise))))
        self.ema += CFG["FSR_EMA_ALPHA"] * (raw - self.ema)
        f_fw = lib.sim_fsr_force_from_mv(self.ema - lib.sim_zero_mv())
        lib.sim_set_limit(1 if self.theta >= 19.5 else 0)   # jaw-open limit switch closes near +20 deg [A]
        return raw, f_fw, amps


def boot_to_idle(lib, plant, rec=None):
    lib.sim_init()
    us = lib.sim_jaw_to_us(CFG["JAW_OPEN_DEG"])
    for _ in range(6000):
        t = lib.sim_now() + 1
        raw, f_fw, amps = plant.step(t, us, lib)
        us = lib.sim_step(raw, f_fw, amps)
        if lib.sim_state() == 3 and abs(lib.sim_theta_cmd() - CFG["JAW_OPEN_DEG"]) < 1e-3 and plant.theta > 19.5:
            return True
    return False


def events(lib):
    n = 4096
    t = (build.ctypes.c_uint32 * n)()
    ty = (build.ctypes.c_int * n)()
    a = (build.ctypes.c_float * n)()
    st = (build.ctypes.c_int * n)()
    m = lib.sim_events(t, ty, a, st, n)
    return [(t[i], lib.sim_event_name(ty[i]).decode(), a[i], lib.sim_state_name(st[i]).decode()) for i in range(m)]


def grip(lib, k, sp=5.0, ms=1500, script=None, touch=None, **pk):
    """Boot, calibrate (no cloth), then grip one ply. script: {t_ms_after_G: callable(lib, plant)}."""
    plant = Plant(k, **pk)
    assert boot_to_idle(lib, plant), "did not reach IDLE"
    c0 = lib.sim_theta_c0()
    plant.touch = TH_TOUCH_PLY if touch is None else touch
    lib.sim_clear_events()
    lib.sim_post(EV["CMD_GRIP"], sp)
    t0 = lib.sim_now()
    us = lib.sim_jaw_to_us(lib.sim_theta_cmd())
    ser = {k_: [] for k_ in ("t", "th_cmd", "th", "F", "F_fw", "state")}
    script = script or {}
    for i in range(ms):
        if i in script:
            script[i](lib, plant)
        t = lib.sim_now() + 1
        raw, f_fw, amps = plant.step(t, us, lib)
        us = lib.sim_step(raw, f_fw, amps)
        ser["t"].append((t - t0) / 1000)
        ser["th_cmd"].append(lib.sim_theta_cmd())
        ser["th"].append(plant.theta)
        ser["F"].append(plant.F)
        ser["F_fw"].append(lib.sim_force_fw())   # the firmware's own filtered force (fsr_filter.cpp)
        ser["state"].append(lib.sim_state())
    ev = [(tt - t0, n, a, s) for tt, n, a, s in events(lib)]
    return {"c0": c0, "touch": plant.touch if touch is None else touch, "series": ser, "events": ev, "final_state": lib.sim_state_name(lib.sim_state()).decode(),
            "fault": lib.sim_fault()}


def metrics(r, sp=5.0):
    s = r["series"]
    t, F = np.array(s["t"]), np.array(s["F"])
    ev = r["events"]
    first = lambda name: next((e[0] / 1000 for e in ev if e[1] == name), None)  # noqa: E731
    i90 = np.argmax(F >= 0.9 * sp) if (F >= 0.9 * sp).any() else None
    hold = t >= (t[-1] - 0.5)
    th = np.array(s["th"])
    touch = r.get("touch", TH_TOUCH_PLY)
    # HOLD is entered by FSR_TARGET (force on target) or by FORCE_SAT (at the squeeze cap with F >= F_SLIP_N).
    enter_hold = next((e for e in ev if e[3] == "HOLD"), None)

    def v_at(d):  # actual (modelled) jaw closing speed when the jaw passes touch + d deg, deg/s
        idx = np.nonzero(th <= touch + d)[0]
        if not len(idx) or idx[0] < 5 or idx[0] + 5 >= len(th):
            return None
        i = idx[0]
        return float((th[i - 5] - th[i + 5]) / 0.010)
    return {
        "v_jaw_at_touch_plus_3_dps": v_at(3.0), "v_jaw_at_touch_plus_2_dps": v_at(2.0),
        "v_jaw_at_touch_plus_1_dps": v_at(1.0),
        "c0_deg": r["c0"], "c0_err_deg": r["c0"] - TH_TOUCH_NOCLOTH,
        "t_contact_s": first("FSR_CONTACT"), "t_F90_s": float(t[i90]) if i90 is not None else None,
        "t_hold_s": enter_hold[0] / 1000 if enter_hold else None,
        "hold_path": enter_hold[1] if enter_hold else None, "F_max_N": float(F.max()), "overshoot_N": float(F.max() - sp),
        "F_hold_mean_N": float(F[hold].mean()), "F_hold_std_N": float(F[hold].std()),
        "F_hold_min_N": float(F[hold].min()),
        "final_state": r["final_state"], "fault": r["fault"],
        "faults": [e[1] for e in ev if e[1] in ("FSR_OVER", "FAULT_OVERCURRENT", "FAULT_SENSOR")],
    }


def ds(a, n=400):
    a = list(a)
    step = max(1, len(a) // n)
    return [round(float(v), 4) for v in a[::step]]


def run_all():
    lib = build.load()
    for i in range(64):
        name = lib.sim_event_name(i).decode()
        if name == "?":
            break
        EV[name] = i
    out = {"config": {k: CFG[k] for k in ("F_TARGET_DEFAULT_N", "F_TRIP_N", "F_CAP_N", "F_SOFT_LIMIT_N", "F_RAMP_NPS",
                                          "JAW_SPEED_FAST_DPS", "JAW_SPEED_NEAR_DPS", "JAW_SLOW_ZONE_DEG", "JAW_MIN_DEG",
                                          "CTRL_I_DB_HI_N", "CTRL_RATE_LIMIT_DPS", "FSR_NOISE_MV_RMS")},
           "derived": DER, "cases": {}, "series": {}}

    # 1. Step response across the stiffness window (nominal noise).
    for lab, k, src in K_CASES:
        r = grip(lib, k)
        out["cases"][lab] = dict(metrics(r), k_tip=k, source=src)
        s = r["series"]
        out["series"][lab] = {"t": ds(s["t"]), "F": ds(s["F"]), "F_fw": ds(s["F_fw"]), "th_cmd": ds(s["th_cmd"]),
                              "th": ds(s["th"])}

    # 2. Continuous stiffness sweep for overshoot and close time.
    sweep = []
    for k in np.round(np.arange(0.6, 1.81, 0.05), 3):
        m = metrics(grip(lib, float(k)))
        sweep.append({"k": float(k), **{x: m[x] for x in ("F_max_N", "t_contact_s", "t_F90_s", "t_hold_s", "F_hold_mean_N",
                                                          "final_state")}})
    out["sweep_k"] = sweep

    # 3. Sensor noise: 0 / 8 / 20 mV RMS, 10 seeds each, stiff and default finger.
    noise = []
    for k in (1.0, 1.63):
        for sig in (2.0, 8.0, 20.0):   # 2 mV, not 0: a noiseless ADC now trips the stuck-sensor check (FSR_STUCK_MS)
            ms_ = [metrics(grip(lib, k, noise_mv=sig, seed=sd)) for sd in range(10)]
            noise.append({"k": k, "sigma_mv": sig, "F_max_N": max(m["F_max_N"] for m in ms_),
                          "F_hold_std_N": float(np.mean([m["F_hold_std_N"] for m in ms_])),
                          "F_hold_mean_N": float(np.mean([m["F_hold_mean_N"] for m in ms_])),
                          "F_hold_min_N": min(m["F_hold_min_N"] for m in ms_),
                          "t_F90_s_max": max(m["t_F90_s"] or 9 for m in ms_),
                          "states": sorted({m["final_state"] for m in ms_}),
                          "faults": sorted({f for m in ms_ for f in m["faults"]})})
    out["noise"] = noise
    rn = grip(lib, 1.0, noise_mv=20.0, seed=3)
    out["series"]["noise20"] = {k_: ds(rn["series"][k_], 600) for k_ in ("t", "F", "F_fw")}

    # 4. Setpoint steps and a slip disturbance in HOLD (default finger).
    sc = {700: lambda L, p: L.sim_post(EV["CMD_GRIP"], 7.0), 1300: lambda L, p: L.sim_post(EV["CMD_GRIP"], 3.0),
          1900: lambda L, p: L.sim_post(EV["CMD_GRIP"], 5.0), 2500: lambda L, p: setattr(p, "touch", p.touch - 0.5)}
    rs = grip(lib, 1.0, ms=3200, script=sc)
    out["series"]["steps"] = {k_: ds(rs["series"][k_], 800) for k_ in ("t", "F", "F_fw", "th_cmd", "th")}
    out["steps_events"] = [(e[0], e[1], round(e[2], 2), e[3]) for e in rs["events"] if e[1] not in ("POSITION_REACHED",)]
    F = np.array(rs["series"]["F"])
    t = np.array(rs["series"]["t"])
    out["steps"] = {"F_max_N": float(F.max()), "F_at_7_mean": float(F[(t > 1.1) & (t < 1.3)].mean()),
                    "F_at_3_mean": float(F[(t > 1.7) & (t < 1.9)].mean()),
                    "F_after_slip_min": float(F[(t > 2.5) & (t < 2.7)].min()),
                    "F_recovered_mean": float(F[(t > 3.0)].mean()), "final_state": rs["final_state"]}

    # 5. Sensor failures: the position cap alone must keep F <= 10 N.
    fails = {}
    for lab, kw in (("fsr_open", {"fsr_dead": True}), ("fsr_reads_50pct", {"span": 0.5}),
                    ("fsr_reads_150pct", {"span": 1.5})):
        for k in (1.0, 1.63):
            r = grip(lib, k, ms=1500, **kw) if lab != "fsr_open" else None
            if lab == "fsr_open":
                # Boot with a working FSR (calibration needs it), then the FSR opens before the grip.
                plant = Plant(k)
                assert boot_to_idle(lib, plant)
                plant.touch, plant.dead = TH_TOUCH_PLY, True
                lib.sim_clear_events()
                lib.sim_post(EV["CMD_GRIP"], 5.0)
                us, Fm, t0 = lib.sim_jaw_to_us(lib.sim_theta_cmd()), 0.0, lib.sim_now()
                ser = []
                for _ in range(1500):
                    tt = lib.sim_now() + 1
                    raw, f_fw, amps = plant.step(tt, us, lib)
                    us = lib.sim_step(raw, f_fw, amps)
                    Fm = max(Fm, plant.F)
                    ser.append(plant.F)
                fails[f"{lab}@{k}"] = {"F_max_N": Fm, "final_state": lib.sim_state_name(lib.sim_state()).decode(),
                                       "events": [e[1] for e in events(lib) if e[1] not in ("POSITION_REACHED",)]}
                out["series"][f"{lab}@{k}"] = {"t": ds(np.arange(1500) / 1000), "F": ds(ser)}
            else:
                m = metrics(r)
                fails[f"{lab}@{k}"] = {"F_max_N": m["F_max_N"], "final_state": m["final_state"],
                                       "F_hold_mean_N": m["F_hold_mean_N"],
                                       "events": [e[1] for e in r["events"] if e[1] not in ("POSITION_REACHED",)]}
                out["series"][f"{lab}@{k}"] = {"t": ds(r["series"]["t"]), "F": ds(r["series"]["F"])}
    # Contact far above theta_c0 (thick or folded cloth): the jaw touches during the fast leg.
    for dth in (6.0, 8.0, 10.0):
        r = grip(lib, 1.63, ms=1500, touch=TH_TOUCH_NOCLOTH + dth)
        m = metrics(r)
        fails[f"early_contact_{dth:.0f}deg@1.63"] = {"F_max_N": m["F_max_N"], "final_state": m["final_state"],
                                                    "F_hold_mean_N": m["F_hold_mean_N"],
                                                    "events": [e[1] for e in r["events"] if e[1] not in ("POSITION_REACHED",)]}
    out["sensor_faults"] = fails
    return out


# ---------------------------------------------------------------------------------------------------------
def style(ax, xlabel, ylabel):
    ax.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#9aa4ae")
    ax.tick_params(colors=INK2, labelsize=9)
    ax.set_xlabel(xlabel, color=INK2, fontsize=9.5)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9.5)


def refs(ax, x0):
    """Reference lines, labelled at the left edge (x0 in data units) above the line."""
    for y, lab in ((CFG["F_TARGET_DEFAULT_N"], "5 N target"), (CFG["F_TRIP_N"], "8 N trip"), (CFG["F_CAP_N"], "10 N cap")):
        ax.axhline(y, color="#6a7482", lw=1, ls=(0, (4, 3)))
        ax.text(x0, y + 0.15, lab, color=INK2, fontsize=8.5, ha="left", va="bottom")


def figures(out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "savefig.dpi": 150})
    FIG.mkdir(parents=True, exist_ok=True)
    styles = ["-", (0, (6, 2)), (0, (2, 1.5)), (0, (6, 2, 1.5, 2))]

    # Step response
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.5, 6.4), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    for i, (lab, k, _) in enumerate(K_CASES):
        s = out["series"][lab]
        a1.plot(s["t"], s["F"], color=COLORS[i], lw=2, ls=styles[i], label=f"k = {lab} N/mm")
    refs(a1, 0.62)
    a1.set_ylim(0, 11)
    a1.set_xlim(0, 1.0)
    style(a1, "", "Pad force, true (N)")
    a1.legend(frameon=False, fontsize=8.5, loc="upper left")
    a1.set_title("Grip from fully open (+20°): G 5 command at t = 0", color=INK, fontsize=11, loc="left")
    s = out["series"]["1.05 FEA E56+D7"]
    a2.plot(s["t"], s["th_cmd"], color=COLORS[0], lw=2, label="commanded θ")
    a2.plot(s["t"], s["th"], color=COLORS[1], lw=2, ls=(0, (6, 2)), label="servo θ (model)")
    a2.axhline(TH_TOUCH_PLY, color="#6a7482", lw=1, ls=(0, (4, 3)))
    a2.text(0.98, TH_TOUCH_PLY + 0.6, "ply contact −0.31°", color=INK2, fontsize=8.5, ha="right")
    style(a2, "Time after G (s)", "Jaw angle θ (deg)")
    a2.legend(frameon=False, fontsize=8.5, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIG / "controls_step_response.png")
    plt.close(fig)

    # Stiffness sweep: two panels, one quantity each (no dual axis)
    sw = out["sweep_k"]
    k = [r["k"] for r in sw]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.5, 3.6))
    a1.plot(k, [r["F_max_N"] for r in sw], color=COLORS[0], lw=2, marker="o", ms=4)
    refs(a1, 1.66)
    a1.axvspan(0.88, 1.63, color="#1b7443", alpha=0.08, lw=0)
    a1.text(0.9, 0.5, "R12 window", color=INK2, fontsize=8.5)
    a1.set_ylim(0, 11)
    style(a1, "Finger tip stiffness k (N/mm)", "Peak true pad force (N)")
    a1.set_title("Peak force vs stiffness", color=INK, fontsize=10.5, loc="left")
    a2.plot(k, [r["t_contact_s"] for r in sw], color=COLORS[1], lw=2, marker="o", ms=4, label="contact detected")
    a2.plot(k, [r["t_F90_s"] for r in sw], color=COLORS[2], lw=2, ls=(0, (6, 2)), marker="s", ms=4, label="F ≥ 4.5 N")
    a2.plot(k, [r["t_hold_s"] for r in sw], color=COLORS[3], lw=2, ls=(0, (2, 1.5)), marker="^", ms=4, label="HOLD entered")
    a2.axhline(0.75, color="#6a7482", lw=1, ls=(0, (4, 3)))
    a2.text(1.8, 0.76, "R19 0.75 s (ruled)", color=INK2, fontsize=8.5, ha="right", va="bottom")
    a2.axvspan(0.88, 1.63, color="#1b7443", alpha=0.08, lw=0)
    a2.set_ylim(0, 1.0)
    style(a2, "Finger tip stiffness k (N/mm)", "Time after G (s)")
    a2.set_title("Close time vs stiffness", color=INK, fontsize=10.5, loc="left")
    a2.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIG / "controls_stiffness_sweep.png")
    plt.close(fig)

    # Noise
    s = out["series"]["noise20"]
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.plot(s["t"], s["F_fw"], color=COLORS[1], lw=1.2, label="firmware force (FSR, 20 mV RMS noise, EMA)")
    ax.plot(s["t"], s["F"], color=COLORS[0], lw=2, label="true pad force")
    refs(ax, 1.22)
    ax.set_ylim(0, 11)
    ax.set_xlim(0, 1.5)
    style(ax, "Time after G (s)", "Pad force (N)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Sensor noise 2.5× the assumed 8 mV RMS, k = 1.0 N/mm", color=INK, fontsize=10.5, loc="left")
    fig.tight_layout()
    fig.savefig(FIG / "controls_noise.png")
    plt.close(fig)

    # Setpoint steps + slip
    s = out["series"]["steps"]
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.plot(s["t"], s["F"], color=COLORS[0], lw=2, label="true pad force")
    ax.plot(s["t"], s["F_fw"], color=COLORS[1], lw=1.2, ls=(0, (6, 2)), label="firmware force")
    for x, lab in ((0.7, "G 7"), (1.3, "G 3"), (1.9, "G 5"), (2.5, "slip −0.5°")):
        ax.axvline(x, color="#6a7482", lw=1, ls=(0, (2, 2)))
        ax.text(x + 0.02, 9.6, lab, color=INK2, fontsize=8.5)
    ax.set_ylim(0, 10.5)
    ax.set_xlim(0, 3.2)
    style(ax, "Time after G 5 (s)", "Pad force (N)")
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    ax.set_title("HOLD: setpoint steps and a cloth slip, k = 1.0 N/mm", color=INK, fontsize=10.5, loc="left")
    fig.tight_layout()
    fig.savefig(FIG / "controls_setpoint_slip.png")
    plt.close(fig)

    # Sensor faults
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    i = 0
    for key, lab in (("fsr_open@1.63", "FSR open, k 1.63"), ("fsr_reads_50pct@1.63", "FSR reads 50 %, k 1.63"),
                     ("fsr_reads_50pct@1.0", "FSR reads 50 %, k 1.0"), ("fsr_reads_150pct@1.63", "FSR reads 150 %, k 1.63")):
        s = out["series"][key]
        ax.plot(s["t"], s["F"], color=COLORS[i], lw=2, ls=styles[i], label=lab)
        i += 1
    refs(ax, 1.22)
    ax.set_ylim(0, 11)
    ax.set_xlim(0, 1.5)
    style(ax, "Time after G (s)", "True pad force (N)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Sensor faults: the squeeze cap alone bounds the force", color=INK, fontsize=10.5, loc="left")
    fig.tight_layout()
    fig.savefig(FIG / "controls_sensor_faults.png")
    plt.close(fig)


def main():
    out = run_all()
    RES.mkdir(exist_ok=True)
    (RES / "fw_sim.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8", newline="\n")
    figures(out)
    for lab, m in out["cases"].items():
        print(f"{lab:18s} c0 {m['c0_deg']:+.2f} (err {m['c0_err_deg']:+.2f})  contact {m['t_contact_s']}  F90 {m['t_F90_s']}"
              f"  v@+3/+2/+1 {m['v_jaw_at_touch_plus_3_dps']:.0f}/{m['v_jaw_at_touch_plus_2_dps']:.0f}/{m['v_jaw_at_touch_plus_1_dps']:.0f}"
              f"  hold {m['t_hold_s']}  Fmax {m['F_max_N']:.2f}  hold {m['F_hold_mean_N']:.2f}±{m['F_hold_std_N']:.3f}"
              f"  {m['final_state']} {m['faults']}")
    for n in out["noise"]:
        print("noise", n)
    print("steps", out["steps"])
    for k_, v in out["sensor_faults"].items():
        print("fault", k_, {x: v[x] for x in ("F_max_N", "final_state")}, v["events"][:8])


if __name__ == "__main__":
    main()
