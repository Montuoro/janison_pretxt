"""Step 3: Review/correct pairs, give Claude feedback."""

from dash import html, dcc, callback, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
from dash import dash_table
import pandas as pd
import json

from components.page_size_selector import page_size_selector, register_page_size_callback

register_page_size_callback("spot-check-page-size", "spot-check-table")

layout = dbc.Container([
    html.H3("Step 3: Spot Check", className="mb-3"),
    html.P("Review all comparisons below. The harder item is highlighted and underlined. "
           "Use the dropdown in the Harder column to change the judgement."),

    html.Div(id="spot-check-alert"),
    html.Div([
        dash_table.DataTable(
            id="spot-check-table",
            columns=[
                {"name": "#", "id": "row_num", "editable": False},
                {"name": "Item A", "id": "item_a", "editable": False},
                {"name": "Item B", "id": "item_b", "editable": False},
                {"name": "Harder", "id": "harder", "editable": True, "presentation": "dropdown"},
            ],
            data=[],
            editable=True,
            dropdown={
                "harder": {
                    "options": [
                        {"label": "A", "value": "A"},
                        {"label": "B", "value": "B"},
                    ],
                    "clearable": False,
                },
            },
            style_table={"overflowX": "auto", "overflowY": "visible"},
            style_cell={"textAlign": "left", "padding": "8px", "fontSize": "0.85rem",
                         "whiteSpace": "normal", "maxWidth": "350px"},
            style_header={"backgroundColor": "#e9ecef", "fontWeight": "600"},
            style_cell_conditional=[
                {"if": {"column_id": "row_num"}, "width": "50px", "textAlign": "center"},
                {"if": {"column_id": "harder"}, "width": "90px", "textAlign": "center",
                 "fontWeight": "bold", "fontSize": "1rem"},
            ],
            css=[{"selector": ".Select-menu-outer", "rule": "display: block !important;"}],
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
                # Harder cell — bold blue
                {"if": {"filter_query": "{harder} = 'A'", "column_id": "harder"},
                 "color": "#0d6efd", "fontWeight": "700"},
                {"if": {"filter_query": "{harder} = 'B'", "column_id": "harder"},
                 "color": "#0d6efd", "fontWeight": "700"},
                # Highlight + underline Item A when it's the harder one
                {"if": {"filter_query": "{harder} = 'A'", "column_id": "item_a"},
                 "fontWeight": "700", "color": "#0d6efd",
                 "textDecoration": "underline", "backgroundColor": "#e7f1ff"},
                # Highlight + underline Item B when it's the harder one
                {"if": {"filter_query": "{harder} = 'B'", "column_id": "item_b"},
                 "fontWeight": "700", "color": "#0d6efd",
                 "textDecoration": "underline", "backgroundColor": "#e7f1ff"},
                # Highlight changed rows
                {"if": {"filter_query": "{changed} = 'Y'"},
                 "backgroundColor": "#fff3cd"},
            ],
            page_size=25,
            sort_action="native",
            filter_action="native",
            # Hide the 'changed' and 'original' tracking columns
            hidden_columns=["changed", "original"],
        ),
        page_size_selector("spot-check-page-size", default=25),
    ], className="table-with-pager"),

    dbc.Row([
        dbc.Col([
            dbc.Button("Apply Changes & Continue", id="btn-apply-spot-check", color="primary",
                       className="me-2"),
        ]),
    ], className="mt-3"),

    html.Div(id="spot-check-feedback"),
], fluid=True)


@callback(
    Output("spot-check-table", "data"),
    Output("spot-check-table", "columns"),
    Output("spot-check-alert", "children"),
    Input("store-comparisons", "data"),
    State("store-items", "data"),
)
def populate_spot_check(comparisons_json, items_json):
    cols = [
        {"name": "#", "id": "row_num", "editable": False},
        {"name": "Item A", "id": "item_a", "editable": False},
        {"name": "Item B", "id": "item_b", "editable": False},
        {"name": "Harder", "id": "harder", "editable": True, "presentation": "dropdown"},
        {"name": "changed", "id": "changed", "editable": False, "hideable": True},
        {"name": "original", "id": "original", "editable": False, "hideable": True},
    ]
    if not comparisons_json or not items_json:
        return [], cols, dbc.Alert("Complete Step 2 first.", color="warning")

    comparisons = json.loads(comparisons_json)
    items_df = pd.read_json(items_json, orient="split")
    items_dict = {row["item_id"]: row for _, row in items_df.iterrows()}

    rows = []
    for i, comp in enumerate(comparisons):
        item_a = items_dict.get(comp["item_a_id"], {})
        item_b = items_dict.get(comp["item_b_id"], {})
        stem_a = str(item_a.get("stem", ""))[:120]
        stem_b = str(item_b.get("stem", ""))[:120]
        rows.append({
            "row_num": i + 1,
            "item_a": f"{comp['item_a_id']}: {stem_a}",
            "item_b": f"{comp['item_b_id']}: {stem_b}",
            "harder": comp["harder"],
            "original": comp["harder"],
            "changed": "N",
        })

    return rows, cols, dbc.Alert(
        f"{len(comparisons)} comparisons. The harder item is highlighted and underlined. "
        f"Use the Harder dropdown to change any judgement.",
        color="info", className="py-2",
    )


@callback(
    Output("spot-check-table", "data", allow_duplicate=True),
    Input("spot-check-table", "data_timestamp"),
    State("spot-check-table", "data"),
    prevent_initial_call=True,
)
def mark_changed_rows(timestamp, rows):
    """Track which rows the user has edited and validate input."""
    if not rows:
        return no_update
    changed = False
    for row in rows:
        # Validate: only allow A or B
        val = str(row.get("harder", "")).strip().upper()
        if val not in ("A", "B"):
            val = row.get("original", "A")
        if val != row.get("harder"):
            row["harder"] = val
            changed = True
        row["changed"] = "Y" if val != row.get("original") else "N"
    if changed or any(r.get("changed") == "Y" for r in rows):
        return rows
    return no_update


@callback(
    Output("store-comparisons", "data", allow_duplicate=True),
    Output("store-completed-steps", "data", allow_duplicate=True),
    Output("spot-check-feedback", "children"),
    Input("btn-apply-spot-check", "n_clicks"),
    State("spot-check-table", "data"),
    State("store-comparisons", "data"),
    State("store-completed-steps", "data"),
    prevent_initial_call=True,
)
def apply_spot_checks(n_clicks, table_data, comparisons_json, completed):
    if not comparisons_json or not table_data:
        return no_update, no_update, no_update

    comparisons = json.loads(comparisons_json)
    completed = completed or []
    changes = 0

    for row in table_data:
        idx = row["row_num"] - 1
        val = str(row.get("harder", "")).strip().upper()
        if val in ("A", "B") and idx < len(comparisons) and comparisons[idx]["harder"] != val:
            comparisons[idx]["harder"] = val
            comparisons[idx]["reasoning"] = "Manually corrected by user"
            changes += 1

    if 3 not in completed:
        completed = sorted(set(completed + [3]))

    return (
        json.dumps(comparisons),
        completed,
        dbc.Alert(f"Applied {changes} change(s). Ready to proceed.", color="success"),
    )
