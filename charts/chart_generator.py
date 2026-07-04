"""Minimalist black-and-white reward charts rendered to PNG bytes.

Design: white background, black lines, black markers, readable labels, PNG
output. Matplotlib uses the head-less ``Agg`` backend so charts render on a
server with no display.
"""

from __future__ import annotations

import io
from datetime import date
from typing import Sequence

import matplotlib

matplotlib.use("Agg")  # must be set before importing pyplot

import matplotlib.pyplot as plt  # noqa: E402  (after backend selection)

from utils.dates import format_epoch_date
from utils.logging_config import get_logger

logger = get_logger(__name__)


def generate_reward_chart(
    title: str,
    epoch_dates: Sequence[date],
    values: Sequence[float],
) -> bytes:
    """Render a black & white line chart of CYS rewards over epochs.

    Returns PNG image bytes ready to send to Telegram.
    """
    labels = [format_epoch_date(d) for d in epoch_dates]
    # Plot against numeric x positions (not the date strings). Categorical
    # string x-values make annotate() trigger unit conversion that fails on
    # matplotlib 3.9 + NumPy 2.x ("only 0-dimensional arrays can be converted
    # to Python scalars"). Numeric positions + tick labels avoid that entirely.
    positions = list(range(len(labels)))
    y_values = [float(v) for v in values]

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.plot(
        positions,
        y_values,
        color="black",
        linewidth=1.5,
        marker="o",
        markersize=5,
        markerfacecolor="black",
        markeredgecolor="black",
    )

    # Value annotations for readability.
    for x_pos, y in zip(positions, y_values):
        ax.annotate(
            f"{y:.2f}",
            xy=(x_pos, y),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color="black",
        )

    ax.set_title(title, color="black", fontsize=13, fontweight="bold")
    ax.set_xlabel("Epoch Date", color="black", fontsize=11)
    ax.set_ylabel("CYS Reward", color="black", fontsize=11)

    # Monochrome styling.
    ax.tick_params(axis="both", colors="black")
    for spine in ax.spines.values():
        spine.set_color("black")
    ax.grid(True, color="black", alpha=0.15, linewidth=0.6)
    ax.margins(y=0.15)

    # Attach the epoch-date strings as tick labels on the numeric x-axis.
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=150, facecolor="white")
    plt.close(fig)
    buffer.seek(0)
    logger.debug("Generated chart '%s' with %d points", title, len(y_values))
    return buffer.getvalue()
