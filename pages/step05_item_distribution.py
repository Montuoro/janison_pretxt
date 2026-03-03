"""Step 5: Item frequency ruler with hover."""

from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import pandas as pd

from components.hover_ruler import make_item_ruler

layout = dbc.Container([
    html.H3("Step 5: Item Difficulty Ruler", className="mb-3"),
    html.P("Visual distribution of item difficulties. Hover over bars to see which items fall in each bin."),

    dcc.Graph(id="item-ruler-chart", style={"height": "450px"}),

    dbc.Button("Continue", id="btn-step5-continue", color="primary", className="mt-3"),
    html.Div(id="step5-feedback"),
], fluid=True)


@callback(
    Output("item-ruler-chart", "figure"),
    Input("store-btl-results", "data"),
)
def update_ruler(btl_json):
    if not btl_json:
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.update_layout(
            title="No BTL results yet — complete Step 4",
            template="plotly_white",
        )
        return fig

    df = pd.read_json(btl_json, orient="split")
    return make_item_ruler(df)


@callback(
    Output("store-completed-steps", "data", allow_duplicate=True),
    Output("step5-feedback", "children"),
    Input("btn-step5-continue", "n_clicks"),
    State("store-btl-results", "data"),
    State("store-completed-steps", "data"),
    prevent_initial_call=True,
)
def step5_continue(n_clicks, btl_json, completed):
    if not btl_json:
        return no_update, dbc.Alert("Complete Step 4 first.", color="warning")
    completed = completed or []
    if 5 not in completed:
        completed = sorted(set(completed + [5]))
    return completed, ""
