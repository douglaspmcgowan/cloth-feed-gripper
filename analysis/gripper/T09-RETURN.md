23 1 2 161

# T09 return: force cap, firmware floor and trip against the ruled 8 N (T09F, T09P)

## Candidates

Stacks: 100,000 builds, seed 20260922. Simulation: `analysis/gripper/controls/firmware_requests.py` (17-finger R12 window, 1,000 drawn grips, 300 at `G 7`, 300 early contacts), false trips shown as window / drawn / `G 7`.

| Candidate | (a) T09F trip failed | (a) T09P at the trip | (b) T09H | (c) false trips | Result |
|---|---|---|---|---|---|
| floor θ_c0 − 6.2° (round 2, was shipped) | FAIL, Cpk −0.03 | FAIL, 52.95 % (floor-bounded) | MARGINAL 1.28 | 0/17, 0/1,000, 2/300 | fails (a) |
| **floor θ_c0 − 4.9°, trip 7.75 N / 20 ms** | **PASS, Cpk 1.46** | **PASS, Cpk 1.46** | MARGINAL 1.28 (unchanged) | **0/17, 0/1,000, 2/300** | **meets (a)–(c)** |
| floor 5.0° | MARGINAL 1.32 | MARGINAL 1.33 | MARGINAL 1.28 | 0/17, 0/1,000, 2/300 | fails (a) |
| floor 5.1°, 5.2° | MARGINAL 1.21, 1.09 | MARGINAL 1.09 (5.2°) | MARGINAL 1.28 | not simulated | fails (a) |
| floor 5.3°, 5.4°, 5.5°, 5.6°, 5.8° | FAIL, Cpk ≤ 0.96 | not run | MARGINAL 1.28 | not simulated | fails (a) |
| trip 7.75 N / 20 ms alone | (does not act) | FAIL 11.53 %, Cpk −0.52 | — | 0/17, 0/1,000, 2/300 | fails (a) |
| trip 7.75/10, 7.75/0, 7.5/10, 7.5/0, 7.0/10, 6.5/10 | (does not act) | FAIL 17.68–93.23 % | — | 7.75/10: 0, 0, 2; 7.5/10: 0, 0, 3; 7.0/10: 9/17, 33, 21 | fails (a) |
| trip 6.0 N / 10 ms | (does not act) | MARGINAL, Cpk 1.02 | drawn R14 0.365 (0.570) | 13/17, 296/1,000, 95/300 | fails (a)–(c) |
| trip 5.5 N / 10 ms | (does not act) | PASS, Cpk 1.48 | drawn R14 0.200 | 15/17, 491/1,000, 155/300 | fails (a) on T09F, (b), (c) |

Count: 10 floors (4.9, 5.0, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.8, 6.2), 9 trips, 4 floor-plus-trip combinations (floors 4.9, 5.0, 5.2, 6.2 with trip 7.75 N / 20 ms bounding T09P).

## Decision and why

Applied `JAW_FLOOR_BELOW_C0_DEG` 6.2 → 4.9 in `firmware/gripper/config.h`; trip stays 7.75 N / 20 ms, `F_CAP_N` 10, `JAW_MIN_DEG` −10.2. It is the only candidate meeting (a), (b) and (c): T09F assumes the trip has failed, so no trip setting can pass it, and the floor bounds the peak at the trip as well. The squeeze cap (4.867°) still binds first, so T09H is unchanged (MARGINAL, Cpk 1.28) and the drawn R14 moves 0.571 → 0.570. The 2 `G 7` false trips were already present at 6.2°.

**Resolved in round 2 (below): `HOLD_BACKOFF_STEP_DEG` 0.3 → 0.33.** At the 4.9° floor, the former 0.3° F1 step left the rail-current ratio at 0.58 against the test limit of 0.55. The 0.33° step brings the worst ratio to 0.497 at the 4.9° floor and 0.499 at 6.2°, with the regression test unchanged.

Made the fix variant in `T09F` (`relfloor8`), `T09H` (`relfloor8`), `T09P` (`floor49`, new) and `rev_b.yaml`; rev B is now 22 PASS, 2 MARGINAL, 2 FAIL (T09T, T14B). Docs: `controls.md` 6.4 (dated table), `tolerance_stacks.md`, `RISK.md` (F35, F57, F58, F59), DESIGN-BASIS R15 dated note.

## Proving commands

