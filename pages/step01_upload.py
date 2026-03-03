"""Step 1: Upload items (CSV/Excel)."""

from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import pandas as pd

from core.item_parser import parse_upload, load_sample_items
from components.item_table import make_item_table
from components.page_size_selector import page_size_selector, register_page_size_callback

register_page_size_callback("item-table-page-size", "item-table")

layout = dbc.Container([
    html.H3("Step 1: Upload Items", className="mb-3"),
    html.P("Upload a CSV or Excel file with your test items, or load the sample NAPLAN dataset."),

    dbc.Row([
        dbc.Col([
            dcc.Upload(
                id="upload-items",
                children=dbc.Card(
                    dbc.CardBody([
                        html.I(className="bi bi-cloud-upload fs-1 text-primary"),
                        html.P("Drag & drop or click to upload CSV/Excel", className="mt-2 mb-0"),
                        html.Small("Required columns: item_id, stem, correct_answer", className="text-muted"),
                    ], className="text-center py-4"),
                    className="border-dashed",
                    style={"border": "2px dashed #dee2e6", "cursor": "pointer"},
                ),
                multiple=False,
            ),
        ], md=8),
        dbc.Col([
            dbc.Card(dbc.CardBody([
                html.H6("Sample Data"),
                html.P("Load 35 NAPLAN Year 3 Numeracy items.", className="small text-muted"),
                dbc.Button("Load Sample", id="btn-load-sample", color="secondary", className="w-100"),
            ])),
        ], md=4),
    ], className="mb-3"),

    html.Div(id="upload-feedback"),
    html.Div([
        html.Div(id="items-preview"),
        page_size_selector("item-table-page-size", default=15),
    ], className="table-with-pager"),
], fluid=True)


@callback(
    Output("store-items", "data"),
    Output("upload-feedback", "children"),
    Output("items-preview", "children"),
    Output("store-completed-steps", "data", allow_duplicate=True),
    Input("upload-items", "contents"),
    Input("btn-load-sample", "n_clicks"),
    State("upload-items", "filename"),
    State("store-completed-steps", "data"),
    prevent_initial_call=True,
)
def handle_upload(contents, sample_clicks, filename, completed):
    from dash import ctx
    completed = completed or []

    if ctx.triggered_id == "btn-load-sample":
        df = load_sample_items()
        msg = dbc.Alert(f"Loaded {len(df)} sample NAPLAN items.", color="success")
    elif contents:
        df, error = parse_upload(contents, filename)
        if error:
            return no_update, dbc.Alert(error, color="danger"), no_update, no_update
        msg = dbc.Alert(f"Loaded {len(df)} items from {filename}.", color="success")
    else:
        return no_update, no_update, no_update, no_update

    if 1 not in completed:
        completed = sorted(set(completed + [1]))

    preview = html.Div([
        html.H5(f"{len(df)} Items Loaded", className="mt-3"),
        make_item_table(df, page_size=15),
    ])

    return df.to_json(date_format="iso", orient="split"), msg, preview, completed
