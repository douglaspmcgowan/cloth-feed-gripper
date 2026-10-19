"""Content identity for the CAD inputs embedded in the fit audit."""
import ast
import hashlib
import json
import os
import re
from pathlib import Path


INPUT_PATHS = (
    "gripper_concept.py", "fit3d.py", "params.json", "out/parts.json", "gear_profile.dxf",
    "fit_requirements.json", "assembly/steps.json", "viewer_src/fit3d_inputs.py",
    "viewer_src/so101_context.json", "viewer_src/so101_context.bin", "viewer_src/so101_mesh.py",
    "../so101/SO101 Assembly.step", "../so101/measure_interface.py",
)

# Tolerance inputs are hashed as the values fit3d.py reads, not as whole files: regenerating the tolerance
# stacks must not stale the hour-long audit unless a value the audit uses moved.
TOLSTACK_DIR = "../../analysis/gripper/tolstack/"
BASIS_FILE = TOLSTACK_DIR + "stacks/basis.yaml"
BASIS_CONSTANTS = (
    "axial_min_clear", "fdm_z_tol", "gear_m", "gear_z", "horn_face_runout", "horn_height_tol",
    "keepout_min_clear",
)  # every basis.yaml name fit3d.py reads; tests/test_fit3d_basis.py checks this against fit3d.py's source


BASIS_RE = re.compile(
    r"^\s+(\w+):\s+\{value:\s*([-\d.]+),\s*tag:\s*(\w+),(?:\s*(?!source:)\w+:\s*(?:\"[^\"]*\"|[^,{}\"]+),)*"
    r"\s*source:\s*\"([^\"]*)\"\}", re.M)


def parse_basis(text: str) -> dict:
    """name -> {value, tag, source} from basis.yaml; `cad:` and `cad_derived:` fields between tag and source are skipped."""
    return {m.group(1): {"value": float(m.group(2)), "tag": m.group(3), "source": m.group(4)}
            for m in BASIS_RE.finditer(text)}


def tolstack_projection(gripper: Path) -> dict:
    """The tolerance values fit3d.py reads: its basis constants, and the one stack's summary row and contributors."""
    gripper = gripper.resolve()
    out: dict = {}
    basis_file = gripper / BASIS_FILE
    if basis_file.is_file():
        basis = parse_basis(basis_file.read_text(encoding="utf-8"))
        out["basis"] = {name: basis.get(name) for name in BASIS_CONSTANTS}
    return out


DATA_SUFFIXES = {".bin", ".csv", ".dxf", ".json", ".npz", ".step", ".stl", ".svg", ".txt", ".yaml", ".yml"}


def _path_pattern(node: ast.AST, roots: dict[str, Path]) -> str | None:
    """Resolve a local path expression; unknown names and f-string fields become filename wildcards."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return str(roots[node.id]) if node.id in roots else "*"
    if isinstance(node, ast.JoinedStr):
        parts = [value.value if isinstance(value, ast.Constant) else "*" for value in node.values]
        return "".join(str(part) for part in parts)
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        inner = _path_pattern(node.value, roots)
        return None if inner is None else str(Path(inner).parent)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return "*"
    if isinstance(node, ast.Call):
        func = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        args = [_path_pattern(arg, roots) for arg in node.args]
        if func in {"resolve", "absolute", "expanduser"} and isinstance(node.func, ast.Attribute) and not node.args:
            return _path_pattern(node.func.value, roots)
        if None in args or not args:
            return None
        if func in {"str", "Path", "PurePath", "fspath", "abspath", "realpath", "normpath"} and len(args) == 1:
            return args[0]
        if func in {"join", "Path", "PurePath"}:
            return str(Path(args[0]).joinpath(*args[1:]))
        if func == "dirname" and len(args) == 1:
            return str(Path(args[0]).parent)
        return None
    if isinstance(node, ast.BinOp):
        left, right = _path_pattern(node.left, roots), _path_pattern(node.right, roots)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Div):
            return str(Path(left) / right)
        if isinstance(node.op, ast.Add):
            return left + right
    return None


IMPORT_CALLS = {"import_module", "__import__"}
READ_CALLS = {"open", "read_text", "read_bytes", "importStep"} | IMPORT_CALLS
# Reads whose path is a plain variable, reviewed one by one: (file name, path expression). Anything else
# that cannot be resolved stops the audit, so a new input read cannot slip past the digest.
REVIEWED_VARIABLE_READS = {
    ("measure_interface.py", "str(HERE / fn)"),
    ("fit3d.py", "f"),
    ("gripper_concept.py", "Path(path)"),
    ("gripper_concept.py", "args.params"),
    ("fit3d_inputs.py", "path"),
    ("fit3d_inputs.py", "params"),
    ("fit3d_inputs.py", "basis_file"),
    ("fit3d_inputs.py", "summary_file"),
    ("fit3d_inputs.py", "stack_file"),
}


def read_calls(path: Path, tree: ast.AST, roots: dict[str, Path]) -> list[tuple[str, str]]:
    """Every file read in a source as (call name, resolved path pattern); raise on one that cannot be resolved."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if func not in READ_CALLS:
            continue
        if func in {"read_text", "read_bytes"}:
            if not isinstance(node.func, ast.Attribute):
                continue
            target = node.func.value
        elif node.args:
            target = node.args[0]
        else:
            continue
        if func == "open" and len(node.args) > 1 and isinstance(node.args[1], ast.Constant) \
                and set(str(node.args[1].value)) & set("wax"):
            continue
        pattern = _path_pattern(target, roots)
        where = f"{path.name}:{node.lineno}: {ast.unparse(node)[:80]}"
        if pattern is None:
            raise ValueError(f"{where}: input path cannot be resolved; make it a constant or add it to INPUT_PATHS")
        if func in IMPORT_CALLS:
            if pattern == "*" or "/" in pattern and Path(pattern).name == "*":
                raise ValueError(f"{where}: imported module name cannot be resolved; use a constant name")
            found.append((func, pattern))
            continue
        if Path(pattern).name == "*" or not Path(pattern).suffix:
            if (path.name, ast.unparse(target)) not in REVIEWED_VARIABLE_READS:
                raise ValueError(f"{where}: input path is a variable; review it in REVIEWED_VARIABLE_READS")
            continue
        if Path(pattern).suffix.lower() not in DATA_SUFFIXES | {".py"}:
            raise ValueError(f"{where}: input suffix {Path(pattern).suffix} is not in DATA_SUFFIXES")
        found.append((func, pattern))
    return found





