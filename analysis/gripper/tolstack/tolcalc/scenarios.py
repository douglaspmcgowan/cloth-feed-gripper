"""Combined scenarios (CAD rev B overlay, hot seat, servo width) and input sensitivity.

Both read `stacks/rev_b.yaml`. A *case* re-runs every baseline stack with a set of constant overrides and a
stack-to-variant `pick` (for the rev B changes that are structural, not a constant), so the whole design is
judged as one set instead of one fix at a time.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from . import run_all
from .engine import CPK_MARGINAL, VERDICT_SE_MULTIPLE
from .model import load_constants, load_stacks
from . import report

KEYS = ("id", "title", "role", "variant_of", "nominal", "wc", "spec", "units", "method", "verdict3",
        "own_verdict3", "verdict_band", "verdict_decided", "sampling_runs", "yield_pct", "dominant",
        "blocked_by", "rss_clipped", "warnings")


def load_overlay(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def case_plan(overlay: dict, name: str) -> tuple[dict, dict]:
    """(constant overrides, stack pick) of a case."""
    case = overlay["cases"][name]
    consts: dict = {}
    pick: dict = {}
    if case.get("base", True):
        consts.update(overlay["rev_b"].get("set") or {})
        pick.update(overlay["rev_b"].get("pick") or {})
    if case.get("set_from"):
        consts.update(overlay[case["set_from"]]["set"])
    consts.update(case.get("set") or {})
    pick.update(case.get("pick") or {})
    return consts, pick


def base_ids(stacks_dir: Path) -> list[str]:
    ids = []
    for f in sorted(Path(stacks_dir).glob("*.yaml"), key=lambda p: p.name.lower()):
        s = load_stacks(f)
        if s:
            ids.append(s[0].id)
    return ids


def run_case(stacks_dir: Path, overlay: dict, name: str, n: int, seed: int, extra: dict | None = None):
    """Run every baseline stack under a case; a picked stack is replaced by its variant.
    Returns (results, also): `also` holds the extra variants listed under rev_b.also, shown but not tallied."""
    consts, pick = case_plan(overlay, name)
    consts = {**consts, **(extra or {})}
    ids = base_ids(stacks_dir)
    want = [f"{i}-{pick[i]}" if i in pick else i for i in ids]
    also = list(overlay["rev_b"].get("also") or []) if overlay["cases"][name].get("base", True) else []
    res = run_all([str(stacks_dir)], n=n, seed=seed, const_overrides=consts, only=set(want) | set(also))
    by = {r["id"]: r for r in res}
    missing = [w for w in want if w not in by]
    if missing:
        raise SystemExit(f"case {name}: stack(s) not found: {', '.join(missing)}")
    out = []
    for i, w in zip(ids, want):
        r = by[w]
        r["_base_id"] = i
        r["_picked"] = w if w != i else None
        out.append(r)
    for a in also:
        by[a]["_base_id"], by[a]["_picked"] = a.split("-")[0], a
    return out, [by[a] for a in also]


def trim(r: dict) -> dict:
    d = {k: r[k] for k in KEYS if k in r}
    d["base_id"] = r["_base_id"]
    d["picked_variant"] = r["_picked"]
    d["mc"] = {k: r["mc"][k] for k in ("mean", "std", "p0135", "p99865", "out_pct",
                                                "cpk_percentile", "cpk_percentile_se", "n")}
    return d


def cpk(r) -> float:
    c = r["mc"]["cpk_percentile"]
    return float("inf") if c is None else c


def cpk_uncertainty(r) -> float | None:
    """Half-width of the 99 % Cpk interval: 2.576 x the delete-a-batch jackknife standard error."""
    se = r["mc"].get("cpk_percentile_se")
    return None if se is None else VERDICT_SE_MULTIPLE * se


def threshold_sides(c: dict) -> list[tuple[str, float]]:
    """(side, threshold) for each side of a verdict change whose Cpk lies within its uncertainty of 1.00 or cpk_min."""
    out = []
    for side, v, u in (("before", c["cpk_from"], c["cpk_u_from"]), ("after", c["cpk_to"], c["cpk_u_to"])):
        for t in (CPK_MARGINAL, c["cpk_min"]):
            if u is not None and abs(v - t) <= u:
                out.append((side, t))
                break
    return out


def at_threshold(c: dict) -> bool:
    """True when the Cpk on either side of a verdict change lies within its uncertainty of 1.00 or cpk_min."""
    return bool(threshold_sides(c))


def threshold_note(c: dict) -> str:
    """Name the undecided side: ' (at threshold: before within sampling error of 1.33)'."""
    sides = threshold_sides(c)
    if not sides:
        return ""
    return " (at threshold: " + ", ".join(f"{s} within sampling error of {t:.2f}" for s, t in sides) + ")"


def differs(a: dict, b: dict) -> bool:
    """True when two results of the same check differ in verdict or by more than 0.005 in Cpk."""
    return a["verdict3"] != b["verdict3"] or abs(cpk(a) - cpk(b)) > 0.005


def case_table(res: list[dict], ref: list[dict] | None, also: list[dict] | None = None,
               main: list[dict] | None = None) -> list[str]:
    """Rows of a case. With `main`, only the checks that differ from that main case are listed."""
    refs = {r["_base_id"]: r for r in ref} if ref else {}
    L = ["| Stack | Run as | Verdict | Yield (MC) | Cpk | Worst case | Spec | Rev A as drawn |",
         "|---|---|---|---|---:|---|---|---|"]
    mains = {r["_base_id"]: r for r in main} if main else {}
    for r in list(res) + ([dict(x, _also=True) for x in (also or [])] if main is None else []):
        if main is not None and not differs(r, mains[r["_base_id"]]):
            continue
        d = refs.get(r["_base_id"])
        was = f"{report.V3[d['verdict3']]}, Cpk {report.f3(d['mc']['cpk_percentile'], 2)}" if d else "-"
        run_as = (r["_picked"] or "base stack") + (" (alternative, not counted)" if r.get("_also") else "")
        L.append(f"| {r['_base_id']} | {run_as} | **{report.v3_str(r)}** | "
                 f"{report.yield_str(r)} | {report.cpk_str(r['mc'])} | "
                 f"{report.rng_str(r['wc'])} ({'in' if r['pass']['wc'] else 'out'}) | "
                 f"{report.spec_str(r['spec'])} {r['units'].split(' (')[0]} | {was} |")
    return L


def tally(res: list[dict]) -> dict:
    v = [r["verdict3"] for r in res]
    own = [r["own_verdict3"] for r in res]
    thin = min(res, key=cpk)
    thin_unwaived = min((r for r in res if r["_base_id"] not in ("T03", "T03B")), key=cpk)
    return {"n": len(res), "pass": v.count("pass"), "marginal": v.count("marginal"), "fail": v.count("fail"),
            "undecided": sum(not r["verdict_decided"] for r in res),
            "own_fail": own.count("fail"), "thinnest": thin["_base_id"], "thinnest_cpk": cpk(thin),
            "thinnest_ex_horn": thin_unwaived["_base_id"], "thinnest_ex_horn_cpk": cpk(thin_unwaived),
            "marginal_ids": [r["_base_id"] for r in res if r["verdict3"] == "marginal"],
            "fail_ids": [r["_base_id"] for r in res if r["verdict3"] == "fail"]}


def tally_line(t: dict) -> str:
    s = (f"{t['n']} checks: {t['pass']} PASS, {t['marginal']} MARGINAL, {t['fail']} FAIL, "
         f"{t['undecided']} UNDECIDED (gated worse) "
         f"({t['own_fail']} independent).")
    if t["marginal_ids"]:
        s += f" MARGINAL: {', '.join(t['marginal_ids'])}."
    if t["fail_ids"]:
        s += f" FAIL: {', '.join(t['fail_ids'])}."
    s += f" Thinnest by Cpk: {t['thinnest']}, Cpk {t['thinnest_cpk']:.2f}."
    return s


# ---------------------------------------------------------------- sensitivity

def scaled_overrides(stacks_dir: Path, base_consts: dict, factor: dict, scale: float) -> dict:
    """Override the named basis constants by `scale` times the value they have under `base_consts`."""
    ns, _ = load_constants(Path(stacks_dir) / "basis.yaml", base_consts)
    out = dict(base_consts)
    for c in factor["consts"]:
        out[c] = ns[c] * scale
    return out


def sample_head_sha256(r: dict) -> str:
    """SHA-256 of the first 1000 samples of the run at the requested n and seed (before any undecided rerun)."""
    if r.get("sampling_runs"):
        return r["sampling_runs"][0]["sample_head_sha256"]
    return hashlib.sha256(r["_samples"][:1000].tobytes()).hexdigest()


def run_sens(stacks_dir: Path, overlay: dict, n: int, seed: int, progress=None) -> dict:
    sens = overlay["sensitivity"]
    ids = base_ids(stacks_dir)
    changes = []
    table = {}
    for design in sens["designs"]:
        consts, pick = case_plan(overlay, "revb" if design == "revb" else "drawn")
        want = [f"{i}-{pick[i]}" if i in pick else i for i in ids]
        ref = {r["id"]: r for r in run_all([str(stacks_dir)], n=n, seed=seed, const_overrides=consts, only=set(want))}
        for f in sens["factors"]:
            for sc in sens["scales"]:
                ov = scaled_overrides(stacks_dir, consts, f, sc)
                if progress:
                    progress(f"{design} {f['id']} x{sc}")
                got = {r["id"]: r for r in run_all([str(stacks_dir)], n=n, seed=seed, const_overrides=ov,
                                                   only=set(want))}
                for i, w in zip(ids, want):
                    a, b = ref[w], got[w]
                    table.setdefault((design, f["id"], sc), {})[i] = (a["verdict3"], b["verdict3"], cpk(a), cpk(b),
                                                                    a["mc"]["out_pct"], b["mc"]["out_pct"])
                    if a["verdict3"] != b["verdict3"]:
                        changes.append({"design": design, "factor": f["id"], "label": f["label"], "scale": sc,
                                        "stack": i, "from": a["verdict3"], "to": b["verdict3"],
                                        "cpk_from": cpk(a), "cpk_to": cpk(b), "cpk_min": b["cpk_min"],
                                        "cpk_u_from": cpk_uncertainty(a), "cpk_u_to": cpk_uncertainty(b),
                                        "yield_from": 100 - a["mc"]["out_pct"], "yield_to": 100 - b["mc"]["out_pct"],
                                        "sample_head_sha256": sample_head_sha256(b)})
    return {"samples": n, "seed": seed, "scales": sens["scales"], "factors": sens["factors"], "changes": changes}


def sens_tables(data: dict) -> list[str]:
    L = []
    for design, title in (("drawn", "CAD rev A as drawn"), ("revb", "CAD rev B, all changes at once")):
        rows = [c for c in data["changes"] if c["design"] == design]
        L += [f"**{title}**", ""]
        if not rows:
            L += ["No verdict changes at 0.5x or 2x.", ""]
            continue
        L += ["| Input scaled | x | Stack | Verdict change | Cpk | Yield (MC) |", "|---|---:|---|---|---|---|"]
        order = {f["id"]: i for i, f in enumerate(data["factors"])}
        for c in sorted(rows, key=lambda c: (order[c["factor"]], c["scale"], c["stack"])):
            y = lambda v: "100 %" if v >= 99.99999 else (f"{v:.3f} %" if v >= 99.99 else f"{v:.2f} %")  # noqa: E731
            u = lambda v: "" if v is None else f" ± {v:.3f}"  # noqa: E731
            note = threshold_note(c)
            L.append(f"| {c['label']} | {c['scale']:g} | {c['stack']} | {report.V3[c['from']]} -> "
                     f"**{report.V3[c['to']]}**{note} | {c['cpk_from']:.2f}{u(c['cpk_u_from'])} -> "
                     f"{c['cpk_to']:.2f}{u(c['cpk_u_to'])} | {y(c['yield_from'])} -> {y(c['yield_to'])} |")
        quiet = [f["label"] for f in data["factors"]
                 if not any(c["design"] == design and c["factor"] == f["id"] for c in data["changes"])]
        if quiet:
            L += ["", "No verdict change at 0.5x or 2x: " + "; ".join(quiet) + "."]
        L.append("")
    L.append("Cpk ± is the 99 % sampling uncertainty: 2.576 x the delete-a-batch jackknife standard error of the "
             "percentile Cpk (20 interleaved batches of the run's samples). A change is marked *at threshold* when the "
             "Cpk before or after lies within that uncertainty of 1.00 or of the stack's cpk_min (1.33 unless set); "
             "the label names that side, whose verdict is not resolved; a side not named is resolved.")
    return L
