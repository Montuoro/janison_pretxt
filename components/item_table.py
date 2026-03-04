"""Reusable item display table."""

from dash import html, dash_table
import pandas as pd


# Columns that should be left-aligned (text-heavy)
_LEFT_ALIGN_COLS = {"item_id", "stem"}

# Columns to hide from display
_HIDDEN_COLS = {"max_score"}

# Custom column header labels
_COL_LABELS = {
    "n_comparisons": "# Comp",
    "n_selected": "# Selected",
    "obs_proportion": "Obs Prop",
    "outfit": "Outfit",
    "chi_sq": "Chi Sq",
    "item_df": "DF",
    "difficulty": "Estimated",
    "difficulty_se": "Std Error",
}

# Narrow columns that don't need much width
_NARROW_COLS = {"correct_answer": "90px", "item_type": "80px",
                "option_a": "80px", "option_b": "80px",
                "option_c": "80px", "option_d": "80px",
                "item_id": "80px",
                "rank": "55px", "difficulty": "90px", "difficulty_se": "90px",
                "n_comparisons": "80px", "n_selected": "80px",
                "obs_proportion": "80px",
                "outfit": "70px", "chi_sq": "80px", "item_df": "55px"}


def make_item_table(df: pd.DataFrame, table_id: str = "item-table", page_size: int = 15) -> dash_table.DataTable:
    """Create a DataTable from a DataFrame of items.

    NOTE: The page-size selector dropdown should be placed in the static layout
    of the page, not inside this function. Use page_size_selector() in the layout
    and register_page_size_callback() at module level.
    """
    display_cols = [c for c in df.columns
                    if not c.startswith("_") and c not in _HIDDEN_COLS]

    # Column width + alignment overrides
    style_cell_conditional = []
    for col in display_cols:
        cond = {"if": {"column_id": col}}
        if col in _LEFT_ALIGN_COLS:
            cond["textAlign"] = "left"
        else:
            cond["textAlign"] = "center"
        if col in _NARROW_COLS:
            w = _NARROW_COLS[col]
            cond["width"] = w
            cond["minWidth"] = w
            cond["maxWidth"] = w
        if col == "stem":
            cond["maxWidth"] = "250px"
            cond["whiteSpace"] = "normal"
        style_cell_conditional.append(cond)

    return dash_table.DataTable(
        id=table_id,
        columns=[{"name": _COL_LABELS.get(c, c.replace("_", " ").title()), "id": c}
                 for c in display_cols],
        data=df[display_cols].to_dict("records"),
        page_action="none",
        style_table={"overflowX": "auto"},
        style_cell={
            "padding": "6px 8px",
            "fontSize": "0.82rem",
            "whiteSpace": "nowrap",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
        },
        style_header={
            "backgroundColor": "#e9ecef",
            "fontWeight": "600",
            "textAlign": "center",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
        ],
        style_cell_conditional=style_cell_conditional,
    )
