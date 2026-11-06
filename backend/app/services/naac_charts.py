"""Charts for the NAAC report as PNG bytes (matplotlib, Agg backend, CPU only).

They follow docs/DESIGN.md: the sentiment trio (blue / grey / red, never red-green) with text
labels on every segment, one hue for a single series, no gridline clutter, values written on
the bars. Light theme only: the report is printed and read as a document.
"""

import io
import threading
from typing import Any

from app.feedback_spec import ASPECT_KEYS, ASPECT_LABELS, CURRICULUM_KEYS, CURRICULUM_LABELS

SENTIMENT = [
    ("negative", "Negative", "#e34948"),
    ("neutral", "Neutral", "#8a8a8a"),
    ("positive", "Positive", "#2a78d6"),
]
MAIN = "#1d5fbf"
INK = "#16181b"
MUTED = "#535960"
DPI = 200
LOCK = threading.Lock()  # pyplot isn't thread-safe, and two exports may run together


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.edgecolor": "#cfd4db",
            "axes.labelcolor": MUTED,
            "xtick.color": MUTED,
            "ytick.color": INK,
        }
    )
    return plt


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, bbox_inches="tight", facecolor="white")
    import matplotlib.pyplot as plt

    plt.close(fig)
    return buf.getvalue()


def _bare(ax) -> None:
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)


def sentiment_split(rows: list[tuple[str, dict[str, float]]]) -> bytes:
    """100% horizontal bars, one per department (and the institution), labelled segments."""
    plt = _plt()
    rows = [(name, s) for name, s in rows if s and sum(s.values())]
    fig, ax = plt.subplots(figsize=(6.6, 0.5 * len(rows) + 0.9))
    for i, (_, s) in enumerate(rows):
        total = sum(s.values())
        left = 0.0
        for key, _label, color in SENTIMENT:
            share = s.get(key, 0) / total
            ax.barh(i, share, left=left, color=color, height=0.55, edgecolor="white", linewidth=1.5)
            if share >= 0.07:
                ax.text(
                    left + share / 2,
                    i,
                    f"{share:.0%}",
                    ha="center",
                    va="center",
                    color="white" if key != "neutral" else INK,
                    fontsize=8,
                )
            left += share
    ax.set_yticks(range(len(rows)), [name for name, _ in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    _bare(ax)
    ax.spines["bottom"].set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in SENTIMENT]
    ax.legend(
        handles,
        [label for _, label, _ in SENTIMENT],
        ncol=3,
        frameon=False,
        loc="upper left",
        bbox_to_anchor=(0, -0.02),
        fontsize=8,
    )
    return _png(fig)


def mean_ratings(means: dict[str, float | None], kind: str = "teaching") -> bytes:
    """One hue, one bar per aspect (or curriculum item), the value written at the end."""
    plt = _plt()
    keys = ASPECT_KEYS if kind == "teaching" else CURRICULUM_KEYS
    labels = ASPECT_LABELS if kind == "teaching" else CURRICULUM_LABELS
    rows = [(labels[k], means.get(k)) for k in keys if means.get(k) is not None]
    fig, ax = plt.subplots(figsize=(6.6, 0.32 * len(rows) + 0.6))
    for i, (_, value) in enumerate(rows):
        ax.barh(i, value - 1, left=1, color=MAIN, height=0.6)
        ax.text(value + 0.05, i, f"{value:.1f}", va="center", color=INK, fontsize=8)
    ax.set_yticks(range(len(rows)), [label for label, _ in rows])
    ax.invert_yaxis()
    ax.set_xlim(1, 5.4)
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_xlabel("Mean rating (1 = Poor, 5 = Excellent)")
    _bare(ax)
    return _png(fig)


def all_charts(data: dict[str, Any]) -> dict[str, bytes]:
    charts = {
        "sentiment": sentiment_split(
            [("All departments", data["totals"]["sentiment"])]
            + [(d["name"], d["sentiment"]) for d in data["departments"]]
        )
    }
    for d in data["departments"]:
        if any(v is not None for v in d["aspect_means"].values()):
            charts[f"aspects:{d['code']}"] = mean_ratings(d["aspect_means"], "teaching")
        if any(v is not None for v in d["curriculum"]["means"].values()):
            charts[f"curriculum:{d['code']}"] = mean_ratings(d["curriculum"]["means"], "curriculum")
    return charts
