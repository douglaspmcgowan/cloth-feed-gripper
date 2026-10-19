#!/usr/bin/env python3
"""Lint committed gripper procedures without modifying them; CRLF and LF are equivalent."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEST_REL = Path("docs/gripper/test")
COPY_DIRS = (Path("docs/gripper"), Path("cad/gripper"), Path("analysis/gripper"), Path("firmware"))
IGNORED = {"check_procedures.py", "test_test_plan.py"}

# Numbered-step vocabulary (fail closed). Classification is per clause; the
# strongest clause wins. Arm nouns include arm, named arm
# joints, pose, and the arm/motor rail. Gripper commands include serial G/R/O/E/X,
# logger --sequence, and imperative close/grip/release. Explicit rail-off, by-hand,
# unpowered, or disconnected language is unpowered. Reading, recording, inspecting,
# waiting, and analysis are neutral unless combined with hardware actuation language.
STEP = re.compile(r"^[ \t]*(\d+)\.[ \t]+.*(?:\n(?![ \t]*(?:\d+\.|#|\*\*|<!--)).*)*", re.M)
MARKER = re.compile(r"<!--\s*([\w-]+):(begin|end)\s*-->")
ARM_NOUN = re.compile(r"\b(?:arm|shoulder(?:_lift|_pan)?|elbow|wrist|pose|motor rail|arm rail)\b", re.I)
GRIPPER_NOUN = re.compile(r"\b(?:gripper|servo|jaw|finger)\b", re.I)
ACTUATE = re.compile(r"\b(?:power(?:ed)?|energise|energize|command\w*|drive|move|raise|lower|hold|turn\w*\s+(?:the\s+)?(?:arm |motor )?rail\s+on)\b", re.I)
UNPOWERED = re.compile(r"\b(?:rail(?: and \w+)? (?:still )?off|power supply (?:is )?disconnected|unpowered|by hand|disconnected|do not (?:power|energize|energise|command)|never (?:power|energize|energise|command)|not commanded)\b", re.I)
GRIPPER_COMMAND = re.compile(r"(?:`(?:G(?:\s+[0-9.]+)?|R|O|E|X|C|H|p(?:\s+[^`]+)?)`|--sequence\b|\b(?:command\w*|type|send|run|repeat|cycle|begin|start)\b[^.\n]{0,60}\b(?:close|grip|release)\b|\bturn\b[^.\n]{0,30}\bgripper\b[^.\n]{0,20}\brail on\b|\bpress\s+START\b|^\s*\d+\.\s*(?:close|grip|release)\b)", re.I)
MOTION_OR_POWER = re.compile(r"\b(?:power|energ\w*|command\w*|drive|move|bring|raise|lower|hold|turn|close|grip|release|actuate|actuate)\b", re.I)
ANALYSIS_ONLY = re.compile(r"\b(?:analysis|analy[sz]e(?:_log)?|calculate|compute|prints?|record|read|inspect)\b", re.I)
VERDICT = re.compile(r"\b(?:PASS|FAIL|INDETERMINATE|limit|at most|at least|within|no more than|no less than|exceeds|must not exceed|shall)\b", re.I)
NUMBER_UNIT = re.compile(r"(?<![\w.])(-?\d[\d,]*(?:\.\d+)?)\s*(%|°C|°|ms|s|N/mm|N·m|N|g·mm|mm|g|V|A|Hz|fps)\b|(?<![\w.])(-?\d+(?:\.\d+)?)\s*%")
SENTENCE = re.compile(r"[^\n]+")
CLAUSE = re.compile(r"(?<=[.!?;])\s+|\s*;\s*|\s+then\s+", re.I)
CLASS_RANK = {"neutral": 0, "unpowered": 1, "ambiguous": 2, "gripper-power": 3, "arm-power": 4}
LITERAL_CEILINGS = {
    "TP-01": 20, "TP-02": 22, "TP-03": 20, "TP-04": 9,
    "TP-05": 34, "TP-06": 27, "TP-07": 26, "TP-08": 2,
    "TP-09": 9, "TP-10": 3, "TP-11": 12, "TP-12": 9,
    "TP-13": 14, "TP-14": 28, "TP-15": 8, "TP-16": 18,
}


def _regions(text: str):
    """Return generated character spans and marker-balance findings."""
    spans, findings, stack = [], [], []
    for m in MARKER.finditer(text):
        name, kind = m.groups()
        if kind == "begin":
            stack.append((name, m.start()))
        elif not stack or stack[-1][0] != name:
            findings.append(f"unmatched generated marker {name}")
        else:
            opened = stack.pop()
            spans.append((opened[1], m.end(), name))
    findings.extend(f"unclosed generated marker {name}" for name, _ in stack)
    return spans, findings


def _generated(pos: int, spans) -> bool:
    return any(a <= pos < b for a, b, _ in spans)


def classify_step(step: str) -> str:
    kinds = []
    for clause in filter(str.strip, CLAUSE.split(step)):
        if UNPOWERED.search(clause):
            kinds.append("unpowered")
        elif ARM_NOUN.search(clause) and ACTUATE.search(clause):
            kinds.append("arm-power")
        elif ANALYSIS_ONLY.search(clause) and not ACTUATE.search(clause):
            kinds.append("neutral")
        elif GRIPPER_COMMAND.search(clause) or (GRIPPER_NOUN.search(clause) and (ACTUATE.search(clause) or (re.search(r"\brail\b", clause, re.I) and re.search(r"\bon\b", clause, re.I)))):
            kinds.append("gripper-power")
        elif (ARM_NOUN.search(clause) or GRIPPER_NOUN.search(clause) or re.search(r"\brail\b", clause, re.I)) and MOTION_OR_POWER.search(clause):
            kinds.append("ambiguous")
        else:
            kinds.append("neutral")
    return max(kinds or ["neutral"], key=CLASS_RANK.__getitem__)


def _scope(text: str):
    m = re.search(r"Hardware scope — arm: `(?:absent|off|gated)`; gripper: `(?:none|bench|on-arm)`", text)
    if not m:
        return None
    x = re.search(r"arm: `(absent|off|gated)`; gripper: `(none|bench|on-arm)`", m.group())
    return x.groups()


def _number_unit(m):
    return float((m.group(1) or m.group(3)).replace(",", "")), (m.group(2) or "%")


def _canonical(value, unit):
    return (value / 1000.0, "s") if unit == "ms" else (value, unit)


def _plan_numbers(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _plan_numbers(item)
    elif isinstance(value, list):
        for item in value:
            yield from _plan_numbers(item)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield float(value)


def _thresholds(plan, pid):
    out = []
    for row in plan["resolvability"]:
        if row["test"] == pid:
            out.extend(((row["limit"], row["unit"], "limit"), (row["U_k2"], row["unit"], "U")))
    return list(dict.fromkeys(out))


def _looks_generated(value, plan_values):
    """Accept a generator value rendered to the precision used in prose."""
    token = f"{value:g}"
    decimals = len(token.partition(".")[2])
    return any(round(candidate, decimals) == value for candidate in plan_values)


def _rule_b(path: Path, text: str, thresholds, plan_values, allow_generated=True):
    findings, literals = [], 0
    for sm in SENTENCE.finditer(text):
        sentence = sm.group().strip()
        if allow_generated and not VERDICT.search(sentence):
            continue
        for nm in NUMBER_UNIT.finditer(sentence):
            value, unit = _number_unit(nm)
            cv, cu = _canonical(value, unit)
            matches = [(v, u, kind) for v, u, kind in thresholds
                       if _canonical(v, u)[1] == cu and abs(cv - _canonical(v, u)[0]) <= .15 * max(abs(_canonical(v, u)[0]), 1e-12)]
            exact = next(((v, u, kind) for v, u, kind in matches if cv == _canonical(v, u)[0]), None)
            if exact:
                findings.append(f"{path.name}:{text[:sm.start() + nm.start()].count(chr(10)) + 1} rule B duplicate: {value:g} {unit}; generated {exact[0]:g} {exact[1]}")
            elif matches and (not allow_generated or not _looks_generated(value, plan_values)):
                v, u, _ = min(matches, key=lambda x: abs(cv - _canonical(x[0], x[1])[0]))
                findings.append(f"{path.name}:{text[:sm.start() + nm.start()].count(chr(10)) + 1} rule B contradiction: {value:g} {unit}; generated {v:g} {u}")
            elif not matches:
                literals += 1
    return findings, literals

def _files(test_dir: Path):
    return {p.relative_to(test_dir): p.read_bytes().replace(b"\r\n", b"\n") for p in test_dir.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.name not in IGNORED and p.suffix != ".pyc"}


def _generation_findings(root: Path) -> list[str]:
    before = _files(root / TEST_REL)
    with tempfile.TemporaryDirectory(prefix="gripper-plan-") as td:
        clone = Path(td)
        for rel in COPY_DIRS:
            shutil.copytree(root / rel, clone / rel)
        run = subprocess.run([sys.executable, str(clone / TEST_REL / "test_plan.py")], cwd=clone,
                             text=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if run.returncode:
            return [f"generator failed in temporary tree: {run.stderr.strip()}"]
        after = _files(clone / TEST_REL)
    changed = sorted(set(before) | set(after), key=str)
    return [f"generated file is stale: {TEST_REL / rel}" for rel in changed if before.get(rel) != after.get(rel)]


def lint_procedures(root: Path | str, report_literals: bool = False) -> list[str]:
    root = Path(root).resolve()
    findings: list[str] = []
    proc = root / TEST_REL / "procedures"
    plan = json.loads((root / TEST_REL / "test_plan_out.json").read_text(encoding="utf-8"))
    plan_values = list(_plan_numbers(plan))
    gate_records = {g["id"]: g for g in plan["expected"].get("gate_records", [])}
    literal_counts = {}
    for path in sorted(proc.glob("TP-*.md")):
        pid = "-".join(path.stem.split("-")[:2])
        template = root / TEST_REL / "procedure_templates" / path.name
        template_text = template.read_text(encoding="utf-8")
        template_spans, _ = _regions(template_text)
        text = path.read_text(encoding="utf-8")
        spans, marker_findings = _regions(text)
        findings.extend(f"{path.name} {x}" for x in marker_findings)
        scope = _scope(text)
        if scope is None:
            findings.append(f"{path.name} missing generated hardware-scope")
            continue
        arm_scope, gripper_scope = scope
        steps = []
        for m in STEP.finditer(text):
            number, body = int(m.group(1)), m.group(0)
            kind = classify_step(body)
            regions = {name for a, b, name in spans if a <= m.start() < b}
            generated = bool(regions)
            steps.append((number, body, kind, generated, m.start()))
            label = body.splitlines()[0].strip()
            template_line = next((i for i, value in enumerate(template_text.splitlines(), 1) if value.strip() == label), 0)
            template_pos = template_text.find(label) if template_line else -1
            template_generated = any(a <= template_pos < b for a, b, _ in template_spans)
            if kind == "arm-power" and (not generated or (template_line and not template_generated)):
                line = template_line
                source = f"procedure_templates/{path.name}:{line}" if "procedure-body" in regions else path.name
                findings.append(f"{source} arm-power step outside generated region: {label}")
            if kind == "arm-power" and arm_scope != "gated":
                findings.append(f"{path.name} arm-power step requires gated arm scope: {label}")
            if kind == "gripper-power" and gripper_scope == "none":
                findings.append(f"{path.name} gripper-power step forbidden by none scope: {label}")
            if kind == "ambiguous":
                findings.append(f"{path.name} ambiguous hardware step: {label}")
            if kind == "arm-power":
                meta = re.search(r"<!-- poses:([^>]+?) gate-records:([^>]+?) -->", body)
                if not meta:
                    findings.append(f"{path.name} step {number} powered or commanded arm pose has no gate record")
                else:
                    poses, gate_ids = meta.group(1).split("|"), meta.group(2).split("|")
                    if len(poses) != len(gate_ids):
                        findings.append(f"{path.name} step {number} pose and gate-record counts differ")
                    for pose, gate_id in zip(poses, gate_ids):
                        record = gate_records.get(gate_id)
                        if not record or record["procedure"] != pid or record["pose"] != pose:
                            findings.append(f"{path.name} step {number} pose {pose} has no matching gate record {gate_id}")
                            continue
                        gate = next((s for s in steps if s[0] == record["step"]), None)
                        missing = []
                        if not gate or gate[4] >= m.start():
                            missing.append("earlier gate step")
                        else:
                            gate_body, gate_kind = gate[1], gate[2]
                            if gate_kind != "unpowered":
                                missing.append("unpowered gate")
                            required = (record["pose"], record["datum"], record["measurement"],
                                        record["combination"], record["decision"], f"gate-record:{gate_id}")
                            missing.extend(value for value in required if value.lower() not in gate_body.lower())
                        if missing:
                            findings.append(f"{path.name} step {number} pose {pose} gate {gate_id} missing: {', '.join(missing)}")
                        if not re.search(r"\bcommand(?:ed)?(?: only)?\b[^\n]*\b%s\b" % re.escape(pose), body, re.I):
                            findings.append(f"{path.name} step {number} does not command only recorded pose {pose}")
        rule_b, count = _rule_b(template, template_text, _thresholds(plan, pid), plan_values)
        findings.extend(rule_b)
        handwritten = text
        for start, end, _ in reversed(spans):
            handwritten = handwritten[:start] + ("\n" * handwritten[start:end].count("\n")) + handwritten[end:]
        extra_rule_b, _ = _rule_b(path, handwritten, _thresholds(plan, pid), plan_values, allow_generated=False)
        findings.extend(extra_rule_b)
        literal_counts[pid] = count
        if count > LITERAL_CEILINGS[pid]:
            findings.append(f"{path.name} rule B literal count {count} exceeds ceiling {LITERAL_CEILINGS[pid]}; lower the ceiling when the count falls")

    if report_literals:
        for pid, count in sorted(literal_counts.items()):
            print(f"{pid} literal count: {count}")

    # Independent R10 cap: fitcheck supplies mass/COM geometry, not the generator's pose cap.
    fit = json.loads((root / "cad/gripper/out/fitcheck.json").read_text(encoding="utf-8"))["mass"]
    cloth_u = next(i["u_past_H"] for i in fit["items"] if i["name"] == "cloth at the pad [D DB]")
    cap = min(300.0, fit["budget_gmm"] / fit["total_g_incl_cloth"] + cloth_u - fit["com_u_past_H"])
    poses = plan["expected"]["mass"]["powered_pose_rules"]
    for pose in poses:
        if pose.get("commanded") and pose["max_fingertip_reach_mm"] > cap:
            findings.append(f"generator pose {pose['name']} exceeds independent R10 fingertip cap {cap:.1f} mm")
    tp14 = (proc / "TP-14-work-cell.md").read_text(encoding="utf-8")
    if "horizontal distance from the shoulder_pan axis" in tp14 or "The shoulder_pan axis is the centre" in tp14:
        findings.append("TP-14 reach uses shoulder_pan axis; required datum is shoulder_lift")
    gate = tp14.find("<!-- gate-record:tp14-feed -->")
    powered = [m.start() for m in re.finditer(r"^\s*\d+\.[^\n]*(?:turn the motor rail on|command the feed pose|command the powered)", tp14, re.I | re.M)
               if "do not energize or command" not in m.group(0).lower()
               or re.match(r"^\s*\d+\.\s*command", m.group(0), re.I)]
    if gate < 0 or any(i < gate for i in powered):
        findings.append("TP-14 powered pose appears before its reach gate")
    if re.search(r"(?:command|hold)[^\n]{0,80}full[- ]extension", tp14, re.I) and "not commanded" not in tp14:
        findings.append("TP-14 commands or holds prohibited full extension")
    if "pose (i)" in tp14:
        findings.append("TP-14 contains stale pose (i) wording")
    if "T_full = T_arm,full + (T_meas − T_arm,meas) × r_g,full / r_g,meas" not in tp14:
        findings.append("TP-14 full-extension extrapolation formula is missing")

    # Current revision-B physical figures may differ only inside an explicitly marked history block.
    legacy = ("144.4 g", "115.8 g", "40.7 mm", "40,507 g·mm", "50,511 g·mm")
    for path in proc.glob("TP-*.md"):
        text = re.sub(r"<!-- history:begin -->.*?<!-- history:end -->", "", path.read_text(encoding="utf-8"), flags=re.S)
        for value in legacy:
            if value in text:
                findings.append(f"{path.name} has non-current mass figure outside history: {value}")

    findings.extend(_generation_findings(root))
    return list(dict.fromkeys(findings))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[3])
    args = ap.parse_args(argv)
    findings = lint_procedures(args.root, report_literals=True)
    for finding in findings:
        print(finding)
    if not findings:
        print("No procedure findings.")
    return bool(findings)


if __name__ == "__main__":
    raise SystemExit(main())
