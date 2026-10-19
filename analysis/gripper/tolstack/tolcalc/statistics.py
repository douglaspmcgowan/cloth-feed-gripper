"""Shared statistical helpers."""
from __future__ import annotations

import math

OUT_BOUND_CONFIDENCE = 0.95


def small_count_upper_bound(events: int, n: int) -> float:
    """Exact one-sided Clopper-Pearson upper bound for a binomial count."""
    if events >= n:
        return 1.0
    target = 1.0 - OUT_BOUND_CONFIDENCE

    def lower_tail(p):
        terms = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                 + i * math.log(p) + (n - i) * math.log1p(-p)
                 for i in range(events + 1)]
        peak = max(terms)
        return math.exp(peak) * sum(math.exp(term - peak) for term in terms)

    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if lower_tail(mid) > target:
            lo = mid
        else:
            hi = mid
    return hi