| Command | Last line | Exit |
|---|---|---|
| `python analysis/gripper/tolstack/tolstack.py --check` | generated output current: 7 blocks, 83 files, 69 verdicts checked | 0 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider analysis/gripper/tolstack` | `ModuleNotFoundError: No module named 'pygments'` | 1 (round 3 environment) |
| `python ecad/gripper/calc/run_all.py --check` | check: all generated outputs match | 0 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider ecad/gripper/calc` | 201 passed in 1449.61s (0:24:09) (run on this branch before the master merge, which touched no ecad file) | 0 |
| `python firmware/gripper/test/run_host_tests.py` | PASS 2124 / 2124 checks | 0 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider analysis/gripper/firmware_sim` | 14 passed | 0 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider analysis/gripper/controls` | 2 failed, 26 passed (`test_hold_current_reading_sorts_the_regime`, both discontinuous fits; see *Open* above) | 1 |
| Controls sim, chosen candidate (`firmware_requests.py`, row `shipped`) | false trips 0 of 17 (window), 0 of 1,000 (drawn `G 5`); `G 7` 2 of 300, same as the 6.2° floor | 0 |
| `python analysis/gripper/controls/run_all.py` | gates.py: arduino-cli compile exit 1 (`esp_task_wdt_init` signature on esp32 core 3.3.8, not touched here; master recorded "not run"), host FSM test 0, simulation pytest 1 (the 2 failures above) | 1 |
| `git diff --check origin/master HEAD` | (no output) | 0 |

Wall time: the 3-hour ceiling was passed by about 20 minutes, spent on the full regeneration (tolstack sens and sweeps, controls `run_all`); the harness harvested and pushed the branch at the ceiling (`824cd39`).

Specs checked: INTENT.md (intent-gripper-complete), DESIGN-BASIS (R14, R15, D8), controls.md (4.4, 6.4), tolstack.py (docstring and `--help`), RISK.md (F57).

## Assumptions

- `analysis/gripper/controls/firmware_requests.py`, `analysis/gripper/firmware_sim/` (`build.py`, `test_firmware_sim.py`) and the regenerated `docs/gripper/test/` outputs are in scope as generators and tests a firmware constant feeds; edited outside the owned list.
- `basis.yaml` `F_trip` 8.0 was a stale copy of `config.h` `F_TRIP_N` 7.75; corrected to the firmware value (T09P base now 11.53 % within, was 4.47 %).
- T09P's floor-bounded variant uses the same samples as T09F (shared `servo_angle_error_at_floor`): the peak cannot pass the force at the floor.
- The firmware sim's per-finger R12 stiffness (0.88–1.63 N/mm) and the stack's pair stiffness (0.523–0.621 N/mm) are different quantities, not a source disagreement.
- `JAW_MIN_DEG` kept at −10.2 (binds only without a calibrated contact); `test_firmware_sim.py` now pins it exactly and checks it sits at or below `CAL_C0_MIN_DEG − JAW_FLOOR_BELOW_C0_DEG`.
- Host test `jaw floor relative to theta_c0`: first scenario `touchBelow` 2.0 → 1.2 so the touch sits above θ_c0 and the squeeze reaches U_MAX; assertions unchanged.
- Regenerated PNG figures were kept as produced by the generators (not byte-stable across matplotlib builds).
- `docs/gripper/test/` stall-trip currents (3.3 → 3.0 A, 3.6 → 3.1 A) were already stale on master since PR #83 and are regenerated here.

## Defects met

- `analysis/gripper/firmware_sim/build.py` rewrote `config.h` on every variant, forcing a rebuild of a DLL the process had already loaded (ld "Permission denied" on Windows), and pool workers raced copying the same sources (WinError 32). Fixed in this PR (`_copy_if_changed`; `config.h` written only on content change).
- `pytest ecad/gripper/calc` rewrites 7 tracked ecad files and `docs/gripper/analysis/electrical.md` with LF endings (no content change); restored by hand. Repository defect, not filed to the harness.
- `tolstack.py --check` reports input-digest drift on every `results/sweep_*.json` after a `basis.yaml` change, and no tolstack command regenerates all sweeps; rerun one by one from each JSON's stored parameters.
- Stop hook repeatedly asked to reformat TASK.md, which the brief forbids editing: filed as agent-harness intake `t09-stop-hook-taskmd-vs-brief`.
- `arduino-cli compile` (controls `run_all` gate) fails on this machine's esp32 core 3.3.8 at `esp_task_wdt_init`; outside this change, recorded in `firmware_sim/results/gates.json`.
- The 10-minute default background limit killed the first tolstack regeneration mid-`sens`; restarted from `sens` with a longer limit.

