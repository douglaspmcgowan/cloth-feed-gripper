import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import ImageChops


ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def numbers():
    return load("film_numbers", ROOT / "video/gripper/src/film_numbers.py")


def write_basis(root, criterion):
    path = root / "docs/gripper/DESIGN-BASIS.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"| R15 | Force cap | {criterion} | owner ruling | test |\n", encoding="utf-8")


def test_r15_requirement_tracks_authoritative_row(numbers, tmp_path, monkeypatch):
    monkeypatch.setattr(numbers, "ROOT", str(tmp_path))
    write_basis(tmp_path, "Pad force ≤ **8 N**.")
    assert numbers.requirement_force_limit_n() == 8
    write_basis(tmp_path, "Pad force ≤ **7.5 N**.")
    assert numbers.requirement_force_limit_n() == 7.5


@pytest.mark.parametrize("text", ["", "| R15 | Force cap | no numeric criterion | owner | test |\n",
                                   "| R15 | Force cap | Pad force ≤ **8 N**. | owner | test |\n"
                                   "| R15 | Force cap | Pad force ≤ **7 N**. | owner | test |\n"])
def test_r15_requirement_fails_closed(numbers, tmp_path, monkeypatch, text):
    monkeypatch.setattr(numbers, "ROOT", str(tmp_path))
    path = tmp_path / "docs/gripper/DESIGN-BASIS.md"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        numbers.requirement_force_limit_n()


def test_force_semantics_keeps_config_ceiling_distinct(numbers, tmp_path, monkeypatch):
    monkeypatch.setattr(numbers, "ROOT", str(tmp_path))
    cfg = tmp_path / "firmware/gripper/config.h"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("#define F_TARGET_DEFAULT_N 5\n#define F_TRIP_N 7.75\n#define F_CAP_N 10\n", encoding="utf-8")
    write_basis(tmp_path, "Pad force ≤ **8 N**.")
    assert numbers.force_semantics() == (5, 7.75, 8, 10)


def test_mass_reads_canonical_fitcheck(numbers, tmp_path, monkeypatch):
    monkeypatch.setattr(numbers, "ROOT", str(tmp_path))
    fit = tmp_path / "cad/gripper/out/fitcheck.json"
    fit.parent.mkdir(parents=True)
    fit.write_text(json.dumps({"mass": {"total_g_incl_cloth": 153.9}}), encoding="utf-8")
    assert numbers.total_mass_g() == 153.9
    fit.write_text(json.dumps({"mass": {"total_g_incl_cloth": 154.2}}), encoding="utf-8")
    assert numbers.total_mass_g() == 154.2


def test_s7_has_four_distinct_nonoverlapping_references():
    graphics = load("make_graphics", ROOT / "video/gripper/graphics/make_graphics.py")
    assert [value for value, _ in graphics.REFS] == [5, 7.75, 8, 10]
    assert "requirement (R15)" in graphics.REFS[2][1]
    assert "conditional controller ceiling" in graphics.REFS[3][1]
    for layout in ("land", "sq"):
        entries = graphics.s7_reference_layout(layout)
        bounds = [entry["bounds"] for entry in entries]
        for i, a in enumerate(bounds):
            for b in bounds[i + 1:]:
                assert a[3] <= b[1] or b[3] <= a[1], (layout, a, b)


@pytest.mark.parametrize("layout", ["land", "sq"])
def test_s7_reference_lines_do_not_intrude_into_label_clearance(layout):
    """Rendered reference/grid strokes must yield to the four annotation labels."""
    graphics = load("make_graphics", ROOT / "video/gripper/graphics/make_graphics.py")
    original_text = graphics.Canvas.text

    def suppress_reference_text(canvas, xy, text, *args, **kwargs):
        if text not in {label for _, label in graphics.REFS}:
            original_text(canvas, xy, text, *args, **kwargs)

    graphics.Canvas.text = suppress_reference_text
    image = graphics.s7_frame(layout, 120)
    clean = graphics.background(*graphics.LAYOUTS[layout]).convert("RGB").resize(
        graphics.LAYOUTS[layout], graphics.Image.Resampling.LANCZOS
    )
    lines = [entry["line_y"] for entry in graphics.s7_reference_layout(layout)]
    lines += [graphics.s7_geom(layout)["py1"] - force / graphics.YMAX *
              (graphics.s7_geom(layout)["py1"] - graphics.s7_geom(layout)["py0"])
              for force in range(0, 11, 2)]
    checked = 0
    for entry in graphics.s7_reference_layout(layout):
        fallback = (entry["bounds"][0] - 10, entry["bounds"][1] - 8,
                    entry["bounds"][2] + 6, entry["bounds"][3] + 28)
        x0, y0, x1, y1 = map(round, entry.get("clearance", fallback))
        intruders = [round(y) for y in lines if y0 <= y <= y1]
        for y in intruders:
            checked += 1
            # With glyphs suppressed, their interior must be pristine plot background.
            diff = ImageChops.difference(image.crop((x0 + 30, y - 2, x1 - 10, y + 3)),
                                         clean.crop((x0 + 30, y - 2, x1 - 10, y + 3)))
            assert diff.getbbox() is None, (layout, entry["label"], y)
    assert checked >= 3, layout
