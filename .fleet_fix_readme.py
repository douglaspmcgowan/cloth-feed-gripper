"""Align the hand-authored mass section with current fitcheck and R10 options."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
readme = root / "cad/gripper/README.md"
fit = json.loads((root / "cad/gripper/out/fitcheck.json").read_text(encoding="utf-8"))["mass"]
options = json.loads((root / "cad/gripper/out/r10_options.json").read_text(encoding="utf-8"))
assert options["base_g"] == fit["total_g_incl_cloth"]
assert options["base_gmm"] == fit["mass_moment_gmm"]
text = readme.read_text(encoding="utf-8")


def change(old, new, count=1):
    global text
    seen = text.count(old)
    if seen != count:
        raise SystemExit(f"README: expected {count} matches, found {seen}: {old[:80]}")
    text = text.replace(old, new)


change("**R10 mass moment is 52,995 g·mm, 121.2 % of the 43,720 limit**",
       "**R10 mass moment is 53,342 g·mm, 122.0 % of the 43,720 limit**")
change("**R10 fails: 152.9 g including 13.5 g cloth and 5 g wiring, COM 37.6 mm past H, 52,995 g·mm = 121.2 % of 43,720** (C001 at 7.4 V) [D `fitcheck.py`]. 58,505 with the wrist UVC option.",
       "**R10 fails: 153.9 g including 13.5 g cloth and 5 g wiring, COM 37.5 mm past H, 53,342 g·mm = 122.0 % of 43,720** (C001 at 7.4 V) [D `fitcheck.py`]. 58,852 with the wrist UVC option.")
change("**B.1 is 8.5 g and 2,864 g·mm heavier than rev A:**",
       "**B.1 with B40 is 9.5 g and 3,211 g·mm heavier than rev A:**")
change("| housing | 11.71 | 21.5 | 3,871 |", "| housing | 11.66 | 21.4 | 3,854 |")
change("| horn | 2.36 | 31.0 | 803 |", "| horn | 3.43 | 31.0 | 1,167 |")
change("| **total** | **152.9** | COM 37.6 | **52,995** |",
       "| **total** | **153.9** | COM 37.5 | **53,342** |")
change("so 27 g has to go.", "so about 28 g has to go.")

start = text.index("| Option | Δ g | Δ g·mm | Basis | What it costs | Running total g·mm |")
end = text.index("\n\n**Closest combination:**", start)
table = ["| Option | Δ g | Δ g·mm | Basis | What it costs | Running total g·mm |",
         "|---|---:|---:|---|---|---:|"]
for row in options["rows"]:
    running = f"{row['running_gmm']:,}" if row["running_gmm"] is not None else "not counted"
    table.append(f"| {row['option']} | {row['d_g']:+.2f} | {row['d_gmm']:+,} | {row['basis']} | {row['cost']} | {running} |")
text = text[:start] + "\n".join(table) + text[end:]

old_closest = next(line for line in text.splitlines() if line.startswith("**Closest combination:**"))
new_closest = ("**Closest combination:** every counted row together (infill trims, short bushes, aluminium "
               "limiters, knuckle lightening holes, 40 mm fingers) gives "
               f"{options['combo_gmm']:,} g·mm, {options['combo_use']:.1%} of 43,720, still "
               f"{options['combo_short_gmm']:,} g·mm (about {options['combo_short_g_at_com']:.1f} g "
               "at the COM lever) over. No qualifying servo is lighter than the DS3230, and moving the servo "
               "toward the wrist adds more than it saves in both forms the model can build. The servo alone "
               "is 20,406 g·mm and the cloth 5,469.")
change(old_closest, new_closest)
change("2 × M3x10 set screws", "2 × custom hardened M3×10 shoulder dog screws and 2 × Ø6×3×3 steel horn inserts")
readme.write_text(text, encoding="utf-8", newline="\n")
