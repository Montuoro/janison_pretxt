"""Step 10: Reports — Wright map, fit, Guttman, gaps."""

from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from dash import dash_table
import pandas as pd
import numpy as np
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.report_builder import (
    build_item_params_table, identify_misfit_items, find_gaps, guttman_scalogram,
)
from components.page_size_selector import page_size_selector, register_page_size_callback

# Pre-register page-size callbacks for dynamically created tables
register_page_size_callback("report-params-page-size", "report-params-table")
register_page_size_callback("report-guttman-page-size", "report-guttman-table")

layout = dbc.Container([
    html.H3("Step 10: Reports", className="mb-3"),

    dbc.Tabs([
        dbc.Tab(label="Item Parameters", tab_id="tab-params"),
        dbc.Tab(label="Wright Map", tab_id="tab-wright"),
        dbc.Tab(label="Test Statistics", tab_id="tab-stats"),
        dbc.Tab(label="Gap Analysis", tab_id="tab-gaps"),
        dbc.Tab(label="Guttman Patterns", tab_id="tab-guttman"),
        dbc.Tab(label="Export", tab_id="tab-export"),
    ], id="report-tabs", active_tab="tab-params"),

    html.Div([
        html.Div(id="report-tab-content", className="report-tab-content"),

        # Page-size selectors (always in DOM; visibility toggled by tab callback)
        html.Div(id="report-params-page-size-container", children=[
            page_size_selector("report-params-page-size", default=15),
        ], style={"display": "none"}),
        html.Div(id="report-guttman-page-size-container", children=[
            page_size_selector("report-guttman-page-size", default=15),
        ], style={"display": "none"}),
    ], className="table-with-pager"),
], fluid=True)


@callback(
    Output("report-tab-content", "children"),
    Output("store-completed-steps", "data", allow_duplicate=True),
    Output("report-params-page-size-container", "style"),
    Output("report-guttman-page-size-container", "style"),
    Input("report-tabs", "active_tab"),
    State("store-btl-results", "data"),
    State("store-tam-results", "data"),
    State("store-abilities", "data"),
    State("store-response-matrix", "data"),
    State("store-discrimination", "data"),
    State("store-completed-steps", "data"),
    prevent_initial_call=True,
)
def render_report_tab(tab, btl_json, tam_json, abilities_json, resp_json, discrim_json, completed):
    completed = completed or []
    if 10 not in completed:
        completed = sorted(set(completed + [10]))

    hide = {"display": "none"}
    show = {"display": "block"}
    params_vis = show if tab == "tab-params" else hide
    guttman_vis = show if tab == "tab-guttman" else hide

    if not btl_json:
        return dbc.Alert("Complete earlier steps first.", color="warning"), completed, hide, hide

    items_df = pd.read_json(btl_json, orient="split")
    tam_results = json.loads(tam_json) if tam_json else None
    abilities = np.array(json.loads(abilities_json)) if abilities_json else None
    resp_df = pd.read_json(resp_json, orient="split") if resp_json else None

    if discrim_json:
        from core.discrimination import apply_discrimination
        flags = json.loads(discrim_json)
        items_df = apply_discrimination(items_df, flags)

    if tab == "tab-params":
        return _render_params(items_df, tam_results), completed, params_vis, guttman_vis
    elif tab == "tab-wright":
        return _render_wright(items_df, tam_results, abilities), completed, params_vis, guttman_vis
    elif tab == "tab-stats":
        return _render_stats(tam_results), completed, params_vis, guttman_vis
    elif tab == "tab-gaps":
        return _render_gaps(items_df, abilities), completed, params_vis, guttman_vis
    elif tab == "tab-guttman":
        return _render_guttman(resp_df, abilities, items_df), completed, params_vis, guttman_vis
    elif tab == "tab-export":
        return _render_export(items_df, tam_results), completed, params_vis, guttman_vis

    return html.Div(), completed


