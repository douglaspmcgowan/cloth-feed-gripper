#!/usr/bin/env python3
"""Scan everything in public/ for content that must not be published.

    python scripts/check_public.py                 scan public/, exit 1 on any hit not allowlisted
    python scripts/check_public.py --handout F     also compare against the text of a course handout
    python scripts/check_public.py --self-test     plant one hit per rule in a temp tree and prove each fires

Rules: email, phone, address, student-id, local-path, credential, person-name, handout.
Text inside the 11 MB review app is scanned line by line, and every long base64 run in it is decoded
and scanned too. Binary media is scanned for embedded strings (ffmpeg and EXIF metadata).

Every hit prints as  file:line:col  rule  matched-text. A hit passes only when scripts/public-allowlist.txt
has a line for it:   path | rule | matched text | one-line reason   (path may be a glob). An allowlist entry that
matches nothing, or has no reason, is itself an error, so the file cannot rot.
"""
from __future__ import annotations

import argparse
import base64
import bisect
import fnmatch
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
ALLOWLIST = ROOT / "scripts" / "public-allowlist.txt"

TEXT_SUFFIXES = {".html", ".css", ".js", ".mjs", ".json", ".txt", ".svg", ".md", ".xml", ".webmanifest", ".map"}

# Names that are ambiguous English words are left out on purpose: the rule must stay quiet on prose.
FIRST_NAMES = """
Aaron Adam Adrian Alan Albert Alex Alexander Alice Alicia Amanda Amy Andrea Andrew Angela Anna Anthony
Benjamin Brian Brandon Brenda Carlos Carol Caroline Catherine Charles Charlotte Christina Christopher Cynthia
Daniel David Deborah Debra Dennis Diana Donald Douglas Dylan Edward Elizabeth Emily Emma Eric Ethan Evan
Frank Gary George Gregory Hannah Heather Henry Ian Isaac Jacob James Jason Jeffrey Jennifer Jeremy Jessica
Joan John Jonathan Jose Joseph Joshua Juan Judith Julia Justin Karen Katherine Kathleen Kayla Keith Kenneth
Kevin Kimberly Kyle Laura Lauren Lawrence Linda Lisa Logan Lucas Madison Margaret Maria Marie Mary Matthew
Megan Melissa Michael Michelle Natalie Nancy Nathan Nicholas Nicole Olivia Patricia Patrick Paul Peter
Rachel Rebecca Richard Robert Ronald Ryan Samantha Samuel Sandra Sarah Scott Sean Sharon Shirley Stephanie
Stephen Steven Susan Teresa Thomas Timothy Tyler Victoria Vincent Walter William Zachary Wei Ming Yuki Priya
""".split()
TITLES = r"(?:Prof\.?|Professor|Dr\.?|Mr\.?|Ms\.?|Mrs\.?|Instructor|GSI|TA)"

RULES: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"),
    "phone": re.compile(r"(?<![\w.\-])(?:\+?1[ .\-]?)?\(?\d{3}\)?[ .\-]\d{3}[ .\-]\d{4}(?![\w\-])"),
    "address": re.compile(
        r"\b\d{1,5}\s+(?:[NSEW]\.?\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+"
        r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Place|Pl)\b\.?"
    ),
    "student-id": re.compile(
        r"(?i)\b(?:SID|student\s*(?:id|number|no\.?)|emplid|calnet(?:\s*id)?)\W{0,3}\d{7,10}\b"
        r"|(?<![\w.+\-/])(?<!: )\d{8,10}(?![\w.])(?!\s*,\s*\d)"
    ),
    "local-path": re.compile(
        r"[A-Za-z]:\\+(?:Users|wt-peer|Documents and Settings|home|Windows|Program Files)\b[^\s\"'<>]*"
        r"|(?<![\w.])/(?:Users|home)/[A-Za-z0-9._-]+[^\s\"'<>]*"
        r"|\\\\[A-Za-z0-9._-]+\\[A-Za-z0-9$._-]+"
    ),
    "credential": re.compile(
        r"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}"
        r"|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
        r"|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"
        r"|(?i:\b(?:api[_-]?key|secret|token|passwd|password)\b)[\"']?\s*[:=]\s*[\"'][^\"'\s]{12,}[\"']"
    ),
    "person-name": re.compile(
        r"\b(?:" + "|".join(FIRST_NAMES) + r")\s+(?:[A-Z]\.\s+)?[A-Z][a-z]{2,}(?:-[A-Z][a-z]+)?\b"
        r"|\b" + TITLES + r"\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"
        r"|\b(?:[Bb]y|[Cc]redit(?:s|ed to)?|[Aa]uthor|[Ww]ritten by|[Dd]esigned by|[Tt]eam(?: members)?)\s*:?\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b"
    ),
    "handout": re.compile(
        r"(?i)\b(?:gradescope|bcourses|syllabus|rubric|points possible|problem set|homework\s*\d+|"
        r"lab\s*\d+\s*(?:handout|report)|handout|office hours|due (?:on|by) (?:mon|tue|wed|thu|fri|sat|sun)\w*|"
        r"midterm|final exam|honor code|academic integrity|ME\s?102B)\b"
    ),
}
# Rules that also run over decoded base64 blobs and binary strings. Prose rules stay out: mesh bytes are noise.
BLOB_RULES = ("email", "local-path", "credential")
BASE64_RUN = re.compile(r"[A-Za-z0-9+/]{400,}={0,2}")
PRINTABLE = re.compile(rb"[\x20-\x7e]{8,}")
# Account and repository names that identify the maintainer or a private source; a hit needs a reviewed reason.
ACCOUNT_TERMS = ("douglaspmcgowan", "berkeley-ai-tutor")


