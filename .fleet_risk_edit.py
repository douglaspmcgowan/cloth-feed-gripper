"""Update only the B40 dog coupling rows of RISK.md."""
from pathlib import Path


path = Path(__file__).resolve().parent / "docs/gripper/RISK.md"
lines = path.read_text(encoding="utf-8").splitlines()
changes = {
    "| 6 | F61 |": "| 6 | F61 | Dog coupling: the as-drawn M3 dogs bind in 59.32 % of builds (T14B, 40.68 % yield); side load on the servo bearing and pin A | 216 | B40: Ø9 boss location, hardened Ø2.9 shoulder dogs in Ø6 steel inserts, and the 3.4 mm slots; T14B-boss34 is MARGINAL at Cpk 1.10, 99.94 % yield [D SUMMARY.md]. The hot-seat case still needs a coupon | Coupon item 8 plus a fitted-servo turn through −11°…+20°. Fail: binding, insert movement, or lash beyond ±1.7° [A; (3.4 − 0.1 − 2.9) / (2 × 7 mm) rad] |",
    "| F46 |": "| F46 | R1 | Assembly: dog pins | Drive knuckle A from the horn | A short or loose dog fails to reach the knuckle slot | Dog leaves the slot; knuckle A uncouples | B40 replaces the old M3×8 / M3×10 screw mismatch with custom M3×10 hardened shoulder dogs threaded into Ø6×3×3 steel horn inserts; the model has 3.0 mm engagement and 0.5 mm floor clearance [D CAD / dog_check.py]. Retention is [A] pending a coupon | Build step and coupon | 7 | 6 | 3 | 126 | Gauge dog projection and insert retention after assembly; reject below 3.0 mm engagement or any hand movement [A] | BOM; `cad/gripper/params.json` (servo.dog_pin) |",
    "| F61 |": "| F61 | R1 | Mechanical: dog coupling | Turn knuckle A from the servo shaft without side load | Servo shaft offset exceeds the dog slot tangential clearance | Dogs jam; servo bearing and pin A take side load, with friction, stiction and wear | As-drawn T14B: FAIL, 40.68 % yield, Cpk −0.06 [D SUMMARY.md]. B40 boss-located Ø2.9 hardened shoulders in Ø6 inserts and 3.4 mm slots: T14B-boss34 option MARGINAL, 99.94 % yield, Cpk 1.10; T09-b40_shoulder34 PASS, Cpk 1.39 [D tolstack results]. Shoulder diameter and printed-slot bias remain assumptions | Step 26 range run [D ASSEMBLY.md] | 6 | 9 | 4 | 216 | Coupon item 8 and fitted-servo hand turn through −11°…+20°; gauge the slot, shoulder and boss fit. Fail: binding or stiction, insert movement, or lash beyond ±1.7° [A; (3.4 − 0.1 − 2.9) / (2 × 7 mm) rad] | `cad/gripper/params.json` (knuckle.dog_slot_w, servo.horn_insert_od) |",
    "| F67 |": "| F67 | R1, R25 | Mechanical: dog coupling | Retain two hardened shoulder dogs and their steel inserts in the horn | A threaded joint or press fit relaxes, or the 1 mm aluminium rim cracks | Dog lash grows; a dog leaves its slot; knuckle A uncouples; one-sided jaw | B40 uses custom M3×10 Ø2.9 smooth-shoulder dogs in Ø6×3×3 steel inserts at r 7 in a Ø22 aluminium horn. The one-dog stall check gives bending SF 1.48, steel bearing SF 1.27, aluminium bearing SF 1.13 [A allowables; D dog_check.py]. Thread strength, press-fit strength, horn rim fatigue and machined dimensions are unmeasured | Coupon before assembly [A] | 6 | 4 | 5 | 120 | Pull-out and 1e5-cycle lash coupon; inspect at 1 week and every 1e4 cycles. Fail: any hand movement, rim crack, or lash beyond ±1.7° [A] | `cad/gripper/params.json` (servo.horn_insert_od, servo.dog_pin); BOM |",
}
for prefix, new in changes.items():
    positions = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if len(positions) != 1:
        raise SystemExit(f"expected one {prefix!r}, found {len(positions)}")
    lines[positions[0]] = new
path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
