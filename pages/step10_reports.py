"""Step 10: Reports — Wright map, fit, Person-Item distribution, Guttman."""

from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from dash import dash_table
import pandas as pd
import numpy as np
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.report_builder import build_item_params_table, identify_misfit_items
from components.page_size_selector import page_size_selector, register_page_size_callback

# Pre-register page-size callbacks for dynamically created tables
register_page_size_callback("report-params-page-size", "report-params-table")
# Guttman table uses virtualization (no pagination), so no page-size callback needed

layout = dbc.Container([
    html.H3("Step 10: Reports", className="mb-3"),

    dbc.Tabs([
        dbc.Tab(label="Item Parameters", tab_id="tab-params"),
        dbc.Tab(label="Wright Map", tab_id="tab-wright"),
        dbc.Tab(label="Test Statistics", tab_id="tab-stats"),
        dbc.Tab(label="Person-Item Distribution", tab_id="tab-person-item"),
        dbc.Tab(label="Guttman Pattern", tab_id="tab-guttman"),
        dbc.Tab(label="Export", tab_id="tab-export"),
    ], id="report-tabs", active_tab="tab-params"),

    html.Div([
        html.Div(id="report-tab-content", className="report-tab-content"),

        # Page-size selectors (always in DOM; visibility toggled by tab callback)
        html.Div(id="report-params-page-size-container", children=[
            page_size_selector("report-params-page-size", default=15),
        ], style={"display": "none"}),
        html.Div(id="report-guttman-page-size-container", children=[
            page_size_selector("report-guttman-page-size", default=50),
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
    guttman_vis = hide  # Guttman uses virtualization, no page-size selector

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
    elif tab == "tab-person-item":
        return _render_person_item_dist(items_df, tam_results, abilities), completed, params_vis, guttman_vis
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


# ── Person-Item Threshold Distribution (replaces Gap Analysis) ───────────────

def _render_person_item_dist(items_df, tam_results, abilities):
    """RUMM2030-style person-item threshold distribution.

    Persons histogram on top (bars up), items histogram on bottom (bars down),
    sharing the same logit x-axis.
    """
    if abilities is None or len(abilities) == 0:
        return dbc.Alert("Generate person data first (Step 8).", color="warning")

    # Use Rasch difficulties if available, else BTL
    if tam_results and "item_params" in tam_results:
        item_diffs = np.array([p["xsi"] for p in tam_results["item_params"]])
    else:
        item_diffs = items_df["difficulty"].values

    # Determine shared bin edges
    all_vals = np.concatenate([abilities, item_diffs])
    lo = np.floor(all_vals.min()) - 0.5
    hi = np.ceil(all_vals.max()) + 0.5
    bin_width = 0.5
    bin_edges = np.arange(lo, hi + bin_width, bin_width)
    bin_centres = (bin_edges[:-1] + bin_edges[1:]) / 2

    # Compute histograms
    person_counts, _ = np.histogram(abilities, bins=bin_edges)
    item_counts, _ = np.histogram(item_diffs, bins=bin_edges)

    n_persons = len(abilities)
    n_items = len(item_diffs)
    person_pct = person_counts / n_persons * 100 if n_persons > 0 else person_counts
    item_pct = item_counts / n_items * 100 if n_items > 0 else item_counts

    # Build figure with two subplots sharing x-axis
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.65, 0.35],
    )

    # ── Top: Persons (bars pointing up) ──────────────────────────────────────
    fig.add_trace(
        go.Bar(
            x=bin_centres, y=person_counts,
            marker_color="#198754", opacity=0.8,
            name="Persons",
            hovertemplate="Location: %{x:.1f}<br>Count: %{y}<br>Pct: %{customdata:.1f}%",
            customdata=person_pct,
        ),
        row=1, col=1,
    )

    # Person stats annotation
    fig.add_annotation(
        x=0.02, y=0.98, xref="paper", yref="paper",
        text=(f"<b>PERSONS</b>  N={n_persons}  "
              f"Mean={abilities.mean():.3f}  SD={abilities.std():.3f}"),
        showarrow=False, font=dict(size=11),
        xanchor="left", yanchor="top",
    )

    # Person y-axes
    person_max = int(person_counts.max()) + 2
    person_pct_max = person_max / n_persons * 100 if n_persons > 0 else 1
    fig.update_yaxes(
        title_text="Frequency", range=[0, person_max],
        row=1, col=1,
    )

    # ── Bottom: Items (bars pointing down = inverted y-axis) ─────────────────
    fig.add_trace(
        go.Bar(
            x=bin_centres, y=item_counts,
            marker_color="#0d6efd", opacity=0.8,
            name="Items",
            hovertemplate="Location: %{x:.1f}<br>Count: %{y}<br>Pct: %{customdata:.1f}%",
            customdata=item_pct,
        ),
        row=2, col=1,
    )

    item_max = int(item_counts.max()) + 2
    fig.update_yaxes(
        title_text="Frequency", autorange="reversed",
        range=[0, item_max],
        row=2, col=1,
    )

    # Items label
    fig.add_annotation(
        x=0.02, y=0.30, xref="paper", yref="paper",
        text=f"<b>ITEMS</b>  N={n_items}",
        showarrow=False, font=dict(size=11),
        xanchor="left", yanchor="top",
    )

    fig.update_xaxes(title_text="Location (logits)", row=2, col=1)

    fig.update_layout(
        title="Person-Item Threshold Distribution",
        template="plotly_white",
        height=550,
        showlegend=True,
        bargap=0.05,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return html.Div([
        html.H5("Person-Item Threshold Distribution"),
        html.P("Persons on top, items on bottom — both on the same logit scale. "
               "Gaps between the two distributions indicate areas with poor measurement precision.",
               className="text-muted small"),
        dcc.Graph(figure=fig),
    ])


# ── Guttman Pattern (RUMM2030-style colored grid) ───────────────────────────

def _render_guttman(resp_df, abilities, items_df):
    """RUMM2030-style Guttman distribution: colored grid of all responses.

    Rows = persons sorted by ability (lowest first).
    Columns = items sorted by difficulty (easiest first).
    1 (correct) = blue, 0 (incorrect) = amber/orange.
    """
    if resp_df is None or abilities is None:
        return dbc.Alert("Generate response data first (Step 8).", color="warning")

    difficulties = items_df["difficulty"].values
    item_ids = items_df["item_id"].values

    # Sort items by difficulty (easiest first)
    item_order = np.argsort(difficulties)
    sorted_item_ids = item_ids[item_order]
    sorted_diffs = difficulties[item_order]
    sorted_responses = resp_df.iloc[:, item_order].values

    # Sort persons by ability (lowest first)
    person_order = np.argsort(abilities)
    sorted_abilities = abilities[person_order]
    sorted_responses = sorted_responses[person_order]

    # Build column headers: difficulty rounded
    item_col_ids = [f"item_{i}" for i in range(len(sorted_diffs))]
    item_col_names = [f"{d:.1f}" for d in sorted_diffs]

    # Build table data
    records = []
    for i in range(len(sorted_abilities)):
        row = {
            "serial": int(person_order[i]),
            "location": round(float(sorted_abilities[i]), 3),
        }
        for j, col_id in enumerate(item_col_ids):
            row[col_id] = int(sorted_responses[i, j])
        records.append(row)

    # Columns definition
    columns = [
        {"name": "Serial", "id": "serial"},
        {"name": "Location", "id": "location"},
    ] + [
        {"name": name, "id": col_id}
        for name, col_id in zip(item_col_names, item_col_ids)
    ]

    # Conditional styling: 1 = blue, 0 = amber for each item column
    style_conditions = []
    for col_id in item_col_ids:
        style_conditions.append({
            "if": {"filter_query": f"{{{col_id}}} = 1", "column_id": col_id},
            "backgroundColor": "#0d6efd", "color": "white",
        })
        style_conditions.append({
            "if": {"filter_query": f"{{{col_id}}} = 0", "column_id": col_id},
            "backgroundColor": "#e67e00", "color": "white",
        })

    return html.Div([
        html.H5("Guttman Pattern"),
        html.P([
            f"{len(records)} persons \u00d7 {len(item_col_ids)} items. "
            "Persons sorted by ability (low \u2192 high). "
            "Items sorted by difficulty (easy \u2192 hard). ",
            html.Span("Blue = correct (1)", style={"color": "#0d6efd", "fontWeight": "700"}),
            ", ",
            html.Span("Amber = incorrect (0)", style={"color": "#e67e00", "fontWeight": "700"}),
            ".",
        ], className="text-muted small mb-2"),
        html.Div(
            dash_table.DataTable(
                id="report-guttman-table",
                columns=columns,
                data=records,
                page_action="none",
                virtualization=True,
                style_table={
                    "overflowX": "auto",
                    "overflowY": "auto",
                    "height": "calc(100vh - 260px)",
                    "minHeight": "400px",
                },
                style_cell={
                    "textAlign": "center", "padding": "2px",
                    "fontSize": "0.7rem", "fontFamily": "monospace",
                    "minWidth": "28px", "maxWidth": "36px",
                    "lineHeight": "20px",
                },
                style_cell_conditional=[
                    {"if": {"column_id": "serial"},
                     "minWidth": "55px", "maxWidth": "70px", "fontWeight": "600",
                     "backgroundColor": "#f8f9fa"},
                    {"if": {"column_id": "location"},
                     "minWidth": "65px", "maxWidth": "80px", "fontWeight": "600",
                     "backgroundColor": "#f8f9fa"},
                ],
                style_header={
                    "backgroundColor": "#e9ecef", "fontWeight": "600",
                    "fontSize": "0.7rem", "padding": "2px",
                },
                style_data_conditional=style_conditions,
                fixed_columns={"headers": True, "data": 2},
                fixed_rows={"headers": True},
            ),
            className="guttman-grid-container",
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
