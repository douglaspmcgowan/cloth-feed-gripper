"""Grip plant for the cloth-feed gripper: servo, gear pair, fingers, cloth, FSR, divider, ADC and servo rail.
Every constant is in PARAMS with its nominal value, the range the Monte Carlo draws from, a tag and a reason:
  [S] sourced (URL and retrieval date in docs/gripper/analysis/controls.md, Sources), or a repository file named;
  [D] derived by a committed script (named); [A] assumed, with the reason.
Units: deg (jaw angle theta, + = open, 0 = rigid pads 1 mm apart [DB R18]), mm, N, N*m, V, A, ms, mV.

The plant runs at 1 kHz. Per step it takes the servo pulse (us) the firmware wrote and returns the raw ADC
reading of the FSR divider node (mV, what analogReadMilliVolts returns) and the servo-rail current (A, what the
INA219 reads). Nothing here imports the firmware: the closed loop is built in loop.py around the compiled core.

Model, block by block (controls.md section 3 explains each with a figure):
  servo   the pulse is sampled once per 20 ms frame (random phase), decoded after a dead time, then a position
          loop: rate = (target + droop - theta_A -/+ deadband/2) / tau, limited by the torque-speed line
          w_max(V) * (1 - T_load / T_stall(V)) when closing against the load, and by w_max(V) when opening.
          Droop = T_load / K_servo: a hobby servo reaches full duty (stall torque) at a few degrees of error.
          Speed and stall torque scale linearly with rail voltage between the 5.0 V and 6.8 V datasheet points.
  rail    V = V_set - R_src * I: the servo's own current sags its supply (and so its speed and torque). I is the
          rail current the INA219 reads: the motor current I_m if the drive conducts discontinuously (the dyno.md
          bound), I_m (I_m / I_stall + w / w0) if continuously (PWM duty = back-EMF + I R over the rail) [thermal.md].
  friction the train holds a load by friction until the motor torque falls below backdrive_factor x the torque that
          closes it (eta_g^2 [A dyno.md]): between the two the jaw does not move (thermal F1's mechanism).
  gears   1:1 pair with backlash b (deg at the jaw). Finger B (the FSR finger) is driven through the mesh:
          under load its loaded flank is engaged and it sits b/2 open of A; unloaded it follows A through a
          play band of width b. The jaw angle that closes the gap is the mean of A and B.
          Losses: T_servo = 2 F r_c / eta closing; F r_c eta / ... opening (eta = mesh + pivots).
  finger  per-finger tip deflection d -> force with a softening law F = F_fold * tanh(k d / F_fold): tangent
          stiffness k at zero load, falling to zero at the FEA limit (fold) load F_fold. Two fingers in series.
  cloth   n plies of thickness t; through-thickness compression c -> F = k_c c / (1 - c / c_max) (stiffens as it
          compacts; c_max = phi * n * t); plies in series, so k_c = k_ply / n.
  gap     closure s (mm) past first touch = 2 d + c, with s = n t - gap(theta) and gap = 1 + 2 r_c theta_rad.
  FSR     sensed force = F * span * (1 + drift) * (1 + hysteresis), span = part-to-part x mounting error;
          drift = c_drift * log10(1 + t_loaded / 1 s) (creep under constant load); hysteresis reads high on
          unloading. Resistance from the fsr_model.h power law with a part-to-part exponent error.
  divider node = V33 * Rf / (R_fsr + Rf), Rf with tolerance; ADC gain and offset error, Gaussian noise,
          1 mV quantisation, saturation near 3.1 V at 11 dB attenuation; unloaded offset.
"""
import math
import random

