"""Committed sampled results must equal a fresh regeneration (third review, B1 and B3; follow-ups 1, 2, 4, 5).

A stamped input digest only proves which inputs a file claims; these tests resample and compare the numbers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tolstack  # noqa: E402
from tolcalc import report, run_all, scenarios  # noqa: E402
from tolcalc.model import load_constants  # noqa: E402
from tolcalc.engine import _eval_expr  # noqa: E402

RESULTS = ROOT / "results"
STACKS = ROOT / "stacks"
REPO = ROOT.parents[2]
NOTE = REPO / "docs" / "gripper" / "analysis" / "tolerance_stacks.md"
CHANGELOG = REPO / "cad" / "gripper" / "CHANGELOG.md"
SWEEPS = sorted(RESULTS.glob("sweep_*.json"), key=lambda p: p.name.lower())


def _t09f(**overrides):
    return {r["id"]: r for r in run_all([STACKS], const_overrides=overrides or None, only={"T09F"})}["T09F"]


def test_t09f_floor_servo_error_is_not_cancelled_by_the_contact_error():
    """B1: the floor error has its own sample key, so it carries variance in a default run."""
    r = _t09f()
    terms = {c["name"]: c for c in r["contributors"]}
    assert terms["servo_angle_error"]["var_pct"] > 0
    committed = json.loads((RESULTS / "T09F.json").read_text(encoding="utf-8"))
    assert {c["name"]: c for c in committed["contributors"]}["servo_angle_error"]["var_pct"] > 0


def test_t09f_is_not_marginal_at_the_basis_servo_repeatability():
    r = _t09f(servo_angle_rep_deg=0.5)
    assert r["verdict3"] != "marginal"


def test_sweep_files_name_the_sweep_set():
    assert len(SWEEPS) == 7
    for path in SWEEPS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert {"paths", "values", "overrides"} <= payload.keys(), path.name


@pytest.mark.parametrize("path", SWEEPS, ids=lambda p: p.stem)
def test_committed_sweep_equals_fresh_regeneration(path, tmp_path, capsys):
    """B3: rerun cmd_sweep from the stored stack, param, values, samples, seed and overrides; compare bytes."""
    stored = json.loads(path.read_text(encoding="utf-8"))
    out = tmp_path / path.with_suffix(".md").name
    args = argparse.Namespace(
        paths=[str(ROOT / p) for p in stored["paths"]], stack=stored["stack"], param=stored["param"],
        values=stored["values"], samples=stored["samples"], seed=stored["seed"],
        set=[f"{k}={v!r}" if isinstance(v, float) else f"{k}={v}" for k, v in stored["overrides"].items()],
        out=str(out))
    assert tolstack.cmd_sweep(args) == 0
    capsys.readouterr()
    assert out.read_bytes() == path.with_suffix(".md").read_bytes(), f"{path.with_suffix('.md').name} is stale"
    assert out.with_suffix(".json").read_bytes() == path.read_bytes(), f"{path.name} is stale"


def _sens():
    return json.loads((RESULTS / "sens" / "sens.json").read_text(encoding="utf-8"))


def test_every_sens_row_stores_its_sample_head():
    rows = _sens()["changes"]
    assert rows and all(re.fullmatch(r"[0-9a-f]{64}", c["sample_head_sha256"]) for c in rows)


@pytest.mark.parametrize("index", range(len(_sens()["changes"])))
def test_every_sens_row_resamples_to_its_stored_head(index):
    data = _sens()
    overlay = scenarios.load_overlay(STACKS / "rev_b.yaml")
    row = data["changes"][index]
    consts, pick = scenarios.case_plan(overlay, "revb" if row["design"] == "revb" else "drawn")
    factor = next(f for f in data["factors"] if f["id"] == row["factor"])
    ov = scenarios.scaled_overrides(STACKS, consts, factor, row["scale"])
    want = f"{row['stack']}-{pick[row['stack']]}" if row["stack"] in pick else row["stack"]
    r = {x["id"]: x for x in run_all([STACKS], n=data["samples"], seed=data["seed"], const_overrides=ov,
                                     only={want}, _allow_rerun=False)}[want]
    assert hashlib.sha256(r["_samples"][:1000].tobytes()).hexdigest() == row["sample_head_sha256"]


_SENS_RUNS: dict = {}


def _sens_run(data: dict, design: str, factor_id: str | None = None, scale: float | None = None) -> dict:
    """Every baseline stack of a design rerun as `tolstack.py sens` runs it (unscaled unless a factor is given),
    keyed by base id. Cached per (design, factor, scale): one run serves every row of that change."""
    key = (design, factor_id, scale)
    if key not in _SENS_RUNS:
        overlay = scenarios.load_overlay(STACKS / "rev_b.yaml")
        consts, pick = scenarios.case_plan(overlay, "revb" if design == "revb" else "drawn")
        if factor_id is not None:
            factor = next(f for f in data["factors"] if f["id"] == factor_id)
            consts = scenarios.scaled_overrides(STACKS, consts, factor, scale)
        want = {i: f"{i}-{pick[i]}" if i in pick else i for i in scenarios.base_ids(STACKS)}
        run = {r["id"]: r for r in run_all([str(STACKS)], n=data["samples"], seed=data["seed"],
                                           const_overrides=consts, only=set(want.values()))}
        _SENS_RUNS[key] = {i: run[w] for i, w in want.items()}
    return _SENS_RUNS[key]


@pytest.mark.parametrize("index", range(len(_sens()["changes"])))
def test_every_sens_row_recomputes_its_reported_values(index):
    """Follow-up 7: each stored verdict, Cpk, Cpk uncertainty, yield and cpk_min is the generator's own function of a rerun."""
    data = _sens()
    row = data["changes"][index]
    a = _sens_run(data, row["design"])[row["stack"]]
    b = _sens_run(data, row["design"], row["factor"], row["scale"])[row["stack"]]
    fresh = {
        "from": a["verdict3"], "to": b["verdict3"], "cpk_min": b["cpk_min"],
        "cpk_from": report.stable(scenarios.cpk(a)), "cpk_to": report.stable(scenarios.cpk(b)),
        "cpk_u_from": report.stable(scenarios.cpk_uncertainty(a)), "cpk_u_to": report.stable(scenarios.cpk_uncertainty(b)),
        "yield_from": report.stable(100 - a["mc"]["out_pct"]), "yield_to": report.stable(100 - b["mc"]["out_pct"]),
    }
    assert fresh == {k: row[k] for k in fresh}, f"sens row {index} ({row['factor']} x{row['scale']}, {row['stack']})"


