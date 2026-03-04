"""Interactive column chart with hover showing item stems per bin."""

import numpy as np
import plotly.graph_objects as go
import pandas as pd


def make_item_ruler(items_df: pd.DataFrame, difficulty_col: str = "difficulty",
                    bin_width: float = 0.5,
                    title: str = "Item Difficulty Ruler") -> go.Figure:
    """Create a bar chart of item difficulties with hover info showing items.

    Args:
        items_df: DataFrame with at least 'item_id', 'stem', and difficulty_col.
        difficulty_col: Column name for difficulty values.
        bin_width: Width of each bin in logits.
        title: Chart title.

    Returns:
        Plotly Figure.
    """
    diffs = items_df[difficulty_col].values
    lo = np.floor(np.min(diffs) / bin_width) * bin_width - bin_width
    hi = np.ceil(np.max(diffs) / bin_width) * bin_width + bin_width
    bin_edges = np.arange(lo, hi + bin_width, bin_width)
    bin_centres = (bin_edges[:-1] + bin_edges[1:]) / 2
    n_bins = len(bin_centres)

    counts = []
    hover_texts = []
    for j in range(n_bins):
        mask = (diffs >= bin_edges[j]) & (diffs < bin_edges[j + 1])
        if j == n_bins - 1:
            mask = mask | (diffs == bin_edges[j + 1])
        bin_items = items_df[mask]
        counts.append(len(bin_items))

        lines = []
        for _, row in bin_items.iterrows():
            d = row[difficulty_col]
            lines.append(f"{row['item_id']} ({d:.2f})")
        hover_text = "<br>".join(lines) if lines else "No items"
        hover_texts.append(hover_text)

    fig = go.Figure(
        go.Bar(
            x=bin_centres,
            y=counts,
            width=bin_width * 0.9,
            marker_color="#0d6efd",
            customdata=hover_texts,
            hovertemplate="<b>Range: %{x:.2f}</b><br>Count: %{y}<br><br>%{customdata}<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Difficulty (logits)",
        yaxis_title="Number of Items",
        template="plotly_white",
        hoverlabel=dict(bgcolor="white", font_size=11, align="left"),
        margin=dict(t=50, b=50),
        height=420,
    )
    return fig


def make_dual_ruler(items_df: pd.DataFrame, person_abilities: np.ndarray = None,
                    difficulty_col: str = "difficulty") -> go.Figure:
    """Item ruler with optional person distribution overlay."""
    fig = make_item_ruler(items_df, difficulty_col, title="Item & Person Distribution")

    if person_abilities is not None and len(person_abilities) > 0:
        from plotly.subplots import make_subplots
        # Overlay person histogram as a secondary trace
        fig.add_trace(
            go.Histogram(
                x=person_abilities,
                opacity=0.3,
                marker_color="#198754",
                name="Persons",
                nbinsx=20,
                yaxis="y2",
            )
        )
        fig.update_layout(
            yaxis2=dict(
                overlaying="y",
                side="right",
                title="Person Count",
                showgrid=False,
            ),
            legend=dict(x=0.01, y=0.99),
        )
        fig.data[0].name = "Items"
        fig.data[0].showlegend = True

    return fig
