"""Replays the named worst Monte Carlo draws (results/worst_cases.json, written by montecarlo.py) and the injected
faults through the compiled firmware, so a firmware change that worsens a tail case fails here.
Run from the repository root:  python -m pytest analysis/gripper/controls -q"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import faults  # noqa: E402
import loop  # noqa: E402
import montecarlo as mc  # noqa: E402

WORST = json.loads((HERE / "results/worst_cases.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module", autouse=True)
def repo_firmware():
    loop.configure(None)
    mc.RANGE, mc.FIX = {}, {}


@pytest.mark.parametrize("name", sorted(WORST))
def test_worst_case_replays_and_stays_safe(name):
    w = WORST[name]
    r = mc.one((mc.SEED, w["i"]))
    m = r["m"]
    assert r["p"] == pytest.approx(w["p"])                              # same draw from (seed, i)
    # Deterministic replay: the recorded metrics come back (a firmware change shows up here first).
    for k in ("F_peak_N", "t_90_s", "F_hold_min_N", "final_state"):
        # relative 1e-3: the committed worst_cases.json is the reference; float results may differ by CPU/compiler.
        assert m.get(k) == pytest.approx(w["m"].get(k), rel=1e-3, abs=1e-3) if isinstance(w["m"].get(k), float) \
            else m.get(k) == w["m"].get(k), (name, k)
    # Safety invariants hold even in the tails: R15 (10 N and the 8 N reading) and no fold.
    assert m["F_peak_N"] <= 8.0
    assert not m["folded"]
    assert m["final_state"] in ("HOLD", "FEED", "FAULT", "RELEASE", "RETRACT")


def test_injected_faults_reach_a_safe_state_in_time():
    loop.lib()
    short = faults.case_fsr_short()
    assert short["state"] == "FAULT" and short["t_safe_ms"] is not None and short["t_safe_ms"] <= 300
    stall = faults.case_stall_in_close()
    assert stall["state"] == "FAULT" and stall["fault"] == 3                  # FAULT_OVERCURRENT
    assert stall["t_safe_ms"] - stall["t_overcurrent_onset_ms"] <= 200       # R20
    blind = faults.case_fsr_open_before_grip(disc=1)
    assert blind["state"] == "FAULT" and blind["fault"] == 9                  # FAULT_FSR_OPEN
    blind_c = faults.case_fsr_open_before_grip(disc=0)                       # continuous drive: a miss, released
    assert blind_c["state"] in ("RELEASE", "RETRACT", "IDLE") and blind_c["t_safe_ms"] is not None
    stuck = faults.case_limit_stuck()
    assert stuck["state"] == "FAULT" and stuck["fault"] == 8                  # FAULT_LIMIT
    stuck_adc = faults.case_fsr_stuck_in_hold()
    assert stuck_adc["state"] == "FAULT" and stuck_adc["fault"] == 10                # FAULT_FSR_STUCK
    half = faults.case_fsr_half_span_stiffest()
    assert half["F_peak_N"] <= 8.0
    ina = faults.case_ina219_fails_in_hold()
    assert ina["state"] == "FAULT" and ina["fault"] == 11 and ina["t_safe_ms"] <= 400   # FAULT_I_SENSOR
    brown = faults.case_brownout_in_hold()
    assert brown["t_safe_ms"] <= 300


def test_slip_reported_in_a_force_sat_hold():
    # Nominal finger k 1.1 enters HOLD at the squeeze cap (FORCE_SAT); the FSR span then halves: FSR_SLIP is posted.
    loop.lib()
    r = faults.case_fsr_half_span_in_hold()
    assert r["hold_path"] == "FORCE_SAT"
    assert r["t_slip_ms"] is not None and r["t_slip_ms"] <= 300


@pytest.mark.parametrize("scenario", [s[0] for s in faults.SCENARIOS])
def test_stall_detected_after_contact_and_in_hold(scenario):
    # R20 in every state: a stall after contact (rigid object) and in HOLD (locked rotor) trips over-current and
    # backs off within 200 ms of the rail passing the trip, for Fit A and Fit B, either conduction regime.
    loop.lib()
    _, fit, disc = next(s for s in faults.SCENARIOS if s[0] == scenario)
    for case in (faults.case_stall_after_contact(fit, disc), faults.case_stall_in_hold(fit, disc)):
        assert case["state"] == "FAULT" and case["overcurrent"]
        assert case["t_detect_after_onset_ms"] <= 200


@pytest.mark.parametrize("scenario", [s[0] for s in faults.SCENARIOS])
def test_hold_current_reading_sorts_the_regime(scenario):
    # F4: the hold reading with the back-off off is under 0.75 A for continuous conduction and over it for
    # discontinuous (thermal.md 0), and F1 at least halves the rail current while the true force drops < 0.1 N.
    loop.lib()
    _, fit, disc = next(s for s in faults.SCENARIOS if s[0] == scenario)
    h = faults.case_hold_current(fit, disc)
    off, on = h["backoff_off"], h["backoff_on"]
    assert (off["F4_reading_A"] > 0.75) == bool(disc)
    assert on["rail_A"] <= 0.55 * off["rail_A"]
    assert off["F_true_N"] - on["F_true_N"] < 0.1
