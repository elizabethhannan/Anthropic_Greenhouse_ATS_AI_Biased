"""Version C neumorphic visualization primitives.

The source repository/commit identifiers below were supplied in the project
brief. The upstream private repository was not independently retrievable here;
this file is a clean Version C adaptation of the visual primitives shown in
the brief, not a verbatim source copy.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patheffects as pe
from matplotlib.patches import FancyBboxPatch

SOURCE_REPOSITORY = "https://github.com/elizabethhannan/AI4ALL_ClinicalMedicalDiabeties_EH-PRIVATE"
SOURCE_FILE = "src/neumorphic_visualizations.py"
SOURCE_COMMIT = "48ab175316e4ff88c81dcde36db9ab0fa788cfd4"
SOURCE_VERIFIED = False
VERSION_C_REPOSITORY = "https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"

CREAM = "#f7f3ea"
PANEL = "#fbfaf5"
NAVY = "#0d1a3d"
GREEN = "#75a95a"
GREEN_DARK = "#356a25"
GREEN_LIGHT = "#d9efc3"
BLUE = "#5279ad"
BLUE_LIGHT = "#a7c9f0"
RED = "#f36f5c"
RED_LIGHT = "#ffa69a"
GOLD = "#efe4ae"
GRID = "#d9d1c4"
BORDER = "#e9e3d8"
SHADOW = "#8d877c"
EXTRA_DEPTH = True
TILE_SHADOW_OFFSET = (5, -5) if EXTRA_DEPTH else (2, -2)
BAR_SHADOW_OFFSET = (3, -3) if EXTRA_DEPTH else (1, -1)
PANEL_SHADOW_OFFSET = (5, -5) if EXTRA_DEPTH else (3, -3)


def neumorphic_figure(figsize: tuple[float, float] = (12, 7)):
    """Return a figure with the Version C cream canvas."""
    return plt.figure(figsize=figsize, facecolor=CREAM)


def add_panel(ax, facecolor: str = PANEL, edgecolor: str = BORDER, shadow: bool = True):
    """Place a rounded recessed panel behind an axis."""
    ax.set_facecolor(facecolor)
    panel = FancyBboxPatch((0, 0), 1, 1, transform=ax.transAxes,
        boxstyle="round,pad=0.018,rounding_size=0.04", facecolor=facecolor,
        edgecolor=edgecolor, linewidth=1.2, zorder=-10, clip_on=False)
    if shadow:
        panel.set_path_effects([pe.SimplePatchShadow(offset=PANEL_SHADOW_OFFSET,
            alpha=.22, shadow_rgbFace=SHADOW),
            pe.SimplePatchShadow(offset=(-3, 3), alpha=.75, shadow_rgbFace="#ffffff"), pe.Normal()])
    ax.add_patch(panel)
    return panel


def add_badge(ax, text: str, color: str = GREEN, x: float = .035, y: float = .94,
              width: float = .34, height: float = .07):
    """Add a compact executive status badge in axis coordinates."""
    badge = FancyBboxPatch((x, y), width, height, transform=ax.transAxes,
        boxstyle="round,pad=0.012,rounding_size=0.025", facecolor=color,
        edgecolor="#ffffff", linewidth=1, zorder=20, clip_on=False)
    badge.set_path_effects([pe.SimplePatchShadow(offset=(3, -3), alpha=.35,
        shadow_rgbFace=NAVY), pe.Normal()])
    ax.add_patch(badge)
    ax.text(x + width/2, y + height/2, text, transform=ax.transAxes,
        ha="center", va="center", color="white", fontsize=9.5,
        fontweight="bold", zorder=21)
    return badge


def add_metric_card(fig, x: float, y: float, width: float, height: float,
                    label: str, value: str, subtitle: str = "", accent: str = GREEN):
    """Draw a rounded figure-relative metric tile."""
    card = FancyBboxPatch((x, y), width, height, transform=fig.transFigure,
        boxstyle="round,pad=0.012,rounding_size=0.025", facecolor=PANEL,
        edgecolor=BORDER, linewidth=1, zorder=10, clip_on=False)
    card.set_path_effects([pe.SimplePatchShadow(offset=TILE_SHADOW_OFFSET,
        alpha=.25, shadow_rgbFace=SHADOW), pe.Normal()])
    fig.patches.append(card)
    fig.text(x + .04*width, y + .68*height, label.upper(), color=NAVY,
             fontsize=9, fontweight="bold")
    fig.text(x + .04*width, y + .29*height, value, color=accent,
             fontsize=22, fontweight="bold")
    if subtitle:
        fig.text(x + .04*width, y + .08*height, subtitle, color=NAVY, fontsize=8)
    return card


def add_beveled_bar(ax, y: float, value: float, label: str, color: str = BLUE,
                    maximum: float = 100.0, height: float = .55):
    """Draw one soft-shadowed horizontal bar on an existing axis."""
    bar = FancyBboxPatch((0, y-height/2), max(0, value), height,
        boxstyle=f"round,pad=0.02,rounding_size={height/2}", facecolor=color,
        edgecolor="white", linewidth=1, zorder=3)
    bar.set_path_effects([pe.SimplePatchShadow(offset=BAR_SHADOW_OFFSET,
        alpha=.25, shadow_rgbFace=SHADOW), pe.Normal()])
    ax.add_patch(bar)
    ax.text(-maximum*.02, y, label, ha="right", va="center", color=NAVY, fontsize=10, fontweight="bold")
    ax.text(min(value + maximum*.02, maximum), y, f"{value:.1f}%", ha="left", va="center", color=NAVY, fontsize=10)
    ax.set_xlim(0, maximum)
    return bar


def outcome_composition_figure(counts: dict[str, int], output: Path | str,
                               title: str = "Observed outcome composition") -> Path:
    """Render aggregate Male/Female/Unknown counts without individual records."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig = neumorphic_figure((10, 4.5))
    ax = fig.add_axes([.10, .22, .82, .55])
    add_panel(ax)
    ax.set_axis_off()
    total = sum(counts.values())
    known = counts.get("MALE", 0) + counts.get("FEMALE", 0)
    male_share = counts.get("MALE", 0) / known * 100 if known else 0
    female_share = counts.get("FEMALE", 0) / known * 100 if known else 0
    fig.text(.08, .88, title, color=NAVY, fontsize=18, fontweight="bold")
    add_metric_card(fig, .10, .62, .24, .20, "Male", f"{counts.get('MALE', 0):,}", f"{male_share:.1f}% of known sex", BLUE)
    add_metric_card(fig, .38, .62, .24, .20, "Female", f"{counts.get('FEMALE', 0):,}", f"{female_share:.1f}% of known sex", RED)
    add_metric_card(fig, .66, .62, .24, .20, "Unknown", f"{counts.get('UNKNOWN', 0):,}", f"of {total:,} observed people", GREEN_DARK)
    ax2 = fig.add_axes([.18, .34, .66, .12])
    ax2.set_xlim(0, 100); ax2.set_ylim(0, 1); ax2.axis("off")
    ax2.barh([.5], [male_share], color=BLUE, height=.58, edgecolor="white")
    ax2.barh([.5], [female_share], left=[male_share], color=RED, height=.58, edgecolor="white")
    fig.text(.18, .25, "Known-sex composition · UNKNOWN excluded from denominator", color=NAVY, fontsize=10)
    fig.savefig(output, dpi=180, facecolor=CREAM, bbox_inches="tight")
    plt.close(fig)
    return output


__all__ = ["CREAM", "PANEL", "NAVY", "GREEN", "BLUE", "RED", "GOLD",
           "neumorphic_figure", "add_panel", "add_badge", "add_metric_card",
           "add_beveled_bar", "outcome_composition_figure"]
