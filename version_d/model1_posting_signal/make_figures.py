"""Model 1 figures from outputs/model1_results.json only (aggregates; no names).

Masculine-coded words navy #24406b, feminine-coded words green #4f7a3a (word counts,
not people). Named-people charts: women #4f7fb3, men #d97757, unknown #b0aea5.
Text >= 14 pt; no yellow or gold. SVG and 300-dpi PNG.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
FIG = OUT / "figures"
MASC, FEM = "#24406b", "#4f7a3a"
WOMEN, MEN, UNK = "#4f7fb3", "#d97757", "#b0aea5"
INK, INK2, GRID = "#141413", "#4a4843", "#e6e1d8"
FOOT = "Observed measurement — posting text; describes wording, not intent. (Anthropic, 2026)"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 14, "axes.titlesize": 15, "axes.labelsize": 14,
    "xtick.labelsize": 14, "ytick.labelsize": 14, "legend.fontsize": 14, "text.color": INK,
    "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": "#c9c3b8",
    "svg.fonttype": "none",
})


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.svg", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def clean(ax, axis="x"):
    ax.grid(axis=axis, color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def f1(r):
    fams = ["Fellows", "Research-titled", "Engineering", "Other"]
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2), sharey=True)
    for ax, key, title in ((axes[0], "by_family", "Raw lexicon"),
                           (axes[1], "by_family_sense_filtered", "Sense-filtered (low-precision stems dropped)")):
        rows = {x["family"]: x for x in r["wording"][key]}
        y = np.arange(len(fams))[::-1]
        for yi, f in zip(y, fams):
            for off, mtr, col in ((0.14, "masc_per_1k", MASC), (-0.14, "fem_per_1k", FEM)):
                m = rows[f][mtr]
                ax.plot(m["ci"], [yi + off] * 2, color=col, linewidth=3, solid_capstyle="round")
                ax.plot(m["mean"], yi + off, "o", color=col, markersize=10, markeredgecolor="white", markeredgewidth=1.5)
                ax.text(m["ci"][1] + (0.35 if key == "by_family" else 0.05), yi + off, f"{m['mean']:.2f}",
                        va="center", fontsize=14, color=INK)
        ax.set_yticks(y, [f"{f} (n = {rows[f]['n']})" for f in fams])
        ax.set_title(title, loc="left")
        ax.set_xlabel("Coded words per 1,000 words (mean, bootstrap 95% CI)")
        ax.set_xlim(left=0)
        clean(ax)
    axes[1].set_xlim(0, 4)
    leg = [Line2D([0], [0], color=MASC, marker="o", lw=3, label="Masculine-coded"),
           Line2D([0], [0], color=FEM, marker="o", lw=3, label="Feminine-coded")]
    fig.legend(handles=leg, loc="upper left", ncol=2, frameon=False, bbox_to_anchor=(0.005, 0.93))
    fig.suptitle("Gender-coded wording by role family, primary corpus (latest version per posting)",
                 x=0.01, ha="left", fontsize=17)
    fig.text(0.01, -0.03, FOOT + " Lexicon weakly valid here: 21% trait-sense precision; κ = "
             f"{r['wording']['convergent_check']['kappa']:.2f}.", fontsize=14, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    save(fig, "f1_wording_by_family")


def f2(r):
    order = ["AI Security Fellow (Apr 2)", "AI Safety Fellow (Apr 3)", "ML Systems & Performance (Apr 15)",
             "STEM Fellow (Apr 18)", "Economics (Apr 26 capture)", "Reinforcement Learning (Jun 10)",
             "AI Safety & Security, combined (Sep 29)", "ML Systems & RL, combined (Sep 29)",
             "Economics & Policy, Anthropic Institute (Sep 29)"]
    rows = {x["version"]: x for x in r["visibility"]["by_version"]}
    order = [o for o in order if o in rows] + [k for k in rows if k not in order]
    fig, ax = plt.subplots(figsize=(14, 7.5))
    y = np.arange(len(order))[::-1]
    for yi, v in zip(y, order):
        d = rows[v]
        left = 0
        for k, col in (("women", WOMEN), ("men", MEN), ("unknown", UNK)):
            if d[k]:
                ax.barh(yi, d[k], left=left, color=col, edgecolor="white", linewidth=2, height=0.62)
                ax.text(left + d[k] / 2, yi, str(d[k]), ha="center", va="center", fontsize=14,
                        color="white" if k != "unknown" else INK)
            left += d[k]
        ax.text(left + 0.4, yi, f"{d['named']} named", va="center", fontsize=14, color=INK2)
    ax.set_yticks(y, order)
    ax.set_xlabel("People named in the posting version (listed mentors + past-project credits)")
    ax.set_xlim(0, 36)
    clean(ax)
    v = r["visibility"]
    leg = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (WOMEN, MEN, UNK)]
    ax.legend(leg, ["Woman (public self-ID)", "Man (public self-ID)", "Unknown"], loc="lower right", frameon=False)
    ax.set_title(f"Named people in Fellows postings, by version — {v['named_people']} distinct people; "
                 f"{v['coded']['women']} women, {v['coded']['men']} men, {v['coded']['unknown']} Unknown",
                 loc="left", fontsize=16)
    fig.text(0.01, -0.03, "Gender from public self-identification only; never inferred from names. Counts only; no "
             "names shown. (Anthropic, 2026)", fontsize=14, color=INK2)
    fig.tight_layout()
    save(fig, "f2_named_people_by_version")


def f3(r):
    sa = r["wording"]["sense_audit"]
    fig, axes = plt.subplots(1, 2, figsize=(15, 13))
    for ax, lname, col in ((axes[0], "masculine", MASC), (axes[1], "feminine", FEM)):
        rows = sorted([p for p in sa["precision_by_stem"] if p["list"] == lname], key=lambda p: (p["precision"], p["stem"]))
        y = np.arange(len(rows))
        ax.scatter([p["precision"] for p in rows], y, s=[40 + 25 * p["n"] for p in rows], color=col,
                   edgecolor="white", linewidth=1, zorder=3)
        ax.axvline(0.5, color=INK2, linestyle="--", linewidth=1.4)
        ax.set_yticks(y, [f"{p['stem']} ({p['trait']}/{p['n']})" for p in rows], fontsize=14)
        ax.set_xlim(-0.05, 1.05)
        ax.set_xlabel("Share of audited matches in a trait sense")
        ax.set_title(f"{lname.capitalize()}-coded stems", loc="left", color=col)
        clean(ax)
    fig.suptitle(f"Sense audit: {sa['sampled']} matches, {sa['stems_audited']} stems; "
                 f"overall precision {100 * sa['overall_precision']:.0f}%; {len(sa['dropped_stems'])} stems below 0.50 "
                 "dropped in the sense-filtered score", x=0.01, ha="left", fontsize=16)
    fig.text(0.01, -0.02, "Labels: trait sense / other sense (technical term, task, proper noun, heading). "
             "Dashed line = 0.50 drop rule. Label (trait/n) after each stem.", fontsize=14, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    save(fig, "f3_sense_audit_precision")


def f4(r):
    pairs = [p for p in r["wording"]["change_over_time"]["pairs"] if p["computed"]]
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5), sharey=True)
    for ax, mtr, col, title in ((axes[0], "masc_per_1k", MASC, "Masculine-coded per 1,000"),
                                (axes[1], "fem_per_1k", FEM, "Feminine-coded per 1,000")):
        y = np.arange(len(pairs))[::-1]
        for yi, p in zip(y, pairs):
            a, b = p["from"][mtr], p["to"][mtr]
            ax.annotate("", xy=(b, yi), xytext=(a, yi),
                        arrowprops=dict(arrowstyle="-|>", color=col, lw=2.5, mutation_scale=18))
            ax.plot(a, yi, "o", color="white", markeredgecolor=col, markeredgewidth=2.2, markersize=11)
            ax.text(a, yi + 0.22, f"{a:.2f}", ha="center", fontsize=14, color=INK2)
            ax.text(b, yi - 0.34, f"{b:.2f}", ha="center", fontsize=14, color=INK)
        ax.set_yticks(y, [p["change"].replace(" → ", "\n→ ") for p in pairs], fontsize=14)
        ax.set_title(title, loc="left", color=col)
        ax.set_xlim(0, max(max(p["from"][mtr], p["to"][mtr]) for p in pairs) * 1.25)
        ax.set_ylim(-0.7, len(pairs) - 0.3)
        clean(ax)
    fig.suptitle("Fellows posting versions: wording change from April to September 2026 (raw lexicon)",
                 x=0.01, ha="left", fontsize=17)
    fig.text(0.01, -0.03, FOOT + " Hollow = earlier version. Economics (Apr 26) not scored: text not provided.",
             fontsize=14, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "f4_fellows_version_changes")


def main():
    r = json.loads((OUT / "model1_results.json").read_text(encoding="utf-8"))
    f1(r)
    f2(r)
    f3(r)
    f4(r)
    print(sorted(p.name for p in FIG.iterdir()))


if __name__ == "__main__":
    main()