class Hit:
    __slots__ = ("file", "line", "col", "rule", "text", "where")

    def __init__(self, file: str, line: int, col: int, rule: str, text: str, where: str = "") -> None:
        self.file, self.line, self.col, self.rule, self.text, self.where = file, line, col, rule, text, where


def line_index(text: str) -> list[int]:
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def locate(starts: list[int], pos: int) -> tuple[int, int]:
    n = bisect.bisect_right(starts, pos) - 1
    return n + 1, pos - starts[n] + 1


def dynamic_terms() -> list[str]:
    """The maintainer's own name and account handle, read from git config, are never publishable unreviewed."""
    terms: list[str] = list(ACCOUNT_TERMS)
    try:
        name = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True, cwd=ROOT, timeout=10).stdout.strip()
        if len(name) > 3:
            terms += [name, name.replace(" ", "").lower()]
    except (OSError, subprocess.SubprocessError):
        pass
    return terms


def scan_text(rel: str, text: str, rules: tuple[str, ...], hits: list[Hit], offset_note: str = "", terms: list[str] | None = None) -> None:
    starts = line_index(text)
    for rule in rules:
        for m in RULES[rule].finditer(text):
            line, col = locate(starts, m.start())
            hits.append(Hit(rel, line, col, rule, m.group(0), offset_note))
    for term in terms or []:
        for m in re.finditer(re.escape(term), text):
            line, col = locate(starts, m.start())
            hits.append(Hit(rel, line, col, "person-name", m.group(0), offset_note))


def scan_file(path: Path, hits: list[Hit], terms: list[str]) -> None:
    rel = path.relative_to(PUBLIC).as_posix()
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        text = data.decode("utf-8", errors="replace")
        # Blobs are blanked (same length) for the prose rules, then decoded and scanned on their own.
        blobs = [(m.start(), m.group(0)) for m in BASE64_RUN.finditer(text)]
        plain = BASE64_RUN.sub(lambda m: " " * len(m.group(0)), text)
        scan_text(rel, plain, tuple(RULES), hits, terms=terms)
        starts = line_index(text)
        for pos, blob in blobs:
            try:
                raw = base64.b64decode(blob + "=" * (-len(blob) % 4))
            except ValueError:
                continue
            line, col = locate(starts, pos)
            strings = "\n".join(s.decode("ascii") for s in PRINTABLE.findall(raw))
            sub: list[Hit] = []
            scan_text(rel, strings, BLOB_RULES, sub)
            for h in sub:
                h.line, h.col, h.where = line, col, "inside base64 blob"
            hits.extend(sub)
    else:
        strings = "\n".join(s.decode("ascii") for s in PRINTABLE.findall(data))
        sub = []
        scan_text(rel, strings, BLOB_RULES, sub, terms=terms)
        for h in sub:
            h.line, h.col, h.where = 0, 0, "embedded string in binary"
        hits.extend(sub)


