"""Figure style shared by every report figure: 300 dpi, greyscale-legible, labelled axes."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import config  # noqa: E402

# Distinguishable in greyscale: line styles and markers carry the identity, colour only helps.
STYLES = {
    "snaive": {"color": "#7f7f7f", "linestyle": ":", "marker": "x"},
    "arima": {"color": "#1f4e79", "linestyle": "--", "marker": "o"},
    "ets": {"color": "#548235", "linestyle": "-.", "marker": "s"},
    "ffnn": {"color": "#c55a11", "linestyle": (0, (5, 2, 1, 2)), "marker": "^"},
    "lstm": {"color": "#7030a0", "linestyle": (0, (1, 1)), "marker": "v"},
    "hyb_d": {"color": "#000000", "linestyle": "-", "marker": "D"},
    "hyb_ms": {"color": "#404040", "linestyle": "-", "marker": "P"},
    "hyb_z": {"color": "#a6a6a6", "linestyle": "-", "marker": "*"},
}
LABELS = {
    "snaive": "Seasonal naive",
    "arima": "ARIMA",
    "ets": "ETS",
    "ffnn": "FFNN",
    "lstm": "LSTM",
    "hyb_d": "Hybrid (direct)",
    "hyb_ms": "Hybrid (multi-step errors)",
    "hyb_z": "Hybrid (recursive)",
}


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "figure.dpi": 100,
            "savefig.dpi": 300,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def save(fig, name: str) -> str:
    """Save a figure as 300-dpi PNG into ``outputs/figures`` and return the relative path."""
    config.FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    path = config.FIGURE_DIR / f"{name}.png"
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return str(path.relative_to(config.CODE_DIR)).replace("\\", "/")
