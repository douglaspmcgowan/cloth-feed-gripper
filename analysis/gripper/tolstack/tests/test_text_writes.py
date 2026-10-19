"""Guards for platform-independent generated text."""
import ast
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tolstack  # noqa: E402


def _missing_text_write_options(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        is_write_text = isinstance(node.func, ast.Attribute) and node.func.attr == "write_text"
        is_text_open = isinstance(node.func, ast.Name) and node.func.id == "open"
        is_text_open |= isinstance(node.func, ast.Attribute) and node.func.attr == "open"
        if is_text_open:
            mode = node.args[1] if len(node.args) > 1 else None
            mode = next((kw.value for kw in node.keywords if kw.arg == "mode"), mode)
            is_text_open = isinstance(mode, ast.Constant) and "w" in str(mode.value) and "b" not in str(mode.value)
        if is_write_text or is_text_open:
            keywords = {kw.arg for kw in node.keywords}
            missing = {"encoding", "newline"} - keywords
            if missing:
                yield node.lineno, missing


def test_all_text_writes_name_encoding_and_newline():
    failures = []
    for path in ROOT.rglob("*.py"):
        if "tests" in path.relative_to(ROOT).parts:
            continue
        for line, missing in _missing_text_write_options(path):
            failures.append(f"{path.relative_to(ROOT)}:{line}: missing {', '.join(sorted(missing))}")
    assert not failures, "text writes must explicitly name encoding and newline:\n" + "\n".join(failures)


def test_stack_report_stays_lf_when_default_translation_is_crlf(tmp_path, monkeypatch):
    original = Path.write_text

    def windows_write_text(self, data, encoding=None, errors=None, newline=None):
        if newline is None:
            data = data.replace("\n", "\r\n")
        return original(self, data, encoding=encoding, errors=errors, newline="")

    monkeypatch.setattr(Path, "write_text", windows_write_text)
    stack = {"id": "LF", "parts": [], "title": "line endings", "contributors": [{"name": "x", "tol": 0.1}]}
    source = tmp_path / "stack.yaml"
    original(source, yaml.safe_dump(stack), encoding="utf-8", newline="\n")
    out = tmp_path / "out"
    assert tolstack.main(["run", str(source), "--out", str(out), "--samples", "20000", "--no-doc"]) == 0
    for path in out.rglob("*"):
        if path.is_file() and path.suffix != ".png":
            assert b"\r" not in path.read_bytes(), str(path)


def _d(base, name):
    (base / name).mkdir()
    return base / name


def _digest_root(tmp_path, text):
    (tmp_path / "stacks").mkdir(exist_ok=True)
    (tmp_path / "tolcalc").mkdir(exist_ok=True)
    (tmp_path / "stacks" / "a.yaml").write_bytes(text)
    (tmp_path / "tolcalc" / "m.py").write_bytes(b"x = 1\n")
    (tmp_path / "tolstack.py").write_bytes(b"y = 2\n")
    return tmp_path


def test_input_digest_ignores_crlf_but_sees_content(tmp_path):
    report = tolstack.report
    lf = report.input_digest(_digest_root(_d(tmp_path, "lf"), b"id: T1\nv: 1\n"))["digest"]
    crlf = report.input_digest(_digest_root(_d(tmp_path, "crlf"), b"id: T1\r\nv: 1\r\n"))["digest"]
    changed = report.input_digest(_digest_root(_d(tmp_path, "chg"), b"id: T1\nv: 2\n"))["digest"]
    spaced = report.input_digest(_digest_root(_d(tmp_path, "sp"), b"id: T1\nv:  1\n"))["digest"]
    assert lf == crlf
    assert lf != changed
    assert lf != spaced
