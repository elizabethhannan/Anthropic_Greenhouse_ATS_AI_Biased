"""Figures g1–g6 for Model 2 v1.1, drawn from outputs/model2_v1_1_results.json only.

Purple family (#5b3f8c, #8a6fbf, #c9b8e6) plus a neutral gray; no yellow or gold.
Every title starts with "SIMULATION:"; text >= 14 pt. SVG and PNG (300 dpi).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
FIG = OUT / "figures"

DARK, MID, LIGHT, GRAY = "#5b3f8c", "#8a6fbf", "#c9b8e6", "#8c8a93"
INK, INK2, GRID = "#1d1a22", "#4a4552", "#ebe6f3"
FOOT = "SIMULATION — synthetic applicants; not Anthropic data. Lines = median of runs."

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


def style(ax):
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def ext(r, eid):
    return next(e for e in r["extensions"] if e["id"] == eid)


def pick(e, **kw):
    return [x for x in e["results"] if all(x.get(k) == v for k, v in kw.items())]


def foot(fig, text=FOOT, y=-0.02):
    fig.text(0.01, y, text, fontsize=14, color=INK2, ha="left", va="top")


def g1(r):
    e = ext(r, "X1")
    colors = {0: GRAY, 0.25: LIGHT, 0.5: MID, 0.75: DARK}
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), sharex=True, sharey=True)
    for i, scen in enumerate(("S1", "S2")):
        for j, cal in enumerate(("C1", "C2")):
            ax = axes[i, j]
            for x in pick(e, scenario=scen, calibration=cal):
                med = x["overall_ir"]["median"]
                ax.plot(range(1, len(med) + 1), med, color=colors[x["value"]], linewidth=2.6, marker="o",
                        markersize=6, label=f"w = {x['value']}")
            ax.axhline(0.80, color=GRAY, linestyle="--", linewidth=1.4)
            ax.set_title(f"{scen} {'even-handed interviews' if scen == 'S1' else 'interview penalty continues'}, {cal}")
            style(ax)
            if i == 1:
                ax.set_xlabel("Hiring cycle")
            if j == 0:
                ax.set_ylabel("Overall impact ratio")
    axes[0, 0].legend(frameon=False, loc="lower left", title="Reliance on screen score")
    fig.suptitle("SIMULATION: Interviewer reliance on the AI screen score (X1)", x=0.01, ha="left")
    foot(fig, FOOT + " Dashed line = 0.80 (four-fifths).")
    fig.tight_layout()
    save(fig, "g1_reliance_overall_ir")


def g2(r):
    e = ext(r, "X2")
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), sharex=True)
    for j, scen in enumerate(("S1", "S2")):
        rows = pick(e, scenario=scen, calibration="C2")
        ref = rows[0]["reference_v1_0_same_seeds"]
        for i, (key, lab) in enumerate((("screen_ir", "Screen impact ratio"), ("proxy_signal", "Proxy weight (x₃)"))):
            ax = axes[i, j]
            med = ref[key]["median"]
            ax.plot(range(1, len(med) + 1), med, color=GRAY, linewidth=2.6, marker="o", markersize=6,
                    label="ε = 0 (v1.0)")
            for x, c in zip(rows, (MID, DARK)):
                med = x[key]["median"]
                ax.plot(range(1, len(med) + 1), med, color=c, linewidth=2.6, marker="o", markersize=6,
                        label=f"ε = {x['value']} (+{x['extra_interviews_per_cycle']} interviews/cycle)")
            if key == "screen_ir":
                ax.axhline(1.0, color=LIGHT, linewidth=1.2)
            else:
                ax.axhline(0.0, color=LIGHT, linewidth=1.2)
            ax.set_title(f"{scen}, C2: {lab.lower()}")
            ax.set_ylabel(lab)
            style(ax)
            if i == 1:
                ax.set_xlabel("Hiring cycle")
    axes[0, 0].legend(frameon=False, loc="lower right")
    fig.suptitle("SIMULATION: Exploration — interviewing a random share of screened-out applicants (X2)",
                 x=0.01, ha="left")
    foot(fig)
    fig.tight_layout()
    save(fig, "g2_exploration")


def g3(r, cycle=5):
    e = ext(r, "X3")
    cycle = min(cycle, r["config"]["T"])
    arms = ("S0", "S1", "S2", "I1", "I2")
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5), sharey=True)
    for ax, cal in zip(axes, ("C1", "C2")):
        for k, arm in enumerate(arms):
            x = pick(e, calibration=cal, arm=arm)[0]
            for off, src, c, lab in ((-0.15, x["reference_v1_0_same_seeds"]["screen_ir"], GRAY, "Logistic (v1.0)"),
                                     (0.15, x["screen_ir"], DARK, "Gradient boosting")):
                med, lo, hi = src["median"][cycle - 1], src["p05"][cycle - 1], src["p95"][cycle - 1]
                ax.plot([k + off, k + off], [lo, hi], color=c, linewidth=2.2)
                ax.plot(k + off, med, "o", color=c, markersize=10, label=lab if k == 0 else None)
        ax.axhline(0.80, color=GRAY, linestyle="--", linewidth=1.4)
        ax.axhline(1.0, color=LIGHT, linewidth=1.2)
        ax.set_xticks(range(len(arms)), arms)
        ax.set_title(f"{cal}: screen impact ratio, cycle {cycle}")
        style(ax)
    axes[0].set_ylabel("Screen impact ratio")
    axes[0].legend(frameon=False, loc="lower left")
    fig.suptitle("SIMULATION: Gradient-boosted vs. logistic screener, same seeds (X3)", x=0.01, ha="left")
    foot(fig, "SIMULATION — synthetic applicants; not Anthropic data. Dot = median; bar = 5th–95th percentile; "
              "100 runs, same seeds.\nS0 null, S1 even-handed interviews, S2 penalty continues, "
              "I1 proxy removed, I2 reweighing.", y=-0.04)
    fig.tight_layout()
    save(fig, "g3_boosted_vs_logistic")


def g4(r, cycle=5):
    e = ext(r, "X4")
    cycle = min(cycle, r["config"]["T"])
    lam_c = {0: LIGHT, 0.3: MID, 0.6: DARK}
    markers = {"S2": "o", "I1": "s", "I2": "^"}
    fig, ax = plt.subplots(figsize=(11, 8))
    for x in e["results"]:
        v, s = x["screen_validity"], x["screen_ir"]
        vx, sy = v["median"][cycle - 1], s["median"][cycle - 1]
        ax.plot([v["p05"][cycle - 1], v["p95"][cycle - 1]], [sy, sy], color=lam_c[x["value"]], linewidth=1.6)
        ax.plot([vx, vx], [s["p05"][cycle - 1], s["p95"][cycle - 1]], color=lam_c[x["value"]], linewidth=1.6)
        ax.plot(vx, sy, markers[x["arm"]], color=lam_c[x["value"]], markersize=13, markeredgecolor=INK,
                markeredgewidth=0.8)
    ax.axhline(0.80, color=GRAY, linestyle="--", linewidth=1.4)
    ax.axhline(1.0, color=GRAY, linewidth=1.0)
    ax.set_xlabel(f"Screen validity (Spearman with true qualification), cycle {cycle}")
    ax.set_ylabel(f"Screen impact ratio, cycle {cycle}")
    style(ax)
    h = [Line2D([], [], marker=markers[a], color=GRAY, linestyle="none", markersize=12, label=lab)
         for a, lab in (("S2", "S2 no fix"), ("I1", "I1 remove proxy"), ("I2", "I2 reweighing"))]
    h += [Line2D([], [], color=lam_c[lv], linewidth=5, label=f"λ = {lv}") for lv in (0, 0.3, 0.6)]
    ax.legend(handles=h, frameon=False, loc="lower right", ncol=2)
    ax.set_title("SIMULATION: The price of each fix when the proxy carries job signal (X4, C2)", loc="left")
    foot(fig, "SIMULATION — synthetic applicants; not Anthropic data. Marker = median; lines = 5th–95th "
              "percentile.\nλ = share of true qualification in the proxy. I1 does not use the proxy, so its three λ points coincide.", y=-0.03)
    fig.tight_layout()
    save(fig, "g4_proxy_relevance_tradeoff")


def g5(r):
    e = ext(r, "X5")
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), sharex=True, sharey=True)
    for i, scen in enumerate(("S1", "S2")):
        for j, cal in enumerate(("C1", "C2")):
            ax = axes[i, j]
            x = pick(e, scenario=scen, calibration=cal)[0]
            for src, c, lab in ((x["reference_v1_0_same_seeds"]["screen_ir"], GRAY, "Last cycle only (v1.0)"),
                                (x["screen_ir"], DARK, "All past cycles (X5)")):
                med = src["median"]
                ax.fill_between(range(1, len(med) + 1), src["p05"], src["p95"], color=c, alpha=0.12, linewidth=0)
                ax.plot(range(1, len(med) + 1), med, color=c, linewidth=2.6, marker="o", markersize=6, label=lab)
            ax.axhline(0.80, color=GRAY, linestyle="--", linewidth=1.4)
            ax.set_title(f"{scen}, {cal}: screen impact ratio")
            style(ax)
            if i == 1:
                ax.set_xlabel("Hiring cycle")
            if j == 0:
                ax.set_ylabel("Screen impact ratio")
    axes[0, 0].legend(frameon=False, loc="lower right")
    fig.suptitle("SIMULATION: Training on all history vs. the last cycle (X5)", x=0.01, ha="left")
    foot(fig, FOOT + " Band = 5th–95th percentile.")
    fig.tight_layout()
    save(fig, "g5_cumulative_window")


def g6(r):
    pw = r["power"]
    styles = {0.97: (GRAY, ":"), 0.86: (LIGHT, "-"), 0.80: (MID, "--"), 0.62: (DARK, "-"), 0.60: (DARK, "--")}
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), sharex=True, sharey=True)
    for i, stage in enumerate(("screen", "interview")):
        for j, p in enumerate((0.203, 0.30)):
            ax = axes[i, j]
            for row in (x for x in pw["rows"] if x["stage"] == stage and x["pool_share_women"] == p):
                As = [int(a) for a in row["power_by_A"]]
                c, ls = styles[row["true_ir"]]
                ax.plot(As, list(row["power_by_A"].values()), color=c, linestyle=ls, linewidth=2.8, marker="o",
                        markersize=6, label=f"true ratio {row['true_ir']:.2f}")
            ax.axhline(0.80, color=GRAY, linewidth=1.4)
            ax.set_xscale("log")
            ax.set_xticks(As, [f"{a:,}" for a in As], rotation=30)
            ax.set_ylim(0, 1.02)
            ax.set_title(f"{stage.capitalize()} stage, women {p * 100:g}% of applicants")
            style(ax)
            if i == 1:
                ax.set_xlabel("Applicants per role family per reporting period")
            if j == 0:
                ax.set_ylabel("Power (Fisher's exact, α = .05)")
    axes[0, 0].legend(frameon=False, loc="upper left")
    fig.suptitle("SIMULATION: How many applicants an audit needs to detect a gap (P1)", x=0.01, ha="left")
    foot(fig, "SIMULATION — synthetic counts; not Anthropic data. 2,000 replicates per point; "
              "gray line = 80% power. Interview stage at risk = the 10% shortlisted.")
    fig.tight_layout()
    save(fig, "g6_power_curves")


def main():
    r = json.loads((OUT / "model2_v1_1_results.json").read_text(encoding="utf-8"))
    for f in (g1, g2, g3, g4, g5, g6):
        f(r)


if __name__ == "__main__":
    main()
