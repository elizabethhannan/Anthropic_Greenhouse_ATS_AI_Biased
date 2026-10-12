"""Figures h1–h5 for Model 3, drawn from outputs/ only.

Purple family (#5b3f8c, #8a6fbf, #c9b8e6) plus a neutral gray; no yellow or gold.
Every title starts with "AUDIT:"; text >= 14 pt. SVG and PNG (300 dpi).
"""

from __future__ import annotations

import csv
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
FOOT = ("AUDIT OF STAND-IN AI SCREENERS — synthetic résumés scored against Anthropic's public postings; "
        "not Greenhouse's or Anthropic's system.")
SHORT = {"SC1": "WordLlama\n(primary)", "SC2": "GloVe", "SC3": "fastText\n(failed validity)",
         "SC0": "TF-IDF keywords\n(control)"}

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


def style(ax, axis="y"):
    ax.grid(axis=axis, color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def foot(fig, extra="", y=-0.02):
    fig.text(0.01, y, FOOT + ("\n" + extra if extra else ""), fontsize=14, color=INK2, ha="left", va="top")


def label(e):
    lab = SHORT.get(e["id"], e["id"])
    if e["validity"]["flag_not_meaningful"] and "failed" not in lab:
        lab += "\n(failed validity)"
    return lab


def h1(r):
    S = r["screeners"]
    fig, ax = plt.subplots(figsize=(13, 7))
    for k, e in enumerate(S):
        g = e["name_gap"]
        ax.plot([k, k], [g["null_p025"], g["null_p975"]], color=LIGHT, linewidth=14, solid_capstyle="butt",
                label="95% of random name splits" if k == 0 else None)
        ax.plot(k, g["G_std"], "o", color=DARK, markersize=13, label="Women's − men's names" if k == 0 else None)
        ax.annotate(f"{g['G_std']:+.3f}\np = {g['p_exact']:.3f}", (k, g["G_std"]), xytext=(18, 0),
                    textcoords="offset points", va="center", fontsize=14, color=INK)
    ax.axhline(0, color=GRAY, linewidth=1.2)
    ax.set_xticks(range(len(S)), [label(e) for e in S])
    ax.set_xlim(-0.5, len(S) - 0.2)
    ax.set_ylabel("Score gap (SD of résumé spread)")
    ax.legend(frameon=False, loc="upper left")
    style(ax)
    ax.set_title("AUDIT: Same résumé, women's vs. men's names — score gap by screener", loc="left")
    foot(fig, "Below 0 = men's names scored higher. p = exact test over all 184,756 ways to split the 20 names. "
              "442 technical postings.")
    fig.tight_layout()
    save(fig, "h1_name_gap_by_screener")


def h2(r):
    S = [e for e in r["screeners"] if e["kind"] != "tfidf"]
    fig, axes = plt.subplots(1, len(S), figsize=(16, 9), sharey=True)
    for ax, e in zip(axes, S):
        rows = e["per_name"]
        for i, x in enumerate(rows):
            c, mk = (DARK, "o") if x["group"] == "women" else (GRAY, "s")
            ax.plot(x["effect_std"], i, mk, color=c, markersize=10)
        ax.axvline(0, color=GRAY, linewidth=1)
        ax.set_title(SHORT[e["id"]].replace("\n", " "))
        ax.set_xlabel("Effect vs. unnamed (SD)")
        style(ax, "x")
    axes[0].set_yticks(range(len(S[0]["per_name"])), [x["name"] for x in S[0]["per_name"]])
    axes[0].invert_yaxis()
    h = [Line2D([], [], marker="o", color=DARK, linestyle="none", markersize=10, label="Women's names"),
         Line2D([], [], marker="s", color=GRAY, linestyle="none", markersize=10, label="Men's names")]
    axes[-1].legend(handles=h, frameon=False, loc="lower right")
    fig.suptitle("AUDIT: Each name's effect on the match score", x=0.01, ha="left")
    foot(fig, "Effect = mean change in score versus the same résumé with no name, in SDs of résumé spread.")
    fig.tight_layout()
    save(fig, "h2_per_name_effects")


def h3(r):
    S = r["screeners"]
    fig, ax = plt.subplots(figsize=(13, 7))
    for k, e in enumerate(S):
        s = e["selection"]
        ax.plot([k, k], [s["null_pooled_ir_p025"], s["null_pooled_ir_p975"]], color=LIGHT, linewidth=14,
                solid_capstyle="butt", label="95% of random name splits" if k == 0 else None)
        ax.plot(k, s["pooled_ir"], "o", color=DARK, markersize=13, label="Impact ratio (women ÷ men)" if k == 0 else None)
        ax.annotate(f"{s['pooled_ir']:.2f}", (k, s["pooled_ir"]), xytext=(18, 0), textcoords="offset points",
                    va="center", fontsize=14)
    ax.axhline(0.80, color=GRAY, linestyle="--", linewidth=1.4)
    ax.axhline(1.0, color=GRAY, linewidth=1.0)
    ax.set_xticks(range(len(S)), [label(e) for e in S])
    ax.set_xlim(-0.5, len(S) - 0.2)
    ax.set_ylabel("Selection impact ratio, top 10%")
    ax.legend(frameon=False, loc="upper left")
    style(ax)
    ax.set_title("AUDIT: If each screener picked the top 10% — women's rate ÷ men's rate", loc="left")
    foot(fig, "100 simulated pools per posting; half the résumés carry a woman's name. Dashed line = 0.80 (four-fifths).")
    fig.tight_layout()
    save(fig, "h3_selection_impact_ratio")


def h4(r):
    S = r["screeners"]
    items = r["config"]["word_test_items"]
    fig, ax = plt.subplots(figsize=(13, 7))
    w = 0.18
    colors = (LIGHT, MID, DARK)
    for k, e in enumerate(S):
        for i, it in enumerate(items):
            ax.bar(k + (i - 1) * w, e["word_test"]["by_item"][it], width=w, color=colors[i],
                   label=f"\"women's\" vs. \"men's\" {it}" if k == 0 else None)
        g = e["word_test"]["gap_std_women_minus_men"]
        ax.annotate(f"mean {g:+.3f}", (k, 0), xytext=(0, 10 if g <= 0 else -24), textcoords="offset points",
                    ha="center", fontsize=14, color=INK)
    ax.axhline(0, color=GRAY, linewidth=1.2)
    ax.set_xticks(range(len(S)), [label(e) for e in S])
    ax.set_ylabel("Score gap (SD of résumé spread)")
    ax.legend(frameon=False, loc="upper right")
    style(ax)
    ax.set_title("AUDIT: One word changed — \"Captain, women's …\" vs. \"Captain, men's …\"", loc="left")
    foot(fig, "Unnamed résumés. Below 0 = the \"men's\" version scored higher. Three items only: a probe of these "
              "words, not of gendered wording in general.")
    fig.tight_layout()
    save(fig, "h4_word_test")


def h5(r):
    prim = r["screeners"][0]
    rows = [x for x in csv.DictReader(open(OUT / "posting_gaps.csv", encoding="utf-8")) if x["screener"] == prim["id"]]
    fam_c = {"research": DARK, "engineering": MID, "fellows": GRAY}
    fig, ax = plt.subplots(figsize=(12, 7.5))
    for fam, c in fam_c.items():
        xs = [float(x["masc_per_1k"]) for x in rows if x["family"] == fam and x["masc_per_1k"]]
        ys = [float(x["d_name"]) for x in rows if x["family"] == fam and x["masc_per_1k"]]
        ax.scatter(xs, ys, s=40, color=c, alpha=0.75, edgecolor="none", label=fam.capitalize())
    ax.axhline(0, color=GRAY, linewidth=1)
    lk = prim["posting_link_model1"]
    ax.set_xlabel("Masculine-coded words per 1,000 (Model 1, sense-filtered)")
    ax.set_ylabel("Name gap in that posting (SD)")
    ax.legend(frameon=False, loc="lower right")
    style(ax)
    ax.set_title(f"AUDIT: Posting language vs. name gap ({prim['name'].split(' ')[0]}), "
                 f"Spearman {lk['spearman']:+.2f}, p = {lk['p_perm']:.2f}", loc="left")
    foot(fig, "Exploratory link to Model 1. Each dot is one public Anthropic technical posting.")
    fig.tight_layout()
    save(fig, "h5_posting_language_link")


def main():
    r = json.loads((OUT / "model3_results.json").read_text(encoding="utf-8"))
    for f in (h1, h2, h3, h4, h5):
        f(r)


if __name__ == "__main__":
    main()
