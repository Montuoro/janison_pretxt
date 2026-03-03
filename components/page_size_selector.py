"""Reusable page-size selector for DataTables.

Renders a compact dropdown positioned at the bottom-right of the table's
pagination area.  Wrap the table and selector together inside a div with
className="table-with-pager" so the CSS can position them.
"""

from dash import html, dcc, callback, Input, Output

PAGE_SIZE_OPTIONS = [
    {"label": "15 rows", "value": 15},
    {"label": "25 rows", "value": 25},
    {"label": "50 rows", "value": 50},
    {"label": "All", "value": 9999},
]


def page_size_selector(selector_id: str, default: int = 15):
    """Return a compact inline dropdown for choosing page size.

    Place this AFTER the DataTable it controls, inside a common parent
    with className="table-with-pager".
    """
    return html.Div([
        html.Small("Show: ", className="text-muted me-1"),
        dcc.Dropdown(
            id=selector_id,
            options=PAGE_SIZE_OPTIONS,
            value=default,
            clearable=False,
            searchable=False,
            style={"width": "120px"},
        ),
    ], className="table-page-size-selector")


def register_page_size_callback(selector_id: str, table_id: str):
    """Register a callback that wires a selector to a DataTable's page_size."""
    @callback(
        Output(table_id, "page_size"),
        Input(selector_id, "value"),
    )
    def _update_page_size(value):
        return int(value) if value else 15
