"""Shared matplotlib style so every figure in the project looks the same.

Class colours: blue = legitimate, orange = phishing. Checked for colour-vision
deficiency (CVD separation dE 24.7, contrast >= 3:1). Red/green is avoided in
charts because it is the pair most colour-blind readers cannot separate.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

LEGIT = "#2a78d6"
PHISH = "#eb6834"
CLASS_COLORS = {0: LEGIT, 1: PHISH}
CLASS_NAMES = {0: "legitimate", 1: "phishing"}
MODEL_COLORS = {"distilbert": "#2a78d6", "tfidf_lr": "#1baf7a"}   # slots 1 and 3
TEXT = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"

FIG_DIR = Path(__file__).resolve().parents[1] / "figures"


def use_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "figure.dpi": 110, "savefig.dpi": 150, "savefig.bbox": "tight",
        "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": TEXT,
        "axes.edgecolor": GRID, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
        "lines.linewidth": 2, "legend.frameon": False,
    })


def save(fig, name: str) -> Path:
    FIG_DIR.mkdir(exist_ok=True)
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path)
    return path
