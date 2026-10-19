"""Read firmware/gripper/config.h and derive the force-loop constants with the same formulas as
firmware/gripper/force_ctrl.h. pytest checks the compiled firmware against these values."""
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG_H = ROOT / "firmware/gripper/config.h"
_DEF = re.compile(r"^\s*#define\s+([A-Z0-9_]+)\s+(-?[0-9.]+)\b")


def load(path=CONFIG_H):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = _DEF.match(line)
        if m:
            out[m.group(1)] = float(m.group(2))
    return out


def derived(c=None):
    c = c or load()
    deg = math.pi / 180.0
    k_stiff = c["FINGER_K_MAX_N_PER_MM"] * c["R_C_MM"] * deg
    k_def = c["FINGER_K_DEF_N_PER_MM"] * c["R_C_MM"] * deg
    kp = c["SERVO_TAU_S"] / (k_stiff * (c["CTRL_TAU_CL_S"] + c["CTRL_DELAY_S"]))
    ti = min(c["SERVO_TAU_S"], 4.0 * (c["CTRL_TAU_CL_S"] + c["CTRL_DELAY_S"]))
    return {
        "K_STIFF_N_PER_DEG": k_stiff,
        "K_DEF_N_PER_DEG": k_def,
        "CTRL_KP_DEG_PER_N": kp,
        "CTRL_TI_S": ti,
        "CTRL_KI_DEG_PER_NS": kp / ti,
        "CTRL_U_MAX_DEG": (c["F_CAP_N"] - c.get("F_CAP_MARGIN_N", 0.0) - c["F_TOUCH_N"]) / k_stiff,
        "CTRL_LAG_COMP_DEG": c["JAW_SPEED_NEAR_DPS"] * c["CTRL_LAG_COMP_S"],
        "US_PER_DEG": (c["SERVO_US_AT_180DEG"] - c["SERVO_US_AT_0DEG"]) / 180.0,
        "DEADBAND_DEG": c["SERVO_DEADBAND_US"] / ((c["SERVO_US_AT_180DEG"] - c["SERVO_US_AT_0DEG"]) / 180.0),
    }


if __name__ == "__main__":
    for k, v in derived().items():
        print(f"{k:22s} {v:.4f}")
