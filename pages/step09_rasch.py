"""Step 9: Run TAM via R subprocess."""

from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import pandas as pd
import json

from core.rasch_runner import run_tam_analysis

layout = dbc.Container([
    html.H3("Step 9: Rasch Analysis (TAM)", className="mb-3"),
    html.P("Run the TAM Rasch model on the simulated response data via R."),

    dbc.Alert(
        "This step calls R/TAM via subprocess. Ensure R and the TAM package are installed.",
        color="info",
    ),

    dbc.Button("Run Rasch Analysis", id="btn-run-rasch", color="primary", size="lg"),

    dcc.Loading(
        html.Div(id="rasch-results", className="mt-3"),
        type="circle",
    ),
], fluid=True)


@callback(
    Output("store-tam-results", "data"),
    Output("store-completed-steps", "data", allow_duplicate=True),
    Output("rasch-results", "children"),
    Input("btn-run-rasch", "n_clicks"),
    State("store-response-matrix", "data"),
    State("store-completed-steps", "data"),
    prevent_initial_call=True,
    running=[
        (Output("btn-run-rasch", "disabled"), True, False),
    ],
)
def run_rasch(n_clicks, resp_json, completed):
    if not resp_json:
        return no_update, no_update, dbc.Alert("Complete Step 8 first.", color="warning")

    completed = completed or []
    resp_df = pd.read_json(resp_json, orient="split")

    try:
        tam_results = run_tam_analysis(resp_df, item_ids=resp_df.columns.tolist())
    except FileNotFoundError as e:
        return no_update, no_update, dbc.Alert(f"R not found: {e}", color="danger")
    except RuntimeError as e:
        return no_update, no_update, dbc.Alert(f"R error: {e}", color="danger")
    except Exception as e:
        return no_update, no_update, dbc.Alert(f"Error: {e}", color="danger")

    if 9 not in completed:
        completed = sorted(set(completed + [9]))

    # Display summary
    rel = tam_results.get("reliability", {})
    n_items = tam_results.get("n_items", 0)
    n_persons = tam_results.get("n_persons", 0)

    results = html.Div([
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(f"{n_items}", className="stat-value"),
                html.Div("Items Calibrated", className="stat-label"),
            ]), className="stat-card"), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(f"{n_persons}", className="stat-value"),
                html.Div("Persons", className="stat-label"),
            ]), className="stat-card"), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(f"{rel.get('cronbach_alpha', 0):.3f}", className="stat-value"),
                html.Div("Cronbach's Alpha", className="stat-label"),
            ]), className="stat-card"), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(f"{rel.get('wle_rel', 0):.3f}", className="stat-value"),
                html.Div("WLE Reliability", className="stat-label"),
            ]), className="stat-card"), md=3),
        ], className="mb-3"),

        dbc.Alert("Rasch analysis complete! Proceed to Reports.", color="success"),
    ])

    return json.dumps(tam_results), completed, results
