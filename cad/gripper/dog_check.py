#!/usr/bin/env python3
"""Dog coupling (horn -> knuckle A) at the servo's stall torque (DESIGN-BASIS LC3): hand calculation, CHANGELOG B40.

Each dog is a cantilever from the horn's front face to the middle of its engagement in the knuckle slot, held in a
socket the depth of the horn. Two checks per candidate, for one dog carrying the torque (lash leaves the other
clear) and for both sharing:
  bending at the horn face   sigma = F L / (pi d^3 / 32)
  bearing in a socket p = F / (D t) (4 + 6 L / t)   (rigid pin, linear pressure along the socket)
Writes out/dog_check.json and prints the table.   python3 cad/gripper/dog_check.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import gripper_concept as gc

HERE = Path(__file__).resolve().parent

# [A] values: no datasheet opened in this run
D3_M3 = 2.387             # M3 coarse thread minor diameter, mm [A, ISO 724 class value]
SIGMA_45H = 1400.0        # ISO 4026 set screw, property class 45H, bending allowable ~ yield, MPa [A]
SIGMA_DOWEL = 1700.0      # hardened ground dowel (ISO 8734 class, ~60 HRC through-hardened), MPa [A]
SIGMA_SHOULDER = 1400.0   # hardened custom dog screw smooth shoulder, MPa [A; grade and notch test required]
P_HORN = 386.0            # aluminium horn socket bearing yield, 6061-T6 class, MPa [A; horn alloy unknown]
P_INSERT = 900.0          # hardened steel sleeve bearing allowable, MPa [A; coupon/grade to verify]
MIN_HORN_RIM = 1.0        # radial aluminium rim beyond the Ø6 insert, mm [A; coupon to verify]


def main():
    P = gc.resolve(json.loads((HERE / "params.json").read_text(encoding="utf-8")))
    G = gc.derive(P)
    s, k = P["servo"], P["knuckle"]
    T = s["stall_torque_kgcm"]["6.5V"] * 9.80665 / 100.0          # N m at the 6.5 V rail (LC3 = stall)
    r = s["dog_r"]
    F1 = T * 1000.0 / r                                             # N, one dog
    z_tip = G.z_horn0 + s["dog_pin_len"]
    engage = z_tip - G.z_k0
    L = (G.z_k0 + engage / 2) - G.z_horn1                           # horn front face -> mid engagement
    t = s["horn_t"]
    rows = {}
    candidates = (
        ("M3 set screw 45H (as drawn)", D3_M3, SIGMA_45H, 3.0, P_HORN, None),
        ("hardened Ø3 dowel, bare aluminium", 3.0, SIGMA_DOWEL, 3.0, P_HORN, None),
        ("hardened Ø3 dowel, Ø6 steel insert", 3.0, SIGMA_DOWEL,
         s.get("horn_insert_od", 6.0), P_HORN, P_INSERT),
        ("hardened Ø2.9 shoulder M3 dog screw, Ø6 insert", s["dog_d"], SIGMA_SHOULDER,
         s.get("horn_insert_od", 6.0), P_HORN, P_INSERT),
    )
    for name, d, allow, outer_d, horn_allow, inner_allow in candidates:
        Z = math.pi * d ** 3 / 32
        for n in (1, 2):
            F = F1 / n
            sb = F * L / Z
            ph = F / (outer_d * t) * (4 + 6 * L / t)
            pi = F / (d * t) * (4 + 6 * L / t) if inner_allow else None
            rows[f"{name}, {n} dog{'s' if n > 1 else ''}"] = dict(
                F_N=round(F, 1), bending_MPa=round(sb), bending_allow_MPa=allow, SF_bending=round(allow / sb, 2),
                horn_bearing_MPa=round(ph), horn_allow_MPa=horn_allow, SF_horn=round(horn_allow / ph, 2),
                insert_bearing_MPa=round(pi) if pi else None, insert_allow_MPa=inner_allow,
                SF_insert=round(inner_allow / pi, 2) if pi else None,
                passes=allow / sb >= 1 and horn_allow / ph >= 1 and (inner_allow is None or inner_allow / pi >= 1))
    # torque one dog can carry before the weaker check (horn socket or set screw) reaches its allowable
    Z = math.pi * D3_M3 ** 3 / 32
    F_allow = min(SIGMA_45H * Z / L, P_HORN * 3.0 * t / (4 + 6 * L / t))
    T_allow = F_allow * r / 1000.0
    chosen = "hardened Ø2.9 shoulder M3 dog screw, Ø6 insert"
    horn_rim = s["horn_d"] / 2 - r - s.get("horn_insert_od", 6.0) / 2
    chosen_one = rows[f"{chosen}, 1 dog"]
    chosen_margin = min(chosen_one["SF_bending"], chosen_one["SF_horn"], chosen_one["SF_insert"])
    out = {"T_stall_6p5V_Nm": round(T, 3), "dog_r_mm": r, "lever_L_mm": round(L, 2), "engagement_mm": round(engage, 2),
           "horn_t_mm": t, "rows": rows, "one_dog_T_allow_Nm": round(T_allow, 2),
           "one_dog_T_allow_over_stall": round(T_allow / T, 2),
           "T_servo_LC1_Nm": P["grip"]["T_servo_LC1_Nm"], "T_servo_LC2_Nm": P["grip"]["T_servo_LC2_Nm"],
           "chosen": chosen, "horn_rim_mm": round(horn_rim, 2),
           "chosen_one_dog_min_SF": chosen_margin,
           "chosen_one_dog_T_allow_Nm": round(T * chosen_margin, 2),
           "chosen_passes": horn_rim >= MIN_HORN_RIM and all(rows[f"{chosen}, {n} dog{'s' if n > 1 else ''}"]["passes"] for n in (1, 2)),
           "basis": "D: geometry from gripper_concept.derive and params.json; A: D3_M3, SIGMA_45H, SIGMA_DOWEL, SIGMA_SHOULDER, P_HORN, P_INSERT, MIN_HORN_RIM"}
    (HERE / "out" / "dog_check.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"LC3 stall {T:.3f} N m at 6.5 V; dogs at r {r}; lever {L:.2f} mm (engagement {engage:.2f}); horn socket {t}")
    print(f"{'candidate':<44}{'F N':>8}{'bend MPa':>10}{'SF':>6}{'horn MPa':>10}{'SF':>6}{'insert MPa':>12}{'SF':>6}")
    for n, v in rows.items():
        print(f"{n:<44}{v['F_N']:>8.1f}{v['bending_MPa']:>10}{v['SF_bending']:>6.2f}{v['horn_bearing_MPa']:>10}{v['SF_horn']:>6.2f}{str(v['insert_bearing_MPa'] or '-'):>12}{str(v['SF_insert'] or '-'):>6}")
    print(f"as drawn one dog carries {T_allow:.2f} N m ({T_allow / T:.2f} x stall); chosen one dog {out['chosen_one_dog_T_allow_Nm']:.2f} N m ({chosen_margin:.2f} x stall); LC1 hold {out['T_servo_LC1_Nm']}, LC2 cap {out['T_servo_LC2_Nm']} N m")
    if not out["chosen_passes"]:
        raise SystemExit("chosen dog coupling fails stall check")
    return out


if __name__ == "__main__":
    main()