def _render_params(items_df, tam_results):
    params_df = build_item_params_table(items_df, tam_results)
    params_df = identify_misfit_items(params_df)

    # Color-code misfit
    style_conditions = []
    if "infit" in params_df.columns:
        style_conditions.extend([
            {"if": {"filter_query": "{infit} > 1.3", "column_id": "infit"},
             "backgroundColor": "#f8d7da"},
            {"if": {"filter_query": "{infit} < 0.7", "column_id": "infit"},
             "backgroundColor": "#f8d7da"},
            {"if": {"filter_query": "{outfit} > 1.3", "column_id": "outfit"},
             "backgroundColor": "#f8d7da"},
            {"if": {"filter_query": "{outfit} < 0.7", "column_id": "outfit"},
             "backgroundColor": "#f8d7da"},
        ])

    # Round numeric columns
    for col in ["btl_difficulty", "btl_se", "rasch_difficulty", "rasch_se", "infit", "outfit",
                "infit_t", "outfit_t", "discrimination"]:
        if col in params_df.columns:
            params_df[col] = pd.to_numeric(params_df[col], errors="coerce").round(3)

    display_cols = [c for c in params_df.columns if c not in ("misfit",)]

    return html.Div([
        html.H5("Item Parameters"),
        dash_table.DataTable(
            id="report-params-table",
            columns=[{"name": c.replace("_", " ").title(), "id": c} for c in display_cols],
            data=params_df[display_cols].to_dict("records"),
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "6px", "fontSize": "0.8rem"},
            style_header={"backgroundColor": "#e9ecef", "fontWeight": "600"},
            style_data_conditional=style_conditions,
            page_size=15,
            sort_action="native",
            filter_action="native",
        ),
    ])


def _render_wright(items_df, tam_results, abilities):
    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.5, 0.5],
        shared_yaxes=True,
        horizontal_spacing=0.02,
    )

    # Use Rasch difficulties if available, else BTL
    if tam_results and "item_params" in tam_results:
        item_diffs = [p["xsi"] for p in tam_results["item_params"]]
    else:
        item_diffs = items_df["difficulty"].values.tolist()

    # Person histogram (left side, mirrored)
    if abilities is not None and len(abilities) > 0:
        fig.add_trace(
            go.Histogram(
                y=abilities,
                nbinsy=25,
                marker_color="#198754",
                opacity=0.7,
                name="Persons",
            ),
            row=1, col=1,
        )
        fig.update_xaxes(autorange="reversed", title_text="Person Count", row=1, col=1)

    # Item markers (right side)
    fig.add_trace(
        go.Scatter(
            x=[0.5] * len(item_diffs),
            y=item_diffs,
            mode="markers+text",
            marker=dict(size=10, color="#0d6efd", symbol="diamond"),
            text=items_df["item_id"].values,
            textposition="middle right",
            textfont=dict(size=8),
            name="Items",
        ),
        row=1, col=2,
    )

    fig.update_xaxes(visible=False, row=1, col=2)
    fig.update_yaxes(title_text="Logit Scale", row=1, col=1)

    fig.update_layout(
        title="Wright Map",
        template="plotly_white",
        height=600,
        showlegend=True,
    )

    return html.Div([
        html.H5("Wright Map"),
        dcc.Graph(figure=fig),
    ])


def _render_stats(tam_results):
    if not tam_results:
        return dbc.Alert("Run Rasch analysis in Step 9 first.", color="warning")

    rel = tam_results.get("reliability", {})

    return html.Div([
        html.H5("Test Statistics"),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(f"{rel.get('cronbach_alpha', 0):.3f}", className="stat-value"),
                html.Div("Cronbach's Alpha", className="stat-label"),
            ]), className="stat-card"), md=4),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(f"{rel.get('wle_rel', 0):.3f}", className="stat-value"),
                html.Div("WLE PSI Reliability", className="stat-label"),
            ]), className="stat-card"), md=4),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(f"{rel.get('eap_rel', 0):.3f}", className="stat-value"),
                html.Div("EAP Reliability", className="stat-label"),
            ]), className="stat-card"), md=4),
        ]),
        html.Hr(),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(f"{tam_results.get('n_items', 0)}", className="stat-value"),
                html.Div("Items", className="stat-label"),
            ]), className="stat-card"), md=6),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(f"{tam_results.get('n_persons', 0)}", className="stat-value"),
                html.Div("Persons", className="stat-label"),
            ]), className="stat-card"), md=6),
        ]),
    ])


