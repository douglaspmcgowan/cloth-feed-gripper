"""Discover supplier-facing release artifacts and their ordering gates."""
import csv
from dataclasses import dataclass
from pathlib import Path


GERBER_SUFFIXES = {".gbl", ".gbo", ".gbp", ".gbr", ".gbs", ".gm1", ".gtl", ".gto", ".gtp", ".gts"}
ARCHIVE_SUFFIXES = {".7z", ".rar", ".tar", ".tgz", ".zip"}
BOM_HEADER_SETS = (
    {"item", "qty", "manufacturer", "mpn"},
    {"comment", "designator", "footprint", "lcsc part #"},
)
PLACEMENT_COLUMNS = {"ref", "posx", "posy", "rot", "side"}


@dataclass(frozen=True)
class ReleaseArtifacts:
    directories: tuple[Path, ...]
    boms: tuple[Path, ...]
    placements: tuple[Path, ...]


def csv_kind(path):
    """Classify a CSV from header columns, never from its filename."""
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            header = next(csv.reader(handle), [])
    except (OSError, UnicodeError, csv.Error):
        return None
    columns = {column.strip().lower() for column in header}
    if any(required <= columns for required in BOM_HEADER_SETS):
        return "bom"
    if PLACEMENT_COLUMNS <= columns:
        return "placement"
    return None


def artifact_kind(path):
    """Return the declared supplier-facing artifact kind, or None."""
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return csv_kind(path)
    if suffix in GERBER_SUFFIXES:
        return "gerber"
    if suffix == ".drl" or name.endswith("-drl_map.pdf"):
        return "drill"
    if suffix == ".gbrjob":
        return "job"
    if suffix in (".step", ".stp"):
        return "step"
    if suffix in ARCHIVE_SUFFIXES or name.endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
        return "archive"
    return None


def discover_release_artifacts(gripper_root):
    """Walk a gripper tree and return artifact directories, BOMs, and placements."""
    root = Path(gripper_root)
    directories = set()
    boms = []
    placements = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        kind = artifact_kind(path)
        if kind is None:
            continue
        directories.add(path.parent)
        if kind == "bom":
            boms.append(path)
        elif kind == "placement":
            placements.append(path)
    return ReleaseArtifacts(tuple(sorted(directories)), tuple(boms), tuple(placements))


def required_status_paths(gripper_root):
    """Return directory and per-BOM status paths implied by discovery."""
    artifacts = discover_release_artifacts(gripper_root)
    directory_statuses = tuple(path / "ORDER-STATUS.md" for path in artifacts.directories)
    bom_statuses = tuple(path.with_name(path.stem + "-ORDER-STATUS.md") for path in artifacts.boms)
    return directory_statuses + bom_statuses


def validate_statuses(gripper_root, block):
    """Raise a path-specific assertion unless every discovered status has block."""
    begin = "<!-- ORDER-STATUS:BEGIN -->"
    end = "<!-- ORDER-STATUS:END -->"
    for path in required_status_paths(gripper_root):
        relative = path.relative_to(gripper_root).as_posix()
        if not path.exists():
            raise AssertionError("%s ordering block is missing" % relative)
        text = path.read_text(encoding="utf-8")
        if begin not in text or end not in text:
            raise AssertionError("%s ordering block markers are missing" % relative)
        actual = text[text.index(begin):text.index(end) + len(end)]
        if actual != block:
            raise AssertionError("%s ordering block is stale or not identical" % relative)
