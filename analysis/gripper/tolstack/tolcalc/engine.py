"""Worst case, RSS and Monte Carlo evaluation of a Stack.

Linear/radial model:  y = constant + sum(a_i * x_i) + | sum(a_j * v_j) |
  x_i linear contributors (scalars along the stack direction),
  v_j radial contributors (2D offsets; the magnitude of their vector sum is added).
Expression model:      y = f(x_1..x_n), numpy expression over contributor names.

WC   : linear exact (mid +/- sum|a|*half); radial magnitudes add arithmetically;
       expression by corner enumeration (n <= 16) else linearised.
RSS  : 'classic' = mid +/- sqrt(sum (a*t)^2) with every t read as 3 sigma (Scholz 1995 eq. 2);
       'dist'    = mid +/- 3*sqrt(sum (a*sigma)^2) with sigma from each distribution
                   (uniform t/sqrt3, triangular t/sqrt6); radial part via Rayleigh 99.73 %.
MC   : seeded numpy sampling, N samples; capability from the samples. The sampler calls no libm function
       (log, cos, sin, hypot come from detmath or +-*/sqrt), so a seed gives the same bytes on every platform.

Correlation across chained stacks (from_stack): every leaf contributor draws its random
variates from one run-wide SampleBank keyed by its name (or its `shared:` key). The same
name in two stacks of one run is therefore the SAME physical deviation, sample by sample,
and a from_stack dependency hands over its samples index-aligned (no re-shuffle), so a
leaf reached twice through a chain (T09 -> T07 -> T06 and T09 -> T06) keeps its correlation.
Distribution shapes are applied to one shared U(0,1) variate by inverse CDF, so a name used
with different distributions stays rank-correlated; the run records a warning when that
happens. Give a contributor `shared: <unique key>` when two stacks reuse a name for
different physical features.

RSS clipping: the distribution-adjusted RSS can exceed worst case when a bounded
(uniform, disk) term dominates, because 3 sigma of such a term lies outside its bounds.
It is clipped to the WC band and flagged `rss_clipped`.

Expression stacks: Var % comes from Monte Carlo freeze-one (see analyse), not from sensitivities. The RSS bands
are linearised at the mids and are flagged `rss_nonlinear` when the MC band disagrees with them.
Known limitation: the expression worst case is taken over the 2^n corners only, so a minimum inside the box
(the kink of abs() where its argument crosses 0) can be missed; the printed bound is then slightly optimistic.
"""
from __future__ import annotations

import itertools
import math
import zlib

import numpy as np

from . import detmath
from .model import Stack
from .statistics import small_count_upper_bound

BATCH_COUNT = 20
VERDICT_SE_MULTIPLE = 2.576  # two-sided 99% normal coverage

RAYLEIGH_9973 = math.sqrt(-2.0 * math.log(0.0027))  # 3.4394: radius holding 99.73 % of a 2D normal
# Expression names: IEEE-exact operations only. libm transcendentals (sin, cos, tan, arctan*, arcsin, arccos,
# hypot, exp, log) are left out because their last bit differs between C runtimes; route one through detmath first.
NP_NS = {k: getattr(np, k) for k in (
    "sqrt", "abs", "minimum", "maximum", "radians", "degrees", "pi", "where")}


def _eval_expr(expr: str, env: dict):
    return eval(expr, {"__builtins__": {}}, {**NP_NS, **env})  # noqa: S307


