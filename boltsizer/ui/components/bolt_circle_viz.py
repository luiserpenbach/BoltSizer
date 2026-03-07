"""Plotly bolt circle visualisation component.

Draws bolts as circles on the PCD.
Critical bolt highlighted in red; others in blue.
"""
from __future__ import annotations
import math
from typing import List, Optional
import plotly.graph_objects as go


def make_bolt_circle_diagram(
    num_bolts: int,
    bolt_circle_diameter_mm: float,
    critical_bolt_index: Optional[int] = None,
    bolt_axial_forces: Optional[List[float]] = None,
    title: str = "Bolt Circle",
) -> go.Figure:
    """Create a Plotly polar scatter plot of the bolt circle.

    Args:
        num_bolts: Number of bolts.
        bolt_circle_diameter_mm: PCD [mm].
        critical_bolt_index: Index of the critical bolt (highlighted red).
        bolt_axial_forces: Axial force on each bolt [N] (used for sizing/text).
        title: Chart title.

    Returns:
        Plotly Figure.
    """
    r = bolt_circle_diameter_mm / 2.0
    angles_deg = [360.0 * i / num_bolts for i in range(num_bolts)]
    angles_rad = [math.radians(a) for a in angles_deg]

    x_bolts = [r * math.cos(a) for a in angles_rad]
    y_bolts = [r * math.sin(a) for a in angles_rad]

    colours = []
    sizes = []
    labels = []
    for i in range(num_bolts):
        is_crit = (critical_bolt_index is not None and i == critical_bolt_index)
        colours.append("#d62728" if is_crit else "#1f77b4")
        sizes.append(20 if is_crit else 14)
        if bolt_axial_forces:
            labels.append(f"Bolt {i+1}<br>{bolt_axial_forces[i]:.0f} N")
        else:
            labels.append(f"Bolt {i+1}")

    fig = go.Figure()

    # PCD circle
    theta_circle = [math.radians(a) for a in range(361)]
    fig.add_trace(go.Scatter(
        x=[r * math.cos(t) for t in theta_circle],
        y=[r * math.sin(t) for t in theta_circle],
        mode="lines",
        line=dict(color="#aaa", width=1, dash="dash"),
        name="PCD",
        hoverinfo="skip",
    ))

    # Bolt positions
    fig.add_trace(go.Scatter(
        x=x_bolts,
        y=y_bolts,
        mode="markers+text",
        marker=dict(size=sizes, color=colours, line=dict(color="white", width=1)),
        text=[str(i + 1) for i in range(num_bolts)],
        textposition="middle center",
        textfont=dict(color="white", size=9, family="Arial Black"),
        hovertext=labels,
        hoverinfo="text",
        name="Bolts",
    ))

    # Centre cross
    fig.add_trace(go.Scatter(
        x=[0], y=[0],
        mode="markers",
        marker=dict(size=6, color="#444", symbol="cross"),
        hoverinfo="skip",
        showlegend=False,
    ))

    pad = r * 1.4
    fig.update_layout(
        title=dict(text=title, font=dict(size=14)),
        xaxis=dict(range=[-pad, pad], visible=False, scaleanchor="y"),
        yaxis=dict(range=[-pad, pad], visible=False),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=300,
        width=300,
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=False,
    )

    return fig