def scan_handout(handout: Path, hits: list[Hit]) -> None:
    """Flag any 8-word run of a course handout that also appears in a served text file."""
    def words(s: str) -> list[str]:
        return re.findall(r"[a-z0-9']+", s.lower())

    hw = words(handout.read_text(encoding="utf-8", errors="replace"))
    shingles = {" ".join(hw[i : i + 8]) for i in range(len(hw) - 7)}
    if not shingles:
        return
    for path in sorted(PUBLIC.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        plain = BASE64_RUN.sub(" ", text)
        starts = line_index(plain)
        seen: set[str] = set()
        for m in re.finditer(r"[A-Za-z0-9']+", plain):
            pass
        toks = [(m.group(0).lower(), m.start()) for m in re.finditer(r"[A-Za-z0-9']+", plain)]
        for i in range(len(toks) - 7):
            key = " ".join(t for t, _ in toks[i : i + 8])
            if key in shingles and key not in seen:
                seen.add(key)
                line, col = locate(starts, toks[i][1])
                hits.append(Hit(path.relative_to(PUBLIC).as_posix(), line, col, "handout", key, "8 words match the handout"))


def load_allowlist() -> tuple[list[dict], list[str]]:
    entries: list[dict] = []
    errors: list[str] = []
    if not ALLOWLIST.exists():
        return entries, errors
    for n, raw in enumerate(ALLOWLIST.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|", 3)]
        if len(parts) != 4 or not all(parts):
            errors.append(f"{ALLOWLIST.name}:{n}: need 'path | rule | matched text | reason', every field filled")
            continue
        if parts[1] not in RULES:
            errors.append(f"{ALLOWLIST.name}:{n}: unknown rule {parts[1]!r}")
            continue
        entries.append({"path": parts[0], "rule": parts[1], "text": parts[2], "reason": parts[3], "line": n, "used": 0})
    return entries, errors


def run(handout: Path | None) -> int:
    hits: list[Hit] = []
    terms = dynamic_terms()
    files = sorted(p for p in PUBLIC.rglob("*") if p.is_file())
    for path in files:
        scan_file(path, hits, terms)
    if handout:
        scan_handout(handout, hits)

    entries, errors = load_allowlist()
    open_hits: list[Hit] = []
    allowed = 0
    for h in hits:
        for e in entries:
            if e["rule"] == h.rule and e["text"] == h.text and fnmatch.fnmatch(h.file, e["path"]):
                e["used"] += 1
                allowed += 1
                break
        else:
            open_hits.append(h)

    for e in entries:
        if not e["used"]:
            errors.append(f"{ALLOWLIST.name}:{e['line']}: stale entry matches nothing: {e['path']} | {e['rule']} | {e['text']}")

    for h in open_hits:
        where = f" ({h.where})" if h.where else ""
        print(f"HIT {h.file}:{h.line}:{h.col} {h.rule} {h.text[:120]!r}{where}")
    for err in errors:
        print(f"ALLOWLIST {err}")
    print(
        f"check_public: scanned {len(files)} files, {len(hits)} hits, {allowed} allowlisted, "
        f"{len(open_hits)} open, {len(errors)} allowlist errors"
    )
    return 1 if open_hits or errors else 0


PLANTED = {
    "email": "write to jo.example@example.org",
    "phone": "call (510) 555-0142 today",
    "address": "visit 2594 Hearst Avenue",
    "student-id": "SID 3035123456",
    "local-path": "saved at C:\\Users\\someone\\Desktop\\a.txt",
    "credential": "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8",
    "person-name": "built by Jennifer Alvarez",
    "handout": "see the Gradescope rubric",
}


def self_test() -> int:
    global PUBLIC, ALLOWLIST
    saved = PUBLIC, ALLOWLIST
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        PUBLIC = Path(tmp) / "public"
        ALLOWLIST = Path(tmp) / "allow.txt"
        PUBLIC.mkdir()
        (PUBLIC / "page.html").write_text("<p>" + "</p>\n<p>".join(PLANTED.values()) + "</p>\n", encoding="utf-8")
        blob = base64.b64encode(b"x" * 300 + b" /Users/someone/secret.txt " + b"y" * 300).decode()
        (PUBLIC / "data.js").write_text(f'const D="{blob}";\n', encoding="utf-8")
        (PUBLIC / "clip.mp4").write_bytes(b"\x00\x01encoder=C:\\Users\\someone\\ffmpeg.exe\x00")
        hits: list[Hit] = []
        for p in sorted(PUBLIC.iterdir()):
            scan_file(p, hits, [])
        fired = {h.rule for h in hits if h.file == "page.html"}
        for rule in PLANTED:
            ok = rule in fired
            print(f"self-test {rule}: {'fires' if ok else 'MISSED'}")
            failures += not ok
        for file, label in (("data.js", "path inside a base64 blob"), ("clip.mp4", "path inside a binary")):
            ok = any(h.file == file and h.rule == "local-path" for h in hits)
            print(f"self-test {label}: {'fires' if ok else 'MISSED'}")
            failures += not ok
        ALLOWLIST.write_text("page.html | email | jo.example@example.org | planted by the self-test\n", encoding="utf-8")
        entries, errs = load_allowlist()
        ok = len(entries) == 1 and not errs
        print(f"self-test allowlist parse: {'ok' if ok else 'FAILED'}")
        failures += not ok
        ALLOWLIST.write_text("page.html | email | jo.example@example.org |\n", encoding="utf-8")
        _, errs = load_allowlist()
        ok = bool(errs)
        print(f"self-test allowlist without a reason is rejected: {'ok' if ok else 'FAILED'}")
        failures += not ok
    PUBLIC, ALLOWLIST = saved
    print(f"self-test: {'passed' if not failures else f'{failures} failures'}")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--handout", type=Path, help="text of a course handout to compare against (8-word runs)")
    ap.add_argument("--self-test", action="store_true", help="plant one hit per rule and prove each fires")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not PUBLIC.is_dir():
        print(f"no public/ directory at {PUBLIC}", file=sys.stderr)
        return 2
    return run(args.handout)


if __name__ == "__main__":
    sys.exit(main())