def norm_ppf(p):
    """Inverse standard-normal CDF (Acklam rational approximation, relative error < 1.2e-9)."""
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00)
    p = np.clip(np.asarray(p, float), 1e-15, 1 - 1e-15)
    x = np.empty_like(p)
    lo, hi = p < 0.02425, p > 1 - 0.02425
    mid = ~(lo | hi)
    q = p[mid] - 0.5
    r = q * q
    x[mid] = (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
             (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    for m, sgn, pp in ((lo, 1.0, p[lo]), (hi, -1.0, 1 - p[hi])):
        qq = np.sqrt(-2 * detmath.log(pp))
        x[m] = sgn * (((((c[0]*qq+c[1])*qq+c[2])*qq+c[3])*qq+c[4])*qq+c[5]) / \
            ((((d[0]*qq+d[1])*qq+d[2])*qq+d[3])*qq+1)
    return x


class SampleBank:
    """Run-wide store of U(0,1) variates, one array per contributor key (seeded per key)."""

    def __init__(self, n: int, seed: int):
        self.n, self.seed = n, seed
        self._u: dict = {}
        self._shape: dict = {}
        self.warnings: list = []

    def uniform(self, key: str) -> np.ndarray:
        if key not in self._u:
            self._u[key] = np.random.default_rng([self.seed, zlib.crc32(key.encode())]).random(self.n)
        return self._u[key]

    def note(self, key: str, shape: tuple, where: str) -> None:
        old = self._shape.setdefault(key, shape + (where,))
        if old[:-1] != shape:
            self.warnings.append(f"contributor '{key}' is {old[:-1]} in {old[-1]} but {shape} in {where}; "
                                 "samples stay rank-correlated. Add `shared:` if they are different features")


def _sample(c, bank, n, where=""):
    if c.dep is not None and c.kind != "radial":
        y = np.asarray(c.dep["_samples"], float)
        if len(y) != n:
            bank.warnings.append(f"{where}: from_stack {c.from_stack} has {len(y)} samples, not {n}; "
                                 "resampled, so correlation with shared leaves is lost")
            y = np.random.default_rng([bank.seed, zlib.crc32(c.name.encode())]).choice(y, n)
        return y
    if c.kind == "radial":  # projected radial zone: one component of the same 2D sample
        x, yy = _sample_radial(c, bank, n, where)
        return c.mid + (yy if c.project_axis else x)
    m, h = c.mid, c.half
    if h == 0:
        return np.full(n, m)
    bank.note(c.key, ("linear", c.dist), where)
    u = bank.uniform(c.key)
    if c.dist == "normal":
        return m + c.sigma * norm_ppf(u)
    if c.dist == "uniform":
        return m - h + 2 * h * u
    if c.dist == "triangular":
        return np.where(u < 0.5, m - h + h * np.sqrt(2 * u), m + h - h * np.sqrt(2 * (1 - u)))
    raise ValueError(c.dist)


def _sample_radial(c, bank, n, where=""):
    bank.note(c.key, ("radial", c.dist), where)
    ur, ut = bank.uniform(c.key + "#r"), bank.uniform(c.key + "#theta")
    R = c.dep_radius_samples() if c.dep is not None else c.half
    if c.dist == "disk":
        r = R * np.sqrt(ur)
    elif c.dist == "ring":
        r = R * np.ones(n)
    elif c.dist == "ring_uniform":
        r = R * ur
    elif c.dist == "normal2d":
        if c.dep is not None:
            raise ValueError(f"{c.name}: normal2d cannot take its radius from a stack")
        s = c.half / c.k
        return s * norm_ppf(ur), s * norm_ppf(ut)
    else:
        raise ValueError(c.dist)
    cos, sin = detmath.cos_sin_turns(ut)
    return r * cos, r * sin


def _cpks(y: np.ndarray, spec: dict) -> tuple[float | None, float | None]:
    mu, sd = float(np.mean(y)), float(np.std(y, ddof=1))
    p_lo, p50, p_hi = (float(v) for v in np.percentile(y, [0.135, 50.0, 99.865]))
    normal, percentile = [], []
    if spec.get("usl") is not None:
        normal.append((spec["usl"] - mu) / (3 * sd) if sd > 0 else math.inf)
        percentile.append((spec["usl"] - p50) / (p_hi - p50) if p_hi > p50 else math.inf)
    if spec.get("lsl") is not None:
        normal.append((mu - spec["lsl"]) / (3 * sd) if sd > 0 else math.inf)
        percentile.append((p50 - spec["lsl"]) / (p50 - p_lo) if p50 > p_lo else math.inf)
    return (min(normal) if normal else None, min(percentile) if percentile else None)


def _cpk_standard_errors(y: np.ndarray, spec: dict) -> tuple[float | None, float | None]:
    """Delete-a-batch jackknife errors; batches preserve the estimator's tail behavior."""
    if len(y) < BATCH_COUNT * 10:
        return None, None
    indices = np.arange(len(y))
    values = [_cpks(y[np.remainder(indices, BATCH_COUNT) != batch], spec)
              for batch in range(BATCH_COUNT)]
    normal = [v[0] for v in values]
    percentile = [v[1] for v in values]
    scale = (BATCH_COUNT - 1) / math.sqrt(BATCH_COUNT)
    normal_se = float(np.std(normal, ddof=1) * scale) if normal[0] is not None else None
    percentile_se = float(np.std(percentile, ddof=1) * scale) if percentile[0] is not None else None
    return normal_se, percentile_se


def capability(y: np.ndarray, spec: dict) -> dict:
    mu, sd = float(np.mean(y)), float(np.std(y, ddof=1))
    p_lo, p50, p_hi = (float(v) for v in np.percentile(y, [0.135, 50.0, 99.865]))
    n = len(y)
    lsl, usl = spec.get("lsl"), spec.get("usl")
    out_lo = float(np.mean(y < lsl)) if lsl is not None else 0.0
    out_hi = float(np.mean(y > usl)) if usl is not None else 0.0
    cpk_n, cpk_p = _cpks(y, spec)
    cpk_n_se, cpk_p_se = _cpk_standard_errors(y, spec)
    out = out_lo + out_hi
    result = {
        "n": n, "mean": mu, "std": sd, "min": float(np.min(y)), "max": float(np.max(y)),
        "p0135": p_lo, "p50": p50, "p99865": p_hi,
        "out_lo_pct": 100 * out_lo, "out_hi_pct": 100 * out_hi, "out_pct": 100 * out,
        "out_pct_se": 100 * math.sqrt(max(out * (1 - out), 1e-300) / n),
        "cpk_normal": cpk_n, "cpk_percentile": cpk_p,
        "cpk_normal_se": cpk_n_se, "cpk_percentile_se": cpk_p_se,
    }
    return result


CPK_MARGINAL = 1.0  # below this a stack fails outright (yield < 99.73 % for a centred normal)


def classify(r: dict) -> str:
    """Three-level verdict: 'pass', 'marginal' or 'fail'.

    MC-accepted stacks: pass at Cpk >= cpk_min (default 1.33, about 63 ppm out for a centred normal),
    marginal at 1.0 <= Cpk < cpk_min (about 2,700 ... 63 ppm), fail below 1.0. A `max_out_pct` in `accept`
    must also hold for a pass. WC-accepted stacks (jams, interference): pass when the whole worst-case band is
    inside the spec; marginal when worst case breaks the spec but the Monte Carlo Cpk is still >= 1.0 (a rare
    stack-up, so an inspection step can catch it); fail otherwise. A stack whose `requires` stacks fail is
    capped at the worst verdict among them.
    """
    cpk = r["mc"]["cpk_percentile"]
    cpk = -math.inf if cpk is None else cpk
    if r["method"] == "wc":
        v = "pass" if r["pass"]["wc"] else ("marginal" if cpk >= CPK_MARGINAL else "fail")
    elif r["method"] == "rss":
        v = "pass" if r["pass"]["rss"] else ("marginal" if cpk >= CPK_MARGINAL else "fail")
    else:
        ok_out = r["mc"]["out_pct"] <= r["accept"].get("max_out_pct", math.inf)
        v = "pass" if (cpk >= r["cpk_min"] and ok_out) else ("marginal" if cpk >= CPK_MARGINAL else "fail")
    return v


def verdict_band(r: dict) -> list[str]:
    """Verdicts reachable within the Cpk confidence interval.

    WC/RSS pass is deterministic; only their marginal/fail boundary can be undecided.
    """
    cpk = r["mc"]["cpk_percentile"]
    se = r["mc"]["cpk_percentile_se"]
    if cpk is None or se is None:
        return [classify(r)]
    lo = cpk - VERDICT_SE_MULTIPLE * se
    hi = cpk + VERDICT_SE_MULTIPLE * se
    if r["method"] in ("wc", "rss") and r["pass"][r["method"]]:
        return ["pass"]
    thresholds = [CPK_MARGINAL]
    if r["method"] == "mc":
        thresholds.append(r["cpk_min"])
    points = [lo, hi] + [t for t in thresholds if lo <= t <= hi]
    found = set()
    for point in points:
        trial = {**r, "mc": {**r["mc"], "cpk_percentile": point}}
        found.add(classify(trial))
    if r["method"] == "mc" and "max_out_pct" in r["accept"] and "pass" in found:
        events = int(round(r["mc"]["out_pct"] * r["mc"]["n"] / 100))
        upper_pct = 100 * small_count_upper_bound(events, r["mc"]["n"])
        if upper_pct > r["accept"]["max_out_pct"]:
            found.remove("pass")
    return sorted(found, key={"pass": 0, "marginal": 1, "fail": 2}.get)


def worst(*vs: str) -> str:
    order = {"pass": 0, "marginal": 1, "fail": 2}
    return max(vs, key=order.__getitem__)


def verdict_fields(r: dict, dependency_bands=()) -> dict:
    """Derive stored verdict fields from result numbers and dependency bands."""
    own_band = verdict_band(r)
    bands = [own_band, *dependency_bands]
    combined = sorted(
        {worst(*choices) for choices in itertools.product(*bands)},
        key={"pass": 0, "marginal": 1, "fail": 2}.get,
    )
    return {
        "own_verdict3": worst(*own_band),
        "verdict3": worst(*combined),
        "verdict_decided": len(combined) == 1,
        "verdict_band": combined,
    }


def _within(lo, hi, spec):
    ok = True
    if spec.get("lsl") is not None:
        ok &= lo >= spec["lsl"] - 1e-12
    if spec.get("usl") is not None:
        ok &= hi <= spec["usl"] + 1e-12
    return bool(ok)


def _expression_bands(st, lin, bank, n):
    lin = [c for c in st.contributors if c.is_linear_term]
    rad = [c for c in st.contributors if not c.is_linear_term]
    names = [c.name for c in lin]
    consts = {k: v for k, v in (st.constants_used or {}).items() if isinstance(v, (int, float))}
    f = lambda vals: float(_eval_expr(st.expression, {**consts, **dict(zip(names, vals))}))  # noqa: E731
    nominal = f([c.nom_value for c in lin])
    mids = [c.mid for c in lin]
    mid = f(mids)
    sens = []
    for i, c in enumerate(lin):
        h = max(c.half, 1e-6) * 1e-3
        up, dn = list(mids), list(mids)
        up[i] += h
        dn[i] -= h
        sens.append((f(up) - f(dn)) / (2 * h))
    if len(lin) <= 16:
        vals = [f([c.mid + s * c.half for c, s in zip(lin, signs)])
                for signs in itertools.product((-1, 1), repeat=len(lin))]
        wc = (min(vals + [mid]), max(vals + [mid]))
    else:
        hw = sum(abs(a) * c.half for a, c in zip(sens, lin))
        wc = (mid - hw, mid + hw)
    rc = math.sqrt(sum((a * c.rss_half) ** 2 for a, c in zip(sens, lin)))
    rd = 3 * math.sqrt(sum((a * c.sigma) ** 2 for a, c in zip(sens, lin)))
    rss_classic, rss_dist = (mid - rc, mid + rc), (mid - rd, mid + rd)
    draws = {c.name: _sample(c, bank, n, st.id) for c in lin}
    y = np.asarray(_eval_expr(st.expression, {**consts, **draws}), float)
    var_y = float(np.var(y))
    var_parts = []
    for c in lin:
        held = float(np.mean(draws[c.name])) if c.dep is not None else c.mid
        env = {**consts, **{**draws, c.name: np.full(n, held)}}
        y_i = np.asarray(_eval_expr(st.expression, env), float)
        var_parts.append(max(var_y - float(np.var(y_i)), 0.0))
    mc_lo, mc_hi = (float(v) for v in np.percentile(y, [0.135, 99.865]))
    slack = 0.25 * (rss_dist[1] - rss_dist[0]) / 2 + 1e-12
    rss_nonlinear = bool(mc_lo < rss_dist[0] - slack or mc_hi > rss_dist[1] + slack)
    return nominal, mid, wc, rss_classic, rss_dist, y, var_parts, list(zip(lin, sens)), rss_nonlinear


def _linear_bands(st, lin, rad, bank, n):
    nominal = st.constant + sum(c.a * c.nom_value for c in lin)
    mid = st.constant + sum(c.a * c.mid for c in lin)
    hw = sum(abs(c.a) * c.half for c in lin)
    rc_lin = math.sqrt(sum((c.a * c.rss_half) ** 2 for c in lin))
    rd_lin = 3 * math.sqrt(sum((c.a * c.sigma) ** 2 for c in lin))
    y = np.full(n, st.constant, float)
    for c in lin:
        y += c.a * _sample(c, bank, n, st.id)
    var_parts = [(c.a * c.sigma) ** 2 for c in lin]
    if rad:
        Rs = [abs(c.a) * c.half for c in rad]
        R_wc = sum(Rs)
        R_min = max(0.0, 2 * max(Rs) - R_wc) if all(c.dist == "ring" for c in rad) else 0.0
        R_classic = math.sqrt(sum(r * r for r in Rs))
        R_rss = RAYLEIGH_9973 * math.sqrt(sum((c.a * c.sigma) ** 2 for c in rad))
        wc = (mid - hw + R_min, mid + hw + R_wc)
        rss_classic = (mid - rc_lin, mid + math.hypot(rc_lin, R_classic))
        rss_dist = (mid - rd_lin, mid + math.hypot(rd_lin, R_rss))
        vx, vy = np.zeros(n), np.zeros(n)
        for c in rad:
            x, yy = _sample_radial(c, bank, n, st.id)
            vx += c.a * x
            vy += c.a * yy
        y = y + np.sqrt(vx * vx + vy * vy)
        var_parts += [2 * (c.a * c.sigma) ** 2 for c in rad]
    else:
        wc = (mid - hw, mid + hw)
        rss_classic = (mid - rc_lin, mid + rc_lin)
        rss_dist = (mid - rd_lin, mid + rd_lin)
    rows = [(c, c.a) for c in lin] + [(c, c.a) for c in rad]
    return nominal, mid, wc, rss_classic, rss_dist, y, var_parts, rows


def _contributor_rows(rows, var_parts):
    tot = sum(var_parts) or 1.0
    contrib = []
    for (c, a), v in zip(rows, var_parts):
        projection = (" (2nd-axis proj.)" if c.project_axis else " (X proj.)") if c.project else ""
        contrib.append({
            "name": c.name, "kind": c.kind + projection, "nominal": c.nom_value,
            "bias": c.bias, "upper": c.upper, "lower": c.lower, "mid": c.mid, "half": c.half,
            "sensitivity": a, "dist": "empirical" if c.dep is not None else c.dist,
            "sigma": c.sigma, "tag": c.tag, "source": c.source, "note": c.note,
            "from_stack": c.from_stack, "gdt": c.gdt, "var_pct": 100 * v / tot})
    return contrib


def analyse(st: Stack, n: int = 100_000, seed: int = 20260922, bank: SampleBank | None = None) -> dict:
    if bank is None:
        bank = SampleBank(n, seed)
    n, seed = bank.n, bank.seed
    nwarn = len(bank.warnings)
    lin = [c for c in st.contributors if c.is_linear_term]
    rad = [c for c in st.contributors if not c.is_linear_term]
    if st.mode == "expression":
        if rad:
            raise ValueError("radial contributors are not supported in expression mode")
        bands = _expression_bands(st, lin, bank, n)
        nominal, mid, wc, rss_classic, rss_dist, y, var_parts, rows, rss_nonlinear = bands
    else:
        bands = _linear_bands(st, lin, rad, bank, n)
        nominal, mid, wc, rss_classic, rss_dist, y, var_parts, rows = bands
        rss_nonlinear = False
    rss_raw = rss_dist
    rss_dist = (max(rss_dist[0], wc[0]), min(rss_dist[1], wc[1]))
    rss_clipped = rss_dist != rss_raw
    contrib = _contributor_rows(rows, var_parts)
    mc = capability(y, st.spec)
    wc_ok = _within(*wc, st.spec)
    rss_ok = _within(*rss_dist, st.spec)
    cpk_min = st.accept.get("cpk_min", 1.33)
    mc_ok = mc["cpk_percentile"] is not None and mc["cpk_percentile"] >= cpk_min
    if "max_out_pct" in st.accept:
        mc_ok = mc_ok and mc["out_pct"] <= st.accept["max_out_pct"]
    method = st.accept.get("method", "mc")
    verdict = {"wc": wc_ok, "rss": rss_ok, "mc": mc_ok}[method]
    dom = max(contrib, key=lambda c: c["var_pct"]) if contrib else None
    result = {
        "role": st.role, "fix": st.fix, "fix_variant": st.fix_variant, "companion_of": st.companion_of,
        "dominant": {"name": dom["name"], "var_pct": dom["var_pct"]} if dom else None,
        "yield_pct": 100.0 - mc["out_pct"],
        "id": st.id, "title": st.title, "mode": st.mode, "units": st.units,
        "requirement": st.requirement, "notes": st.notes, "spec": st.spec, "accept": st.accept,
        "variant_of": st.variant_of, "variant_label": st.variant_label, "path": st.path,
        "nominal": nominal, "mid": mid, "wc": wc, "rss_classic": rss_classic, "rss_dist": rss_dist,
        "rss_dist_unclipped": rss_raw, "rss_clipped": rss_clipped, "rss_nonlinear": rss_nonlinear,
        "warnings": bank.warnings[nwarn:], "requires": list(st.accept.get("requires") or []),
        "blocked_by": [], "own_verdict": bool(verdict),
        "mc": mc, "pass": {"wc": wc_ok, "rss": rss_ok, "mc": mc_ok}, "verdict": bool(verdict),
        "method": method, "cpk_min": cpk_min, "contributors": contrib, "seed": seed,
        "_samples": y,
    }
    result.update(verdict_fields(result))
    return result
