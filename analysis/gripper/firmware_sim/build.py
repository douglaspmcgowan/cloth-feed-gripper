"""Compile shim.cpp + the hardware-free firmware sources into a shared library and load it with ctypes.
The library is rebuilt whenever a source is newer than it. Output goes to a cache directory, not the repo.

load(overrides) builds a variant with some config.h values replaced (design sweeps in analysis/gripper/controls):
the firmware sources are copied to a cache directory, the named "#define NAME value" lines are rewritten there,
and that copy is compiled. With no overrides the repository sources are compiled as they are."""
import ctypes
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FW = ROOT / "firmware/gripper"
FW_SOURCES = ("fsm.cpp", "force_ctrl.cpp", "motion.cpp", "events.cpp", "fsr_filter.cpp")
SOURCES = [HERE / "shim.cpp"] + [FW / n for n in FW_SOURCES]
HEADERS = list(FW.glob("*.h"))
WINDOWS = sys.platform == "win32"


def cache_dir():
    d = Path(os.environ.get("FW_SIM_CACHE", Path(tempfile.gettempdir()) / "gripper_fw_sim"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def lib_path(tag=""):
    # Windows (MinGW g++) loads a .dll; -fPIC is meaningless there and the runtime is linked statically so the
    # DLL loads without MinGW on PATH. The Windows branch is untested (written in a Linux container, 2026-10-11).
    name = "gripper_fw" + (("_" + tag) if tag else "")
    return cache_dir() / ((name + ".dll") if WINDOWS else ("lib" + name + ".so"))


def _copy_if_changed(src, dst):
    # Pool workers each rebuild the variant path; on Windows a copy over a file another worker is copying fails
    # (WinError 32), so an up-to-date copy (copy2 keeps size and mtime) is left alone.
    s = src.stat()
    if dst.exists():
        t = dst.stat()
        if t.st_size == s.st_size and t.st_mtime == s.st_mtime:
            return
    shutil.copy2(src, dst)


def _variant_sources(overrides):
    key = hashlib.sha256(repr(sorted(overrides.items())).encode()).hexdigest()[:12]
    d = cache_dir() / ("src_" + key)
    d.mkdir(exist_ok=True)
    for p in FW.glob("*.h"):
        if p.name != "config.h":   # written below, with the overrides
            _copy_if_changed(p, d / p.name)
    for n in FW_SOURCES:
        _copy_if_changed(FW / n, d / n)
    cfg = (FW / "config.h").read_text(encoding="utf-8")
    for name, val in overrides.items():
        cfg, n = re.subn(rf"^(\s*#define\s+{name}\s+)(-?[0-9.]+)", lambda m: m.group(1) + repr(float(val)), cfg,
                         flags=re.M)
        if n != 1:
            raise KeyError(f"config.h has no single numeric #define {name}")
    # Rewrite only on a change: a fresh mtime forces a rebuild, and Windows cannot overwrite a DLL this process
    # has already loaded (firmware_requests.run loads the variant, then design_sweep loads it again).
    if not (d / "config.h").exists() or (d / "config.h").read_text(encoding="utf-8") != cfg:
        (d / "config.h").write_text(cfg, encoding="utf-8")
    return key, d


def config_value(name):
    """One numeric "#define NAME value" from firmware/gripper/config.h."""
    m = re.search(rf"^\s*#define\s+{name}\s+(-?[0-9.]+)", (FW / "config.h").read_text(encoding="utf-8"), flags=re.M)
    if not m:
        raise KeyError(name)
    return float(m.group(1))


def build(force=False, overrides=None):
    if overrides:
        tag, src = _variant_sources(overrides)
    else:
        tag, src = "", FW
    out = lib_path(tag)
    srcs = [HERE / "shim.cpp"] + [src / n for n in FW_SOURCES]
    newest = max(p.stat().st_mtime for p in srcs + list(src.glob("*.h")))
    if force or not out.exists() or out.stat().st_mtime < newest:
        cmd = ["g++", "-std=c++17", "-O2", "-shared", "-Wall", "-Wextra", f"-I{src}", "-o", str(out)]
        cmd += ["-static-libgcc", "-static-libstdc++"] if WINDOWS else ["-fPIC"]
        cmd += [str(s) for s in srcs] + ["-lm"]
        subprocess.run(cmd, check=True)
    return out


def load(overrides=None):
    lib = ctypes.CDLL(str(build(overrides=overrides)))
    f, i, u, s = ctypes.c_float, ctypes.c_int, ctypes.c_uint32, ctypes.c_char_p
    sig = {
        "sim_init": (None, []), "sim_step": (i, [f, f, f]), "sim_post": (None, [i, f]),
        "sim_now": (u, []), "sim_state": (i, []), "sim_theta_cmd": (f, []), "sim_theta_c0": (f, []),
        "sim_zero_mv": (f, []), "sim_force_on": (i, []), "sim_theta_ref": (f, []), "sim_sp_ramp": (f, []),
        "sim_fault": (i, []), "sim_force_fw": (f, []), "sim_u": (f, []), "sim_relaxed": (i, []),
        "sim_calibrated": (i, []), "sim_set_span": (i, [f]), "sim_reset_mcu": (None, [f]), "sim_set_limit": (None, [i]),
        "sim_line_count": (i, []), "sim_line": (s, [i]), "sim_k_est": (f, []), "sim_set_hold_limit": (i, [f]),
        "sim_set_backoff": (i, [f]), "sim_set_current_present": (None, [i]), "sim_hold_i_ref": (f, []), "sim_boff": (f, []), "sim_sp": (f, []),
        "sim_clear_events": (None, []), "sim_event_name": (s, [i]), "sim_state_name": (s, [i]),
        "sim_fsr_mv_from_force": (f, [f]), "sim_fsr_force_from_mv": (f, [f]), "sim_jaw_to_us": (i, [f]),
        "sim_k_stiff": (f, []), "sim_kp": (f, []), "sim_ti": (f, []), "sim_u_max": (f, []), "sim_lag_comp": (f, []),
        "sim_transition_count": (i, []),
        "sim_events": (i, [ctypes.POINTER(u), ctypes.POINTER(i), ctypes.POINTER(f), ctypes.POINTER(i), i]),
    }
    for name, (res, args) in sig.items():
        fn = getattr(lib, name)
        fn.restype = res
        fn.argtypes = args
    return lib
