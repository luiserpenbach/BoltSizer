"""Plotly preload waterfall chart component.

Shows: Assembly preload → −scatter loss → −embedding loss → Min preload
       → +external bolt fraction → Max bolt load.
"""
from __future__ import annotations
import plotly.graph_objects as go
from boltsizer.models.results import PreloadResult, StiffnessResult


def make_preload_waterfall(
    preload: PreloadResult,
    stiffness: StiffnessResult,
    F_ext: float,
    title: str = "Preload & Bolt Load Waterfall",
) -> go.Figure:
    """Create a Plotly waterfall chart showing the preload budget.

    Args:
        preload: Preload results.
        stiffness: Stiffness results (for phi_n).
        F_ext: External axial force on critical bolt [N].
        title: Chart title.

    Returns:
        Plotly Figure.
    """
    scatter_loss = preload.F_M_max - preload.F_M_min
    F_ext_bolt_fraction = stiffness.phi_n * max(0.0, F_ext)

    measures = ["absolute", "relative", "relative", "total", "relative", "total"]
    x = [
        "Assembly\nPreload",
        "−Scatter\nloss",
        "−Embedding\nloss",
        "Min\nPreload",
        "+External\nfraction",
        "Max\nBolt Load",
    ]
    y = [
        preload.F_M_max,
        -scatter_loss,
        -preload.F_Z,
        preload.F_preload_min,
        F_ext_bolt_fraction,
        preload.F_M_max + F_ext_bolt_fraction,
    ]

    # Colour each bar
    increasing_color = "#2ca02c"
    decreasing_color = "#d62728"
    total_color = "#1f77b4"

    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=measures,
        x=x,
        y=y,
        connector=dict(line=dict(color="#888", width=1, dash="dot")),
        increasing=dict(marker=dict(color=increasing_color)),
        decreasing=dict(marker=dict(color=decreasing_color)),
        totals=dict(marker=dict(color=total_color)),
        texttemplate="%{y:,.0f} N",
        textposition="outside",
    ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        yaxis=dict(
            title="Force [N]",
            gridcolor="#e0e0e0",
        ),
        xaxis=dict(tickfont=dict(size=11)),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=380,
        margin=dict(l=80, r=30, t=60, b=60),
        showlegend=False,
    )

    return fig
