import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import margins
import release_artifacts


def release_copy(tmp_path):
    gripper = tmp_path / "ecad/gripper"
    shutil.copytree(ROOT / "ecad/gripper/kicad/fab", gripper / "kicad/fab")
    return gripper


def validate(gripper):
    release_artifacts.validate_statuses(gripper, margins.order_block(margins.run()))


def test_discovery_finds_current_release_artifacts():
    found = release_artifacts.discover_release_artifacts(ROOT / "ecad/gripper")
    directories = [path.relative_to(ROOT).as_posix() for path in found.directories]
    boms = [path.relative_to(ROOT).as_posix() for path in found.boms]
    assert directories == ["ecad/gripper/kicad/fab", "ecad/gripper/kicad/fab/gerber"]
    assert boms == [
        "ecad/gripper/kicad/fab/gripper-bom-jlcpcb.csv",
        "ecad/gripper/kicad/fab/gripper-bom.csv",
        "ecad/gripper/kicad/fab/gripper-harness-bom.csv",
    ]


@pytest.mark.parametrize(
    ("mutation", "fault"),
    [
        ("new_bom", "new-bom-ORDER-STATUS.md ordering block is missing"),
        ("new_placement", "assembly/ORDER-STATUS.md ordering block is missing"),
        ("new_gerber", "panel/ORDER-STATUS.md ordering block is missing"),
        ("delete_gerber_status", "gerber/ORDER-STATUS.md ordering block is missing"),
        ("stale_status", "gripper-bom-ORDER-STATUS.md ordering block is stale or not identical"),
    ],
)
def test_release_mutations_name_uncovered_artifact(tmp_path, mutation, fault):
    gripper = release_copy(tmp_path)
    fab = gripper / "kicad/fab"
    if mutation == "new_bom":
        target = fab / "new-bom.csv"
        target.write_text("Item,Qty,Manufacturer,MPN\n1,1,Acme,X1\n", encoding="utf-8", newline="\n")
    elif mutation == "new_placement":
        target = fab / "assembly/parts.csv"
        target.parent.mkdir()
        target.write_text("Ref,PosX,PosY,Rot,Side\nR1,1,2,0,top\n", encoding="utf-8", newline="\n")
    elif mutation == "new_gerber":
        target = fab / "panel/panel.gbr"
        target.parent.mkdir()
        target.write_text("G04 panel*\n", encoding="utf-8", newline="\n")
    elif mutation == "delete_gerber_status":
        (fab / "gerber/ORDER-STATUS.md").unlink()
    else:
        target = fab / "gripper-bom-ORDER-STATUS.md"
        text = target.read_text(encoding="utf-8").replace("verify transient heating", "ignore heating", 1)
        target.write_text(text, encoding="utf-8", newline="\n")
    with pytest.raises(AssertionError, match=fault):
        validate(gripper)


def test_missing_fault_row_has_specific_message():
    result = margins.run()
    result["faults"] = [row for row in result["faults"] if row.get("id") != "fault-limit-servo"]
    with pytest.raises(AssertionError, match="required fault row fault-limit-servo is missing"):
        margins.order_block(result)
