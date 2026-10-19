"""Platform-independent float64 log, cos and sin for the Monte Carlo sampler.

numpy's np.log / np.cos / np.sin call the C runtime's libm (glibc on Linux, UCRT on Windows) or a SIMD
kernel; those are not correctly rounded and disagree in the last bit for some inputs, so the same seed gave
different samples on Linux and Windows. These versions use only IEEE-754 +, -, *, / (correctly rounded on
every platform, and numpy never fuses them into FMA) plus exact frexp / floor, so the bytes are the same
everywhere. Absolute error is within about 2 ulp of 1.0 (<= 3.4e-16 against an exact cos(2 pi u)); relative
error near the zeros of cos and sin is much larger (up to about 5.6e4 ulp of the tiny result), and log is
faithful (< 1 ulp) on the norm_ppf tail domain. All of it is far below anything a tolerance stack reads.
"""
from __future__ import annotations

import math

import numpy as np

LN2_HI = 6.93147180369123816490e-01  # ln 2 split so e * LN2_HI is exact for |e| < 2**11
LN2_LO = 1.90821492927058770002e-10
SQRT_HALF = 0.7071067811865476
HALF_PI = 1.5707963267948966
# Taylor coefficients 1/(2k+1) of atanh, and of sin / cos about 0, highest power first (Horner)
_ATANH = [1.0 / (2 * k + 1) for k in range(13, -1, -1)]
_SIN = [(-1) ** k / math.factorial(2 * k + 1) for k in range(13, -1, -1)]  # int / int: correctly rounded
_COS = [(-1) ** k / math.factorial(2 * k) for k in range(13, -1, -1)]


def _horner(coeffs, x):
    acc = np.full_like(x, coeffs[0])
    for c in coeffs[1:]:
        acc = acc * x + c
    return acc


def log(x) -> np.ndarray:
    """Natural log of positive finite float64 values."""
    x = np.asarray(x, dtype=np.float64)
    m, e = np.frexp(x)                      # x = m * 2**e, m in [0.5, 1): exact
    low = m < SQRT_HALF
    m = np.where(low, 2.0 * m, m)           # m in [0.707, 1.414): exact
    e = (e - low).astype(np.float64)
    s = (m - 1.0) / (m + 1.0)               # m - 1 is exact (Sterbenz)
    s2 = s * s                              # <= 0.0295, so 14 terms reach 1e-22
    return e * LN2_HI + (2.0 * s * _horner(_ATANH, s2) + e * LN2_LO)


def cos_sin_turns(u) -> tuple[np.ndarray, np.ndarray]:
    """(cos, sin) of 2*pi*u for u in [0, 1); the quarter-turn reduction 4u = q + f is exact."""
    u4 = 4.0 * np.asarray(u, dtype=np.float64)
    q = np.floor(u4)
    a = (u4 - q) * HALF_PI                  # angle within the quarter, [0, pi/2)
    a2 = a * a
    s, c = a * _horner(_SIN, a2), _horner(_COS, a2)
    q = q.astype(np.int64) % 4
    cos = np.select([q == 0, q == 1, q == 2], [c, -s, -c], s)
    sin = np.select([q == 0, q == 1, q == 2], [s, c, -s], -c)
    return cos, sin