# name: (nominal, lo, hi, tag, reason / source)
PARAMS = {
    # --- servo (DS3230 MG at the 6.5 V rail, rev B.1; was DS3218MG) ---
    "frame_ms": (20, 20, 20, "S", "50 Hz servo frame [DB R7]"),
    "dead_ms": (10.0, 5.0, 20.0, "A", "pulse decode + internal loop delay; no datasheet value; M8 bench step"),
    "tau_s": (0.040, 0.025, 0.070, "A", "small-signal position-loop lag; M8 (scope the pot or a pointer on video)"),
    "deadband_us": (3.0, 2.0, 5.0, "A", "3 us [A17 value kept, A32 lists none]; up to 5 us for a worn or cheaper unit [A]"),
    "w0_dps_at_6v5": (327.0, 280.0, 370.0, "D", "60 deg / 0.1833 s at 6.5 V, interpolated 0.20 s @5.0 / 0.18 s @6.8 V [S A32]; +/-14 % unit spread [A]"),
    "tstall_nm_at_6v5": (2.876, 2.50, 3.19, "D", "29.33 kg*cm at 6.5 V interpolated from 26 @5.0 / 30 @6.8 [S A32]; -13/+11 % unit spread [A]"),
    "istall_a": (3.99, 3.75, 4.80, "D", "3.99 A sizing [D actuation_trade.md, A32]; 3.75 A datasheet at 6.5 V (3.5 @5.0, 3.8 @6.8 [S A32]) to 4.8 A for a +20 % unit [A]"),
    "i_idle_a": (0.15, 0.08, 0.30, "A", "electronics + no-load motor current; M6"),
    "droop_deg_at_stall": (3.0, 1.5, 5.0, "A", "error at which the servo reaches full duty; dyno.md uses 3 deg [A]"),
    # --- rail ---
    "v_set": (6.5, 6.35, 6.65, "S", "6.5 +/- 0.15 V buck [S torque_and_actuator.md section 3.2, Douglas ruling]"),
    "r_src_ohm": (0.15, 0.05, 0.35, "A", "buck output + wiring + connector resistance; scope M (R27 proof)"),
    # --- transmission ---
    "r_c_mm": (65.0, 65.0, 65.0, "S", "pivot to pad line of action [DB D3]"),
    "backlash_deg": (1.01, 0.65, 1.37, "D", "j_t 0.25 mm (0.16-0.34) = 1.01 deg at the jaw [D gears.md, printed PA6-CF pick]"),
    "eta": (0.85, 0.75, 0.92, "A", "mesh + pivot efficiency [DB, A]; M18"),
    # --- fingers ---
    "k_tip_n_per_mm": (1.10, 0.88, 1.63, "S", "R12 window 0.88-1.63 [DB R12]; FEA pick 1.10 [D fea_summary / dyno.md]"),
    "k_mismatch": (0.0, -0.10, 0.10, "A", "finger A vs B stiffness mismatch (print-to-print); M10 on both fingers"),
    "f_fold_n": (8.88, 8.41, 10.6, "D", "FEA limit load: 8.88 N bare at E 56, 8.41 N with the PLA nail, 10.6 N at E 67 [D finger.md 5.2]"),
    # --- cloth ---
    "plies": (1, 1, 4, "A", "one ply is the scenario (DB section 6); 2-4 for seams and folds [A]"),
    "ply_mm": (0.30, 0.20, 0.50, "S", "0.3 mm [DB M4 default]; 0.2-0.5 mm for shirting to denim [A]"),
    "k_ply_n_per_mm": (30.0, 10.0, 60.0, "A", "through-thickness stiffness of one ply under the pad; dyno.md uses 30 [A]"),
    "phi_compact": (0.5, 0.35, 0.65, "A", "fraction of the stack thickness that can compress before the fibres lock"),
    # --- FSR, divider, ADC ---
    "span_part": (1.0, 0.94, 1.06, "S", "FSR 400 part-to-part repeatability +/-6 % (single batch) [S Interlink FSR 400 page]"),
    "span_mount": (1.0, 0.90, 1.10, "A", "residual error after CALF <N> (M11) on the TPU pad backing; 0.5-1.5 if CALF is skipped"),
    "fsr_exp_err": (0.0, -0.05, 0.05, "A", "power-law exponent error vs the Adafruit-table fit (fsr_model.h)"),
    "drift_per_dec": (0.02, 0.0, 0.05, "S", "creep < 5 % per log10(time) at constant load [S Interlink FSR 400 page]"),
    "hyst": (0.05, 0.0, 0.10, "S", "+5 to +10 % (reads high on unloading) [S Interlink datasheet PDS-10004; distributor listing]"),
    "rf_tol": (0.0, -0.01, 0.01, "A", "1 % fixed resistor"),
    "v33_mv": (3300.0, 3240.0, 3360.0, "A", "ESP32 3V3 LDO tolerance +/-1.8 %; the firmware assumes 3300"),
    "adc_gain_err": (0.0, -0.03, 0.03, "A", "analogReadMilliVolts after eFuse calibration; M11"),
    "adc_offset_mv": (0.0, -15.0, 15.0, "A", "same"),
    "noise_mv": (8.0, 4.0, 20.0, "A", "Gaussian ADC noise, RMS; M11"),
    "zero_mv": (20.0, 0.0, 60.0, "A", "unloaded node offset (preload from the pad backing)"),
    "adc_sat_mv": (3100.0, 3050.0, 3200.0, "A", "11 dB attenuation reads saturate near 3.1 V"),
    # --- timing ---
    "frame_phase_ms": (10, 0, 19, "A", "phase of the servo's frame against the firmware control tick (uniform)"),
    # --- added 2026-10-11 (review follow-up); appended so the draws of every constant above are unchanged ---
    "backdrive_factor": (0.4225, 0.25, 0.64, "D", "motor torque below which the held load back-drives the gear train, / the "
                         "torque to close: eta_g^2, eta_g 0.65 [A dyno.md], 0.5-0.8 [thermal.md 4.4]; what F1 exploits"),
    "disc_conduction": (0, 0, 1, "A", "servo drive conduction: 0 continuous (rail I = I_m (I_m / I_stall + w / w0)), 1 "
                        "discontinuous (rail I = I_m) [thermal.md 0: unmeasured; the F4 hold reading decides]"),
    "early_contact_deg": (0.0, 0.0, 10.0, "A", "contact this far above theta_c0 (a fold, a seam stack or an object, rigid: "
                          "2.27 mm of extra stack per deg); 0 unless a run draws it (--early) [A, O9]"),
}

