"""As-is charts for the deck (dataviz skill rules: one series colour, one accent, direct labels, light grid)."""
from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SERIES, ACCENT, INK, MUTED, LINE = "#2A78D6", "#EB6834", "#1E2A38", "#5B6878", "#DCE2EA"


def _style(ax, title: str) -> None:
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(LINE)
    ax.tick_params(colors=MUTED)
    ax.set_axisbelow(True)


def _prefixed(metrics: dict, prefix: str, suffix: str = "") -> list[tuple[str, float]]:
    return [(k[len(prefix):len(k) - len(suffix)], v["value"]) for k, v in metrics.items()
            if k.startswith(prefix) and k.endswith(suffix) and v["value"] is not None]


def _barh(data, title, path, fmt, accent=None):
    data = sorted(data, key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(8, 0.45 * len(data) + 1.2), dpi=150)
    ax.barh([k for k, _ in data], [v for _, v in data], color=[ACCENT if k == accent else SERIES for k, _ in data])
    top = max(v for _, v in data) or 1
    for i, (_, v) in enumerate(data):
        ax.text(v + top * 0.01, i, fmt.format(v), va="center", color=INK, fontsize=9)
    ax.set_xlim(0, top * 1.15)
    if "%" in fmt:
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.grid(axis="x", color=LINE, linewidth=0.8)
    _style(ax, title)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def demand_by_hour(metrics: dict, path: Path) -> None:
    data = sorted(_prefixed(metrics, "demand.by_hour."))
    fig, ax = plt.subplots(figsize=(8, 3.2), dpi=150)
    ax.bar([h for h, _ in data], [v for _, v in data], color=SERIES)
    ax.grid(axis="y", color=LINE, linewidth=0.8)
    ax.set_xlabel("Hour of day", color=MUTED)
    _style(ax, "Contacts by hour of day (12 months to 2026-06-17)")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def dispute_handling(metrics: dict, path: Path) -> None:
    """Three hero numbers, not a chart: different units, one message (the slide-1 problem)."""
    get = lambda k: (metrics.get(k) or {}).get("value")  # noqa: E731
    stats = [(f"{get('disputes.first_response_h_p50'):.0f} h", "median time to first response"),
             (f"{get('disputes.resolution_days_p50'):.1f} days", "median time to resolve"),
             (f"{get('disputes.backlog_share'):.0%}", "still open or in process")]
    n = (metrics.get("disputes.count") or {}).get("value")
    fig = plt.figure(figsize=(8, 2.6), dpi=150)
    fig.text(0.03, 0.88, f"Dispute handling today ({n:,} dispute complaints, 12 months to 2026-06-17)",
             color=INK, fontsize=12, fontweight="bold")
    for i, (value, label) in enumerate(stats):
        x = 0.03 + i * 0.36
        fig.text(x, 0.42, value, color=ACCENT if i == 0 else INK, fontsize=28, fontweight="bold")
        fig.text(x, 0.24, label, color=MUTED, fontsize=10)
    fig.text(0.03, 0.05, "Source: organizer data, as-is report; evidence-tagged figures only.", color=MUTED, fontsize=8)
    fig.savefig(path)
    plt.close(fig)


def render_all(metrics: dict, out_dir: Path) -> list[str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    demand_by_hour(metrics, out_dir / "asis-demand-by-hour.png")
    _barh(_prefixed(metrics, "quality.", ".fcr"), "First-contact resolution by contact reason",
          out_dir / "asis-fcr-by-reason.png", "{:.0%}", accent="Queja")  # the pain, not the solved case
    _barh(_prefixed(metrics, "demand.by_channel."), "Share of contacts by channel",
          out_dir / "asis-channel-mix.png", "{:.0%}", accent="Phone")
    dispute_handling(metrics, out_dir / "asis-dispute-handling.png")
    return ["asis-demand-by-hour.png", "asis-fcr-by-reason.png", "asis-channel-mix.png", "asis-dispute-handling.png"]
