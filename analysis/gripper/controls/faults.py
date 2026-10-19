"""Fault injection through the simulation: the compiled firmware core against the plant.py plant, nominal draw.
Each case runs a normal grip to HOLD (or into CLOSE), injects one fault, and measures how long the firmware takes
to reach a safe state: FAULT entered (or RELEASE for a miss) AND the true pad force below 0.5 N (cloth unloaded),
or for a stall the pulse detached / the rail current back under the trip.

Run from the repository root:  python analysis/gripper/controls/faults.py
Writes results/faults.json and results/faults_stdout.txt."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import loop  # noqa: E402
import plant as P  # noqa: E402

RES = HERE / "results"


def to_hold(r, sp=5.0, max_ms=2000):
    r.pl.cloth = True
    r.L.sim_post(loop.EV["CMD_GRIP"], sp)
    for i in range(max_ms):
        r.step()
        if r.state() == "HOLD" and i > 300:
            break
    for _ in range(300):
        r.step()
    return r.state()


def watch(r, max_ms, until):
    t0 = r.L.sim_now()
    t_fault = None
    t_over = None
    fmax = r.pl.F
    for _ in range(max_ms):
        r.step()
        fmax = max(fmax, r.pl.F)
        if t_over is None and r.pl.I > loop.cfg("STALL_CURRENT_A"):
            t_over = r.L.sim_now() - t0
        if t_fault is None and r.state() in ("FAULT", "RELEASE", "RETRACT"):
            t_fault = r.L.sim_now() - t0
        if until(r):
            return {"t_state_ms": t_fault, "t_safe_ms": r.L.sim_now() - t0, "t_overcurrent_onset_ms": t_over,
                    "t_fault_after_onset_ms": (t_fault - t_over) if (t_fault is not None and t_over is not None) else None, "state": r.state(),
                    "fault": r.L.sim_fault(), "F_max_after_N": fmax, "F_now_N": r.pl.F, "relaxed": bool(r.L.sim_relaxed())}
    return {"t_state_ms": t_fault, "t_safe_ms": None, "state": r.state(), "fault": r.L.sim_fault(),
            "F_max_after_N": fmax, "F_now_N": r.pl.F, "relaxed": bool(r.L.sim_relaxed())}


def unloaded(r):
    return r.state() in ("FAULT", "RELEASE", "RETRACT") and r.pl.F < 0.5


def case_fsr_short():
    r = loop.Run(P.nominal(), seed=11)
    assert r.boot()
    s0 = to_hold(r)
    r.pl.fsr_short = True
    return dict(watch(r, 2000, unloaded), before=s0)


def case_fsr_open_in_hold():
    r = loop.Run(P.nominal(), seed=12)
    assert r.boot()
    s0 = to_hold(r)
    r.pl.fsr_open = True
    return dict(watch(r, 2000, unloaded), before=s0)


def case_fsr_open_before_grip(disc=0):
    # The check needs >= FSR_OPEN_I_A on the rail at the search end: met when the drive conducts discontinuously
    # (rail = motor current), missed when it conducts continuously (rail ~ I_m^2 / I_stall): then it is a miss.
    r = loop.Run(dict(P.nominal(), disc_conduction=disc), seed=13)
    assert r.boot()
    r.pl.fsr_open = True
    r.pl.cloth = True
    r.L.sim_post(loop.EV["CMD_GRIP"], 5.0)
    return watch(r, 3000, unloaded)


def case_stall_in_close():
    # A rigid obstruction stops finger A 8 deg above the cloth during the fast leg (a jammed finger, R20).
    r = loop.Run(P.nominal(), seed=14)
    assert r.boot()
    r.pl.cloth = True
    r.pl.blocked_at = r.L.sim_theta_c0() + 8.0
    r.L.sim_post(loop.EV["CMD_GRIP"], 5.0)
    return watch(r, 3000, lambda rr: rr.state() == "FAULT" and (rr.L.sim_relaxed() or rr.pl.I < 1.8))


def case_limit_stuck():
    r = loop.Run(P.nominal(), seed=15)
    assert r.boot()
    r.limit_stuck = True
    r.pl.cloth = True
    r.L.sim_post(loop.EV["CMD_GRIP"], 5.0)
    return watch(r, 3000, unloaded)


def case_brownout_in_hold():
    r = loop.Run(P.nominal(), seed=16)
    assert r.boot()
    s0 = to_hold(r)
    r.L.sim_reset_mcu(r.raw)
    r.L.sim_clear_events()
    t0 = r.L.sim_now()
    for _ in range(3000):
        r.step()
        if r.pl.F < 0.5:
            break
    t_unload = r.L.sim_now() - t0
    # It then re-homes and recalibrates; with cloth still in the jaw the calibration search touches early.
    for _ in range(6000):
        r.step()
        if r.state() in ("IDLE", "FAULT"):
            break
    return {"before": s0, "t_safe_ms": t_unload, "state_after_rehome": r.state(), "fault": r.L.sim_fault()}


def case_serial_garbage_in_hold():
    # Every byte pattern from the host-test fuzz reaches the core only through parseCommand; here the parsed
    # extremes are posted straight into the core during HOLD: G with inf and huge values, and a NaN.
    r = loop.Run(P.nominal(), seed=17)
    assert r.boot()
    s0 = to_hold(r)
    fmax = 0.0
    for arg in (float("inf"), 1e30, float("nan"), -5.0, 0.0):
        r.L.sim_post(loop.EV["CMD_GRIP"], arg)
        for _ in range(400):
            r.step()
            fmax = max(fmax, r.pl.F)
    return {"before": s0, "state": r.state(), "F_max_N": fmax, "t_safe_ms": 0}


def case_fsr_stuck_in_hold():
    # The ADC conversion freezes at its present value while a grip is held (review 2026-10-11, finding 2).
    r = loop.Run(P.nominal(), seed=18)
    assert r.boot()
    s0 = to_hold(r)
    frozen = r.raw
    r.pl.adc_mv = lambda: frozen
    return dict(watch(r, 3000, unloaded), before=s0, frozen_mv=frozen)


def case_fsr_half_span_stiffest():
    # An FSR reading 50 % (no CALF, delaminated backing) on the stiffest R12 finger with the stiffest servo: the
    # squeeze cap alone bounds the true force. Compare the W2b-1 linear plant (firmware_sim, 9.66 N).
    p = dict(P.nominal(), k_tip_n_per_mm=1.63, span_mount=0.5, droop_deg_at_stall=1.5, f_fold_n=10.6, plies=1,
             ply_mm=0.2, k_ply_n_per_mm=60.0)
    m = loop.grip(p, seed=19)
    return {"F_peak_N": m["F_peak_N"], "state": m["final_state"], "warns": m["warns"], "t_safe_ms": 0}


def case_fsr_half_span_in_hold():
    # The FSR span halves mid-hold (backing delaminates) on the nominal finger (k 1.1), whose grip enters HOLD at the
    # squeeze cap (FORCE_SAT). Slip must be reported in that hold too (review 2026-10-11: it was not).
    r = loop.Run(P.nominal(), seed=20)
    assert r.boot()
    r.L.sim_clear_events()
    s0 = to_hold(r)
    path = next((e[1] for e in loop.events(r.L) if e[3] == "HOLD"), None)
    r.pl.p["span_mount"] *= 0.5
    t0 = r.L.sim_now()
    t_slip = None
    for _ in range(1500):
        r.step()
        if t_slip is None and any(e[1] == "FSR_SLIP" for e in loop.events(r.L)):
            t_slip = r.L.sim_now() - t0
    return {"before": s0, "hold_path": path, "t_slip_ms": t_slip, "state": r.state(), "F_now_N": r.pl.F, "t_safe_ms": 0}


def case_ina219_fails_in_hold():
    # The INA219 answered at boot, then stops answering mid-hold (loose I2C wire): FAULT I_SENSOR, cloth released.
    r = loop.Run(P.nominal(), seed=24)
    assert r.boot()
    s0 = to_hold(r)
    r.ina = False
    return dict(watch(r, 2000, unloaded), before=s0)


# Thermal scenarios (thermal.md 0), re-based on the DS3230 MG (A32): Fit A takes the 3.99 A sizing stall current, Fit B
# the 3.75 A datasheet value at 6.5 V (3.5 @5.0, 3.8 @6.8 [S]); the servo drive conducts continuously or discontinuously.
# M6 and the F4 reading decide which.
SCENARIOS = [("Fit B, continuous", 3.75, 0), ("Fit B, discontinuous", 3.75, 1), ("Fit A, continuous", 3.99, 0),
             ("Fit A, discontinuous", 3.99, 1)]


def scen(fit, disc, **kw):
    return dict(P.nominal(), istall_a=fit, disc_conduction=disc, **kw)


def case_hold_current(fit, disc):
    """F4: the rail current the INA219 reads in a 5 N hold with the F1 back-off off, then with it on."""
    out = {}
    for bo in (0.0, loop.cfg("HOLD_BACKOFF_FACTOR")):
        r = loop.Run(scen(fit, disc), seed=21)
        assert r.boot()
        r.L.sim_set_backoff(bo)
        s0 = to_hold(r)
        I, F = [], []
        for _ in range(2500):
            r.step()
            I.append(r.pl.I)
            F.append(r.pl.F)
        key = "backoff_off" if bo == 0.0 else "backoff_on"
        out[key] = {"state": r.state(), "before": s0, "F4_reading_A": r.L.sim_hold_i_ref(), "rail_A": sum(I[-500:]) / 500,
                    "motor_A": r.pl.I_motor, "F_true_N": sum(F[-500:]) / 500, "backoff_deg": r.L.sim_boff()}
    return out


def case_stall_after_contact(fit, disc):
    # A rigid object stops finger A just after FSR contact (R20 after contact): the loop squeezes to its cap
    # against it and the servo stalls.
    r = loop.Run(scen(fit, disc), seed=22)
    assert r.boot()
    r.pl.cloth = True
    r.L.sim_post(loop.EV["CMD_GRIP"], 5.0)
    for _ in range(2000):
        r.step()
        if r.L.sim_force_on():
            break
    r.pl.blocked_at = r.pl.thA
    return watch_stall(r)


def case_stall_in_hold(fit, disc):
    # In HOLD the rotor locks at full duty (a jammed gear train): the rail draws the stall current (R20 in HOLD).
    r = loop.Run(scen(fit, disc), seed=23)
    assert r.boot()
    s0 = to_hold(r)
    r.pl.rotor_locked = True
    return dict(watch_stall(r), before=s0)


def watch_stall(r, max_ms=1500):
    trip = loop.cfg("STALL_CURRENT_HOLD_A")
    t0 = r.L.sim_now()
    t_over = t_state = None
    for _ in range(max_ms):
        r.step()
        if t_over is None and r.pl.I > trip:
            t_over = r.L.sim_now() - t0
        if t_state is None and r.state() in ("FAULT", "RELEASE", "RETRACT"):
            t_state = r.L.sim_now() - t0
            break
    ev = [e[1] for e in loop.events(r.L)]
    return {"state": r.state(), "fault": r.L.sim_fault(), "t_onset_ms": t_over, "t_state_ms": t_state,
            "t_detect_after_onset_ms": (t_state - t_over) if (t_state is not None and t_over is not None) else None,
            "rail_A": r.pl.I, "overcurrent": "FAULT_OVERCURRENT" in ev, "t_safe_ms": t_state}


CASES = [("FSR short in HOLD", case_fsr_short), ("FSR open in HOLD", case_fsr_open_in_hold),
         ("FSR open before the grip, continuous", case_fsr_open_before_grip),
         ("FSR open before the grip, discontinuous", lambda: case_fsr_open_before_grip(1)), ("stall (finger jammed) in CLOSE", case_stall_in_close),
         ("limit switch stuck closed", case_limit_stuck), ("brown-out reset in HOLD", case_brownout_in_hold),
         ("serial extremes in HOLD", case_serial_garbage_in_hold), ("FSR stuck (ADC frozen) in HOLD", case_fsr_stuck_in_hold),
         ("FSR reads 50 %, stiffest finger", case_fsr_half_span_stiffest),
         ("FSR span halves in a FORCE_SAT hold", case_fsr_half_span_in_hold),
         ("INA219 fails in HOLD", case_ina219_fails_in_hold)]
for _name, _fit, _disc in SCENARIOS:
    CASES += [(f"hold current, {_name}", lambda f=_fit, d=_disc: case_hold_current(f, d)),
              (f"stall after contact, {_name}", lambda f=_fit, d=_disc: case_stall_after_contact(f, d)),
              (f"stall in HOLD, {_name}", lambda f=_fit, d=_disc: case_stall_in_hold(f, d))]


def main():
    loop.lib()
    out = {}
    lines = []
    for name, fn in CASES:
        res = fn()
        out[name] = res
        fmt = lambda v: f"{v:.2f}" if isinstance(v, float) else (  # noqa: E731
            "{" + ", ".join(f"{a} {fmt(b)}" for a, b in v.items()) + "}" if isinstance(v, dict) else f"{v}")
        lines.append(f"{name:32s} " + "  ".join(f"{k} {fmt(v)}" for k, v in res.items()))
    RES.mkdir(exist_ok=True)
    (RES / "faults.json").write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    (RES / "faults_stdout.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
