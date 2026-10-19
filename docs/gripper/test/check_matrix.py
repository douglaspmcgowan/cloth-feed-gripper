"""Coverage check for the gripper verification matrix.

Fails (exit 1) if any requirement id in DESIGN-BASIS section 1 has no row in
`verification_matrix.csv`, a row with no recognised method, or a procedure id with no
file under `procedures/`. Also fails on matrix rows for ids that DB does not have.

Run from the repository root:  python docs/gripper/test/check_matrix.py
Optional: --design-basis PATH --matrix PATH --procedures DIR (used by the tests).
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
METHODS = ("inspection", "analysis", "demonstration", "test")


def requirement_ids(design_basis_md: Path) -> list[str]:
    text = design_basis_md.read_text(encoding="utf-8")
    start = text.index("## 1. Requirements")
    end = text.index("\n## 2.", start)
    return re.findall(r"^\|\s*(R\d+)\s*\|", text[start:end], flags=re.M)


def check(design_basis: Path, matrix: Path, procedures: Path) -> tuple[list[str], list[str], dict]:
    errors = []
    ids = requirement_ids(design_basis)
    if not ids:
        errors.append("no requirement ids found in section 1 of %s" % design_basis)
    with matrix.open(encoding="utf-8", newline="") as f:
        rows = {r["id"].strip(): r for r in csv.DictReader(f)}
    files = {p.name for p in procedures.glob("TP-*.md")}
    for rid in ids:
        r = rows.get(rid)
        if r is None:
            errors.append("%s: no matrix row" % rid)
            continue
        if not any(m in r.get("method", "").lower() for m in METHODS):
            errors.append("%s: no method (one of %s)" % (rid, ", ".join(METHODS)))
        pids = re.findall(r"TP-\d\d", r.get("procedure", ""))
        if not pids:
            errors.append("%s: no procedure id" % rid)
        for pid in pids:
            if not any(f.startswith(pid + "-") for f in files):
                errors.append("%s: procedure %s has no file in %s" % (rid, pid, procedures))
        if not r.get("pass_criterion", "").strip():
            errors.append("%s: empty pass criterion" % rid)
    for extra in sorted(set(rows) - set(ids)):
        errors.append("%s: matrix row for an id not in DESIGN-BASIS section 1" % extra)
    return errors, ids, rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--design-basis", type=Path, default=ROOT / "docs/gripper/DESIGN-BASIS.md")
    ap.add_argument("--matrix", type=Path, default=HERE / "verification_matrix.csv")
    ap.add_argument("--procedures", type=Path, default=HERE / "procedures")
    a = ap.parse_args(argv)
    errors, ids, rows = check(a.design_basis, a.matrix, a.procedures)
    covered = [i for i in ids if i in rows]
    print("requirements in DESIGN-BASIS section 1: %d (%s)" % (len(ids), ", ".join(ids)))
    print("matrix rows: %d; requirements covered: %d" % (len(rows), len(covered)))
    procs = sorted({p for r in rows.values() for p in re.findall(r"TP-\d\d", r.get("procedure", ""))})
    print("procedures referenced: %d (%s)" % (len(procs), ", ".join(procs)))
    if errors:
        for e in errors:
            print("FAIL " + e)
        return 1
    print("PASS every requirement has a row, a method, a pass criterion and a procedure file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
