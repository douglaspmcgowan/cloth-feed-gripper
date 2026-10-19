"""Lumped thermal network solver and natural-convection correlations.

Generic pieces used by thermal.py. Nothing here knows about the gripper.

- Air properties: linear interpolation of the Engineering ToolBox dry-air table
  (300 K and 350 K rows) [S], extrapolated linearly outside that band.
- Vertical plate: Churchill & Chu (1975) all-Ra form [S].
- Horizontal plate, hot face up: Nu = 0.54 Ra^1/4; hot face down: Nu = 0.27 Ra^1/4,
  L = area / perimeter [S, Incropera & DeWitt via Wikipedia "Nusselt number"]. Both
  are stated for Ra >= 1e4 (up) / 1e5 (down); below that they are extrapolated and
  flagged.
- Radiation to large surroundings: h_r = eps * sigma * (Ts^2 + Tsur^2)(Ts + Tsur) [S, textbook].

Units: SI throughout (m, W, K or degC where noted).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import fsolve

SIGMA = 5.670374419e-8  # Stefan-Boltzmann, W/m^2/K^4 (CODATA 2018) [S]
G = 9.80665  # m/s^2 [S]

# Engineering ToolBox dry air, 1 atm, rows 300 K and 350 K [S]
_AIR_T = (300.0, 350.0)
_AIR_K = (0.02624, 0.03003)  # W/m/K
_AIR_NU = (1.568e-5, 2.056e-5)  # m^2/s
_AIR_ALPHA = (22.18e-6, 29.50e-6)  # m^2/s
_AIR_PR = (0.707, 0.697)


def _lin(T_K: float, pair: tuple[float, float]) -> float:
    f = (T_K - _AIR_T[0]) / (_AIR_T[1] - _AIR_T[0])
    return pair[0] + f * (pair[1] - pair[0])


def air(T_film_C: float) -> dict:
    """Air properties at the film temperature (degC)."""
    # clip so solver trial points far outside the physical range cannot give negative properties
    T = min(max(T_film_C, -20.0), 300.0) + 273.15
    return {"k": _lin(T, _AIR_K), "nu": _lin(T, _AIR_NU), "alpha": _lin(T, _AIR_ALPHA),
            "Pr": _lin(T, _AIR_PR), "beta": 1.0 / T}


def rayleigh(Ts_C: float, Ta_C: float, L: float) -> float:
    p = air(0.5 * (Ts_C + Ta_C))
    return G * p["beta"] * abs(Ts_C - Ta_C) * L ** 3 / (p["nu"] * p["alpha"])


def nu_vertical_churchill_chu(Ra: float, Pr: float) -> float:
    """Churchill & Chu 1975, isothermal vertical plate, all Ra < 1e12."""
    return (0.825 + 0.387 * Ra ** (1 / 6) / (1 + (0.492 / Pr) ** (9 / 16)) ** (8 / 27)) ** 2


def nu_horizontal_up(Ra: float) -> float:
    """Hot face up (or cold face down). Stated range 1e4..1e7 (0.54), 1e7..1e11 (0.15)."""
    return 0.54 * Ra ** 0.25 if Ra <= 1e7 else 0.15 * Ra ** (1 / 3)


def nu_horizontal_down(Ra: float) -> float:
    """Hot face down (or cold face up). Stated range 1e5..1e10."""
    return 0.27 * Ra ** 0.25


@dataclass
class Face:
    """One exposed flat face. orient: 'vertical', 'up' or 'down'. L_char for vertical = height."""
    name: str
    area: float  # m^2
    orient: str
    L_char: float  # m
    eps: float = 0.9
    view: float = 1.0  # radiation view factor to ambient surroundings

    def h_conv(self, Ts: float, Ta: float, scale: float = 1.0) -> float:
        if abs(Ts - Ta) < 1e-9:
            Ts = Ta + 1e-6
        Ra = rayleigh(Ts, Ta, self.L_char)
        p = air(0.5 * (Ts + Ta))
        if self.orient == "vertical":
            Nu = nu_vertical_churchill_chu(Ra, p["Pr"])
        elif self.orient == "up":
            Nu = nu_horizontal_up(Ra)
        elif self.orient == "down":
            Nu = nu_horizontal_down(Ra)
        else:
            raise ValueError(self.orient)
        return scale * Nu * p["k"] / self.L_char

    def h_rad(self, Ts: float, Tsur: float) -> float:
        a, b = Ts + 273.15, Tsur + 273.15
        return self.eps * self.view * SIGMA * (a * a + b * b) * (a + b)

    def conductance(self, Ts: float, Ta: float, h_scale: float = 1.0) -> float:
        return (self.h_conv(Ts, Ta, h_scale) + self.h_rad(Ts, Ta)) * self.area

    def ra_in_range(self, Ts: float, Ta: float) -> bool:
        Ra = rayleigh(Ts, Ta, self.L_char)
        return {"vertical": Ra < 1e12, "up": Ra >= 1e4, "down": Ra >= 1e5}[self.orient]


@dataclass
class Network:
    """Nodes with heat capacity; links between nodes; links from nodes to fixed boundaries.

    links:     (i, j, G) with G a float or a callable G(T_array) -> W/K
    bounds:    (i, T_boundary_C, G) with G a float or callable G(T_array)
    power:     callable P(t, T_array) -> array of W per node
    """
    names: list[str]
    C: np.ndarray
    links: list = field(default_factory=list)
    bounds: list = field(default_factory=list)

    def idx(self, name: str) -> int:
        return self.names.index(name)

    @staticmethod
    def _g(G, T):
        return G(T) if callable(G) else G

    def net_flow(self, T: np.ndarray, P: np.ndarray) -> np.ndarray:
        q = np.array(P, dtype=float).copy()
        for i, j, Gij in self.links:
            g = self._g(Gij, T)
            f = g * (T[i] - T[j])
            q[i] -= f
            q[j] += f
        for i, Tb, Gb in self.bounds:
            q[i] -= self._g(Gb, T) * (T[i] - Tb)
        return q

    def steady(self, power, T0: np.ndarray, t: float = 0.0) -> tuple[np.ndarray, bool]:
        """Solve net_flow(T, P(T)) = 0. Returns (T, converged)."""
        def f(T):
            return self.net_flow(T, power(t, T))
        T, info, ier, msg = fsolve(f, T0, full_output=True, xtol=1e-10, maxfev=20000)
        ok = ier == 1 and np.all(np.isfinite(T)) and np.max(np.abs(f(T))) < 1e-6
        return T, bool(ok)

    def transient(self, power, T0: np.ndarray, t_end: float, dt: float) -> tuple[np.ndarray, np.ndarray]:
        """Explicit Heun (RK2) with fixed step. Deterministic."""
        n = int(round(t_end / dt))
        ts = np.linspace(0.0, n * dt, n + 1)
        out = np.empty((n + 1, len(self.names)))
        T = np.array(T0, dtype=float)
        out[0] = T
        for k in range(n):
            t = ts[k]
            k1 = self.net_flow(T, power(t, T)) / self.C
            Tp = T + dt * k1
            k2 = self.net_flow(Tp, power(t + dt, Tp)) / self.C
            T = T + 0.5 * dt * (k1 + k2)
            out[k + 1] = T
        return ts, out


def stable_dt(C: np.ndarray, Gmax_per_node: np.ndarray) -> float:
    """Explicit stability bound min(C/G_total)."""
    return float(np.min(C / np.maximum(Gmax_per_node, 1e-12)))


def first_crossing(ts: np.ndarray, y: np.ndarray, level: float) -> float | None:
    idx = np.nonzero(y >= level)[0]
    return None if len(idx) == 0 else float(ts[idx[0]])


def runaway_factor(I2R0_alpha: float, R_total: float) -> float:
    """Electro-thermal loop gain for copper loss P = I^2 R0 (1 + alpha (T - T0)) behind a
    thermal resistance R_total: steady state exists only if I^2 R0 alpha R_total < 1."""
    return I2R0_alpha * R_total


if __name__ == "__main__":
    f = Face("demo", 0.02 * 0.04, "vertical", 0.02)
    print(f.h_conv(60, 25), f.h_rad(60, 25), math.isfinite(f.conductance(60, 25)))