def test_sens_tables_are_rendered_from_the_stored_rows():
    """A label edited in SENS.md, sens.json's block and the note together still differs from the rows."""
    data = _sens()
    body = "\n".join(scenarios.sens_tables(data)).rstrip()
    assert data["generated_blocks"]["sens"] == body
    assert (RESULTS / "sens" / "SENS.md").read_text(encoding="utf-8").endswith(body + "\n")


def test_threshold_label_names_the_undecided_side():
    """Follow-up 4: a FAIL far below 1.00 is resolved; only the side near a threshold is labelled."""
    c = {"cpk_from": 1.31, "cpk_u_from": 0.047, "cpk_to": 0.83, "cpk_u_to": 0.029, "cpk_min": 1.33}
    assert scenarios.threshold_note(c) == " (at threshold: before within sampling error of 1.33)"
    c = {"cpk_from": 1.20, "cpk_u_from": 0.01, "cpk_to": 0.99, "cpk_u_to": 0.02, "cpk_min": 1.33}
    assert scenarios.threshold_note(c) == " (at threshold: after within sampling error of 1.00)"
    assert scenarios.threshold_note(dict(c, cpk_to=0.5)) == ""


@pytest.mark.parametrize("name", ["sin", "cos", "tan", "arctan", "arctan2", "arcsin", "arccos", "hypot",
                                  "exp", "log"])
def test_expressions_cannot_call_a_libm_transcendental(name):
    """Follow-up 5: a C-runtime transcendental would make samples platform-dependent."""
    with pytest.raises(NameError):
        _eval_expr(f"{name}(x)", {"x": 0.5})


# ------------------------------------------------------------ prose quoting sampled results

