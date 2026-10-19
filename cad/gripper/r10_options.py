#!/usr/bin/env python3
"""R10 mass-moment options for revision B: what each real option buys, estimated, none built (CHANGELOG B24).

Mass moment as fitcheck.py: sum m (lever + u), u = distance past horn face H, plus 13.5 g cloth at the pad and 5 g
wiring at u 40. Options marked D rebuild the model with one parameter changed (gripper_concept.build + mass_props);
options marked A scale a modelled mass by an assumed fraction. Writes out/r10_options.json; prints a Markdown table.

    python3 cad/gripper/r10_options.py
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import gripper_concept as gc

HERE = Path(__file__).resolve().parent
RHO_AL, RHO_BRASS = 2.70, 8.5        # g/cm3 [A]
LIMIT = 43720.0


def moment(P):
    """(total g, g mm, per-part rows) for one parameter set, the fitcheck.py way."""
    G, parts, _ = gc.build(P)
    mp = gc.mass_props(gc.resolve(P), gc.world(parts, G, 0.0), G)
    items = [(n, r["mass_g"], r["u_past_H"]) for n, r in mp.items()]
    Q = gc.resolve(P)
    pad_u = G.Y_H - (G.y0 - (Q["finger"]["length"] - Q["grip"]["pad_centroid_from_tip_mm"]))
    items += [("cloth", Q["work_cell"]["cloth"]["mass_g"], pad_u), ("wiring", 5.0, 40.0)]
    lever = Q["payload_scenarios"]["lever_shoulder_lift_to_H_mm"]
    return sum(m for _, m, _ in items), sum(m * (lever + u) for _, m, u in items), mp, lever, G


def variant(P0, edit):
    P = copy.deepcopy(P0)
    edit(P)
    return moment(P)


def main():
    P0 = json.loads((HERE / "params.json").read_text(encoding="utf-8"))
    M0, I0, mp, lever, G0 = moment(P0)
    rows = []

    def add(name, dm, dI, basis, cost, in_combo=True):
        rows.append(dict(option=name, d_g=round(dm, 2), d_gmm=round(dI), basis=basis, cost=cost, in_combo=in_combo))

    # 1-4: the four trims the README listed
    M, I, *_ = variant(P0, lambda P: P["materials"].__setitem__("print_fill", 0.4))
    add("Housing and front plate 60 → 40 % gyroid", M - M0, I - I0, "D model, A strength",
        "pin-plate and boss-web stiffness unchecked (T14B, T16 line-ream); coupon first")
    wm = mp["wrist_mount"]
    add("Wrist plate 100 → 60 % (4 walls)", -0.4 * wm["mass_g"], -0.4 * wm["mass_g"] * (lever + wm["u_past_H"]),
        "A: 40 % of the solid mass", "clamp under the 4 horn screws and the Ø19.56 pilot recess (T02) unchecked")
    M, I, *_ = variant(P0, lambda P: P["knuckle"].__setitem__("sleeve_len", 8.0))
    add("Bushes 3 × 6 × 10 → 3 × 6 × 8", M - M0, I - I0, "D model",
        "bearing length 8 in a 10.5 hub; T16 / T10B re-base (tolerance owner)")
    li = P0["housing"]["limiter"]
    import math
    v_li = 4 * math.pi / 4 * (li["od"] ** 2 - li["id"] ** 2) * li["len"] / 1000.0
    u_li = G0.Y_H - sum(y for _, y in gc.ear_holes(gc.resolve(P0), G0)) / 4
    add("Limiter sleeves brass → aluminium", -v_li * (RHO_BRASS - RHO_AL), -v_li * (RHO_BRASS - RHO_AL) * (lever + u_li),
        "D volume, A densities", "aluminium creep and fretting under the nut at 60 °C (thermal owner)")
    # 5: lighter servo that still meets the actuation study (none in its set; the rows that exist)
    s = P0["servo"]
    add("Lighter servo: DS3218MG at 1:1 (58 g)", -2.0, -2.0 * (lever + mp["servo"]["u_past_H"]), "S mass (actuators.csv A17)",
        "fails the actuation study: R16 hold P 0.53 (actuation_trade.md 0); not a qualifying option", in_combo=False)
    add("Lighter servo: DS3218MG + 1.5:1 stage (58 + 8.2 g)", 6.2, 6.2 * (lever + mp["servo"]["u_past_H"]), "S/A (actuation_trade.md 5.2)",
        "qualifies on torque but is heavier; new bay, +0.95° backlash", in_combo=False)
    # 6: servo moved toward the wrist: the long-Y layout (case along Y, shaft 10 from the finger-side end) puts the
    # case above pivot A; the deck rises with it
    try:
        def long_y(P):
            P["servo"]["long_axis"] = "Y"
            P["housing"]["tc_hole_d"] = 0  # the rev B thermocouple hole is placed for the long-X ears only
        M, I, mpY, _, GY = variant(P0, long_y)
        add(f"Servo case turned up toward the wrist (long-Y layout; case 10 mm up from pivot A, but the deck rises "
            f"so pivot-to-H {GY.Y_H - G0.Y_H:+.1f} mm and servo u {mp['servo']['u_past_H']:.1f} → {mpY['servo']['u_past_H']:.1f})", M - M0, I - I0, "D model",
            "whole gripper moves away from H with the taller deck; housing redesign; wrist flex / keep-out re-check", in_combo=I < I0)
    except Exception as e:  # noqa: BLE001
        add("Servo case turned up toward the wrist (long-Y layout)", 0.0, 0.0, f"not built: {type(e).__name__}", "housing redesign", in_combo=False)
    d = 10.0
    add(f"Servo body {d:g} mm nearer the wrist on a 1:1 stage (shaft off pivot A)", 8.2, -s["mass_g"] * d + 8.2 * (lever + mp["servo"]["u_past_H"]),
        "D lever, A stage 8.2 g as actuation_trade.md 5.2", "net heavier: the stage's own moment exceeds the 600 g·mm the move saves",
        in_combo=False)
    # 7: lightening holes in the knuckle arms (lightening_holes 0 today)
    kn = [mp["knuckle_a"], mp["knuckle_b"]]
    add("Lightening holes, both knuckles (20 % of each)", -0.2 * sum(r["mass_g"] for r in kn),
        -0.2 * sum(r["mass_g"] * (lever + r["u_past_H"]) for r in kn), "A: 20 % removed",
        "arm and gear-root stress unchecked (gears.py); PA6-CF print")
    # 8: shorter finger (hollow: the Fin Ray is already open-celled; only length is a real lever)
    M, I, *_ = variant(P0, lambda P: P["finger"].__setitem__("length", 40.0))
    add("Finger 45 → 40 mm (cloth, nail, FSR 5 mm nearer H; a hollow finger buys nothing more: the Fin Ray is already open cells)", M - M0, I - I0, "D model",
        "r_c 65 → about 60 (R17, gear and servo sizing), tip stiffness R12 rises about (45/40)³, reach; finger lane")
    run = I0
    for r in rows:
        if r["in_combo"]:
            run += r["d_gmm"]
        r["running_gmm"] = round(run) if r["in_combo"] else None
    out = dict(base_g=round(M0, 1), base_gmm=round(I0), limit_gmm=LIMIT, lever_mm=lever, rows=rows,
               combo_gmm=round(run), combo_use=round(run / LIMIT, 3), combo_short_gmm=round(run - LIMIT),
               combo_short_g_at_com=round((run - LIMIT) / (lever + 37.6), 1),
               basis="D = rebuilt model with one parameter changed; A = assumed fraction; S = sourced")
    (HERE / "out" / "r10_options.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"base {M0:.1f} g, {I0:,.0f} g·mm ({I0 / LIMIT:.1%} of {LIMIT:,.0f})")
    print("| Option | Δ g | Δ g·mm | Basis | What it costs | Running total g·mm |")
    print("|---|---:|---:|---|---|---:|")
    for r in rows:
        rt = f"{r['running_gmm']:,}" if r["running_gmm"] is not None else "not counted"
        print(f"| {r['option']} | {r['d_g']:+.2f} | {r['d_gmm']:+,} | {r['basis']} | {r['cost']} | {rt} |")
    print(f"all counted options: {run:,.0f} g·mm = {run / LIMIT:.1%}; still {run - LIMIT:,.0f} g·mm over "
          f"(about {out['combo_short_g_at_com']} g at the COM lever)")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
