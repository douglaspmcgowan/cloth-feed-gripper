"""Linearised force loop: margins, sensitivity peak, bandwidth, and what limits it.

Run from the repository root:  python analysis/gripper/controls/linear.py
Writes results/linear.json, results/linear_stdout.txt and results/figures/loop_bode.png.

Loop (small signal about a held force F0; the rate limit, the deadband and the cap are inactive):
  e = F_sp - F_meas  ->  PI (discrete, T = 20 ms, as force_ctrl.cpp: u = g Kp e + integ, integ += g Kp/Ti e T)
  -> zero-order hold (T)  ->  servo frame phase phi (0-20 ms: the servo samples the held pulse once per frame)
  -> servo dead time d  ->  servo lag 1/(tau s + 1)  ->  contact stiffness K_eff (N per deg of command)
  -> FSR span (gain 1 nominal)  ->  firmware EMA (alpha 0.1 at 1 kHz)  ->  F_meas
K_eff is the tangent stiffness of finger A + finger B + cloth in series at F0 (plant.py laws), reduced by the
servo droop (load torque opens the jaw by T / K_servo): K_eff = K_c / (1 + K_c * 2 r_c / (1000 eta K_servo)) with
K_c in N/deg of jaw angle. g = K_STIFF / K_est is the gain schedule (K_est = secant (F0 - 0.5) / u at steady state).
The ZOH-plus-continuous-plant form ignores aliasing above 25 Hz; the margins it gives are the usual design
approximation and are checked against the nonlinear closed loop in test_linear.py.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "firmware_sim"))
import fwconfig  # noqa: E402
import plant as P  # noqa: E402

CFG = fwconfig.load()
DER = fwconfig.derived(CFG)
RES = HERE / "results"
T = CFG["CONTROL_PERIOD_MS"] / 1000.0
ALPHA = CFG["FSR_EMA_ALPHA"]
TS_ADC = CFG["ADC_PERIOD_US"] * 1e-6
W = np.logspace(-1, math.log10(math.pi / T * 0.999), 4000)   # rad/s, up to the Nyquist of the 50 Hz loop


def k_contact(p, f0, cloth=True):
    """Tangent stiffness dF/dtheta (N/deg of jaw angle) of the finger + finger + cloth stack at force f0."""
    ff = p["f_fold_n"]
    kA = p["k_tip_n_per_mm"] * (1 + p["k_mismatch"])
    kB = p["k_tip_n_per_mm"] * (1 - p["k_mismatch"])

    def kt(k):   # tangent of F = ff tanh(k d / ff): k (1 - (F/ff)^2)
        return k * (1.0 - (f0 / ff) ** 2)
    comp = 1.0 / kt(kA) + 1.0 / kt(kB)                     # mm/N
    if cloth:
        n = p["plies"]
        k_c = p["k_ply_n_per_mm"] / n
        c_max = p["phi_compact"] * n * p["ply_mm"]
        # F = k_c c / (1 - c/c_max) -> dF/dc = k_c / (1 - c/c_max)^2, with c at f0.
        c = P.cloth_comp(f0, k_c, c_max)
        comp += (1.0 - c / c_max) ** 2 / k_c
    ds_dth = 2.0 * p["r_c_mm"] * math.pi / 180.0          # mm of closure per deg of jaw angle
    return ds_dth / comp


def k_secant(p, f0, cloth=True):
    pl = P.Plant(p)
    pl.cloth = cloth
    s = P.finger_defl(f0, pl.kA, p["f_fold_n"]) + P.finger_defl(f0, pl.kB, p["f_fold_n"])
    if cloth:
        n = p["plies"]
        s += P.cloth_comp(f0, p["k_ply_n_per_mm"] / n, p["phi_compact"] * n * p["ply_mm"])
    return (f0 - CFG["F_TOUCH_N"]) / (s / (2.0 * p["r_c_mm"] * math.pi / 180.0))


def droop_factor(p, kc):
    k_servo = p["tstall_nm_at_6v5"] / p["droop_deg_at_stall"]          # N*m per deg
    c_d = 2.0 * p["r_c_mm"] / 1000.0 / p["eta"] / k_servo              # deg of droop per N of pad force
    return 1.0 / (1.0 + kc * c_d)


def loop_tf(w, kp, ti, keff, tau, delay_s, ema=True, t=T, span=1.0):
    z = np.exp(1j * w * t)
    c = kp * (1.0 + t / ti / (1.0 - 1.0 / z))
    zoh = (1.0 - np.exp(-1j * w * t)) / (1j * w * t)
    servo = np.exp(-1j * w * delay_s) / (1j * w * tau + 1.0)
    h = ALPHA / (1.0 - (1.0 - ALPHA) * np.exp(-1j * w * TS_ADC)) if ema else 1.0
    return c * zoh * servo * keff * span * h


def margins(L, w=W):
    mag = np.abs(L)
    ph = np.unwrap(np.angle(L))
    out = {"pm_deg": None, "wc_rad_s": None, "gm_db": None, "w180_rad_s": None}
    i = np.nonzero((mag[:-1] >= 1.0) & (mag[1:] < 1.0))[0]
    if len(i):
        k = i[0]
        out["wc_rad_s"] = float(w[k])
        out["pm_deg"] = float(180.0 + math.degrees(ph[k]))
    j = np.nonzero((ph[:-1] > -math.pi) & (ph[1:] <= -math.pi))[0]
    if len(j):
        k = j[0]
        out["w180_rad_s"] = float(w[k])
        out["gm_db"] = float(-20 * math.log10(mag[k]))
    S = 1.0 / (1.0 + L)
    Tc = L / (1.0 + L)
    out["Ms"] = float(np.max(np.abs(S)))
    out["Ms_db"] = float(20 * math.log10(out["Ms"]))
    bw = np.nonzero(np.abs(Tc) < 1 / math.sqrt(2))[0]
    out["bw_hz"] = float(w[bw[0]] / 2 / math.pi) if len(bw) else None
    return out


def operating_points():
    nom = P.nominal()
    soft = dict(nom, k_tip_n_per_mm=0.88, plies=4, ply_mm=0.5, k_ply_n_per_mm=10.0, droop_deg_at_stall=5.0,
                f_fold_n=8.41, tau_s=0.070, dead_ms=20.0)
    stiff = dict(nom, k_tip_n_per_mm=1.63, plies=1, ply_mm=0.2, k_ply_n_per_mm=60.0, droop_deg_at_stall=1.5,
                 f_fold_n=10.6, tau_s=0.025, dead_ms=5.0)
    return [("softest (k 0.88, 4 plies, slow servo)", soft, 6.0), ("nominal (k 1.10, 1 ply)", nom, 6.0),
            ("stiffest (k 1.63, thin ply, fast servo)", stiff, 6.0)]


def analyse(p, f0, schedule, kp_base=None, t=T, phase_ms=None, ema=True):
    kc = k_contact(p, f0)
    keff = kc * droop_factor(p, kc)
    ksec = k_secant(p, f0)
    ksec_eff = ksec * droop_factor(p, ksec)                            # what K_est converges to
    k_stiff = DER["K_STIFF_N_PER_DEG"]
    g = min(k_stiff / max(ksec_eff, CFG["K_SCHED_MIN_N_PER_MM"] * p["r_c_mm"] * math.pi / 180), k_stiff / 1e-9) \
        if schedule else 1.0
    g = max(g, 1.0)
    kp = (kp_base if kp_base is not None else DER["CTRL_KP_DEG_PER_N"]) * g
    ti = DER["CTRL_TI_S"]
    phase = (T * 1000 / 2 if phase_ms is None else phase_ms) / 1000.0
    worst = phase_ms is None
    out = {}
    for lab, ph in (("mean frame phase", T / 2), ("worst frame phase", T)) if worst else (("phase", phase),):
        L = loop_tf(W, kp, ti, keff, p["tau_s"], ph + p["dead_ms"] / 1000.0, ema=ema, t=t)
        out[lab] = margins(L)
    out.update({"K_c_N_per_deg": kc, "K_eff_N_per_deg": keff, "K_est_N_per_deg": ksec_eff, "g": g, "kp": kp,
                "loop_gain_kp_keff": kp * keff, "tau_s": p["tau_s"], "dead_ms": p["dead_ms"]})
    return out


def max_kp(p, f0, pm_min=45.0, gm_min_db=6.0):
    """Largest base Kp (deg/N) with the schedule that keeps PM >= pm_min and GM >= gm_min at the worst frame phase."""
    lo, hi = 0.01, 3.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        m = analyse(p, f0, True, kp_base=mid)["worst frame phase"]
        ok = (m["pm_deg"] is None or m["pm_deg"] >= pm_min) and (m["gm_db"] is None or m["gm_db"] >= gm_min_db)
        lo, hi = (mid, hi) if ok else (lo, mid)
    return lo


def main():
    out = {"T_s": T, "kp_deg_per_N": DER["CTRL_KP_DEG_PER_N"], "ti_s": DER["CTRL_TI_S"], "points": {}}
    lines = [f"Force loop, T = {T * 1000:.0f} ms, base Kp {DER['CTRL_KP_DEG_PER_N']:.3f} deg/N, Ti {DER['CTRL_TI_S']:.3f} s"]
    for name, p, f0 in operating_points():
        row = {}
        for sched in (True, False):
            a = analyse(p, f0, sched)
            row["schedule" if sched else "W2b-1 (no schedule)"] = a
        # Effect of the control period (servo frame stays 20 ms) and of the EMA, at the worst phase.
        row["T_10ms"] = analyse(p, f0, True, t=0.010, phase_ms=20.0)
        row["no_EMA"] = analyse(p, f0, True, phase_ms=20.0, ema=False)
        row["kp_max_45deg_6dB"] = max_kp(p, f0)
        out["points"][name] = row
        for k in ("schedule", "W2b-1 (no schedule)"):
            a = row[k]
            for ph in ("mean frame phase", "worst frame phase"):
                m = a[ph]
                lines.append(f"{name:40s} {k:20s} {ph:17s} g {a['g']:.2f}  Kp*K {a['loop_gain_kp_keff']:.3f}"
                             f"  PM {m['pm_deg']:.1f} deg at {m['wc_rad_s'] / 2 / math.pi:.2f} Hz"
                             f"  GM {m['gm_db']:.1f} dB  Ms {m['Ms']:.2f}  BW {m['bw_hz']:.2f} Hz")
        m10, me = row["T_10ms"]["phase"], row["no_EMA"]["phase"]
        lines.append(f"{name:40s} T 10 ms: PM {m10['pm_deg']:.1f} GM {m10['gm_db']:.1f} Ms {m10['Ms']:.2f}; "
                     f"no EMA: PM {me['pm_deg']:.1f} GM {me['gm_db']:.1f}; Kp max for PM 45 / GM 6 dB "
                     f"{row['kp_max_45deg_6dB']:.3f} deg/N")
    # Delay budget at the nominal point (what limits bandwidth).
    nom = P.nominal()
    budget = {"zero-order hold (T/2)": T / 2 * 1000, "frame phase (mean)": 10.0, "servo dead time": nom["dead_ms"],
              "FSR EMA (tau)": TS_ADC * 1000 * (1 - ALPHA) / ALPHA, "servo lag tau": nom["tau_s"] * 1000}
    out["delay_budget_ms"] = budget
    lines.append("delay budget (ms): " + ", ".join(f"{k} {v:.1f}" for k, v in budget.items())
                 + f"; total {sum(budget.values()):.1f}")
    RES.mkdir(exist_ok=True)
    (RES / "linear.json").write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    (RES / "linear_stdout.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    figure()


def figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.5, 6), sharex=True)
    cols = ["#1c5bb8", "#c9601a", "#008a63"]
    for (name, p, f0), c in zip(operating_points(), cols):
        a = analyse(p, f0, True)
        L = loop_tf(W, a["kp"], DER["CTRL_TI_S"], a["K_eff_N_per_deg"], p["tau_s"], T + p["dead_ms"] / 1000.0)
        f = W / 2 / math.pi
        a1.semilogx(f, 20 * np.log10(np.abs(L)), color=c, lw=2, label=name)
        a2.semilogx(f, np.degrees(np.unwrap(np.angle(L))), color=c, lw=2)
    a1.axhline(0, color="#6a7482", lw=1, ls=(0, (4, 3)))
    a2.axhline(-180, color="#6a7482", lw=1, ls=(0, (4, 3)))
    a1.set_ylabel("|L| (dB)")
    a2.set_ylabel("phase of L (deg)")
    a2.set_xlabel("frequency (Hz)")
    a1.legend(frameon=False, fontsize=8)
    a1.set_title("Force loop gain, shipped gains with the schedule, worst frame phase", loc="left", fontsize=10.5)
    for ax in (a1, a2):
        ax.grid(True, color="#e2e6eb")
    a2.set_ylim(-360, 0)
    fig.tight_layout()
    (RES / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(RES / "figures/loop_bode.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
