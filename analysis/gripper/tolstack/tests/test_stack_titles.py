import json
import re
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tolcalc.model import load_stacks  # noqa: E402

STACKS = ROOT / "stacks"
RESULTS = ROOT / "results"
LITERAL_LENGTH = re.compile(r"(?<![A-Za-z_{])\d+(?:\.\d+)?\s*(?:mm|cm|m|in)\b", re.IGNORECASE)


def test_stack_titles_use_placeholders_for_dimensions():
    offenders = []
    for path in STACKS.glob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and LITERAL_LENGTH.search(str(data.get("title", ""))):
            offenders.append(path.name)
    assert offenders == []


def test_t16_title_tracks_each_revision_face_width():
    rev_a = json.loads((RESULTS / "T16.json").read_text(encoding="utf-8"))
    rev_b = json.loads((RESULTS / "rev_b" / "revb.json").read_text(encoding="utf-8"))
    rev_b_t16 = next(stack for stack in rev_b["stacks"] if stack["id"] == "T16")
    overlay = yaml.safe_load((STACKS / "rev_b.yaml").read_text(encoding="utf-8"))
    resolved = load_stacks(STACKS / "T16_pin_tilt.yaml", overlay["rev_b"]["set"])[0]
    assert rev_a["title"] == "Pin axis tilt, centre-distance change across the 8 mm gear face"
    assert rev_b_t16["title"] == "Pin axis tilt, centre-distance change across the 10.5 mm gear face"
    assert rev_b_t16["title"] == resolved.title