def _render_gaps(items_df, abilities):
    item_diffs = items_df["difficulty"].values

    fig = go.Figure()

    # Item distribution
    fig.add_trace(go.Histogram(
        x=item_diffs,
        nbinsx=15,
        marker_color="#0d6efd",
        opacity=0.6,
        name="Items",
    ))

    if abilities is not None:
        fig.add_trace(go.Histogram(
            x=abilities,
            nbinsx=25,
            marker_color="#198754",
            opacity=0.4,
            name="Persons",
            yaxis="y2",
        ))
        fig.update_layout(
            yaxis2=dict(overlaying="y", side="right", title="Person Count", showgrid=False),
        )

    fig.update_layout(
        title="Item & Person Distribution Overlap",
        xaxis_title="Logit Scale",
        yaxis_title="Item Count",
        template="plotly_white",
        barmode="overlay",
        height=400,
    )

    gaps_list = []
    if abilities is not None:
        gaps_list = find_gaps(item_diffs, abilities)

    gap_content = []
    if gaps_list:
        gap_content.append(html.H6(f"{len(gaps_list)} gap(s) identified:"))
        for g in gaps_list:
            gap_content.append(dbc.Alert(g["description"], color="warning", className="py-1"))
    else:
        gap_content.append(dbc.Alert("No significant gaps detected.", color="success"))

    return html.Div([
        html.H5("Gap Analysis"),
        dcc.Graph(figure=fig),
        html.Div(gap_content, className="mt-3"),
    ])


def _render_guttman(resp_df, abilities, items_df):
    if resp_df is None or abilities is None:
        return dbc.Alert("Generate response data first (Step 8).", color="warning")

    difficulties = items_df["difficulty"].values
    scalogram = guttman_scalogram(resp_df, abilities, difficulties, n_show=20)

    return html.Div([
        html.H5("Most Aberrant Guttman Patterns"),
        html.P("Response patterns sorted by aberrance (number of Guttman inversions). "
               "Items sorted easiest→hardest.", className="text-muted"),
        dash_table.DataTable(
            id="report-guttman-table",
            columns=[
                {"name": "Person", "id": "person"},
                {"name": "Ability", "id": "ability"},
                {"name": "Score", "id": "score"},
                {"name": "Aberrance", "id": "aberrance"},
                {"name": "Pattern (easy→hard)", "id": "pattern"},
            ],
            data=scalogram.to_dict("records"),
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center", "padding": "6px", "fontSize": "0.8rem",
                         "fontFamily": "monospace"},
            style_header={"backgroundColor": "#e9ecef", "fontWeight": "600"},
            page_size=15,
        ),
    ])


def _render_export(items_df, tam_results):
    params_df = build_item_params_table(items_df, tam_results)
    csv_string = params_df.to_csv(index=False)

    return html.Div([
        html.H5("Export"),
        dbc.Row([
            dbc.Col([
                html.H6("Item Parameters CSV"),
                html.P("Download item difficulty, fit, and discrimination parameters."),
                dbc.Button(
                    "Download CSV",
                    id="btn-download-csv",
                    color="primary",
                ),
                dcc.Download(id="download-csv"),
            ], md=6),
            dbc.Col([
                html.H6("Full Report (HTML)"),
                html.P("Coming soon: export a standalone HTML report with all charts and tables."),
                dbc.Button("Download HTML", color="secondary", disabled=True),
            ], md=6),
        ]),
        dcc.Store(id="export-csv-data", data=csv_string),
    ])


@callback(
    Output("download-csv", "data"),
    Input("btn-download-csv", "n_clicks"),
    State("export-csv-data", "data"),
    prevent_initial_call=True,
)
def download_csv(n_clicks, csv_string):
    if not csv_string:
        return no_update
    return dict(content=csv_string, filename="pretxt_item_params.csv")
