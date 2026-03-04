"""Step 5: Item frequency ruler with hover."""

from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import pandas as pd

from components.hover_ruler import make_item_ruler

_INTERVAL_OPTIONS = [
    {"label": f"{v:.1f} logits", "value": v}
    for v in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
]

layout = dbc.Container([
    html.H3("Step 5: Item Difficulty Ruler", className="mb-3"),
    html.P("Visual distribution of item difficulties. Hover over bars to see which items fall in each bin."),

    dbc.Row([
        dbc.Col([
            html.Small("Interval:", className="text-muted me-2"),
            dcc.Dropdown(
                id="ruler-interval",
                options=_INTERVAL_OPTIONS,
                value=0.5,
                clearable=False,
                searchable=False,
                style={"width": "140px", "display": "inline-block"},
            ),
        ], width="auto", className="d-flex align-items-center"),
    ], className="mb-2"),

    dcc.Graph(id="item-ruler-chart", style={"height": "450px"}),

    dbc.Button("Continue", id="btn-step5-continue", color="primary", className="mt-3"),
    html.Div(id="step5-feedback"),
], fluid=True)


@callback(
    Output("item-ruler-chart", "figure"),
    Input("store-btl-results", "data"),
    Input("ruler-interval", "value"),
)
def update_ruler(btl_json, bin_width):
    if not btl_json:
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.update_layout(
            title="No BTL results yet — complete Step 4",
            template="plotly_white",
        )
        return fig

    bin_width = float(bin_width or 0.5)
    df = pd.read_json(btl_json, orient="split")
    return make_item_ruler(df, bin_width=bin_width)


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
