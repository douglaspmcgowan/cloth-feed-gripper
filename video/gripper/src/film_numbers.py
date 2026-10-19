"""On-screen numbers read from the committed sources, so the film cannot drift from the CAD or firmware.

Every value names its file in the docstring. `python film_numbers.py` prints the table.
"""
import csv
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def _json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def config_define(name):
    """Numeric value of `#define NAME value` in firmware/gripper/config.h."""
    with open(os.path.join(ROOT, "firmware/gripper/config.h"), encoding="utf-8") as f:
        for line in f:
            m = re.match(r"#define\s+%s\s+(-?[0-9.]+)" % re.escape(name), line)
            if m:
                return float(m.group(1))
    raise KeyError(f"{name} not found in firmware/gripper/config.h")


def servo_model():
    """cad/gripper/out/parts.json `servo_model`, e.g. 'DSServo DS3230 MG'."""
    return _json("cad/gripper/out/parts.json")["servo_model"]


def servo_label():
    """Callout text: the part name without the 'DSServo' brand prefix, then 'servo'."""
    return servo_model().replace("DSServo ", "") + " servo"


def total_mass_g():
    """cad/gripper/out/fitcheck.json mass.total_g_incl_cloth (cloth 13.5 g and wiring 5 g included)."""
    return _json("cad/gripper/out/fitcheck.json")["mass"]["total_g_incl_cloth"]


def servo_price_usd():
    """docs/gripper/research/actuators.csv, the row whose name is the servo model in parts.json (A32 at B.1)."""
    model = servo_model()
    with open(os.path.join(ROOT, "docs/gripper/research/actuators.csv"), encoding="utf-8", newline="") as f:
        for row in csv.reader(f):
            if len(row) > 4 and row[1].startswith(model):
                return float(row[4])
    raise KeyError(f"{model} not in docs/gripper/research/actuators.csv")


def gear_pair_g():
    """analysis/gripper/results/gears.json cad_rev_b: pair mass at the CAD face width (parts.json face_width)."""
    b = _json("cad/gripper/out/parts.json")["face_width"]
    rows = _json("analysis/gripper/results/gears.json")["cad_rev_b"]["rows"][servo_model()]["by_face_width"]
    return rows["b%g" % b]["mass_pair_g"]


def force_refs():
    """(F_TARGET_DEFAULT_N, F_TRIP_N, F_CAP_N) from config.h."""
    return config_define("F_TARGET_DEFAULT_N"), config_define("F_TRIP_N"), config_define("F_CAP_N")


def jaw_floor_deg():
    """config.h JAW_MIN_DEG, the absolute firmware backstop."""
    return config_define("JAW_MIN_DEG")


def lever_mm():
    """config.h R_C_MM."""
    return config_define("R_C_MM")


def g(v):
    return ("%g" % v)


if __name__ == "__main__":
    print("mass g", total_mass_g(), "| servo", servo_label(), servo_price_usd(), "| gear pair g", gear_pair_g())
    print("refs N", force_refs(), "| floor deg", jaw_floor_deg(), "| lever mm", lever_mm())
