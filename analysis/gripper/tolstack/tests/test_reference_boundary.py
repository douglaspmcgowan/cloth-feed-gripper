"""Keep the two independent loop references outside the production package."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
REFERENCES = (HERE / "loop_reference.py", HERE / "loop_sampler.py")


def _production_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    errors = []
    importlib_names = {"importlib"}
    import_module_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib":
                    importlib_names.add(alias.asname or alias.name)
                if alias.name == "tolcalc" or alias.name.startswith("tolcalc."):
                    errors.append(f"{path.name}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "importlib":
                for alias in node.names:
                    if alias.name == "import_module":
                        import_module_names.add(alias.asname or alias.name)
            if node.module == "tolcalc" or (node.module or "").startswith("tolcalc."):
                errors.append(f"{path.name}:{node.lineno}: from {node.module} import")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        target = node.func
        direct = isinstance(target, ast.Name) and target.id in import_module_names | {"__import__"}
        dotted = (isinstance(target, ast.Attribute) and target.attr == "import_module"
                  and isinstance(target.value, ast.Name) and target.value.id in importlib_names)
        module = node.args[0]
        if (direct or dotted) and isinstance(module, ast.Constant) and isinstance(module.value, str):
            if module.value == "tolcalc" or module.value.startswith("tolcalc."):
                errors.append(f"{path.name}:{node.lineno}: dynamic import {module.value}")
    return errors


@pytest.mark.parametrize("path", REFERENCES, ids=lambda path: path.name)
def test_reference_does_not_import_production(path):
    assert not _production_imports(path), "\n".join(_production_imports(path))


def test_importlib_production_import_is_reported(tmp_path):
    path = tmp_path / "reference.py"
    path.write_text('import importlib\nimportlib.import_module("tolcalc.engine")\n',
                    encoding="utf-8", newline="\n")
    assert _production_imports(path) == ["reference.py:2: dynamic import tolcalc.engine"]
