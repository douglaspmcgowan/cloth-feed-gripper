"""Revision B release gate generation and opening-note safety checks."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

TOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOL))

from tolcalc import report, run_all  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
TOL = ROOT / "analysis" / "gripper" / "tolstack"
STACKS = TOL / "stacks"
RESULTS = TOL / "results" / "rev_b"
NOTE = ROOT / "docs" / "gripper" / "analysis" / "tolerance_stacks.md"


def _block(text: str, name: str) -> str:
    start = f"<!-- tolstack:{name}:start -->"
    end = f"<!-- tolstack:{name}:end -->"
    return text.split(start, 1)[1].split(end, 1)[0].strip()


def _fail_parts() -> dict[str, list[str]]:
    result = json.loads((RESULTS / "revb.json").read_text(encoding="utf-8"))
    failed = {item["base_id"] for item in result["stacks"] if item["verdict3"] == "fail"}
    definitions = report._release_stack_data(STACKS)
    return {sid: definitions[sid]["parts"] for sid in sorted(failed)}


def _names_part(sentence: str, part: str) -> bool:
    words = sentence.casefold()
    name = part.casefold()
    family = name.split()[0]
    return name in words or (len(name.split()) > 1 and re.search(rf"\b{re.escape(family)}s?\b", words) is not None)


def test_release_gate_is_fresh() -> None:
    expected = report.release_gate(RESULTS / "revb.json", RESULTS / "revb_hot.json", STACKS)
    assert _block(NOTE.read_text(encoding="utf-8"), "release") == expected


def test_release_gate_never_clears_a_failed_part() -> None:
    clear_line = next(
        line for line in _block(NOTE.read_text(encoding="utf-8"), "release").splitlines()
        if line.startswith("Clear to print")
    )
    for sid, parts in _fail_parts().items():
        for part in parts:
            assert part not in clear_line, f"{part} is held by failing stack {sid}"


def test_handwritten_opening_does_not_print_failed_parts() -> None:
    text = NOTE.read_text(encoding="utf-8")
    opening = text.split("<!-- tolstack:verdicts:start -->", 1)[0]
    release_start = "<!-- tolstack:release:start -->"
    release_end = "<!-- tolstack:release:end -->"
    opening = opening.split(release_start, 1)[0] + opening.split(release_end, 1)[1]
    print_sentences = [sentence for sentence in re.split(r"(?<=[.!?])\s+", opening)
                       if re.search(r"\bprint\b", sentence, re.IGNORECASE)]
    for sid, parts in _fail_parts().items():
        for part in parts:
            assert not any(_names_part(sentence, part) for sentence in print_sentences), (
                f"hand-written opening instructs printing {part}, held by failing stack {sid}"
            )


def test_loader_names_stack_missing_parts(tmp_path: Path) -> None:
    source = STACKS / "T01_bolt_pattern_fit.yaml"
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    del data["parts"]
    path = tmp_path / source.name
    path.write_text(yaml.safe_dump(data), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="T01: stack definition has no parts key"):
        run_all([path], n=20_000)