_SWEEP_REF = re.compile(r"results/(sweep_\w+)\.md")
_MENTION = re.compile(r"\b(T\d+[A-Z]?)\b(?: Cpk)? (-?\d+\.\d\d)\b")
_NUMBER = re.compile(r"(?<![\w.])(\d+\.\d+)(?![\d])")


def _sweep_rows(stem: str) -> tuple[str, dict[float, float]]:
    payload = json.loads((RESULTS / f"{stem}.json").read_text(encoding="utf-8"))
    return payload["stack"].split("-")[0], {round(p[payload["param"]], 6): p["cpk"] for p in payload["points"]}


def _sentences(text: str):
    for line in text.splitlines():
        if line.startswith("|"):
            yield line  # a table row quotes and cites in different cells
        else:
            yield from re.split(r"(?<=\.)\s+(?=[A-Z*(`])", line)


def test_cpk_quoted_beside_a_sweep_citation_equals_the_cited_row():
    """Follow-up 1: in a sentence citing results/sweep_*.md, `<stack> [Cpk] x` after a swept value is that row."""
    checked = 0
    for sentence in _sentences(NOTE.read_text(encoding="utf-8")):
        stems = _SWEEP_REF.findall(sentence)
        if not stems:
            continue
        sweeps = dict(_sweep_rows(s) for s in stems)
        mentions = list(_MENTION.finditer(sentence))
        spans = [m.span() for m in mentions]
        value = None
        events = sorted([(m.start(), "m", m) for m in mentions]
                        + [(n.start(), "n", n) for n in _NUMBER.finditer(sentence)
                           if not any(a <= n.start() < b for a, b in spans)])
        for _, kind, match in events:
            if kind == "n":
                v = round(float(match.group(1)), 6)
                if any(v in rows for rows in sweeps.values()):
                    value = v
                continue
            stack, quoted = match.group(1), float(match.group(2))
            if stack not in sweeps or value is None or value not in sweeps[stack]:
                continue
            assert quoted == round(sweeps[stack][value], 2), (
                f"note quotes {stack} Cpk {quoted} at {value}; the cited sweep row says "
                f"{sweeps[stack][value]:.2f}: {sentence[:160]}")
            checked += 1
    assert checked >= 4


def test_changelog_t14b_cpk_matches_the_rev_b_run():
    """Follow-up 2: the CHANGELOG's T14B Cpk is the combined rev B result."""
    revb = json.loads((RESULTS / "rev_b" / "revb.json").read_text(encoding="utf-8"))
    t14b = next(s for s in revb["stacks"] if s["base_id"] == "T14B")
    quoted = re.findall(r"T14B Cpk (\d+\.\d\d)", CHANGELOG.read_text(encoding="utf-8"))
    assert quoted and all(float(q) == round(t14b["mc"]["cpk_percentile"], 2) for q in quoted)


# ------------------------------------------------- stack Cpk and yield quoted in RISK.md, controls.md and the note

RISK = REPO / "docs" / "gripper" / "RISK.md"
CONTROLS = REPO / "docs" / "gripper" / "analysis" / "controls.md"
_STACK_ID = re.compile(r"\bT\d+[A-Z]?(?:-[A-Za-z0-9]+)*\b")
_CPK = re.compile(r"Cpk (?:to )?([-−]?\d+\.\d\d)\b")
_YIELD = re.compile(r"(\d+(?:\.\d+)?) % (?:yield\b|within \d+(?:\.\d+)? [Ns]\b)|\byield (\d+(?:\.\d+)?) %")