## Round 2: the hold-current regression

**Fixed; floor stays 4.9°, test unchanged.** `firmware/gripper/config.h` `HOLD_BACKOFF_STEP_DEG` 0.3 → 0.33.

**Root cause.** Not the floor's physics and not the fixture: the servo pulse is whole microseconds (`servo_map.h`, 1 µs = 0.09°), and F1 settles two steps short of the step that loses force, so its settled back-off is 6 or 7 µs depending on where the hold command rounds. At the 6.2° floor the hold command (−6.03°) rounded so two 0.3° steps gave 7 µs (0.63°, rail 0.50 of F4); at the 4.9° floor the command is −5.98° (pulse 1434 µs) and the same two steps give 6 µs (0.54°, rail 0.58). The fixture is the firmware's real hold point (nominal plant, `G 5`, a FORCE_SAT hold on either floor), so candidate (a) did not apply.

**Candidates** (`faults.py` fixture, four scenarios, rail ratio limit 0.55, true-force drop limit 0.1 N; 30 variants of step 0.27/0.30/0.315/0.33/0.36 × margin 0.15/0.20/0.25 × floor 4.9/6.2):

| Step, margin 0.2 | 4.9° floor: worst ratio / dF | 6.2° floor | Wider check (k 0.88–1.63 × 4 frame phases × 2 conductions, 48 holds): pass at 4.9° / 6.2° |
|---|---|---|---|
| 0.30 (was) | 0.582 / 0.019, FAIL | 0.497 / 0.019 | 38 / 44 |
| 0.27 | 0.494 / 0.070 | 0.494 / 0.064 | 41 / 38 |
| 0.315 | 0.497 / 0.023 | 0.496 / 0.023 | 41 / 41 |
| **0.33 (chosen)** | **0.497 / 0.023** | **0.499 / 0.027** | **43 / 44** |
| 0.36 | 0.773, FAIL | 0.496 / 0.030 | not run |

0.33 passes at both floors at margins 0.2 and 0.25, and its wider-check pass count at 4.9° (43/48) matches what 0.3 had at 6.2° (44/48). `HOLD_BACKOFF_FACTOR` (0.5) and `HOLD_BACKOFF_MARGIN_N` (0.2) unchanged: the factor's stop (0.25 × F4) is never reached first, so it cannot fix this.

**Thermal (thermal.md 5).** The settled motor-current factor is 0.49 (0.57 / 1.16 A, Fit A discontinuous), inside the 0.4225–0.63 window; `thermal.py` rerun: back-off hold case 35.6 °C, unchanged (it reads the factor, not the step).

**False trips.** F1 ships off (`HOLD_BACKOFF_ENABLED 0`), so the step does not enter the window / drawn / `G 7` grips: 0/17, 0/1,000, 2/300 stand from round 1. `firmware_requests.py` rerun started; see the table.

**Follow-up (not done):** make the F1 step a whole number of pulse microseconds in `holdBackoff` so the settled back-off no longer depends on the hold command's rounding (the wider check still fails 5/48).