def _relative(path: Path, gripper: Path) -> str:
    return Path(os.path.relpath(path, gripper)).as_posix()


def source_closure(gripper: Path) -> set[str]:
    """Follow local Python imports from both geometry entry points, static or through importlib."""
    gripper = gripper.resolve()
    cad = gripper.parent
    analysis = cad.parent / "analysis" / "gripper"
    roots = (cad, analysis)
    pending = [gripper / "gripper_concept.py", gripper / "fit3d.py"]
    found = set()
    while pending:
        path = pending.pop()
        if not path.is_file() or path in found:
            continue
        found.add(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        bases = {"HERE": path.parent.resolve(), "ROOT": cad.parent.resolve(), "SO": (cad / "so101").resolve(),
                 "__file__": path.resolve()}
        for func, pattern in read_calls(path, tree, bases):
            if func in IMPORT_CALLS:
                stem = pattern.replace(".", "/") + ".py"
                for folder in (path.parent, gripper, gripper / "viewer_src", cad, cad / "so101", cad.parent, analysis):
                    pending.extend(candidate.resolve() for candidate in folder.glob(stem)
                                   if candidate.is_file()
                                   and any(candidate.resolve().is_relative_to(root) for root in roots))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = node.module or ""
                names = [prefix, *(f"{prefix}.{alias.name}" for alias in node.names)]
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                pattern = _path_pattern(node, bases)
                if pattern and Path(pattern).suffix == ".py":
                    parent = Path(pattern).parent
                    if parent.is_dir():
                        pending.extend(candidate.resolve() for candidate in parent.glob(Path(pattern).name)
                                       if any(candidate.resolve().is_relative_to(root) for root in roots))
            for name in names:
                stem = name.replace(".", "/") + ".py"
                candidates = [path.parent / stem, gripper / stem, gripper / "viewer_src" / stem,
                              cad / stem, cad / "so101" / stem, cad.parent / stem, analysis / stem]
                pending.extend(candidate.resolve() for candidate in candidates
                               if candidate.is_file()
                               and any(candidate.resolve().is_relative_to(root) for root in roots))
    return {_relative(path, gripper) for path in found}


def params_data(gripper: Path) -> set[str]:
    """Data files named by a params.json string value, such as gear.profile_dxf."""
    gripper = gripper.resolve()
    params = gripper / "params.json"
    if not params.is_file():
        return set()
    values, stack = [], [json.loads(params.read_text(encoding="utf-8"))]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str) and Path(item.replace("\\", "/")).suffix.lower() in DATA_SUFFIXES:
            values.append(item.replace("\\", "/"))
    found = set()
    for value in values:
        candidates = [(base / value).resolve() for base in (gripper, gripper.parent, gripper.parent.parent)]
        existing = [candidate for candidate in candidates if candidate.is_file()]
        found.add(_relative(existing[0] if existing else candidates[0], gripper))
    return found