def _result_rows() -> dict[str, list[tuple[float, float | None]]]:
    """Every stored (Cpk, yield %) per stack id: run results, every rev B case, and sweep points."""
    rows: dict[str, list[tuple[float, float | None]]] = {}

    def add(key, mc, yld):
        row = (round(mc["cpk_percentile"], 2) if mc["cpk_percentile"] is not None else None,
               yld)
        rows.setdefault(key, []).append(row)
        if "-" in key:  # a bare `T14B` may quote any of its variants
            rows.setdefault(key.split("-")[0], []).append(row)

    for s in json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))["stacks"]:
        add(s["id"], s["mc"], s["yield_pct"])
    for path in sorted((RESULTS / "rev_b").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for s in payload["stacks"] + payload["alternatives"]:
            add(s["id"], s["mc"], s["yield_pct"])
    for path in SWEEPS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for p in payload["points"]:
            if p["cpk"] is not None:
                add(payload["stack"], {"cpk_percentile": p["cpk"]}, 100 - p["out_pct"])
    return rows


def _quotes(path: Path):
    """Yield (line number, stack id, clause text) for each stack id with a Cpk quote before the next id or clause end."""
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("| ") and "tolstack:" in line:
            continue
        for cell in (line.split("|") if line.startswith("|") else [line]):  # a table cell is its own scope
            ids = list(_STACK_ID.finditer(cell))
            for i, m in enumerate(ids):
                end = ids[i + 1].start() if i + 1 < len(ids) else len(cell)
                yield no, m.group(0), re.split(r"[.;] ", cell[m.end():end])[0][:140]


@pytest.mark.parametrize("doc", [RISK, CONTROLS, NOTE], ids=lambda p: p.name)
def test_stack_cpk_and_yield_quoted_in_prose_equal_a_stored_result(doc):
    """Fourth review B3 and follow-up 5: `<stack> ... Cpk x.xx` (and the paired yield) is one of that stack's rows."""
    rows = _result_rows()
    checked, bad = 0, []
    for no, stack, clause in _quotes(doc):
        known = rows.get(stack)
        if known is None:
            continue
        cpk = _CPK.search(clause)
        if cpk:
            quoted = float(cpk.group(1).replace("−", "-"))
            checked += 1
            if quoted not in {c for c, _ in known}:
                bad.append(f"{doc.name}:{no}: {stack} Cpk {quoted} is in no stored {stack} result")
        for y in _YIELD.finditer(clause):
            quoted = float(y.group(1) or y.group(2))
            checked += 1
            figure = y.group(1) or y.group(2)
            places = len(figure.split(".")[1]) if "." in figure else 0
            if not any(abs(quoted - v) <= 0.5 * 10 ** -places + 1e-9 for _, v in known if v is not None):
                bad.append(f"{doc.name}:{no}: {stack} {quoted} % is in no stored {stack} result")
    assert not bad, "\n".join(bad)
    assert checked >= 1


def test_changelog_hot_t14b_cpk_matches_revb_hot():
    """Follow-up 4: the CHANGELOG's `N.NN hot` quote is the T14B Cpk of revb_hot.json."""
    hot = json.loads((RESULTS / "rev_b" / "revb_hot.json").read_text(encoding="utf-8"))
    t14b = next(s for s in hot["stacks"] if s["base_id"] == "T14B")
    quoted = re.findall(r"(\d+\.\d\d) hot\b", CHANGELOG.read_text(encoding="utf-8"))
    assert quoted and all(float(q) == round(t14b["mc"]["cpk_percentile"], 2) for q in quoted)


# ------------------------------------------------------ lever and offset quotes, scoped by stack and case (follow-ups 3, 4)

# PR 35 moved the T14B levers: boss web 6.15 -> 6.30 mm, boss-to-dog lever 2.90 -> 3.05 mm, and the tilts they
# feed (0.041 -> 0.042 mm, 0.011 mm unchanged to 3 d.p.). A sentence may quote a superseded value only when it
# names the case that had it, so the scan is by stack (the sentence's T14B id) and by case (its case words).
_SUPERSEDED_LEVER = {6.15: "boss_web_to_pinA", 2.90: "boss_to_dog_lever", 0.041: "boss_web_tilt"}
# A case word exempts a superseded number only inside its own clause: a clause ends at ; : , dash or and/but/while/
# whereas. Bare "was" is not a case word ("the web was 6.15 mm" is a stale quote); only "was" + a change verb is.
_CASE_WORDS = re.compile(r"\b(?:rev A|superseded|previous\w*|before|old|PR 35|was (?:moved|changed|revised|re-?based|"
                         r"replaced))\b", re.IGNORECASE)
_CLAUSE_END = re.compile(r"[;:,—–]|\b(?:and|but|while|whereas)\b")
_DECIMAL = re.compile(r"(?<![\w.])(\d+\.\d+)(?![\d])")


def _current_lever_values() -> dict[float, str]:
    basis = STACKS / "basis.yaml"
    overlay = yaml.safe_load((STACKS / "rev_b.yaml").read_text(encoding="utf-8"))
    c, _ = load_constants(basis, overlay["rev_b"]["set"])
    return {
        round(c["boss_web_to_pinA"], 2): "boss_web_to_pinA",
        round(c["boss_to_dog_lever"], 2): "boss_to_dog_lever",
        round(c["boss_web_to_pinA"] * c["boss_web_perp_zone"] / c["pin_span"], 3): "boss_web_tilt",
        round(c["boss_to_dog_lever"] * c["mount_flatness"] / c["servo_ear_span"], 3): "servo_axis_tilt",
    }


def _units(text: str):
    """(line, text) per table row and per paragraph, so a paragraph's title names the stack for its sentences."""
    block, start = [], 1
    for no, line in enumerate(text.splitlines(), 1):
        if line.startswith("|") or not line.strip():
            if block:
                yield start, " ".join(block)
                block = []
            if line.startswith("|"):
                yield no, line
            continue
        if not block:
            start = no
        block.append(line)
    if block:
        yield start, " ".join(block)


def _stale_levers(sentence: str, current: dict[float, str]) -> list[tuple[str, str]]:
    """(number, lever) for each superseded lever quoted in a clause that no case word names."""
    stale, start = [], 0
    for end in [m.start() for m in _CLAUSE_END.finditer(sentence)] + [len(sentence)]:
        clause = sentence[start:end]
        start = end + 1
        if _CASE_WORDS.search(clause):
            continue
        for m in _DECIMAL.finditer(clause):
            quoted = float(m.group(1))
            if round(quoted, 3) in _SUPERSEDED_LEVER and round(quoted, 2) not in current:
                stale.append((m.group(1), _SUPERSEDED_LEVER[round(quoted, 3)]))
    return stale


def test_case_word_exempts_only_the_superseded_number_in_its_own_clause():
    """Follow-up 3: a case word scopes to its clause; `was` alone and a case word elsewhere in the sentence do not exempt."""
    current = {6.3: "boss_web_to_pinA", 3.05: "boss_to_dog_lever", 0.042: "boss_web_tilt", 0.011: "servo_axis_tilt"}
    assert _stale_levers("Rev A set the boss web at 6.15 mm.", current) == []
    assert _stale_levers("The web was moved, and it is 6.15 mm from pin A.", current) == [("6.15", "boss_web_to_pinA")]
    assert _stale_levers("The boss web was 6.15 mm.", current) == [("6.15", "boss_web_to_pinA")]
    assert _stale_levers("The boss web was 6.15 mm before PR 35; it is 6.15 mm now.", current) == [
        ("6.15", "boss_web_to_pinA")]


def test_lever_quotes_in_t14b_sentences_equal_the_current_inputs():
    """Follow-ups 3 and 4: a lever or offset number in a T14B paragraph is current, unless a case word in its own clause names the case that had it."""
    current = _current_lever_values()
    assert current == {6.3: "boss_web_to_pinA", 3.05: "boss_to_dog_lever", 0.042: "boss_web_tilt",
                       0.011: "servo_axis_tilt"}, current  # a change here is a change to the note's re-base text
    bad, checked = [], 0
    for doc in (NOTE, RISK, CONTROLS, CHANGELOG):
        for no, unit in _units(doc.read_text(encoding="utf-8")):
            if not re.search(r"\bT14B\b", unit):  # the stack is named by the paragraph's title or its own sentence
                continue
            for sentence in _sentences(unit):
                for number, lever in _stale_levers(sentence, current):
                    bad.append(f"{doc.name}:{no}: {number} is the superseded {lever}: {sentence[:120]}")
                for m in _DECIMAL.finditer(sentence):
                    if any(abs(float(m.group(1)) - v) < 1e-9 for v in current):
                        checked += 1
    assert not bad, "\n".join(bad)
    assert checked >= 2