| Round 2 command | Last line | Exit |
|---|---|---|
| `python analysis/gripper/tolstack/tolstack.py --check` | generated output current: 7 blocks, 83 files, 69 verdicts checked | 0 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider analysis/gripper/controls analysis/gripper/firmware_sim` | 42 passed in 462.58s (0:07:42) | 0 |
| `python ecad/gripper/calc/run_all.py --check` | check: all generated outputs match | 0 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider ecad/gripper/calc` | `ModuleNotFoundError: No module named 'pygments'` | 1 (round 3 environment) |
| `python firmware/gripper/test/run_host_tests.py` | PASS 2124 / 2124 checks | 0 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider analysis/gripper/thermal` | `ModuleNotFoundError: No module named 'pygments'` | 1 (round 3 environment) |
| `python cad/gripper/viewer_src/viewer_build.py` then `pytest cad/gripper/tests/test_viewer_static.py` | 26 passed, 1 skipped in 135.44s (0:02:15) | 0 |
| `python analysis/gripper/controls/firmware_requests.py` | `FileNotFoundError: [WinError 2] The system cannot find the file specified` (`g++` missing after the shipped row) | 1 |
| `git diff --check origin/master HEAD` | (no output) | 0 |

Specs checked: INTENT.md (intent-gripper-complete), DESIGN-BASIS (R14, R15, D8, R26), controls.md (4.3, 6.4), thermal.md (4.4, 5), RISK.md (F57).

Round 2 defects met:
- Round 2 was dispatched while the round 1 session (PID 46120) was still running and committing in this worktree (704425e, d724d6b, 0fb3981, PR #101): two writers. Filed as agent-harness intake `t09-round2-dispatched-while-round1-alive`. Round 2 committed only its own paths by name; `controls.md` 6.4 and the tolstack test edits round 1 holds uncommitted were left to it, so `controls.md` 6.4's *Open* line is not updated here.
- `gh pr create` was not run: round 1 had already opened draft PR #101 for this branch; its body is updated instead.
- The controls `run_all.py` and the first `thermal.py` run were stopped by the 1-hour background limit on a host loaded by other lanes (montecarlo `before` alone took 1,075 s); `faults.py` and `thermal.py` outputs were complete and are committed, the montecarlo / design-sweep outputs were not regenerated (F1 is off in them except the design-sweep F1 row).

## Round 4 status

Round 3 dependency and compiler failures are superseded by this Linux run. The controls regression was not a bad tolerance or a bad test: Round 3 could not rebuild the firmware simulation because `g++` was absent, so it exercised the stale Windows shared library from before `HOLD_BACKOFF_STEP_DEG` changed from 0.30° to 0.33°. A clean Linux rebuild uses the already-committed 0.33° fix; both discontinuous fits pass with the original 0.55 rail-current ratio and 0.1 N force-drop limits. No tolerance or assertion was changed.

`analysis/gripper/controls/run_all.py` completed with exit 0, including `bench_k14`, `design_sweep.py`, `firmware_requests.py`, and all controls Monte Carlo cases. It reported `arduino-cli compile exit None not run: arduino-cli not found`, as expected. `cad/gripper/viewer_src/viewer_build.py` also completed with exit 0. The current generated controls and firmware-simulation outputs smaller than 500 KB are committed; the larger host-regenerated artifacts listed below intentionally remain byte-for-byte at `c74d1e3`. The viewer static suite therefore uses the `c74d1e3` gate record paired with that viewer; the current Arduino not-run result is recorded here instead of making a 13.4 MB viewer commit.

| Round 4 proving command | Last line | Exit |
|---|---|---|
| `python analysis/gripper/tolstack/tolstack.py --check` | `generated output current: 7 blocks, 83 files, 69 verdicts checked` | 0 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider analysis/gripper/tolstack` | `642 passed in 1494.72s (0:24:54)` | 0 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider analysis/gripper/controls analysis/gripper/firmware_sim analysis/gripper/thermal` | `63 passed in 10.05s` | 0 |
| `python ecad/gripper/calc/run_all.py --check` | `check: all generated outputs match` | 0 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider ecad/gripper/calc` | `201 passed in 183.82s (0:03:03)` | 0 |
| `python firmware/gripper/test/run_host_tests.py` | `PASS 2124 / 2124 checks` | 0 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider cad/gripper/tests/test_viewer_static.py` | `26 passed, 1 skipped, 1 warning in 6.75s` | 0 |
| `git diff --check c74d1e3 HEAD` | `(no output)` | 0 |

### Host regeneration

These files exceed 500 KB and remain at their `c74d1e3` content to keep the Cloud diff extractable. Sizes are the regenerated sizes observed on this Linux host. Run the exact command shown from the repository root after landing this diff.

| File | Regenerated size | Exact regeneration command |
|---|---:|---|
| `cad/gripper/viewer.html` | 13,387,032 bytes | `python cad/gripper/viewer_src/viewer_build.py` |
| `analysis/gripper/controls/results/montecarlo.json` | 1,370,494 bytes | `python analysis/gripper/controls/montecarlo.py` |
| `analysis/gripper/controls/results/montecarlo_before.json` | 1,360,488 bytes | `python analysis/gripper/controls/montecarlo.py --tag before --set GAIN_SCHED_ENABLED=0,F_HOLD_BIAS_N=0,F_CAP_MARGIN_N=0,STALL_CURRENT_HOLD_A=1.8` |
| `analysis/gripper/controls/results/montecarlo_bench.json` | 1,374,292 bytes | `python analysis/gripper/controls/montecarlo.py --tag bench --set FINGER_K_MAX_N_PER_MM=1.21 --range k_tip_n_per_mm=1.045:1.155,span_mount=0.97:1.03,tau_s=0.035:0.045,dead_ms=8:12` |
| `analysis/gripper/controls/results/montecarlo_bench_k14.json` | 688,485 bytes | `python analysis/gripper/controls/montecarlo.py --tag bench_k14 --n 1000 --set FINGER_K_MAX_N_PER_MM=1.54 --range k_tip_n_per_mm=1.33:1.47,span_mount=0.97:1.03,tau_s=0.035:0.045,dead_ms=8:12` |
| `analysis/gripper/controls/results/montecarlo_g6.json` | 689,885 bytes | `python analysis/gripper/controls/montecarlo.py --tag g6 --n 1000 --sp 6` |
| `analysis/gripper/controls/results/montecarlo_g7.json` | 689,152 bytes | `python analysis/gripper/controls/montecarlo.py --tag g7 --n 1000 --sp 7` |
| `analysis/gripper/controls/results/montecarlo_nocal.json` | 681,724 bytes | `python analysis/gripper/controls/montecarlo.py --tag nocal --n 1000 --range span_mount=0.5:1.5` |
| `analysis/gripper/controls/results/montecarlo_early.json` | 685,870 bytes | `python analysis/gripper/controls/montecarlo.py --tag early --n 1000 --early` |

Specs checked: `INTENT.md` (`intent-gripper-complete`); `docs/gripper/DESIGN-BASIS.md` (R14, R15, D8, R26); `docs/gripper/analysis/controls.md` (4.3, 6.4); `docs/gripper/analysis/thermal.md` (4.4, 5); `docs/gripper/RISK.md` (F57).

Round 4 assumptions:
- The `c74d1e3` revision is already based on the newest master ref available in this checkout; no local or remote `master` ref is present, and network access is unavailable, so there was nothing newer to merge.
- Generated artifacts larger than 500 KB and the viewer-coupled `gates.json` are deliberately restored after proving regeneration; current results are captured in this section and the small generated outputs.

Round 4 defects met:
- `cadquery` is installed but cannot import because the container lacks `libGL.so.1`; the viewer test skips its optional CadQuery-dependent check and reports the environment warning.
- `arduino-cli` is absent, so the compile gate cannot run; this is required to be recorded rather than worked around.
- Replacing only the 13.4 MB viewer with its `c74d1e3` version while retaining a newly written `gates.json` makes `test_committed_viewer_matches_build` fail. The matched `c74d1e3` gate record was restored too; the first static run exposed this coupling, and the required rerun passed.

## Round 3 status

> **Superseded by Round 4:** the Linux environment provides the dependencies and compiler missing in Round 3; current results are recorded below.

The shipped, before, bench, G 6, G 7, no-CAL and early-contact Monte Carlo cases were rerun with their recorded parameters; their generated files match the committed results. All seven `sweep_*.json` input digests match the current tolerance inputs, so none needed regeneration. The ECAD generated-output check passed, and the cached host test executable (built after the firmware sources) passed 2,124/2,124 checks. The required host build command itself could not start because `g++` is absent. `bench_k14`, `design_sweep.py` and `firmware_requests.py` also need new firmware variants and stopped at the missing compiler. The Arduino compile was run on the installed ESP32 core 3.3.8 and failed at the existing `esp_task_wdt_init` signature mismatch. `tolstack.py --check` could not import `yaml`; the required pytest commands could not import `pygments`, and the first controls `run_all.py` step could not import `packaging` through matplotlib. A `pip` install was blocked by the environment hook pending `allow-env`.

| Round 3 proving command | Last line | Exit |
|---|---|---|
| `python analysis/gripper/tolstack/tolstack.py --check` | `ModuleNotFoundError: No module named 'yaml'` | 1 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider analysis/gripper/tolstack` | `ModuleNotFoundError: No module named 'pygments'` | 1 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider analysis/gripper/controls analysis/gripper/firmware_sim analysis/gripper/thermal` | `ModuleNotFoundError: No module named 'pygments'` | 1 |
| `python ecad/gripper/calc/run_all.py --check` | `check: all generated outputs match` | 0 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider ecad/gripper/calc` | `ModuleNotFoundError: No module named 'pygments'` | 1 |
| `python firmware/gripper/test/run_host_tests.py` | `FileNotFoundError: [WinError 2] The system cannot find the file specified` (`g++` absent) | 1 |
| `python -m pytest -q -p no:xdist -p no:cacheprovider cad/gripper/tests/test_viewer_static.py` | `ModuleNotFoundError: No module named 'pygments'` | 1 |
| `git diff --check origin/master HEAD` | (no output) | 0 |

🤖 Generated with [Claude Code](https://claude.com/claude-code)
