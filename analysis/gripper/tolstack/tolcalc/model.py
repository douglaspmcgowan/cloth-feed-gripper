"""Stack definitions: YAML loading, constants, contributors."""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from . import gdt as gdtmod

SAFE = {k: getattr(math, k) for k in (
    "sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "atan2", "radians", "degrees",
    "pi", "hypot", "exp", "log")}
SAFE.update(abs=abs, min=min, max=max)

DISTS_LINEAR = {"normal", "uniform", "triangular", "empirical"}
DISTS_RADIAL = {"disk", "normal2d", "ring", "ring_uniform"}


def evaluate(v, ns: dict):
    """Numbers pass through; strings starting with '=' are arithmetic on constants."""
    if isinstance(v, str) and v.strip().startswith("="):
        return float(eval(v.strip()[1:], {"__builtins__": {}}, {**SAFE, **ns}))  # noqa: S307
    return v


def load_constants(path: Path, overrides: dict | None = None) -> tuple[dict, dict]:
    """Return (values, meta). Entries are numbers, '=expr' strings, or {value, tag, source}."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw = data.get("constants", data)
    ns: dict = {}
    meta: dict = {}
    overrides = overrides or {}
    for k, v in raw.items():
        m = {}
        if isinstance(v, dict):
            m = {kk: vv for kk, vv in v.items() if kk != "value"}
            v = v.get("value")
        if k in overrides:
            v = overrides[k]
            m = {**m, "overridden": True}
        ns[k] = evaluate(v, ns)
        meta[k] = m
    for k, v in overrides.items():
        if k not in ns:
            ns[k] = evaluate(v, ns)
            meta[k] = {"overridden": True}
    return ns, meta


@dataclass
class Contributor:
    name: str
    nominal: float = 0.0
    upper: float = 0.0          # signed deviation from nominal
    lower: float = 0.0          # signed deviation from nominal
    bias: float = 0.0           # systematic process shift (moves the mean, not the nominal)
    a: float = 1.0              # sensitivity
    dist: str = "normal"
    k: float = 3.0              # tol = k*sigma for normal / normal2d
    kind: str = "linear"        # linear | radial
    source: str = ""
    tag: str = "A"
    note: str = ""
    gdt: dict | None = None
    from_stack: str | None = None
    project: bool = False       # radial zone entered as one in-plane component (linear term)
    project_axis: int = 0       # 0 = first in-plane axis ("x"), 1 = second ("y"); same disk sample
    radius_scale: float = 1.0   # radial from_stack: per-sample radius = scale * max(0, dep sample)
    shared: str | None = None   # Monte Carlo sharing key (default: name); see engine.SampleBank
    dep: dict | None = field(default=None, repr=False)  # filled by the runner

    @property
    def key(self) -> str:
        return self.shared or self.name

    @property
    def is_linear_term(self) -> bool:
        return self.kind == "linear" or self.project

    @property
    def nom_value(self) -> float:
        """Nominal used in the stack sum (a radial zone has nominal 0)."""
        if self.kind == "radial":
            return 0.0
        return self.nominal if self.dep is None else self.dep["nominal"]

    def dep_radius_samples(self):
        import numpy as np
        return self.radius_scale * np.clip(np.asarray(self.dep["_samples"], float), 0.0, None)

    @property
    def mid(self) -> float:
        if self.dep is not None and self.kind == "radial":
            return 0.0
        if self.dep is not None:
            return 0.5 * (self.dep["wc"][0] + self.dep["wc"][1])
        return self.nominal + self.bias + 0.5 * (self.upper + self.lower)

    @property
    def half(self) -> float:
        if self.dep is not None and self.kind == "radial":
            return self.radius_scale * max(0.0, self.dep["wc"][1])
        if self.dep is not None:
            return 0.5 * (self.dep["wc"][1] - self.dep["wc"][0])
        return 0.5 * (self.upper - self.lower)

    @property
    def rss_half(self) -> float:
        if self.dep is not None and self.kind != "radial":
            return 0.5 * (self.dep["rss_classic"][1] - self.dep["rss_classic"][0])
        return self.half

    @property
    def sigma(self) -> float:
        """Standard deviation along the stack (linear) or per axis (radial)."""
        h = self.half
        if self.dep is not None and self.kind == "radial":
            r2 = float(np.mean(self.dep_radius_samples() ** 2))
            div = {"disk": 4.0, "ring": 2.0, "ring_uniform": 6.0}.get(self.dist)
            if div is None:
                raise ValueError(f"{self.name}: radial from_stack supports disk, ring, ring_uniform")
            return math.sqrt(r2 / div)
        if self.dep is not None:
            return self.dep["mc"]["std"]
        if self.kind == "radial":
            return {"disk": h / 2.0, "normal2d": h / self.k, "ring": h / math.sqrt(2.0),
                    "ring_uniform": h / math.sqrt(6.0)}[self.dist]
        return {"normal": h / self.k, "uniform": h / math.sqrt(3.0),
                "triangular": h / math.sqrt(6.0)}[self.dist]


def _tolerance(d: dict, ns: dict) -> tuple[float, float]:
    ev = lambda key, default=None: evaluate(d.get(key, default), ns)  # noqa: E731
    if "gdt" in d and d["gdt"]:
        g = {k: evaluate(v, ns) for k, v in d["gdt"].items()}
        return gdtmod.convert(g)
    if "tol" in d:
        t = abs(float(ev("tol")))
        return t, -t
    if "upper" in d or "lower" in d:
        return float(ev("upper", 0.0)), float(ev("lower", 0.0))
    if "unilateral" in d:
        u = float(ev("unilateral"))
        return (u, 0.0) if u >= 0 else (0.0, u)
    return 0.0, 0.0


PROJECT_AXES = {True: 0, "x": 0, "first": 0, "y": 1, "second": 1}


def _project(d: dict) -> tuple[bool, int]:
    """`project: true | x | first` -> first in-plane component; `y | second` -> second component."""
    p = d.get("project", False)
    if p in (False, None):
        return False, 0
    if p not in PROJECT_AXES:
        raise ValueError(f"{d['name']}: project must be true, x/first or y/second, not {p!r}")
    if d.get("kind", "linear") != "radial":
        raise ValueError(f"{d['name']}: project needs kind: radial")
    return True, PROJECT_AXES[p]


def parse_contributor(d: dict, ns: dict) -> Contributor:
    ev = lambda key, default=None: evaluate(d.get(key, default), ns)  # noqa: E731
    kind = d.get("kind", "linear")
    dist = d.get("dist", "disk" if kind == "radial" else "normal")
    if kind == "radial" and dist not in DISTS_RADIAL:
        raise ValueError(f"{d['name']}: radial dist must be one of {sorted(DISTS_RADIAL)}")
    if kind == "linear" and dist not in DISTS_LINEAR:
        raise ValueError(f"{d['name']}: linear dist must be one of {sorted(DISTS_LINEAR)}")
    a = float(ev("sensitivity", ev("direction", 1.0)))
    if "limits" in d:
        lo, hi = (float(evaluate(x, ns)) for x in d["limits"])
        nominal = float(ev("nominal", 0.5 * (lo + hi)))
        upper, lower = hi - nominal, lo - nominal
    else:
        nominal = float(ev("nominal", 0.0))
        upper, lower = _tolerance(d, ns)
    if kind == "radial":
        # a radial zone of radius R: stored as +/-R about zero (radius from a stack: see from_stack)
        R = float(ev("radius", upper if "gdt" in d or "tol" in d else 0.0))
        nominal, upper, lower = 0.0, R, -R
    return Contributor(
        name=d["name"], nominal=nominal, upper=upper, lower=lower, bias=float(ev("bias", 0.0)),
        a=a, dist=dist, k=float(ev("sigma", 3.0)), kind=kind, source=str(d.get("source", "")),
        tag=str(d.get("tag", "A")), note=str(d.get("note", "")), gdt=d.get("gdt"),
        from_stack=d.get("from_stack"), project=_project(d)[0], project_axis=_project(d)[1],
        radius_scale=float(ev("radius_scale", 1.0)), shared=d.get("shared"))


@dataclass
class Stack:
    id: str
    title: str
    mode: str
    contributors: list
    spec: dict
    accept: dict
    constant: float = 0.0
    expression: str | None = None
    units: str = "mm"
    requirement: str = ""
    notes: str = ""
    variant_of: str | None = None
    variant_label: str = ""
    path: str = ""
    constants_used: dict = field(default_factory=dict)
    role: str = "baseline"      # baseline (CAD rev A as drawn) | option (a change to consider) | rejected | scenario
    fix: str = ""               # cheapest change that fixes a marginal or failing baseline (text)
    fix_variant: str | None = None  # id of the variant that proves that fix
    companion_of: str | None = None  # a second check on the same interface (T01H of T01, ...)


ROLES = {"baseline", "option", "rejected", "scenario"}

REPO_ROOT = Path(__file__).resolve().parents[4]


def repo_path(path) -> str:
    """Repository-relative posix path, so result files do not carry a machine path."""
    p = Path(path).resolve()
    try:
        return p.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.name


def _stack_from_dict(d: dict, ns: dict, sid: str, path: str, variant_of=None, label="", role="baseline") -> Stack:
    if role not in ROLES:
        raise ValueError(f"{sid}: role must be one of {sorted(ROLES)}, not {role!r}")
    spec = {k: float(evaluate(v, ns)) for k, v in (d.get("spec") or {}).items() if v is not None}
    accept = dict(d.get("accept") or {"method": "mc"})
    for k in ("cpk_min", "max_out_pct"):
        if k in accept:
            accept[k] = float(evaluate(accept[k], ns))
    cs = [parse_contributor(c, ns) for c in d["contributors"]]
    return Stack(
        id=sid, title=d.get("title", sid).format_map(ns), mode=d.get("mode", "linear"), contributors=cs,
        spec=spec, accept=accept, constant=float(evaluate(d.get("constant", 0.0), ns)),
        expression=d.get("expression"), units=d.get("units", "mm"),
        requirement=str(d.get("requirement", "")), notes=str(d.get("notes", "")),
        variant_of=variant_of, variant_label=label, path=path, constants_used=ns, role=role,
        fix=str(d.get("fix", "")).strip() if variant_of is None else "",
        fix_variant=(f"{sid}-{d['fix_variant']}" if d.get("fix_variant") else None) if variant_of is None else None,
        companion_of=d.get("companion_of"))


def load_stacks(path: Path, const_overrides: dict | None = None) -> list[Stack]:
    """Load one YAML stack file -> [base stack, *variants]."""
    path = Path(path)
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(d, dict) or "id" not in d:
        return []
    cpath = d.get("constants")
    ns: dict = {}
    if cpath:
        ns, _ = load_constants(path.parent / cpath, const_overrides)
    elif const_overrides:
        ns = {k: evaluate(v, {}) for k, v in const_overrides.items()}
    out = [_stack_from_dict(d, ns, d["id"], repo_path(path))]
    for v in d.get("variants") or []:
        vd = copy.deepcopy(d)
        ov = {**(const_overrides or {}), **(v.get("set") or {})}
        vns = load_constants(path.parent / cpath, ov)[0] if cpath else ov
        drop = set(v.get("drop") or [])
        vd["contributors"] = [c for c in vd["contributors"] if c["name"] not in drop]
        vd["contributors"] += v.get("add") or []
        for c in vd["contributors"]:
            if c.get("from_stack") in (v.get("replace_from") or {}):
                c["from_stack"] = v["replace_from"][c["from_stack"]]
        for key in ("spec", "accept", "requirement", "title", "notes", "mode", "expression", "constant", "units"):
            if key in v:
                vd[key] = v[key]
        out.append(_stack_from_dict(vd, vns, f"{d['id']}-{v['id']}", repo_path(path),
                                    variant_of=d["id"], label=v.get("label", v["id"]),
                                    role=v.get("role", "option")))
    return out
