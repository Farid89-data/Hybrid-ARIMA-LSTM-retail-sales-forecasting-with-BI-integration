"""Draw the dashboard design figures: the star schema and the page wireframes.

Usage (from ``Code``)::

    python scripts/make_design_figures.py

These are design drawings, not screenshots. Each wireframe carries the label
"Design wireframe" so that it cannot be mistaken for the built dashboard.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from src.visualisation import apply_style, save  # noqa: E402

DIM_FILL, FACT_FILL, EDGE = "#DBE5F1", "#F2F2F2", "#243F60"


def table_box(ax, x, y, w, title, columns, fill):
    """Draw a table as a box with a title bar; return (x, bottom, width, height)."""
    row = 0.30
    h = 0.62 + row * len(columns) + 0.08
    ax.add_patch(FancyBboxPatch((x, y - h), w, h, boxstyle="round,pad=0.02", facecolor=fill, edgecolor=EDGE,
                                linewidth=1.1))
    ax.text(x + w / 2, y - 0.24, title, ha="center", va="center", fontsize=9, fontweight="bold")
    ax.plot([x, x + w], [y - 0.46, y - 0.46], color=EDGE, linewidth=0.8)
    for i, col in enumerate(columns):
        ax.text(x + 0.1, y - 0.66 - row * i, col, ha="left", va="center", fontsize=7.5)
    return (x, y - h, w, h)


def link(ax, start, end):
    """One-to-many relationship line from a dimension (1) to a fact table (*)."""
    ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="-", color="0.3", linewidth=0.9))
    ax.text(start[0] + 0.12, start[1] - 0.22, "1", fontsize=8, ha="center", va="center")
    ax.text(end[0] + 0.12, end[1] + 0.2, "*", fontsize=9, ha="center", va="center")


def star_schema():
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8.2)
    ax.axis("off")
    ax.grid(False)
    d_date = table_box(ax, 0.2, 8.0, 3.4, "dim_date", ["date (key)", "year, month, month_name", "iso_week, week_start",
                                                        "weekday, weekday_number"], DIM_FILL)
    d_series = table_box(ax, 4.3, 8.0, 3.4, "dim_series", ["series_key (key)", "dataset, series_id", "state (M5)",
                                                            "Rossmann: StoreType, Assortment"], DIM_FILL)
    d_model = table_box(ax, 8.4, 8.0, 3.4, "dim_model", ["model (key)", "model_label", "family"], DIM_FILL)
    f_act = table_box(ax, 0.2, 3.3, 3.4, "fact_actuals", ["series_key, date", "sales", "closed", "split"], FACT_FILL)
    f_fc = table_box(ax, 4.3, 3.3, 3.4, "fact_forecast", ["series_key, model, date", "origin_date, horizon",
                                                          "actual, forecast", "lower, upper (95%)", "scale, scored"],
                     FACT_FILL)
    f_met = table_box(ax, 8.4, 3.3, 3.4, "fact_metrics", ["series_key, model", "rmse, mae, mape, mase",
                                                          "coverage, width_scaled"], FACT_FILL)
    bottom = lambda b: (b[0] + b[2] / 2, b[1])  # noqa: E731
    top = lambda b, dx=0.0: (b[0] + b[2] / 2 + dx, b[1] + b[3])  # noqa: E731
    link(ax, bottom(d_date), top(f_act, -0.6))
    link(ax, (d_date[0] + d_date[2] - 0.3, d_date[1]), top(f_fc, -1.0))
    link(ax, (d_series[0] + 0.4, d_series[1]), top(f_act, 0.6))
    link(ax, bottom(d_series), top(f_fc))
    link(ax, (d_series[0] + d_series[2] - 0.4, d_series[1]), top(f_met, -0.6))
    link(ax, (d_model[0] + 0.4, d_model[1]), top(f_fc, 1.0))
    link(ax, bottom(d_model), top(f_met, 0.6))
    ax.text(6.0, 0.05, "Dimension tables (shaded blue) filter fact tables (grey) through one-to-many relationships.",
            ha="center", fontsize=7.5, style="italic")
    return save(fig, "dash_star_schema")


def wireframe(name, title, panels):
    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9.6)
    ax.axis("off")
    ax.grid(False)
    ax.add_patch(FancyBboxPatch((0.1, 0.1), 15.8, 9.4, boxstyle="square,pad=0", facecolor="white",
                                edgecolor="0.2", linewidth=1.2))
    ax.add_patch(FancyBboxPatch((0.1, 8.7), 15.8, 0.8, boxstyle="square,pad=0", facecolor="#243F60",
                                edgecolor="#243F60"))
    ax.text(0.4, 9.1, title, color="white", fontsize=10, fontweight="bold", va="center")
    ax.text(15.6, 9.1, "Design wireframe", color="white", fontsize=8, va="center", ha="right", style="italic")
    slicers = ["Dataset", "Store", "Model", "Forecast origin"]
    for i, s in enumerate(slicers):
        ax.add_patch(FancyBboxPatch((0.4 + i * 3.9, 7.75), 3.6, 0.65, boxstyle="round,pad=0.02",
                                    facecolor="#F2F2F2", edgecolor="0.4"))
        ax.text(0.6 + i * 3.9, 8.07, f"{s} (slicer)", fontsize=8, va="center")
    for (x, y, w, h, label, kind) in panels:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02", facecolor="#FAFAFA", edgecolor="0.4"))
        ax.text(x + 0.15, y + h - 0.3, label, fontsize=8, fontweight="bold", va="center")
        ax.text(x + w / 2, y + h / 2 - 0.2, kind, fontsize=7.5, ha="center", va="center", color="0.35",
                style="italic")
    return save(fig, name)


def main():
    apply_style()
    print(star_schema())
    print(wireframe("dash_wireframe_forecast", "Page 1: Forecast versus actual", [
        (0.4, 4.2, 11.3, 3.3, "Daily sales: actual, forecast and 95% interval", "Line chart with shaded band"),
        (12.0, 6.0, 3.6, 1.5, "MASE", "Card"),
        (12.0, 4.2, 3.6, 1.5, "Interval coverage", "Card"),
        (0.4, 0.4, 7.5, 3.5, "Error by forecast horizon", "Column chart, days 1 to 28"),
        (8.2, 0.4, 7.4, 3.5, "Forecast detail", "Table: date, actual, forecast, bounds"),
    ]))
    print(wireframe("dash_wireframe_models", "Page 2: Model comparison", [
        (0.4, 4.2, 7.5, 3.3, "Accuracy by model", "Bar chart of MASE, sorted"),
        (8.2, 4.2, 7.4, 3.3, "Error by horizon and model", "Line chart, one line style per model"),
        (0.4, 0.4, 7.5, 3.5, "Per-store MASE", "Matrix: store by model"),
        (8.2, 0.4, 3.6, 3.5, "Best model (MASE)", "Card"),
        (12.0, 0.4, 3.6, 3.5, "Coverage by model", "Bar chart"),
    ]))
    print(wireframe("dash_wireframe_planning", "Page 3: Planning", [
        (0.4, 6.0, 3.6, 1.5, "Forecast sales", "Card (28 days)"),
        (4.3, 6.0, 3.6, 1.5, "Safety stock proxy", "Card"),
        (8.2, 6.0, 3.6, 1.5, "Stock-out risk days", "Card"),
        (12.0, 6.0, 3.6, 1.5, "Overstock risk days", "Card"),
        (0.4, 0.4, 9.0, 5.3, "Weekly forecast and upper bound by store", "Clustered column chart"),
        (9.7, 0.4, 5.9, 5.3, "Bias by store", "Bar chart with zero line"),
    ]))


if __name__ == "__main__":
    main()
