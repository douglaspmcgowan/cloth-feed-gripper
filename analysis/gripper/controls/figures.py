"""Figures for controls.md from the Monte Carlo JSON (no simulation). From the repository root:
    python analysis/gripper/controls/figures.py
Writes results/figures/mc_cdf.png."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
SETS = [("before", "W2b-1 settings", "#6a7482", (0, (4, 3))), ("", "shipped firmware", "#1c5bb8", "-"),
        ("bench", "shipped, after M8/M10/M11", "#c9601a", (0, (6, 2)))]
PANELS = [("t_90_s", "time to 4.5 N after G (s)", (0.5, 0.75), "R19 0.75 s ruled\n0.5 s superseded 2026-10-12"),
          ("F_peak_N", "peak true pad force (N)", (8.0, 10.0), "R15: 8 N proposed, 10 N written"),
          ("F_hold_min_N", "lowest true force in the hold (N)", (5.0,), "R14: 5 N")]


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    data = {}
    for tag, *_ in SETS:
        name = "montecarlo" + (("_" + tag) if tag else "") + ".json"
        data[tag] = json.loads((RES / name).read_text(encoding="utf-8"))["runs"]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6))
    for ax, (key, xl, lines, note) in zip(axes, PANELS):
        for tag, lab, col, ls in SETS:
            v = sorted(r["m"][key] for r in data[tag] if r["m"].get(key) is not None)
            n = len(data[tag])
            ax.plot(v, [(i + 1) / n for i in range(len(v))], color=col, ls=ls, lw=2, label=lab)
        for x in lines:
            ax.axvline(x, color="#141d27", lw=1, ls=(0, (2, 2)))
        ax.set_xlabel(xl, fontsize=9)
        ax.set_ylabel("fraction of grips", fontsize=9)
        ax.set_title(note, fontsize=9.5, loc="left")
        ax.grid(True, color="#e2e6eb")
        ax.set_ylim(0, 1.02)
    axes[0].legend(frameon=False, fontsize=8, loc="lower right")
    fig.suptitle("2,000 simulated grips through the compiled firmware (seed 20261011)", x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    (RES / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(RES / "figures/mc_cdf.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
