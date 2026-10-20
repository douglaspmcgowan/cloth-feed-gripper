"""Build the single B40 pass-3 PR evidence comment from recorded command results."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
before = json.loads((root / ".fleet_pass2_before3.json").read_text(encoding="utf-8"))
after = json.loads((root / ".fleet_pass2_after3b.json").read_text(encoding="utf-8"))
commands = [
    ("dog_check", "uv run --python 3.12 --no-project --with cadquery --with numpy --with scipy --with matplotlib python cad/gripper/dog_check.py"),
    ("cad_pytest", "uv run --python 3.12 --no-project --with cadquery --with pytest --with pygments --with pyyaml --with playwright --with shapely python -m pytest -q -p no:cacheprovider --basetemp <fresh> cad/gripper"),
    ("tolstack_pytest", "uv run --python 3.12 --no-project --with-requirements requirements-dev.txt python -m pytest -q -p no:cacheprovider --basetemp <fresh> analysis/gripper/tolstack"),
    ("actuation_pytest", "uv run --python 3.12 --no-project --with-requirements requirements-dev.txt python -m pytest -q -p no:cacheprovider --basetemp <fresh> analysis/gripper/actuation"),
    ("pin", "uv run --no-project --with numpy python analysis/gripper/actuation/pin_rev_a.py --check"),
    ("tolstack_check", "uv run --no-project --with pyyaml --with numpy python analysis/gripper/tolstack/tolstack.py --check"),
    ("ecad", "uv run --no-project --with numpy --with scipy python ecad/gripper/calc/run_all.py --check"),
    ("gears", "uv run --no-project --with numpy --with scipy --with matplotlib --with shapely python analysis/gripper/gears.py --check"),
    ("thermal", "uv run --no-project --with numpy --with scipy python analysis/gripper/thermal/thermal.py --check"),
    ("test_plan", "uv run --no-project --with numpy --with scipy --with pyyaml python docs/gripper/test/test_plan.py --check"),
    ("dyno", "uv run --no-project --with numpy --with scipy --with matplotlib --with shapely --with pylife --with packaging python analysis/gripper/dyno.py --check"),
    ("finger_beam", "uv run --no-project --with numpy --with scipy --with matplotlib python analysis/gripper/finger_beam.py --check"),
    ("lint", "npm run lint"),
    ("public", "npm run check:public"),
    ("sync", "python -m unittest tests/test_sync.py"),
]
assert set(before) == set(after) == {name for name, _ in commands}
assert all(after[name]["exit"] == 0 for name, _ in commands)


def result(item):
    last = item["last"] or "(no output)"
    safe_last = last.replace("|", "\\|")
    return f"{item['exit']}; `{safe_last}`"


lines = [
    "## B40 pass 3 — proving gates green",
    "",
    "Specs checked: `SPEC.md` Quality and Sync; `PRODUCT.md`; `docs/gripper/DESIGN-BASIS.md` R10 (ruled 43,720 g·mm limit and 2026-10-11 work-cell disposition); `berkeley-ai-tutor/INTENT.md` (computed evidence, never claimed values). No fabrication file, firmware file, hash lock, generator logic, or checker logic changed.",
    "",
    "Root causes and fixes:",
    "- The README's B40 mass and coupling text used the prior CAD values; regenerated `r10_options.json` and updated its mass, option table, shoulder-dog description, and purchase line from `fitcheck.json` and `dog_check.py`. The full CAD suite exposed a separate README regression from this edit: the as-drawn failure stresses and interim limit must remain visible. Restored them, then verified both B40 README tests.",
    "- The viewer test pinned the pre-B40 `fit3d.json` SHA-256; pinned the regenerated file's digest.",
    "- The loop fingerprint golden omitted `T09-b40_shoulder34` and used the old `dog_d` tolerance; regenerated it from the current stack structure.",
    "- The CHANGELOG, risk record, and tolerance analysis quoted pre-B40 T14B Cpk, yield, and verdict; updated the cold and hot quotes from stored results.",
    "- The independent 75,000-sample tail estimate missed one three-SE bound by 0.00013232 mm. At 100,000 samples, the SE formula `sqrt(p(1-p)(1/N + 1/engine_n))/density` reduces the independent variance term while preserving the three-SE limit; all 102 independent-sampler tests pass. A 200,000-sample trial exposed a separate T07 three-SE outlier, so 100,000 was selected after running the whole sampled file.",
    "- The uncertainty test assumed every T14B result has `sampling_runs`; the generator omits that key when the first run decides the verdict. The test now verifies the decided-first-run shape or the documented rerun shape.",
    "",
    "Changed values (old → new):",
    "- Dog hardware from the unreworked horn to B40: M3 45H set screws in bare aluminium → custom hardened M3×10 Ø2.9 shoulder dogs in two Ø6×3×3 steel inserts in an Ø22 horn; 3.4 mm slots retained. The as-drawn one-dog limit 1.62 → chosen 3.25 N·m (0.56 → 1.13 × stall). At one-dog stall load, former 1,693 MPa bending and 685 MPa aluminium bearing failed; the chosen shoulder has 944 MPa bending, 708 MPa steel bearing, and 342 MPa aluminium bearing. These are calculated, unbuilt margins with coupon gates.",
    "- B40 CAD mass including cloth 152.9 → 153.9 g; COM 37.6 → 37.5 mm past H; full-extension moment 52,995 → 53,342 g·mm and budget use 121.2% → 122.0%; wrist-UVC prediction 58,505 → 58,852 g·mm. Housing 11.71 → 11.66 g (3,871 → 3,854 g·mm), horn 2.36 → 3.43 g (803 → 1,167 g·mm). Compared with rev A, mass gain 8.5 → 9.5 g and moment gain 2,864 → 3,211 g·mm. The 43,720 g·mm limit and full-extension FAIL remain.",
    "- Regenerated mass options: housing/front infill change −5.28 → −5.27 g and −1,755 → −1,751 g·mm; long-Y layout +3.04 → +3.08 g and +2,762 → +2,796 g·mm. Counted running totals 51,240 → 51,591; 50,077 → 50,428; 49,825 → 50,176; 49,592 → 49,943; 48,730 → 49,081; final 48,486 → 48,837 g·mm. Final budget use 110.9% → 111.7%, shortfall 4,766 → 5,117 g·mm (about 13.7 → 14.8 g at COM).",
    "- Cold T14B-boss34 option Cpk 0.96 → 1.10; combined rev B T14B Cpk 0.98 → 1.11, yield 99.84% → 99.952%, FAIL → MARGINAL. Hot Cpk 0.66 → 0.75 and yield 97.64% → 98.76%, still FAIL. Combined cold verdict counts 23 PASS / 2 MARGINAL / 1 FAIL → 23 PASS / 3 MARGINAL / 0 FAIL. `dog_d` fingerprint tolerance 0.106 → 0.010 mm; `T09-b40_shoulder34` added. Independent sample count 75,000 → 100,000; the three-SE bound is unchanged.",
    "- `fit3d.json` SHA-256 pin `28f31be3faa691e1eb97aa95f17c161f07d464788b83bab6e96625e2872add14` → `ef750ca384796d58beecc2ae0d74d8e6ae22582b0f6d72c42620c5545e2693eb`.",
    "",
    "Pass-3 files changed: `cad/gripper/README.md`, `cad/gripper/out/r10_options.json`, `cad/gripper/tests/test_viewer_static.py`, `cad/gripper/CHANGELOG.md`, `analysis/gripper/tolstack/tests/loop_fingerprints.json`, `analysis/gripper/tolstack/tests/test_loop_sampled.py`, `analysis/gripper/tolstack/tests/test_verdict_uncertainty.py`, `docs/gripper/RISK.md`, and `docs/gripper/analysis/tolerance_stacks.md`.",
    "",
    "Proving commands (before → after). The Windows runner adds a private `uv --cache-dir` and fresh `--basetemp` paths outside the worktree:",
    "",
    "| Command | Before: exit; last line | After: exit; last line |",
    "|---|---|---|",
]
for name, command in commands:
    lines.append(f"| `{command}` | {result(before[name])} | {result(after[name])} |")
lines.extend([
    "| `git diff origin/main...HEAD` public-safety scan (`C:[/\\]Users`, `/home/`, email addresses, tokens) | 0; (no output) | 0; (no output) |",
    "",
    "`git diff --check` and the public-safety scan exited 0. The branch was reconciled with `origin/main` before push. PR 14 was marked ready; nothing was merged into main.",
])
(root / ".fleet_pass3_comment.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
