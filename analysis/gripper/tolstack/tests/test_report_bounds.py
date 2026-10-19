import math
import sys
from pathlib import Path

import pytest
from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tolcalc import report  # noqa: E402


@pytest.mark.parametrize("events, expected", [(0, 2.996), (1, 4.744), (2, 6.296),
                                               (4, 9.154), (9, 15.705)])
def test_small_count_bound_known_values(events, expected):
    bound_events = report.small_count_upper_bound(events, 100_000) * 100_000
    assert bound_events == pytest.approx(expected, rel=0.001)


@pytest.mark.parametrize("n", [20_000, 1_000_000])
@pytest.mark.parametrize("events", range(10))
def test_small_count_bound_matches_scipy(events, n):
    expected = beta.ppf(report.OUT_BOUND_CONFIDENCE, events + 1, n - events)
    assert report.small_count_upper_bound(events, n) == pytest.approx(expected, rel=1e-10)


@pytest.mark.parametrize("n", [20_000, 100_000, 1_000_000])
@pytest.mark.parametrize("events", range(10))
def test_printed_bound_never_rounds_down(events, n):
    mc = {"n": n, "out_pct": events * 100 / n}
    printed_ppm = float(report.out_str(mc).split()[0][1:])
    exact_ppm = report.small_count_upper_bound(events, n) * 1_000_000
    assert printed_ppm >= exact_ppm
    assert math.isfinite(printed_ppm)
