"""Closed loop: the compiled firmware core (analysis/gripper/firmware_sim/shim.cpp + firmware/gripper/*.cpp, the
same sources the ESP32 sketch builds) driving the plant of plant.py at 1 kHz.

One grip = power-up (BOOT -> HOME -> CALIBRATE with no cloth -> IDLE), cloth goes between the pads, host sends
"G <sp>", the run continues GRIP_MS; then the long hold is compressed: the FSR creep clock jumps to the end of the
25.5 s hold (DB section 7) and the loop runs HOLD_TAIL_MS more, so the drift's effect on the held force shows.
Run from the repository root:  python analysis/gripper/controls/loop.py   (prints one nominal grip)
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "firmware_sim"))
import build  # noqa: E402
import plant as plant_mod  # noqa: E402

GRIP_MS = 1500
HOLD_TAIL_MS = 800
HOLD_END_S = 25.5         # DB section 7 hold [S DESIGN-BASIS]
LIMIT_CLOSED_ABOVE = 19.5  # jaw-open limit switch closes within 0.5 deg of +20 [A]
BOOT_MAX_MS = 9000

_LIB = None
_OVR = None
EV = {}
ST = {}


def cfg(name):
    """A numeric config.h value of the selected firmware variant (overrides first)."""
    if _OVR and name in _OVR:
        return float(_OVR[name])
    return build.config_value(name)


def configure(overrides=None):
    """Select a firmware variant: config.h values replaced (design sweeps); None = the repository firmware."""
    global _LIB, _OVR
    _OVR = dict(overrides) if overrides else None
    _LIB = None


def lib():
    global _LIB
    if _LIB is None:
        _LIB = build.load(_OVR)
        for i in range(64):
            n = _LIB.sim_event_name(i).decode()
            if n == "?":
                break
            EV[n] = i
        for i in range(16):
            n = _LIB.sim_state_name(i).decode()
            if n == "?":
                break
            ST[n] = i
    return _LIB


def events(L):
    n = 4096
    t = (build.ctypes.c_uint32 * n)()
    ty = (build.ctypes.c_int * n)()
    a = (build.ctypes.c_float * n)()
    st = (build.ctypes.c_int * n)()
    m = L.sim_events(t, ty, a, st, n)
    return [(int(t[i]), L.sim_event_name(ty[i]).decode(), float(a[i]), L.sim_state_name(st[i]).decode())
            for i in range(m)]


class Run:
    """Holds the firmware + plant pair; step() advances 1 ms."""

    def __init__(self, p=None, seed=1, ina_present=True):
        self.L = lib()
        self.pl = plant_mod.Plant(p, seed=seed)
        self.L.sim_init()
        self.L.sim_set_current_present(1 if ina_present else 0)   # what setup() learns from the boot probe
        self.us = self.L.sim_jaw_to_us(20.0)
        self.ina = ina_present
        self.raw = 0.0
        self.serial_garbage = None
        self.limit_stuck = None    # None, True (stuck closed) or False (stuck open)

    def step(self):
        t = self.L.sim_now() + 1
        raw, amps = self.pl.step(t, self.us)
        self.raw = raw
        lim = self.pl.thA >= LIMIT_CLOSED_ABOVE if self.limit_stuck is None else self.limit_stuck
        self.L.sim_set_limit(1 if lim else 0)
        us = self.L.sim_step(raw, 0.0, amps if self.ina else -1.0)
        if us > 0:
            self.us = us
        else:
            self.us = 0           # detached: the plant keeps the last target (servo holds or goes limp: [A] holds)
        return t

    def state(self):
        return self.L.sim_state_name(self.L.sim_state()).decode()

    def boot(self):
        for _ in range(BOOT_MAX_MS):
            self.step()
            if self.state() == "IDLE" and self.pl.thA > 19.0:
                return True
            if self.state() == "FAULT":
                return False
        return False


def grip(p=None, seed=1, sp=5.0, grip_ms=GRIP_MS, hold_tail_ms=HOLD_TAIL_MS, script=None, ina_present=True,
         keep_series=False):
    """One full grip. script: {ms_after_G: callable(run)} for fault injection. Returns a metrics dict."""
    r = Run(p, seed, ina_present)
    L, pl = r.L, r.pl
    booted = r.boot()
    out = {"booted": booted, "c0_deg": L.sim_theta_c0(), "calibrated": bool(L.sim_calibrated())}
    # The true 0.5 N angle with no cloth (what CALIBRATE should find), for the calibration error.
    out["c0_true_deg"] = half_newton_angle(pl)
    if not booted:
        out.update({"final_state": r.state(), "fault": L.sim_fault(), "events": [e[1] for e in events(L)][-12:]})
        return out
    pl.cloth = True
    touch = pl.touch_theta()
    L.sim_clear_events()
    L.sim_post(EV["CMD_GRIP"], sp)
    t0 = L.sim_now()
    script = script or {}
    F, th, thc, Ffw, st = [], [], [], [], []
    total = grip_ms + hold_tail_ms
    for i in range(total):
        if i in script:
            script[i](r)
        if i == grip_ms:
            pl.t_loaded = max(pl.t_loaded, HOLD_END_S)     # creep clock to the end of the hold
        r.step()
        F.append(pl.F)
        th.append(pl.theta_eff())
        if keep_series:
            thc.append(L.sim_theta_cmd())
            Ffw.append(L.sim_force_fw())
            st.append(r.state())
    ev = [(t - t0, n, a, s) for t, n, a, s in events(L)]
    first = lambda name: next((e[0] / 1000 for e in ev if e[1] == name), None)  # noqa: E731
    i90 = next((i for i, f in enumerate(F[:grip_ms]) if f >= 0.9 * sp), None)
    isp = next((i for i, f in enumerate(F[:grip_ms]) if f >= sp), None)
    # HOLD entered by either path: FSR_TARGET (on target) or FORCE_SAT (at the squeeze cap, F >= F_SLIP_N).
    enter_hold = next((e for e in ev if e[3] == "HOLD"), None)
    t_hold = enter_hold[0] / 1000 if enter_hold else None
    sat = first("FORCE_SAT")
    # Held force: after HOLD is entered (plus 0.2 s), through the compressed long hold.
    hold_from = int((t_hold if t_hold is not None else (sat if sat is not None else 9e9)) * 1000) + 200
    held = F[hold_from:] if hold_from < total else []
    tail = F[grip_ms + hold_tail_ms // 2:]

    def v_at(d):
        idx = next((i for i, x in enumerate(th) if x <= touch + d), None)
        if idx is None or idx < 5 or idx + 5 >= len(th):
            return None
        return (th[idx - 5] - th[idx + 5]) / 0.010
    faults = [e[1] for e in ev if e[1] in ("FSR_OVER", "FAULT_OVERCURRENT", "FAULT_SENSOR", "FAULT_STALL")]
    out.update({
        "t_contact_s": first("FSR_CONTACT"), "t_90_s": None if i90 is None else i90 / 1000,
        "t_sp_s": None if isp is None else isp / 1000, "t_hold_s": t_hold, "t_sat_s": sat,
        "hold_path": enter_hold[1] if enter_hold else None,
        "F_peak_N": max(F), "F_peak_grip_N": max(F[:grip_ms]),
        "F_hold_min_N": min(held) if held else None, "F_hold_mean_N": sum(held) / len(held) if held else None,
        "F_end_N": sum(tail) / len(tail), "sse_N": sum(F[grip_ms - 300:grip_ms]) / 300 - sp,
        "F_fold_N": pl.p["f_fold_n"], "folded": max(F) >= 0.98 * pl.p["f_fold_n"],
        "v_touch3_dps": v_at(3.0), "v_touch0_dps": v_at(0.0),
        "touch_deg": touch, "final_state": r.state(), "fault": L.sim_fault(), "relaxed": bool(L.sim_relaxed()),
        "faults": faults, "warns": sorted({e[1] for e in ev if e[1] in ("NO_CONTACT", "FORCE_SAT", "FSR_LOST", "FSR_SLIP")}),
        "states": [e[3] for e in ev],
    })
    if keep_series:
        out["series"] = {"F": F, "th": th, "th_cmd": thc, "F_fw": Ffw, "state": st}
        out["events"] = ev
    return out


def half_newton_angle(pl):
    """theta_eff at which the bare pads (no cloth) carry 0.5 N, by the same finger law as the plant."""
    ff = pl.p["f_fold_n"]
    s = plant_mod.finger_defl(0.5, pl.kA, ff) + plant_mod.finger_defl(0.5, pl.kB, ff)
    # closure s = 0 - gap -> gap = -s; gap = 1 + 2 r_c theta_rad; the B finger sits b/2 open under load.
    th_eff = math.degrees((-s - 1.0) / (2.0 * pl.r_c))
    return th_eff - pl.p["backlash_deg"] / 4.0   # theta_eff -> servo-side theta_A reference (A = eff - b/4)


if __name__ == "__main__":
    m = grip()
    for k, v in m.items():
        if k != "states":
            print(f"{k:16s} {v}")
