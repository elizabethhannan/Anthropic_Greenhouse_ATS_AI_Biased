"""Figures for Model 2, drawn from outputs/ only.

Purple family only (#5b3f8c, #8a6fbf, #c9b8e6); every title starts with
"SIMULATION:"; minimum text size 14 pt. Writes SVG and PNG (300 dpi).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
FIG = OUT / "figures"

DARK, MID, LIGHT = "#5b3f8c", "#8a6fbf", "#c9b8e6"
INK, INK2, GRID = "#1d1a22", "#4a4552", "#ebe6f3"
FOOT = "SIMULATION — synthetic applicants; not Anthropic data. Median of runs; band or bar = 5th–95th percentile."

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 14, "axes.titlesize": 15, "axes.labelsize": 14,
    "xtick.labelsize": 14, "ytick.labelsize": 14, "legend.fontsize": 14, "figure.titlesize": 18,
    "text.color": INK, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.edgecolor": "#b9b2c4", "axes.linewidth": 0.8, "svg.fonttype": "none",
})


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.svg", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def style_axes(ax):
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def e1(r, cal):
    c = next(x for x in r["calibrations"] if x["id"] == cal)
    scen = [s for s in r["scenarios"] if s["calibration"] == cal]
    fig, axes = plt.subplots(2, 2, figsize=(14, 9.5), sharex=True, sharey=True)
    for ax, s in zip(axes.flat, scen):
        m = s["screen_impact_ratio"]
        x = s["cycles"]
        ax.fill_between(x, m["p05"], m["p95"], color=LIGHT, alpha=0.75, linewidth=0)
        ax.plot(x, m["median"], color=DARK, linewidth=2.2, marker="o", markersize=7)
        ax.axhline(0.80, color=MID, linestyle="--", linewidth=1.6)
        ax.axhline(1.0, color="#b9b2c4", linewidth=1)
        ax.set_title(f"{s['id']} · {s['name']}", loc="left", fontsize=15, color=INK)
        ax.text(x[-1], m["median"][-1] + 0.035, f"{m['median'][-1]:.2f}", ha="right", va="bottom",
                fontsize=14, color=INK)
        style_axes(ax)
        ax.set_ylim(0.6, 1.25)
        ax.set_xticks(x)
    for ax in axes[1]:
        ax.set_xlabel("Hiring cycle (retraining after each)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Screen impact ratio\n(women ÷ men selection rate)")
    axes[0, 0].text(1, 0.785, "Four-fifths threshold 0.80", va="top", fontsize=14, color=INK2)
    fig.suptitle(f"SIMULATION: Screen-stage impact ratio by hiring cycle, {cal} {c['name']}\n"
                 f"pool {c['pool_share_women']:.1%} women; history calibrated to {c['target_hire_share_women']:.1%} "
                 f"of hires (δ₀ = {c['delta0']:.3f}); ρ = {r['config']['rho']:g}; {r['config']['runs']} runs",
                 x=0.01, ha="left", fontsize=17)
    legend = [Line2D([0], [0], color=DARK, lw=2.2, marker="o", label="Median"),
              Patch(facecolor=LIGHT, alpha=0.75, label="5th–95th percentile"),
              Line2D([0], [0], color=MID, lw=1.6, ls="--", label="0.80 threshold")]
    fig.legend(handles=legend, loc="upper left", ncol=3, frameon=False, bbox_to_anchor=(0.005, 0.925))
    fig.text(0.01, -0.01, FOOT, fontsize=14, color=INK2, ha="left")
    fig.tight_layout(rect=(0, 0.01, 1, 0.905))
    save(fig, f"e1_screen_ir_by_cycle_{cal}")


def e2(r, cycle):
    g = r["sensitivity"]
    M = np.array(g[f"screen_ir_cycle{cycle}"], dtype=float)
    rhos, ps = g["proxy_strength"], g["pool_share"]
    cmap = LinearSegmentedColormap.from_list("sim", [DARK, MID, LIGHT, "#f7f4fb"])
    fig, ax = plt.subplots(figsize=(12, 8.5))
    im = ax.imshow(M, cmap=cmap, vmin=0.70, vmax=1.02, origin="lower", aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=15,
                    color="white" if v < 0.78 else INK, fontweight="bold" if v < 0.80 else "normal")
            if v < 0.80:
                ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor=INK, linewidth=2.5))
    ax.set_xticks(range(len(ps)), [f"{p:.3f}".rstrip("0").rstrip(".") for p in ps])
    ax.set_yticks(range(len(rhos)), [f"{x:g}" for x in rhos])
    ax.set_xlabel("Assumed pool share of women (p)")
    ax.set_ylabel("Proxy strength ρ (standardized difference)")
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("Median screen impact ratio", fontsize=14)
    cb.ax.tick_params(labelsize=14)
    ax.set_title(f"SIMULATION: Median screen impact ratio, S2 (interview penalty continues), cycle {cycle}\n"
                 f"δ₀ calibrated per column to a {g['target_hire_share_women']:.3f} cycle-0 hire share; "
                 f"{r['grid_runs_per_cell']} runs per cell; outlined cells < 0.80",
                 loc="left", fontsize=16)
    fig.text(0.01, -0.03, "SIMULATION — synthetic applicants; not Anthropic data. Which assumptions would have "
             "to be true for a screening model to carry a gap forward.", fontsize=14, color=INK2)
    fig.tight_layout()
    save(fig, f"e2_sensitivity_S2_cycle{cycle}")


def e3(r):
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.6), sharey=True)
    for ax, cal in zip(axes, ("C1", "C2")):
        base = next(s for s in r["scenarios"] if s["calibration"] == cal and s["id"] == "S2")
        rows = [("S2 baseline", base["screen_impact_ratio"]["median"][4], base["screen_impact_ratio"]["p05"][4],
                 base["screen_impact_ratio"]["p95"][4], True)]
        for iv in r["interventions"]:
            if iv["calibration"] != cal:
                continue
            d = iv["screen_ir_cycle5"]
            rows.append((f"{iv['id']} {iv['name']}", d["median"], d["p05"], d["p95"], False))
        y = np.arange(len(rows))[::-1]
        for yi, (lab, med, lo, hi, is_base) in zip(y, rows):
            ax.plot([lo, hi], [yi, yi], color=MID if is_base else DARK, linewidth=3, solid_capstyle="round")
            ax.plot(med, yi, marker="o", markersize=12, markerfacecolor="white" if is_base else DARK,
                    markeredgecolor=DARK, markeredgewidth=2.2, linestyle="none")
            ax.text(hi + 0.012, yi, f"{med:.2f}", va="center", fontsize=14, color=INK)
        ax.axvline(0.80, color=MID, linestyle="--", linewidth=1.6)
        ax.axvline(1.0, color="#b9b2c4", linewidth=1)
        ax.text(0.795, y[0] + 0.45, "0.80", ha="right", va="center", fontsize=14, color=INK2)
        ax.set_ylim(-0.6, len(rows) - 0.3)
        ax.set_yticks(y, [row[0] for row in rows])
        ax.set_xlim(0.7, 1.25)
        c = next(x for x in r["calibrations"] if x["id"] == cal)
        ax.set_title(f"{cal} {c['name']}", loc="left", fontsize=15)
        ax.set_xlabel("Screen impact ratio at cycle 5")
        ax.grid(axis="x", color=GRID, linewidth=1)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    fig.suptitle("SIMULATION: Screen impact ratio at cycle 5 — S2 baseline vs. interventions",
                 x=0.01, ha="left", fontsize=17)
    fig.text(0.01, -0.04, FOOT + " Hollow marker = baseline.", fontsize=14, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    save(fig, "e3_interventions")


def main():
    r = json.loads((OUT / "model2_results.json").read_text(encoding="utf-8"))
    for cal in ("C1", "C2"):
        e1(r, cal)
    for cyc in (1, 5):
        e2(r, cyc)
    e3(r)
    print(sorted(p.name for p in FIG.iterdir()))


if __name__ == "__main__":
    main()
