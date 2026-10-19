"""Fourth review B1 and B2: committed `run` and `revb` results equal a fresh run; every figure caption equals its JSON."""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tolstack  # noqa: E402
from tolcalc import report  # noqa: E402

RESULTS = ROOT / "results"
REVB = RESULTS / "rev_b"
SAMPLES, SEED = 100_000, 20260922  # the CLI defaults the committed files were generated with


def _top_level_files():
    return sorted(p.name for p in RESULTS.iterdir()
                  if p.is_file() and not p.name.startswith("sweep_")
                  and (p.suffix in (".json", ".md") or p.name == "run_stdout.txt"))


def _revb_files():
    return sorted(p.name for p in REVB.iterdir() if p.is_file())


@pytest.fixture(scope="module")
def fresh_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("run")
    shutil.copytree(RESULTS / "figures", out / "figures")  # the .md embeds a figure link only where the PNG exists
    args = argparse.Namespace(paths=[], out=str(out), fig_dir=None, doc=None, no_doc=True, samples=SAMPLES,
                              seed=SEED, set=None, plots=False)
    assert tolstack.cmd_run(args) == 0
    return out


@pytest.fixture(scope="module")
def fresh_revb(tmp_path_factory):
    out = tmp_path_factory.mktemp("revb")
    args = argparse.Namespace(out=str(out), case=None, doc=None, no_doc=True, samples=SAMPLES, seed=SEED)
    assert tolstack.cmd_revb(args) == 0
    return out


def test_run_writes_exactly_the_committed_file_set(fresh_run):
    fresh = sorted(p.name for p in fresh_run.iterdir() if p.is_file())
    assert fresh == _top_level_files()


@pytest.mark.parametrize("name", _top_level_files())
def test_committed_run_result_equals_fresh_regeneration(name, fresh_run):
    assert (fresh_run / name).read_bytes() == (RESULTS / name).read_bytes(), f"results/{name} is stale"


def test_revb_writes_exactly_the_committed_file_set(fresh_revb):
    assert sorted(p.name for p in fresh_revb.iterdir() if p.is_file()) == _revb_files()


@pytest.mark.parametrize("name", _revb_files())
def test_committed_revb_result_equals_fresh_regeneration(name, capsys, fresh_revb):
    capsys.readouterr()
    assert (fresh_revb / name).read_bytes() == (REVB / name).read_bytes(), f"results/rev_b/{name} is stale"


# ------------------------------------------------------------------ figures

def _png_description(path: Path) -> str | None:
    """Read the tEXt `Description` chunk that report.histogram embeds (the caption is not readable from pixels)."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path.name
    pos = 8
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b"tEXt":
            key, _, val = body.partition(b"\0")
            if key == b"Description":
                return val.decode("latin-1")
        elif kind == b"iTXt":
            key, _, rest = body.partition(b"\0")
            if key == b"Description":
                flag, method = rest[0], rest[1]
                text = rest[2:].split(b"\0", 2)[2]
                return (zlib.decompress(text) if flag and method == 0 else text).decode("utf-8")
        elif kind == b"IEND":
            break
    return None


FIGURES = sorted((RESULTS / "figures").glob("tol_*.png"), key=lambda p: p.name.lower())


def test_every_result_has_a_figure_and_every_figure_a_result():
    ids = sorted(p.stem for p in RESULTS.glob("*.json") if not p.name.startswith(("sweep_", "summary")))
    assert sorted(p.stem[4:] for p in FIGURES) == ids


@pytest.mark.parametrize("fig", FIGURES, ids=lambda p: p.stem)
def test_figure_caption_equals_the_one_built_from_its_committed_json(fig):
    r = json.loads((RESULTS / f"{fig.stem[4:]}.json").read_text(encoding="utf-8"))
    assert _png_description(fig) == report.histogram_caption(r), (
        f"{fig.name} caption is stale; run `tolstack.py run --plots`")
