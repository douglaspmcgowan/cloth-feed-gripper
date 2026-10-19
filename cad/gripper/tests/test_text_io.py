"""Generated text stays UTF-8/LF on Windows and Linux."""
import ast
from pathlib import Path

import pytest


CAD = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("path", sorted(CAD.rglob("*.py")), ids=lambda path: str(path.relative_to(CAD)))
def test_text_io_is_explicit(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else (
            node.func.id if isinstance(node.func, ast.Name) else "")
        keys = {keyword.arg for keyword in node.keywords}
        if name == "read_text":
            assert "encoding" in keys, f"{path}:{node.lineno} read_text needs encoding"
        if name == "write_text":
            assert {"encoding", "newline"} <= keys, f"{path}:{node.lineno} write_text needs encoding and newline"
        if name == "open" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            mode = node.args[1].value
            if isinstance(mode, str) and "w" in mode and "b" not in mode:
                assert {"encoding", "newline"} <= keys, f"{path}:{node.lineno} open for writing needs encoding and newline"
