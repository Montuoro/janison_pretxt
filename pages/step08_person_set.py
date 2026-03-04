"""Step 8: Generate N simulated persons."""

from dash import html, dcc, callback, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import json

from core.distribution_fitter import sample_from_distribution
from core.discrimination import apply_discrimination, DISCRIM_LEVELS
from core.person_generator import generate_response_matrix

layout = dbc.Container([
    html.H3("Step 8: Generate Simulated Persons", className="mb-3"),
    html.P("Generate a response matrix from the person distribution and item parameters."),

    dbc.Row([
        dbc.Col([
            dbc.Label("Number of Persons"),
            dbc.Input(id="input-n-persons", type="number", value=500, min=50, max=10000, step=50),
        ], md=4),
        dbc.Col([
            dbc.Label("Random Seed"),
            dbc.Input(id="input-seed", type="number", value=42),
        ], md=4),
    ], className="mb-3"),

    dbc.Button("Generate Persons & Responses", id="btn-generate", color="primary", size="lg"),

    # Progress / loading area
    dcc.Loading(
        html.Div(id="step8-results", className="mt-3"),
        type="default",
        color="#0d6efd",
    ),
], fluid=True)


@callback(
    Output("store-response-matrix", "data"),
    Output("store-abilities", "data"),
    Output("store-completed-steps", "data", allow_duplicate=True),
    Output("step8-results", "children"),
    Input("btn-generate", "n_clicks"),
    State("input-n-persons", "value"),
    State("input-seed", "value"),
    State("store-btl-results", "data"),
    State("store-person-dist", "data"),
    State("store-discrimination", "data"),
    State("store-completed-steps", "data"),
    prevent_initial_call=True,
    running=[
        (Output("btn-generate", "disabled"), True, False),
        (Output("btn-generate", "children"), "Generating...", "Generate Persons & Responses"),
    ],
)
def generate_persons(n_clicks, n_persons, seed, btl_json, dist_json, discrim_json, completed):
    if not btl_json or not dist_json:
        return no_update, no_update, no_update, dbc.Alert(
            "Complete Steps 4 and 6 first.", color="warning"
        )

    completed = completed or []
    n_persons = int(n_persons or 500)
    seed = int(seed or 42)

    items_df = pd.read_json(btl_json, orient="split")
    dist_data = json.loads(dist_json)

    # Sample abilities
    abilities = sample_from_distribution(
        dist_data["x_smooth"], dist_data["cdf_smooth"], n_persons, seed=seed
    )

    # Get difficulties
    difficulties = items_df["difficulty"].values

    # Get discriminations
    if discrim_json:
        flags = json.loads(discrim_json)
        items_df = apply_discrimination(items_df, flags)
        discriminations = items_df["discrimination"].values
    else:
        discriminations = np.ones(len(difficulties))

    # Generate responses
    resp_matrix = generate_response_matrix(abilities, difficulties, discriminations, seed=seed)
    resp_matrix.columns = items_df["item_id"].tolist()

    if 8 not in completed:
        completed = sorted(set(completed + [8]))

    # Summary stats
    mean_score = resp_matrix.sum(axis=1).mean()
    p_values = resp_matrix.mean(axis=0)

    results = html.Div([
        # Completed progress bar
        dbc.Progress(value=100, color="success", className="mb-3",
                     label="Generation Complete"),

        # Success confirmation
        dbc.Alert([
            html.I(className="bi bi-check-circle-fill me-2"),
            html.Strong("Done! "),
            f"{n_persons} persons generated across {len(difficulties)} items. "
            f"Mean score: {mean_score:.1f}, Mean ability: {abilities.mean():.2f}.",
        ], color="success", className="d-flex align-items-center"),

        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(f"{n_persons}", className="stat-value"),
                html.Div("Persons Generated", className="stat-label"),
            ]), className="stat-card"), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(f"{len(difficulties)}", className="stat-value"),
                html.Div("Items", className="stat-label"),
            ]), className="stat-card"), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(f"{mean_score:.1f}", className="stat-value"),
                html.Div("Mean Score", className="stat-label"),
            ]), className="stat-card"), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(f"{abilities.mean():.2f}", className="stat-value"),
                html.Div("Mean Ability", className="stat-label"),
            ]), className="stat-card"), md=3),
        ], className="mb-3"),

        html.H5("Item P-values (proportion correct)"),
        html.Div(
            dash_table.DataTable(
                columns=[
                    {"name": "Item", "id": "Item"},
                    {"name": "P-value", "id": "P-value"},
                    {"name": "Difficulty", "id": "Difficulty"},
                ],
                data=pd.DataFrame({
                    "Item": items_df["item_id"].values,
                    "P-value": p_values.values.round(3),
                    "Difficulty": difficulties.round(2),
                }).sort_values("P-value").to_dict("records"),
                style_table={"overflowX": "auto", "width": "320px"},
                style_cell={"padding": "4px 8px", "fontSize": "0.82rem",
                             "textAlign": "center", "whiteSpace": "nowrap"},
                style_cell_conditional=[
                    {"if": {"column_id": "Item"}, "textAlign": "left",
                     "width": "90px", "minWidth": "90px", "maxWidth": "90px"},
                    {"if": {"column_id": "P-value"}, "width": "90px",
                     "minWidth": "90px", "maxWidth": "90px"},
                    {"if": {"column_id": "Difficulty"}, "width": "90px",
                     "minWidth": "90px", "maxWidth": "90px"},
                ],
                style_header={"backgroundColor": "#e9ecef", "fontWeight": "600",
                               "textAlign": "center"},
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
                ],
                page_action="none",
                sort_action="native",
            ),
        ),
    ])

    return (
        resp_matrix.to_json(date_format="iso", orient="split"),
        json.dumps(abilities.tolist()),
        completed,
        results,
    )
