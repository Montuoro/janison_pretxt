"""Reusable item display table."""

from dash import html, dash_table
import pandas as pd


def make_item_table(df: pd.DataFrame, table_id: str = "item-table", page_size: int = 15) -> dash_table.DataTable:
    """Create a DataTable from a DataFrame of items.

    NOTE: The page-size selector dropdown should be placed in the static layout
    of the page, not inside this function. Use page_size_selector() in the layout
    and register_page_size_callback() at module level.
    """
    display_cols = [c for c in df.columns if not c.startswith("_")]
    return dash_table.DataTable(
        id=table_id,
        columns=[{"name": c.replace("_", " ").title(), "id": c} for c in display_cols],
        data=df[display_cols].to_dict("records"),
        page_size=page_size,
        style_table={"overflowX": "auto"},
        style_cell={
            "textAlign": "left",
            "padding": "8px",
            "fontSize": "0.85rem",
            "whiteSpace": "normal",
            "maxWidth": "300px",
        },
        style_header={
            "backgroundColor": "#e9ecef",
            "fontWeight": "600",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
        ],
    )