R_FSR_FIXED = 2700.0     # [D config.h R_FSR_FIXED_OHM]
FSR_R1N = 6109.0         # [D config.h FSR_FIT_R1N_OHM]
FSR_EXP = 0.8195         # [D config.h FSR_FIT_EXP]
US_PER_DEG = 2000.0 / 180.0   # [DB R7]
V_LO, V_HI = 5.0, 6.8    # datasheet voltage points [S A32]


def nominal():
    return {k: v[0] for k, v in PARAMS.items()}


def sample(rng):
    """One Monte Carlo draw: uniform over each range (no distribution is sourced, so uniform is the honest
    choice; the corners are what the tails are made of). Integers stay integers."""
    p = {}
    for k, (nom, lo, hi, _, _) in PARAMS.items():
        if isinstance(nom, int):
            p[k] = rng.randint(int(lo), int(hi))
        else:
            p[k] = rng.uniform(lo, hi)
    return p


def speed_scale(v):
    # 0.20 s/60 @5.0 V and 0.18 s/60 @6.8 V [S A32]: speed proportional to 60/t, linear in t between the points.
    t = 0.20 + (0.18 - 0.20) * (v - V_LO) / (V_HI - V_LO)
    t65 = 0.20 + (0.18 - 0.20) * (6.5 - V_LO) / (V_HI - V_LO)
    return t65 / t


def torque_scale(v):
    tq = 26.0 + (30.0 - 26.0) * (v - V_LO) / (V_HI - V_LO)
    tq65 = 26.0 + (30.0 - 26.0) * (6.5 - V_LO) / (V_HI - V_LO)
    return tq / tq65


def finger_force(d, k, f_fold):
    """Per-finger tip force (N) at tip deflection d (mm): softening toward the fold load."""
    if d <= 0.0:
        return 0.0
    return f_fold * math.tanh(k * d / f_fold)


def finger_defl(f, k, f_fold):
    if f <= 0.0:
        return 0.0
    x = min(f / f_fold, 0.999999)
    return f_fold / k * math.atanh(x)


def cloth_comp(f, k_c, c_max):
    """Cloth compression (mm) at force f: inverse of F = k_c c / (1 - c / c_max)."""
    if f <= 0.0:
        return 0.0
    return f * c_max / (k_c * c_max + f)


