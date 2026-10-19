"""Markdown reports, JSON results and histogram PNGs."""
from __future__ import annotations

import json
import hashlib
import math
import re
from pathlib import Path

import numpy as np
import yaml

from .engine import verdict_fields

INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e6e5e1"
SERIES, CRIT, SURFACE = "#2a78d6", "#d03b3b", "#fcfcfb"
OUT_BOUND_CONFIDENCE = 0.95
from .statistics import small_count_upper_bound  # noqa: E402


def f3(v, p=3):
    if v is None:
        return "-"
    if isinstance(v, float) and (v != v or abs(v) == float("inf")):
        return "inf" if v == float("inf") else "-"
    return f"{v:.{p}f}"


def rng_str(r, p=3):
    return f"{f3(r[0], p)} … {f3(r[1], p)}"


def spec_str(spec):
    parts = []
    if spec.get("lsl") is not None:
        parts.append(f"LSL {f3(spec['lsl'])}")
    if spec.get("usl") is not None:
        parts.append(f"USL {f3(spec['usl'])}")
    return ", ".join(parts) or "none"


def verdict_str(r):
    if r.get("blocked_by"):
        return "FAIL (own " + ("PASS" if r.get("own_verdict") else "FAIL") + "; needs " + \
            ", ".join(r["blocked_by"]) + ")"
    return "PASS" if r["verdict"] else "FAIL"


def rss_str(r, p=3):
    return rng_str(r["rss_dist"], p) + (" †" if r.get("rss_clipped") else "")


def _round_up_two_significant(value: float) -> float:
    scale = 10 ** (math.floor(math.log10(value)) - 1)
    return math.ceil(value / scale - 1e-12) * scale


def out_str(mc: dict) -> str:
    """Sample-honest out-of-specification fraction."""
    n = int(mc["n"])
    events = int(round(mc["out_pct"] * n / 100))
    if events < 10:
        upper_ppm = _round_up_two_significant(small_count_upper_bound(events, n) * 1_000_000)
        return f"<{upper_ppm:g} ppm ({events} of {n:,} samples; 95% upper bound)"
    if mc["out_pct"] < 0.1:
        return f"{mc['out_pct'] * 1e4:.0f} ppm"
    return f"{mc['out_pct']:.3g} %"


def histogram_caption(r: dict) -> str:
    """The histogram's x-axis caption; built from the result dict so a test can rebuild it from the JSON."""
    mc = r["mc"]
    return (f"{r['units']}   (MC N={mc['n']:,}, Cpk {f3(mc['cpk_percentile'], 2)}, out {mc['out_pct']:.3g} %, "
            f"{verdict_str(r)} by {r['method'].upper()})")


