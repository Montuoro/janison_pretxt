"""Step 7: Flag low discrimination items (optional)."""

from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from dash import dash_table
import pandas as pd
import json

from core.discrimination import DISCRIM_LEVELS
from components.page_size_selector import page_size_selector, register_page_size_callback

_VALID_LEVELS = list(DISCRIM_LEVELS.keys())  # Normal, Slightly Low, Low, Very Low

_COLUMNS = [
    {"name": "Item ID", "id": "item_id", "editable": False},
    {"name": "Stem", "id": "stem", "editable": False},
    {"name": "Difficulty", "id": "difficulty", "editable": False},
    {"name": "Discrimination", "id": "discrimination", "editable": True,
     "presentation": "dropdown"},
]

layout = dbc.Container([
    html.H3("Step 7: Discrimination Flags", className="mb-3"),
    html.P("Optionally flag items with suspected low discrimination. "
           "Use the Discrimination dropdown to change the level. "
           "Leave as 'Normal' if unsure."),

    html.Div(id="discrim-table-alert"),
    html.Div([
        dash_table.DataTable(
            id="discrim-datatable",
            columns=_COLUMNS,
            data=[],
            editable=True,
            dropdown={
                "discrimination": {
                    "options": [{"label": lv, "value": lv} for lv in _VALID_LEVELS],
                },
            },
            style_table={"overflowX": "auto", "overflowY": "visible",
                          "tableLayout": "auto"},
            style_cell={"textAlign": "center", "padding": "6px 8px", "fontSize": "0.82rem",
                         "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis"},
            style_header={"backgroundColor": "#e9ecef", "fontWeight": "600",
                           "textAlign": "center"},
            style_cell_conditional=[
                {"if": {"column_id": "item_id"}, "textAlign": "left",
                 "width": "80px", "minWidth": "80px", "maxWidth": "80px"},
                {"if": {"column_id": "stem"}, "textAlign": "left",
                 "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis"},
                {"if": {"column_id": "difficulty"}, "width": "80px",
                 "minWidth": "80px", "maxWidth": "80px"},
                {"if": {"column_id": "discrimination"}, "fontWeight": "bold",
                 "width": "140px", "minWidth": "140px", "maxWidth": "140px"},
            ],
            css=[{"selector": ".Select-menu-outer", "rule": "display: block !important;"}],
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
                {"if": {"filter_query": "{discrimination} = 'Slightly Low'", "column_id": "discrimination"},
                 "color": "#e67e00", "fontWeight": "700"},
                {"if": {"filter_query": "{discrimination} = 'Low'", "column_id": "discrimination"},
                 "color": "#b35900", "fontWeight": "700"},
                {"if": {"filter_query": "{discrimination} = 'Very Low'", "column_id": "discrimination"},
                 "color": "#7a3d00", "fontWeight": "700", "backgroundColor": "#ffecd2"},
            ],
            page_action="none",
        ),
    ]),

    # Quick-set buttons for bulk operations
    dbc.Row([
        dbc.Col([
            html.Small("Quick set selected: ", className="text-muted me-2"),
            dbc.ButtonGroup([
                dbc.Button(level, id=f"btn-discrim-{level.lower().replace(' ', '-')}",
                           color="outline-secondary", size="sm")
                for level in _VALID_LEVELS
            ]),
        ]),
    ], className="mt-2 mb-3"),

    dbc.Button("Save & Continue", id="btn-save-discrim", color="primary", className="mt-3"),
    html.Div(id="step7-feedback"),
    html.Div(id="discrim-table-container", style={"display": "none"}),
], fluid=True)

register_page_size_callback("discrim-page-size", "discrim-datatable")


@callback(
    Output("discrim-datatable", "data"),
    Output("discrim-table-alert", "children"),
    Input("store-btl-results", "data"),
)
def populate_discrim_table(btl_json):
    if not btl_json:
        return [], dbc.Alert("Complete Step 4 first.", color="warning")

    df = pd.read_json(btl_json, orient="split")

    table_data = df[["item_id", "stem", "difficulty"]].copy()
    table_data["discrimination"] = "Normal"
    table_data["difficulty"] = table_data["difficulty"].round(2)
    table_data["stem"] = table_data["stem"].str[:80]

    return table_data.to_dict("records"), ""


# Quick-set buttons
@callback(
    Output("discrim-datatable", "data", allow_duplicate=True),
    [Input(f"btn-discrim-{level.lower().replace(' ', '-')}", "n_clicks")
     for level in _VALID_LEVELS],
    State("discrim-datatable", "data"),
    State("discrim-datatable", "selected_rows"),
    prevent_initial_call=True,
)
def quick_set_discrimination(*args):
    n_clicks_list = args[:len(_VALID_LEVELS)]
    data = args[len(_VALID_LEVELS)]
    selected = args[len(_VALID_LEVELS) + 1]

    if not data:
        return no_update

    from dash import ctx as _ctx
    triggered = _ctx.triggered_id
    if not triggered:
        return no_update

    # Find which level was clicked
    level = None
    for lv in _VALID_LEVELS:
        if triggered == f"btn-discrim-{lv.lower().replace(' ', '-')}":
            level = lv
            break
    if not level:
        return no_update

    # Apply to selected rows, or all if none selected
    if selected:
        for idx in selected:
            if idx < len(data):
                data[idx]["discrimination"] = level
    else:
        for row in data:
            row["discrimination"] = level

    return data


@callback(
    Output("discrim-datatable", "data", allow_duplicate=True),
    Input("discrim-datatable", "data_timestamp"),
    State("discrim-datatable", "data"),
    prevent_initial_call=True,
)
def validate_discrimination(timestamp, data):
    """Validate manually typed discrimination values."""
    if not data:
        return no_update
    changed = False
    for row in data:
        val = row.get("discrimination", "Normal")
        if val not in _VALID_LEVELS:
            # Try case-insensitive match
            matched = False
            for lv in _VALID_LEVELS:
                if val.strip().lower() == lv.lower():
                    row["discrimination"] = lv
                    matched = True
                    changed = True
                    break
            if not matched:
                row["discrimination"] = "Normal"
                changed = True
    if changed:
        return data
    return no_update


@callback(
    Output("store-discrimination", "data"),
    Output("store-completed-steps", "data", allow_duplicate=True),
    Output("step7-feedback", "children"),
    Input("btn-save-discrim", "n_clicks"),
    State("discrim-datatable", "data"),
    State("store-completed-steps", "data"),
    prevent_initial_call=True,
)
def save_discrimination(n_clicks, table_data, completed):
    if not table_data:
        return no_update, no_update, no_update

    completed = completed or []
    flags = {row["item_id"]: row.get("discrimination", "Normal") for row in table_data}

    flagged = sum(1 for v in flags.values() if v != "Normal")
    if 7 not in completed:
        completed = sorted(set(completed + [7]))

    return json.dumps(flags), completed, dbc.Alert(
        f"Saved. {flagged} item(s) flagged with non-normal discrimination.", color="success"
    )
