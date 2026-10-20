"""Refresh B40 prose from the regenerated cold and hot tolstack results."""
from pathlib import Path


def revise(name, changes):
    path = Path(name)
    body = path.read_text(encoding="utf-8")
    for old, new in changes:
        count = body.count(old)
        if count != 1:
            raise SystemExit(f"{name}: expected one match, found {count}: {old[:90]}")
        body = body.replace(old, new)
    path.write_text(body, encoding="utf-8", newline="\n")


revise("cad/gripper/CHANGELOG.md", [
    ("done; T14B still the thinnest mechanical check and FAILS (T14B Cpk 0.98 in the combined rev B run, 0.66 hot); Oldham disc under requested changes",
     "done; B40 shoulders bring the combined rev B dog coupling to MARGINAL (T14B Cpk 1.11), though the hot-seat scenario still FAILS (0.75 hot); coupon validation remains required"),
    ("T14B-boss34 now FAILS. Consequence for assembly:",
     "T14B-boss34 failed at this pre-B40 step; the B40 shoulder brings the cold option to MARGINAL (Cpk 1.10). Consequence for assembly:"),
])

revise("docs/gripper/analysis/tolerance_stacks.md", [
    ("**Rev B as one set: 23 of 26 checks PASS, 2 are MARGINAL, 1 FAIL**",
     "**Rev B as one set: 23 of 26 checks PASS, 3 are MARGINAL, 0 FAIL**"),
    ("The remaining FAIL is mechanical: T14B, the dog coupling, Cpk 0.98, 99.84 % yield.",
     "The dog coupling T14B is MARGINAL: Cpk 1.11, 99.952 % yield with the B40 shoulders."),
    ("Hot (PETG seat relaxed) it fails: Cpk 0.66.",
     "Hot (PETG seat relaxed) it fails: Cpk 0.75, 98.76 % yield."),
    ("T14B changes from MARGINAL to FAIL; every other combined rev B check keeps its verdict.",
     "The pre-B40 web re-base made T14B FAIL; the B40 shoulder restores a MARGINAL cold verdict. Every other combined rev B check keeps its verdict."),
    ("T14B-boss34: 40.68 % -> 99.84 % yield (FAIL -> FAIL, Cpk 0.98). The added web and servo-axis tilt terms make it the only rev B failure.",
     "T14B-boss34: 40.68 % -> 99.952 % yield in the combined B40 run (FAIL -> MARGINAL, Cpk 1.11). The web and servo-axis tilt terms still require coupon validation."),
    ("**Rev B does not pass as a whole: T14B FAILS; T09H and T16 stay MARGINAL. T09T passes the ruled R19 limit.** The thinnest mechanical check under the combined set is T14B (dog coupling), Cpk 0.98, 99.84 % yield, worst case -0.287 ... 0.238 mm against 0 mm interference.",
     "**Rev B has no FAIL; T09H, T14B and T16 are MARGINAL. T09T passes the ruled R19 limit.** The combined B40 dog coupling T14B has Cpk 1.11, 99.952 % yield, worst case -0.277 ... 0.201 mm against 0 mm interference."),
    ("Prints, but fails: slot 3.4 gives T14B Cpk 0.96 in the sweep (0.98 with every rev B change, `results/rev_b/REVB.md`), and 3.4 costs the closure window; consider an Oldham disc (buy)",
     "B40's 3.4 mm slot gives the combined T14B MARGINAL, Cpk 1.11 (`results/rev_b/REVB.md`), while its lash costs closure margin; gauge the shoulder and slot before assembly"),
    ("T14B from FAIL (Cpk 0.98) to FAIL (Cpk 0.66, 97.64 % yield)",
     "T14B from MARGINAL (Cpk 1.11, 99.952 % yield) to FAIL (Cpk 0.75, 98.76 % yield)"),
    ("T14B-boss34 therefore changes MARGINAL → FAIL. A slot of 3.42 mm is the smallest 0.02 mm increment that restores the prior margin: its extra 0.010 mm half-clearance raises Cpk by about 0.07, from 0.98 to 1.05; this is not a design change and T09 must still be checked. A zero-lash offset coupling remains robust.",
     "At the pre-B40 web re-base, T14B-boss34 changed from MARGINAL to FAIL. The B40 Ø2.9 shoulder restores the cold option to MARGINAL, Cpk 1.10, without widening the 3.4 mm slot; T09-b40_shoulder34 passes at Cpk 1.39. The hot-seat scenario still fails and requires a coupon."),
])

revise("docs/gripper/RISK.md", [
    ("rev B hot: 97.64 % yield, Cpk 0.66", "rev B hot: 98.76 % yield, Cpk 0.75"),
    ("falling further (97.64 % yield, Cpk 0.66)", "falling to 98.76 % yield, Cpk 0.75"),
    ("(the T14B fix still FAILS: Cpk 0.98, 0.66 hot)",
     "(the B40 T14B fix is MARGINAL cold at Cpk 1.11 and still FAILS hot at Cpk 0.75)"),
    ("T14B-boss34 (Cpk 0.98) is still under it, so the coupon decides them.",
     "T14B-boss34 (Cpk 1.10) is MARGINAL on assumed dimensions, so the coupon still decides it."),
    ("**Rev B passes as a set except three checks.** The combined run (`tolerance_stacks.md`, *Combined rev B run*) leaves 21 of 26 checks PASS, 2 MARGINAL (T09H, T16) and 3 FAIL (T09P, T09T, T14B; T14B Cpk 0.98, F61).",
     "**Rev B has no FAIL in the cold combined run.** The combined run (`tolerance_stacks.md`, *Combined rev B run*) has 23 of 26 checks PASS and 3 MARGINAL (T09H, T14B, T16; T14B Cpk 1.11, F61)."),
])