class Plant:
    def __init__(self, p=None, seed=1):
        self.p = dict(nominal() if p is None else p)
        self.rng = random.Random(seed)
        p = self.p
        self.r_c = p["r_c_mm"]
        self.kA = p["k_tip_n_per_mm"] * (1 + p["k_mismatch"])
        self.kB = p["k_tip_n_per_mm"] * (1 - p["k_mismatch"])
        self.db = p["deadband_us"] / US_PER_DEG
        self.thA = 20.0
        self.thB = 20.0
        self.tgt = 20.0
        self.pending = []
        self.cloth = False            # cloth between the pads (False during CALIBRATE)
        self.extra_gap_mm = 0.0       # anything else between the pads (fault injection: thick fold, foreign object)
        self.F = 0.0
        self.Fs_dir = 0.0            # hysteresis memory 0 (loading) .. 1 (unloading)
        self.F_prev = 0.0
        self.t_loaded = 0.0
        self.I = p["i_idle_a"]
        self.I_motor = p["i_idle_a"]
        self.V = p["v_set"]
        self.T = 0.0
        self.fsr_open = False
        self.fsr_short = False
        self.blocked_at = None        # jaw angle at which a rigid obstruction stops finger A (stall injection)
        self.rotor_locked = False     # fault injection: the motor is driven at full duty against a locked rotor
        self.t = 0

    # ------------------------------------------------------------------ geometry and statics
    def stack_mm(self):
        early = 2.0 * self.r_c * math.radians(self.p.get("early_contact_deg", 0.0)) if self.cloth else 0.0
        return (self.p["plies"] * self.p["ply_mm"] if self.cloth else 0.0) + self.extra_gap_mm + early

    def theta_eff(self):
        return 0.5 * (self.thA + self.thB)

    def closure_mm(self):
        gap = 1.0 + 2.0 * self.r_c * math.radians(self.theta_eff())
        return self.stack_mm() - gap

    def force_from_closure(self, s):
        """Solve s = dA(F) + dB(F) + c(F) for the pad force F (bisection; monotone)."""
        if s <= 0.0:
            return 0.0
        p = self.p
        n = p["plies"] if self.cloth else 0
        k_c = p["k_ply_n_per_mm"] / max(n, 1)
        c_max = p["phi_compact"] * n * p["ply_mm"] if n else 0.0
        ff = p["f_fold_n"]
        lo, hi = 0.0, ff * 0.999999
        for _ in range(40):
            f = 0.5 * (lo + hi)
            g = finger_defl(f, self.kA, ff) + finger_defl(f, self.kB, ff) + (cloth_comp(f, k_c, c_max) if n else 0.0)
            if g > s:
                hi = f
            else:
                lo = f
        return 0.5 * (lo + hi)

    def touch_theta(self):
        """Jaw angle (theta_eff) at which the pads first touch whatever is between them."""
        return math.degrees((self.stack_mm() - 1.0) / (2.0 * self.r_c))

    # ------------------------------------------------------------------ dynamics
    def step(self, t_ms, us):
        p = self.p
        self.t = t_ms
        if (t_ms - p["frame_phase_ms"]) % p["frame_ms"] == 0 and us > 0:
            self.pending.append((t_ms + p["dead_ms"], (us - 1500.0) / US_PER_DEG))
        while self.pending and self.pending[0][0] <= t_ms:
            self.tgt = self.pending.pop(0)[1]
        # Load torque at the servo from the last force (closing: through the losses; opening: helped by them).
        T_load = 2.0 * self.F * self.r_c / 1000.0 / p["eta"]
        self.V = p["v_set"] - p["r_src_ohm"] * self.I
        ts = p["tstall_nm_at_6v5"] * torque_scale(self.V)
        w0 = p["w0_dps_at_6v5"] * speed_scale(self.V)
        k_servo = ts / p["droop_deg_at_stall"]                 # N*m per deg of position error
        t_close = self.tgt + T_load / k_servo                  # load pushes the jaw open by the droop
        t_open = self.tgt + p["backdrive_factor"] * T_load / k_servo   # below this the load back-drives the train
        e = t_close - self.thA if self.thA > t_close else (t_open - self.thA if self.thA < t_open else 0.0)
        if abs(e) <= self.db / 2:
            w = 0.0
        else:
            w = (e - math.copysign(self.db / 2, e)) / p["tau_s"]
        if w < 0:
            w = max(w, -w0 * max(0.0, 1.0 - T_load / ts))
        else:
            w = min(w, w0)
        thA = self.thA + (0.0 if self.rotor_locked else w * 0.001)
        if self.blocked_at is not None and thA < self.blocked_at:
            thA = self.blocked_at
            w = 0.0
        self.thA = thA
        # Finger B through the backlash.
        b = p["backlash_deg"]
        if self.F > 0.05:
            self.thB = self.thA + b / 2
        else:
            self.thB = min(max(self.thB, self.thA - b / 2), self.thA + b / 2)
        self.F = self.force_from_closure(self.closure_mm())
        # Servo torque and rail current.
        if self.rotor_locked:
            T_mot = ts
            w = 0.0
        elif self.blocked_at is not None and self.thA <= self.blocked_at + 1e-9:
            T_mot = min(ts, k_servo * max(0.0, self.thA - self.tgt))   # pushing on the obstruction
        else:
            # Held by friction between the back-drive and the closing torque: the motor gives only what the servo's
            # proportional drive asks for.
            T_mot = min(T_load, max(p["backdrive_factor"] * T_load, k_servo * (self.thA - self.tgt)))
        self.T = T_mot
        frac = min(1.0, T_mot / ts) if ts > 0 else 1.0
        moving = min(1.0, abs(w) / max(w0, 1.0))
        i_m = (p["istall_a"] - p["i_idle_a"]) * max(frac, 0.3 * moving)     # motor current, torque-proportional
        self.I_motor = p["i_idle_a"] + i_m
        if p.get("disc_conduction", 0):
            self.I = self.I_motor
        else:
            self.I = p["i_idle_a"] + i_m * min(1.0, i_m / (p["istall_a"] - p["i_idle_a"]) + moving)
        return self.adc_mv(), self.I

    # ------------------------------------------------------------------ sensor
    def fsr_reading_force(self):
        p = self.p
        F = self.F
        if F > 0.3:
            self.t_loaded += 0.001
        else:
            self.t_loaded = 0.0
        dF = F - self.F_prev
        self.F_prev = F
        if F > 1e-3:
            self.Fs_dir = min(1.0, max(0.0, self.Fs_dir - dF / max(0.5, 0.2 * F)))   # 0 loading .. 1 unloading
        else:
            self.Fs_dir = 0.0
        drift = p["drift_per_dec"] * math.log10(1.0 + self.t_loaded)
        return F * p["span_part"] * p["span_mount"] * (1.0 + drift) * (1.0 + p["hyst"] * self.Fs_dir)

    def adc_mv(self):
        p = self.p
        fs = self.fsr_reading_force()
        v33 = p["v33_mv"]
        rf = R_FSR_FIXED * (1.0 + p["rf_tol"])
        if self.fsr_short:
            node = v33
        elif self.fsr_open or fs <= 1e-4:
            node = 0.0
        else:
            r = FSR_R1N * fs ** (-(FSR_EXP * (1.0 + p["fsr_exp_err"])))
            node = v33 * rf / (r + rf)
        if not self.fsr_open:
            node += p["zero_mv"]
        mv = node * (1.0 + p["adc_gain_err"]) + p["adc_offset_mv"] + self.rng.gauss(0.0, p["noise_mv"])
        return float(round(min(p["adc_sat_mv"], max(0.0, mv))))

    def state(self):
        return {"thA": self.thA, "thB": self.thB, "F": self.F, "V": self.V, "I": self.I, "I_motor": self.I_motor, "T": self.T}


def markdown_table():
    rows = ["| Constant | Nominal | Range drawn | Tag | Source or reason |", "|---|---|---|---|---|"]
    for k, (nom, lo, hi, tag, why) in PARAMS.items():
        rows.append(f"| `{k}` | {nom:g} | {lo:g} to {hi:g} | {tag} | {why} |")
    return "\n".join(rows)


if __name__ == "__main__":
    print(markdown_table())
