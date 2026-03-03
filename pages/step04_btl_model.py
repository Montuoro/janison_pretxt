"""Step 4: Run BTL, display scale."""

from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import pandas as pd
import json

from core.btl_model import fit_btl, btl_results_to_df
from core.comparison_engine import comparisons_to_btl_data
from components.item_table import make_item_table
from components.page_size_selector import page_size_selector, register_page_size_callback

register_page_size_callback("btl-item-table-page-size", "btl-item-table")

layout = dbc.Container([
    html.H3("Step 4: BTL Model", className="mb-3"),
    html.P("Fit the Bradley-Terry-Luce model to estimate item difficulties from paired comparisons."),

    dbc.Button("Fit BTL Model", id="btn-fit-btl", color="primary", size="lg"),

    html.Div(id="btl-stats", className="mt-3"),
    html.Div([
        html.Div(id="btl-results", className="mt-1"),
        page_size_selector("btl-item-table-page-size", default=15),
    ], className="table-with-pager"),
], fluid=True)


@callback(
    Output("store-btl-results", "data"),
    Output("store-completed-steps", "data", allow_duplicate=True),
    Output("btl-stats", "children"),
    Output("btl-results", "children"),
    Input("btn-fit-btl", "n_clicks"),
    State("store-items", "data"),
    State("store-comparisons", "data"),
    State("store-completed-steps", "data"),
    prevent_initial_call=True,
)
def fit_btl_callback(n_clicks, items_json, comparisons_json, completed):
    if not items_json or not comparisons_json:
        return no_update, no_update, dbc.Alert("Complete Steps 1-3 first.", color="warning"), ""

    completed = completed or []
    items_df = pd.read_json(items_json, orient="split")
    comparisons = json.loads(comparisons_json)

    item_ids = items_df["item_id"].tolist()
    n_items = len(item_ids)

    try:
        btl_data = comparisons_to_btl_data(comparisons, item_ids)
        result = fit_btl(btl_data, n_items)
    except Exception as e:
        return no_update, no_update, dbc.Alert(f"BTL fitting error: {e}", color="danger"), ""

    result_df = btl_results_to_df(items_df, result)

    if 4 not in completed:
        completed = sorted(set(completed + [4]))

    # Stats cards
    stats = dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div(f"{result['comparisons_used']}", className="stat-value"),
            html.Div("Comparisons Used", className="stat-label"),
        ]), className="stat-card"), md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div(f"{n_items}", className="stat-value"),
            html.Div("Items Scaled", className="stat-label"),
        ]), className="stat-card"), md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div(f"{result['params'].max():.2f}", className="stat-value"),
            html.Div("Max Difficulty", className="stat-label"),
        ]), className="stat-card"), md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div(f"{result['params'].min():.2f}", className="stat-value"),
            html.Div("Min Difficulty", className="stat-label"),
        ]), className="stat-card"), md=3),
    ], className="mb-3")

    # Table
    table = html.Div([
        html.H5("Item Difficulty Estimates (ranked hardest → easiest)"),
        make_item_table(
            result_df[["rank", "item_id", "stem", "difficulty", "difficulty_se"]],
            table_id="btl-item-table",
        ),
    ])

    return result_df.to_json(date_format="iso", orient="split"), completed, stats, table
