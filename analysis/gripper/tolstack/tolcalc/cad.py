"""Validate tolerance constants bound to CAD parameters."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from .model import load_constants


CAD_TOKEN = re.compile(r"\$\{([A-Za-z0-9_.]+)\}")


def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cad_value(data: dict, path: str):
    value = data
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def binding_value(meta: dict, cad_data: dict) -> tuple[float, str]:
    if "cad" in meta:
        path = str(meta["cad"])
        return float(cad_value(cad_data, path)), path
    expression = str(meta["cad_derived"])
    paths = CAD_TOKEN.findall(expression)
    values = {path: float(cad_value(cad_data, path)) for path in paths}
    rendered = CAD_TOKEN.sub(lambda match: repr(values[match.group(1)]), expression)
    value = eval(rendered, {"__builtins__": {}}, {})  # noqa: S307
    return float(value), expression


def constant_bindings(basis_path: Path) -> dict:
    data = yaml.safe_load(Path(basis_path).read_text(encoding="utf-8")) or {}
    return {
        name: value
        for name, value in (data.get("constants") or {}).items()
        if isinstance(value, dict) and ("cad" in value or "cad_derived" in value)
    }


def validate_bindings(basis_path: Path, overlay_path: Path, cad_path: Path) -> list[str]:
    data = yaml.safe_load(Path(basis_path).read_text(encoding="utf-8")) or {}
    raw = data.get("constants") or {}
    overlay = yaml.safe_load(Path(overlay_path).read_text(encoding="utf-8")) or {}
    overrides = (overlay.get("rev_b") or {}).get("set") or {}
    rev_a, meta = load_constants(basis_path)
    rev_b, _ = load_constants(basis_path, overrides)
    cad_data = read_json(cad_path)
    errors = []
    for name, item in raw.items():
        if not isinstance(item, dict):
            continue
        source = str(item.get("source", ""))
        if "params.json" in source and not ({"cad", "cad_derived"} & item.keys()):
            errors.append(f"{name}: source mentions params.json but has no cad or cad_derived binding")
            continue
        if "cad" not in item and "cad_derived" not in item:
            continue
        expected, path = binding_value(meta[name], cad_data)
        if rev_b[name] != expected:
            errors.append(f"{name}: rev B {rev_b[name]} != CAD {expected} at {path}")
        if rev_a[name] != expected and name not in overrides:
            message = f"{name}: rev A {rev_a[name]} differs from CAD {expected}"
            errors.append(f"{message} but rev_b.set has no override")
    return errors