def data_closure(gripper: Path, sources: set[str]) -> set[str]:
    """Include local data named directly or through constructed path expressions."""
    gripper = gripper.resolve()
    found = set()
    repo = gripper.parent.parent
    allowed = [gripper.parent, *(repo / name for name in
                ("analysis/gripper", "docs/gripper", "firmware/gripper", "ecad/gripper"))]
    for name in sources:
        path = gripper / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        roots = {"HERE": path.parent.resolve(), "ROOT": repo.resolve(),
                 "SO": (gripper.parent / "so101").resolve(), "__file__": path.resolve()}
        reads = [pattern for func, pattern in read_calls(path, tree, roots) if func not in IMPORT_CALLS]
        for pattern in reads:
            candidate_pattern = Path(pattern)
            if candidate_pattern.suffix.lower() in DATA_SUFFIXES and candidate_pattern.is_absolute():
                parent = candidate_pattern.parent
                if parent.is_dir() and any(parent.is_relative_to(root) for root in allowed):
                    for candidate in parent.glob(candidate_pattern.name):
                        if candidate.is_file() and candidate != gripper / "out/fit3d.json":
                            found.add(Path(os.path.relpath(candidate, gripper)).as_posix())
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                pattern = _path_pattern(node, roots)
                if pattern and Path(pattern).suffix.lower() in DATA_SUFFIXES:
                    candidate_pattern = Path(pattern)
                    parent = candidate_pattern.parent
                    if parent.is_dir() and any(parent.is_relative_to(root) for root in allowed):
                        for candidate in parent.glob(candidate_pattern.name):
                            if candidate.is_file() and candidate != gripper / "out/fit3d.json":
                                found.add(Path(os.path.relpath(candidate, gripper)).as_posix())
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            literal = node.value.replace("\\", "/")
            if Path(literal).suffix.lower() not in DATA_SUFFIXES:
                continue
            for base in (path.parent, gripper, gripper.parent, gripper.parent.parent):
                candidate = (base / literal).resolve()
                if not any(candidate.is_relative_to(root) for root in allowed):
                    continue
                if candidate.is_file() and candidate != gripper / "out/fit3d.json":
                    found.add(candidate.relative_to(gripper).as_posix()
                              if candidate.is_relative_to(gripper)
                              else "../" + candidate.relative_to(gripper.parent).as_posix()
                              if candidate.is_relative_to(gripper.parent)
                              else "../../" + candidate.relative_to(gripper.parent.parent).as_posix())
    return found


def input_paths(gripper: Path) -> list[str]:
    gripper = gripper.resolve()
    sources = source_closure(gripper)
    found = set(INPUT_PATHS) | sources | data_closure(gripper, sources) | params_data(gripper)
    return sorted(name for name in found if not name.startswith(TOLSTACK_DIR))


def kernel_versions() -> dict[str, str]:
    """Installed CAD kernel distributions; a different OCP can move every distance."""
    from importlib import metadata
    versions = {}
    for name in ("cadquery", "cadquery-ocp"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "missing"
    return versions


def input_digest(gripper: Path, kernel: dict[str, str] | None = None) -> str:
    digest = hashlib.sha256()
    if kernel is not None:
        digest.update(b"kernel\0" + json.dumps(kernel, sort_keys=True).encode("utf-8") + b"\0")
    digest.update(b"tolstack\0" + json.dumps(tolstack_projection(gripper), sort_keys=True).encode("utf-8") + b"\0")
    for name in input_paths(gripper):
        path = gripper / name
        digest.update(name.encode("utf-8") + b"\0")
        if not path.exists():
            digest.update(b"missing\0")
            continue
        raw = path.read_bytes()
        if path.suffix.lower() in {".py", ".json", ".yaml", ".dxf"}:
            raw = raw.replace(b"\r\n", b"\n")
        digest.update(len(raw).to_bytes(8, "big") + raw)
    return digest.hexdigest()


def result_hash(record: dict) -> str:
    body = {key: value for key, value in record.items() if key != "result_sha256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_result(record: dict, gripper: Path) -> None:
    command = "uv run --with cadquery python cad/gripper/fit3d.py"
    if record.get("complete") is not True:
        raise ValueError(f"fit3d.json audit is incomplete; rerun {command}")
    kernel = record.get("kernel")
    if not isinstance(kernel, dict) or not kernel.get("cadquery") or not kernel.get("cadquery-ocp"):
        raise ValueError(f"fit3d.json does not record the CAD kernel version; rerun {command}")
    if record.get("input_digest_sha256") != input_digest(gripper, kernel):
        raise ValueError(f"fit3d.json input digest is stale; rerun {command}")
    if record.get("result_sha256") != result_hash(record):
        raise ValueError(f"fit3d.json result hash is invalid; rerun {command}")