def histogram(r: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    y = r["_samples"]
    fig, ax = plt.subplots(figsize=(6.4, 3.4), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    lo = min(np.percentile(y, 0.01), r["wc"][0], *(v for v in r["spec"].values()))
    hi = max(np.percentile(y, 99.99), r["wc"][1], *(v for v in r["spec"].values()))
    pad = 0.05 * (hi - lo or 1.0)
    ax.hist(y, bins=120, range=(lo - pad, hi + pad), color=SERIES, edgecolor=SURFACE, linewidth=0.3)
    ymax = ax.get_ylim()[1]
    for key, lab in (("lsl", "LSL"), ("usl", "USL")):
        if r["spec"].get(key) is not None:
            x = r["spec"][key]
            ax.axvline(x, color=CRIT, lw=1.6)
            ax.text(x, ymax * 0.97, f" {lab} {x:.3g}", color=INK, fontsize=7.5, va="top")
    for x in r["wc"]:
        ax.axvline(x, color=INK2, lw=1.0, ls=(0, (4, 3)))
    for x in r["rss_dist"]:
        ax.axvline(x, color=INK2, lw=1.0, ls=(0, (1, 2)))
    ax.text(0.99, 0.80, "dashed = worst case\ndotted = RSS (dist.)", transform=ax.transAxes,
            ha="right", va="top", fontsize=7, color=INK2)
    mc = r["mc"]
    ax.set_title(f"{r['id']}  {r['title']}", fontsize=9, color=INK, loc="left")
    caption = histogram_caption(json.loads(dumps({k: v for k, v in r.items() if not k.startswith("_")})))  # as stored
    ax.set_xlabel(caption, fontsize=7.5, color=INK2)
    ax.set_ylabel("samples", fontsize=7.5, color=INK2)
    ax.tick_params(colors=MUTED, labelsize=7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE, metadata={"Software": None, "Description": caption})
    plt.close(fig)


def stack_markdown(r: dict, fig_rel: str | None) -> str:
    mc = r["mc"]
    L = [f"# {r['id']} — {r['title']}", ""]
    if r["variant_of"]:
        L += [f"Variant of `{r['variant_of']}` ({r['role']}): {r['variant_label']}", ""]
    else:
        L += ["Baseline: CAD rev A as drawn (`cad/gripper/params.json`, `cad/gripper/README.md`).", ""]
    L += [f"- Requirement: {r['requirement']}", f"- Spec: {spec_str(r['spec'])} {r['units']}",
          f"- Acceptance: {r['method'].upper()}" + (f" (Cpk ≥ {r['cpk_min']:.2f}, percentile method)"
                                                   if r["method"] == "mc" else ""),
          f"- Model: {r['mode']}; source file `{Path(r['path']).name}`; seed {r['seed']}", ""]
    if r["notes"]:
        L += [r["notes"].strip(), ""]
    expr = r["mode"] == "expression"
    if expr:
        L += ["Var % from Monte Carlo freeze-one (non-linear model); Sens. is a central difference at the "
              "mids and does not rank contributors. Worst case is taken over the corners only, so a minimum "
              "inside the box (the kink of abs()) can be missed.", ""]
    L += ["| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |",
          "|---|---|---:|---:|---|---:|---|---:|---:|---|---|"]
    for c in r["contributors"]:
        tol = (f"from {c['from_stack']}" if c["from_stack"] else
               (f"R {f3(c['half'])}" if c["kind"] == "radial" else f"{f3(c['lower'])} / +{f3(c['upper'])}"))
        src = c["source"] + (f" ({c['note']})" if c["note"] else "")
        L.append(f"| {c['name']} | {c['kind']} | {f3(c['nominal'])} | {f3(c['bias'])} | {tol} | "
                 f"{f3(c['sensitivity'], 4)} | {c['dist']} | {f3(c['sigma'], 4)} | {c['var_pct']:.1f} | "
                 f"{c['tag']} | {src} |")
    nl = " — not valid: non-linear model, use Monte Carlo" if r.get("rss_nonlinear") else ""
    L += ["", "| Result | Value |", "|---|---|",
          f"| Nominal | {f3(r['nominal'])} |", f"| Mean-shifted centre | {f3(r['mid'])} |",
          f"| Worst case | {rng_str(r['wc'])} ({'pass' if r['pass']['wc'] else 'fail'}) |",
          f"| RSS classic (t = 3σ) | {rng_str(r['rss_classic'])}{nl} |",
          f"| RSS distribution-adjusted | {rss_str(r)} ({'pass' if r['pass']['rss'] else 'fail'})"
          + (f"; clipped to WC, unclipped {rng_str(r['rss_dist_unclipped'])}" if r.get("rss_clipped") else "")
          + f"{nl} |",
          f"| MC mean / σ | {f3(mc['mean'])} / {f3(mc['std'], 4)} |",
          f"| MC 0.135 % … 99.865 % | {f3(mc['p0135'])} … {f3(mc['p99865'])} |",
          f"| MC min … max | {f3(mc['min'])} … {f3(mc['max'])} |",
          f"| MC out of spec | {out_str(mc)} |",
          f"| Cpk percentile / normal | {cpk_str(mc)} / "
          f"{f3(mc['cpk_normal'], 2)} ± {f3(mc['cpk_normal_se'], 2)} |",
          f"| Yield (MC) | {yield_str(r)} |",
          f"| Dominant contributor | {dom_str(r)} |",
          f"| Pass/fail by the declared method ({r['method'].upper()}) | {verdict_str(r)} |",
          f"| **Verdict (pass / marginal / fail)** | **{v3_str(r)}** |", ""]
    if r.get("fix"):
        L += [f"Cheapest fix: {r['fix']}" + (f" (proved by `{r['fix_variant']}`)" if r.get("fix_variant") else ""), ""]
    if r.get("requires"):
        L += [f"Verdict is conditional on: {', '.join(r['requires'])}.", ""]
    for w in r.get("warnings") or []:
        L += [f"> Warning: {w}", ""]
    if fig_rel:
        L += [f"![{r['id']} histogram]({fig_rel})", ""]
    return "\n".join(L)


V3 = {"pass": "PASS", "marginal": "MARGINAL", "fail": "FAIL"}


def yield_str(r) -> str:
    """Monte Carlo yield in plain words: % inside spec, with parts per million out when small."""
    out = r["mc"]["out_pct"]
    events = int(round(out * r["mc"]["n"] / 100))
    if events < 10:
        return f"{100 - out:.3f} % ({out_str(r['mc'])} out)"
    if out < 0.1:
        return f"{100 - out:.3f} % ({out * 1e4:.0f} ppm out)"
    return f"{100 - out:.2f} %"


def count_line(results: list[dict]) -> str:
    """PASS / MARGINAL / FAIL counts as reported and by each check's own verdict (a blocked check is not a failure of its own)."""
    base = [r for r in results if r["role"] == "baseline"]
    rep = [r["verdict3"] for r in base]
    own = [r["own_verdict3"] for r in base]
    blocked = [r["id"] for r in base if r["verdict3"] != r["own_verdict3"]]
    undecided = sum(not r.get("verdict_decided", True) for r in base)
    s = (f"{len(base)} checks, {rep.count('pass')} PASS, {rep.count('marginal')} MARGINAL, {rep.count('fail')} FAIL "
         f"as reported; {undecided} UNDECIDED (also gated in the worse count); "
         f"by each check's own verdict {own.count('pass')} PASS, {own.count('marginal')} MARGINAL, "
         f"{own.count('fail')} independent FAIL")
    if blocked:
        s += f" ({', '.join(blocked)} reported as blocked by another check, not failing on its own)"
    return s


def v3_str(r) -> str:
    if not r.get("verdict_decided", True):
        choices = " or ".join(V3[v] for v in reversed(r["verdict_band"]))
        s = f"UNDECIDED ({choices}; N={r['mc']['n']:,})"
    else:
        s = V3[r["verdict3"]]
    if r.get("blocked_by"):
        s += f" (blocked by {', '.join(r['blocked_by'])}; own check {V3[r['own_verdict3']]})"
    return s


def cpk_str(mc: dict) -> str:
    return f"{f3(mc['cpk_percentile'], 2)} ± {f3(mc['cpk_percentile_se'], 2)}"


def dom_str(r) -> str:
    d = r.get("dominant")
    return f"{d['name']} ({d['var_pct']:.0f} %)" if d else "-"


def verdict_rows(results: list[dict]) -> list[str]:
    """One row per baseline stack (CAD rev A as drawn): the verdict table."""
    by_id = {r["id"]: r for r in results}
    L = ["| Stack | Checks | Verdict | Yield (MC) | Cpk | Worst case | Spec | Dominant contributor (variance share) "
         "| Cheapest fix (proved by) |",
         "|---|---|---|---|---:|---|---|---|---|"]
    for r in results:
        if r["role"] != "baseline":
            continue
        fx = r.get("fix") or ("none needed" if r["verdict3"] == "pass" else "see the stack notes")
        fv = r.get("fix_variant")
        if fv:
            fr = by_id.get(fv)
            fx += f" ({fv}: {V3[fr['verdict3']]}, Cpk {f3(fr['mc']['cpk_percentile'], 2)})" if fr else f" ({fv}: not run)"
        L.append(f"| {r['id']} | {r['title']} | **{v3_str(r)}** | {yield_str(r)} | "
                 f"{cpk_str(r['mc'])} | {rng_str(r['wc'])} ({'in' if r['pass']['wc'] else 'out'}) | "
                 f"{spec_str(r['spec'])} {r['units'].split(' (')[0]} | {dom_str(r)} | {fx} |")
    return L


def option_rows(results: list[dict]) -> list[str]:
    """Every variant: options (changes to consider), rejected layouts and scenarios."""
    L = ["| Variant | Role | Change | Verdict | Yield (MC) | Cpk | Worst case |",
         "|---|---|---|---|---|---:|---|"]
    for r in results:
        if r["role"] == "baseline":
            continue
        L.append(f"| {r['id']} | {r['role']} | {r['variant_label']} | {v3_str(r)} | {yield_str(r)} | "
                 f"{cpk_str(r['mc'])} | {rng_str(r['wc'])} |")
    return L


def summary_rows(results: list[dict]) -> list[str]:
    L = ["Nominal is the drawn value with no process bias and no radial term; the other columns include both, so "
         "Nominal can lie outside the WC band (T01, T01H, T04, T14B). Mean (MC) is the Monte Carlo mean with the bias.",
         "",
         "| Stack | Role | Nominal | Mean (MC) | WC | RSS (dist.) | MC 99.73 % band | Out % | Cpk | Spec | Accept | Verdict |",
         "|---|---|---:|---:|---|---|---|---:|---:|---|---|---|"]
    for r in results:
        mc = r["mc"]
        name = f"{r['id']} {r['title']}" if not r["variant_of"] else f"{r['id']} ({r['variant_label']})"
        L.append(f"| {name} | {r['role']} | {f3(r['nominal'])} | {f3(mc['mean'])} | {rng_str(r['wc'])} | {rss_str(r)} | "
                 f"{f3(mc['p0135'])} … {f3(mc['p99865'])} | {out_str(mc)} | "
                 f"{cpk_str(mc)} | {spec_str(r['spec'])} | {r['method'].upper()} | "
                 f"**{v3_str(r)}** |")
    if any(r.get("rss_clipped") for r in results):
        L += ["", "† Distribution-adjusted RSS clipped to the worst-case band (a bounded term dominates)."]
    return L


def stable(o, digits=9):
    """Round every float to `digits` significant digits, so a rerun on another machine (other libm / numpy
    build) writes the same bytes: the last-bit noise of the sampler never reaches a result file."""
    if isinstance(o, (float, np.floating)):
        o = float(o)
        return o if o != o or abs(o) == float("inf") else float(f"{o:.{digits}g}")
    if isinstance(o, dict):
        return {k: stable(v, digits) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [stable(v, digits) for v in o]
    return o


def dumps(o) -> str:
    return json.dumps(stable(o), indent=1, default=float)


def write_generated_text(path: Path, text: str) -> None:
    """Write generated text as UTF-8 with platform-independent LF endings."""
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(r: dict, path: Path) -> None:
    clean = {k: v for k, v in r.items() if not k.startswith("_")}
    write_generated_text(path, dumps(clean))


def input_digest(root: Path) -> dict:
    """Hash stack inputs and engine sources using the loop-fingerprint SHA-256 convention."""
    paths = sorted((root / "stacks").glob("*.yaml"), key=lambda item: item.name.lower())
    paths += sorted((root / "tolcalc").glob("*.py"), key=lambda item: item.name.lower())
    paths.append(root / "tolstack.py")
    digest = hashlib.sha256()
    files = []
    for path in paths:
        name = path.relative_to(root).as_posix()
        files.append(name)
        digest.update(name.encode("utf-8") + b"\0" + path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return {"algorithm": "sha256", "digest": digest.hexdigest(), "files": files}


def attach_input_digest(payload: dict, root: Path) -> dict:
    """Return a result payload carrying reproducibility provenance."""
    return {**payload, "input_digest": input_digest(root)}


def generated_run_text(results_dir: Path) -> tuple[dict[str, str], str]:
    """Render run-generated note blocks and SUMMARY.md from committed JSON only."""
    meta = json.loads((results_dir / "summary.json").read_text(encoding="utf-8"))
    if "generated_blocks" in meta and "generated_summary" in meta:
        blocks = dict(meta["generated_blocks"])
        for path in (results_dir / "rev_b" / "revb.json", results_dir / "sens" / "sens.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            blocks.update(payload.get("generated_blocks", {}))
        return blocks, meta["generated_summary"]
    by_id = {}
    for path in sorted(results_dir.glob("*.json"), key=lambda item: item.name.lower()):
        if path.name == "summary.json" or path.name.startswith("sweep_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if "id" in data:
            by_id[data["id"]] = data
    results = [by_id[item["id"]] for item in meta["stacks"]]
    verdicts = "\n".join(verdict_rows(results))
    options = "\n".join(option_rows(results))
    summary = "\n".join(summary_rows(results))
    head = (f"N = {meta['samples']:,} Monte Carlo samples per stack, seed {meta['seed']}. Verdict: "
            "PASS at Cpk ≥ 1.33 (MC-accepted) or worst case inside spec (WC-accepted); MARGINAL at "
            "1.0 ≤ Cpk < 1.33, or a WC-accepted stack whose worst case breaks the spec while Cpk ≥ "
            "1.0; FAIL otherwise.\n\n")
    head += f"Baseline (CAD rev A as drawn): {count_line(results)}.\n\n"
    text = ("# Tolerance stack summary (generated by tolstack.py; do not hand-edit)\n\n" + head
            + "## Verdicts, CAD rev A baseline\n\n" + verdicts
            + "\n\n## Options, rejected layouts and scenarios\n\n" + options
            + "\n\n## All numbers\n\n" + summary + "\n")
    return {"verdicts": verdicts, "options": options, "summary": summary}, text


def marked_block(text: str, name: str) -> str:
    start, end = f"<!-- tolstack:{name}:start -->", f"<!-- tolstack:{name}:end -->"
    match = re.search(re.escape(start) + r"\n(.*?)\n" + re.escape(end), text, flags=re.S)
    if not match:
        raise ValueError(f"missing generated block {name}")
    return match.group(1)


def first_difference(name: str, actual: str, expected: str) -> str | None:
    """Describe the first differing generated line."""
    actual_lines, expected_lines = actual.splitlines(), expected.splitlines()
    for line in range(max(len(actual_lines), len(expected_lines))):
        old = actual_lines[line] if line < len(actual_lines) else "<missing>"
        new = expected_lines[line] if line < len(expected_lines) else "<missing>"
        if old != new:
            return f"{name} line {line + 1}: committed {old!r}; generated {new!r}"
    return None


def check_generated(results_dir: Path, doc: Path, root: Path) -> tuple[list[str], int, int]:
    """Return drift messages plus generated-block and checked-verdict counts."""
    blocks, summary = generated_run_text(results_dir)
    note = doc.read_text(encoding="utf-8")
    checks = [(name, marked_block(note, name), text) for name, text in blocks.items()]
    checks.append(("results/SUMMARY.md",
                   (results_dir / "SUMMARY.md").read_text(encoding="utf-8"), summary))
    errors = []
    current = input_digest(root)
    paths = [path for path in results_dir.rglob("*.json") if "_superseded" not in path.parts]
    stored = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if path.parent == results_dir and isinstance(payload, dict) and "verdict3" in payload:
            stored[path] = payload
    by_id = {payload["id"]: payload for payload in stored.values()}

    def expected(payload: dict, trail=()) -> dict:
        if payload["id"] in trail:
            raise ValueError(f"circular stored verdict dependency: {' -> '.join(trail + (payload['id'],))}")
        dependency_bands = [expected(by_id[item], trail + (payload["id"],))["verdict_band"]
                            for item in payload.get("requires", [])]
        return verdict_fields(payload, dependency_bands)

    for path, payload in stored.items():
        computed = expected(payload)
        for field in ("verdict3", "own_verdict3", "verdict_decided"):
            if payload.get(field) != computed[field]:
                errors.append(
                    f"{path}: {field}: committed {payload.get(field)!r}; computed {computed[field]!r}"
                )
                return errors, len(checks), len(stored)
    for path in sorted(paths, key=lambda item: item.as_posix().lower()):
        payload = json.loads(path.read_text(encoding="utf-8"))
        stored_digest = (payload.get("input_digest") if isinstance(payload, dict)
                         else payload[-1].get("input_digest"))
        if stored_digest != current:
            errors.append(f"{path}: input digest drift")
            break
    for name, actual, expected in checks:
        difference = first_difference(name, actual, expected)
        if difference:
            errors.append(difference)
            break
    return errors, len(checks), len(stored)


def _release_stack_data(stacks_dir: Path) -> dict[str, dict]:
    """Return release metadata from base stack definitions, validating `parts`."""
    stacks = {}
    for path in sorted(stacks_dir.glob("*.yaml"), key=lambda item: item.name.lower()):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "id" not in data:
            continue
        if "parts" not in data:
            raise ValueError(f"{data['id']}: stack definition has no parts key")
        if data.get("constants"):
            from .model import load_constants
            constants, _ = load_constants(path.parent / data["constants"])
            data["title"] = data.get("title", data["id"]).format_map(constants)
        stacks[data["id"]] = data
    return stacks


def release_gate(revb_path: Path, hot_path: Path, stacks_dir: Path) -> str:
    """Build the revision B print gate solely from result JSON and stack metadata."""
    revb = json.loads(revb_path.read_text(encoding="utf-8"))
    hot = json.loads(hot_path.read_text(encoding="utf-8"))
    definitions = _release_stack_data(stacks_dir)
    hot_by_id = {item["base_id"]: item for item in hot["stacks"]}
    held = [item for item in revb["stacks"] if item["verdict3"] in ("fail", "marginal")]
    fails = [item for item in held if item["verdict3"] == "fail"]
    undecided = [item for item in held if not item.get("verdict_decided", True)]
    first = ("Do not print revision B parts in these loops: "
             + ", ".join(item["base_id"] for item in fails)) if fails else "Revision B: no failing fit"
    if undecided:
        first += ". Undecided (gated as worse): " + ", ".join(item["base_id"] for item in undecided)
    lines = [first, "", "| Stack | Loop | Verdict | Cpk cold | Cpk hot | Parts in loop | What clears it |",
             "|---|---|---|---:|---:|---|---|"]
    for item in held:
        sid = item["base_id"]
        definition = definitions[sid]
        hot_cpk = hot_by_id.get(sid, {}).get("mc", {}).get("cpk_percentile")
        fix = str(definition.get("fix") or "none recorded").strip()
        parts = ", ".join(definition["parts"]) or "none recorded"
        lines.append(f"| {sid} | {definition['title']} | {v3_str(item)} | "
                     f"{cpk_str(item['mc'])} | {f3(hot_cpk, 2)} | {parts} | {fix} |")
    failed_parts = {part for item in fails for part in definitions[item["base_id"]]["parts"]}
    all_parts = {part for definition in definitions.values() for part in definition["parts"]}
    clear = ", ".join(sorted(all_parts - failed_parts, key=str.casefold)) or "none"
    lines += ["", f"Clear to print on the assumed inputs: {clear}.",
              "Every verdict rests on at least one assumed input until coupon measurements replace them."]
    return "\n".join(lines)


def update_doc(doc: Path, blocks) -> None:
    """Replace each <!-- tolstack:<name>:start --> ... :end --> block. `blocks` is {name: text} or a
    plain string (the legacy single `summary` block). Missing markers are an error."""
    if isinstance(blocks, str):
        blocks = {"summary": blocks}
    text = doc.read_text(encoding="utf-8")
    for name, table in blocks.items():
        start, end = f"<!-- tolstack:{name}:start -->", f"<!-- tolstack:{name}:end -->"
        if start not in text:
            raise SystemExit(f"{doc}: no {start} marker")
        text = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: f"{start}\n{table}\n{end}",
                      text, flags=re.S)
    write_generated_text(doc, text)
