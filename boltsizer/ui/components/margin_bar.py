"""Plotly margin bar chart component.

Colour scheme (engineering theme):
  Green  #2ca02c  MS ≥ 0.25  — PASS
  Amber  #ff7f0e  0 ≤ MS < 0.25 — WARNING
  Red    #d62728  MS < 0     — FAIL
"""
from __future__ import annotations
from typing import List
import plotly.graph_objects as go
from boltsizer.models.results import MarginOfSafety


def make_margin_bar_chart(margins: List[MarginOfSafety], title: str = "Margins of Safety") -> go.Figure:
    """Create a horizontal Plotly bar chart of margins of safety.

    Each bar represents one failure mode. Bars extend left/right from MS=0.
    The binding constraint bar is outlined in black.

    Args:
        margins: List of MarginOfSafety objects (displayed in given order).
        title: Chart title.

    Returns:
        Plotly Figure.
    """
    labels = []
    values = []
    colours = []
    border_widths = []
    hover_texts = []

    for m in margins:
        v = m.value if m.value != float("inf") else 5.0
        labels.append(m.check_name)
        values.append(v)

        if m.status == "FAIL":
            colours.append("#d62728")
        elif m.status == "WARNING":
            colours.append("#ff7f0e")
        else:
            colours.append("#2ca02c")

        border_widths.append(2.0 if m.binding else 0.5)
        hover_texts.append(
            f"<b>{m.check_name}</b><br>"
            f"MS = {v:.3f}<br>"
            f"Status: {m.status}<br>"
            f"Allowable: {m.allowable:.2f} {m.unit}<br>"
            f"Applied: {m.applied:.2f} {m.unit}<br>"
            f"{'⚠ BINDING' if m.binding else ''}"
        )

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=labels,
        x=values,
        orientation="h",
        marker=dict(
            color=colours,
            line=dict(color=["black" if bw > 1 else "#888" for bw in border_widths],
                      width=border_widths),
        ),
        hovertext=hover_texts,
        hoverinfo="text",
        name="MS",
    ))

    # Reference line at MS = 0
    fig.add_vline(x=0, line_width=2, line_dash="solid", line_color="black")

    # Reference line at MS = 0.25 (warning threshold)
    fig.add_vline(x=0.25, line_width=1, line_dash="dash", line_color="#888",
                  annotation_text="Warning", annotation_position="top right",
                  annotation_font_size=10)

    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        xaxis=dict(
            title="Margin of Safety",
            zeroline=False,
            gridcolor="#e0e0e0",
            range=[min(-0.5, min(values) - 0.1), max(2.0, max(values) + 0.1)],
        ),
        yaxis=dict(autorange="reversed"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=max(250, 50 * len(margins) + 100),
        margin=dict(l=160, r=30, t=50, b=40),
        showlegend=False,
    )

    return fig
