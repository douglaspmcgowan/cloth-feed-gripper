"""The finger calculation must reject stale committed results."""

import json
from pathlib import Path

import finger_beam


def test_check_detects_changed_value_without_writing(tmp_path, monkeypatch, capsys):
    source = Path(finger_beam.__file__).parent / "results" / "finger_beam.json"
    result = json.loads(source.read_text(encoding="utf-8"))
    result["cases"]["design_L45"]["geometry"]["rc_tip"] = 0
    stored = tmp_path / "finger_beam.json"
    stored.write_text(json.dumps(result), encoding="utf-8")
    before = stored.read_bytes()
    monkeypatch.setattr(finger_beam, "RESULTS", tmp_path)

    assert finger_beam.main(check=True) == 1
    assert "cases.design_L45.geometry.rc_tip" in capsys.readouterr().out
    assert stored.read_bytes() == before


def test_check_accepts_current_result(capsys):
    assert finger_beam.main(check=True) == 0
    assert "FRESH" in capsys.readouterr().out


def test_moment_arm_matches_design_and_current_cad():
    params = finger_beam.load_params()
    finger_beam.apply_overrides(params)
    design = finger_beam.load_geometry(params, design=True)
    current = finger_beam.load_geometry(params, design=False)
    assert abs(design["rc_tip"] - params["grip"]["r_c_design_mm"]) <= 0.5
    assert abs(current["rc_tip"] - params["grip"]["r_c_current_cad_mm"]) <= 0.5
