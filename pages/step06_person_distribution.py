"""Step 6: Draw person distribution + percentile anchors (WACOM freehand)."""

from dash import html, dcc, callback, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import json
import re
import plotly.graph_objects as go

from core.distribution_fitter import fit_distribution

PERCENTILES = [10, 25, 50, 75, 90]
PERCENTILE_FRACS = [p / 100 for p in PERCENTILES]
PCTILE_COLORS = ["#6c757d", "#0d6efd", "#dc3545", "#0d6efd", "#6c757d"]


def parse_svg_path(path_str):
    """Extract (x, y) from SVG path 'M x,y L x,y ...' in data coords."""
    coords = re.findall(r'[ML]\s*([-\d.eE+]+)[,\s]([-\d.eE+]+)', path_str)
    return [float(x) for x, _ in coords], [float(y) for _, y in coords]


# ── Layout ────────────────────────────────────────────────────────────────────

layout = dbc.Container([
    html.H3("Step 6: Person Distribution", className="mb-3"),
    html.P("Use the draw tool (pencil icon in toolbar) to sketch the expected "
           "person ability distribution. Then click 'Fit Distribution' to smooth it."),

    dcc.Graph(
        id="person-dist-chart",
        style={"height": "500px"},
        config={
            "modeBarButtonsToAdd": ["drawopenpath", "eraseshape"],
        },
    ),
    html.Small("Draw a freehand curve on the chart, then click Fit Distribution.",
               className="text-muted"),

    # ── Action buttons ────────────────────────────────────────────────────────
    dbc.Row([
        dbc.Col(dbc.Button("Fit Distribution", id="btn-fit-dist", color="primary",
                           disabled=True, className="me-2"), width="auto"),
        dbc.Col(dbc.Button("Clear Drawing", id="btn-clear-drawing",
                           color="outline-danger", className="me-2"), width="auto"),
        dbc.Col(dbc.Button("Save Distribution", id="btn-save-dist", color="success",
                           disabled=True), width="auto"),
    ], className="mt-3 mb-3"),

    # ── Percentile summary (hidden until fit) ─────────────────────────────────
    html.Div(id="percentile-section", style={"display": "none"}, children=[
        html.H5("Percentile Anchors", className="mt-3"),
        html.P("Drag the vertical lines on the chart to adjust percentiles, "
               "or edit the values in the table below.", className="small text-muted"),
        html.Div(id="percentile-table-container"),
    ]),

    html.Div(id="step6-feedback", className="mt-3"),

    # ── Stores ────────────────────────────────────────────────────────────────
    dcc.Store(id="drawn-path-data", data=None),
    dcc.Store(id="fitted-dist-data", data=None),
    dcc.Store(id="percentile-values", data=None),
    # Keep old store id for backward compat with handle_click (no longer used)
    dcc.Store(id="drawn-points", data={"x": [], "y": []}),
], fluid=True)


# ── 1. Capture drawn path from relayoutData ──────────────────────────────────

@callback(
    Output("drawn-path-data", "data"),
    Output("btn-fit-dist", "disabled"),
    Input("person-dist-chart", "relayoutData"),
    Input("btn-clear-drawing", "n_clicks"),
    prevent_initial_call=True,
)
def capture_drawn_path(relayout_data, clear_clicks):
    if ctx.triggered_id == "btn-clear-drawing":
        return None, True

    if not relayout_data:
        return no_update, no_update

    # Look for new shapes in relayoutData
    shapes = None
    if "shapes" in relayout_data:
        shapes = relayout_data["shapes"]
    else:
        # Check for incremental shape additions like shapes[0].path
        for key in relayout_data:
            if key.startswith("shapes[") and key.endswith("].path"):
                # We have shape path data — need to trigger a fit-enable
                # but we'll read the full shapes from the figure in the fit callback
                return relayout_data[key], False

    if shapes:
        # Find the last drawn open path (not our percentile lines)
        for shape in reversed(shapes):
            if shape.get("type") == "path" and shape.get("path"):
                return shape["path"], False

    return no_update, no_update


# ── 2. Fit distribution on button click ───────────────────────────────────────

@callback(
    Output("fitted-dist-data", "data"),
    Output("percentile-values", "data"),
    Output("percentile-section", "style"),
    Output("btn-save-dist", "disabled"),
    Input("btn-fit-dist", "n_clicks"),
    Input("btn-clear-drawing", "n_clicks"),
    State("drawn-path-data", "data"),
    prevent_initial_call=True,
)
def fit_drawn_distribution(fit_clicks, clear_clicks, path_data):
    if ctx.triggered_id == "btn-clear-drawing":
        return None, None, {"display": "none"}, True

    if not path_data:
        return no_update, no_update, no_update, no_update

    try:
        xs, ys = parse_svg_path(path_data)
    except Exception:
        return no_update, no_update, no_update, no_update

    if len(xs) < 3:
        return no_update, no_update, no_update, no_update

    # Clamp y >= 0
    ys = [max(0, y) for y in ys]

    try:
        result = fit_distribution(xs, ys)
    except Exception:
        return no_update, no_update, no_update, no_update

    # Compute percentiles from CDF
    x_arr = np.array(result["x_smooth"])
    cdf = np.array(result["cdf_smooth"])
    pctile_vals = {}
    for p, frac in zip(PERCENTILES, PERCENTILE_FRACS):
        val = float(np.interp(frac, cdf, x_arr))
        pctile_vals[str(p)] = round(val, 2)

    return (
        json.dumps(result),
        json.dumps(pctile_vals),
        {"display": "block"},
        False,
    )


# ── 3. Render chart ──────────────────────────────────────────────────────────

@callback(
    Output("person-dist-chart", "figure"),
    Input("fitted-dist-data", "data"),
    Input("percentile-values", "data"),
    Input("btn-clear-drawing", "n_clicks"),
    State("store-btl-results", "data"),
)
def render_chart(fitted_json, pctile_json, clear_clicks, btl_json):
    fig = go.Figure()

    # Item difficulty markers as reference
    lo, hi = -4, 4
    if btl_json:
        df = pd.read_json(btl_json, orient="split")
        diffs = df["difficulty"].values
        lo, hi = float(diffs.min()) - 1, float(diffs.max()) + 1
        fig.add_trace(go.Scatter(
            x=diffs.tolist(), y=[0] * len(diffs),
            mode="markers",
            marker=dict(size=8, color="#0d6efd", symbol="diamond"),
            name="Items",
            hovertext=df["item_id"].values.tolist(),
        ))

    shapes = []

    # Fitted curve
    y_peak = 0.5  # default for empty chart
    if fitted_json and ctx.triggered_id != "btn-clear-drawing":
        result = json.loads(fitted_json)
        x_smooth = result["x_smooth"]
        y_smooth = result["y_smooth"]

        # Plot the actual fitted density values (no rescaling)
        y_plot = y_smooth
        y_peak = float(np.max(y_smooth)) if len(y_smooth) > 0 else 0.5

        fig.add_trace(go.Scatter(
            x=x_smooth, y=y_plot,
            mode="lines",
            line=dict(color="#198754", width=2),
            fill="tozeroy",
            fillcolor="rgba(25, 135, 84, 0.15)",
            name="Fitted Distribution",
        ))

        # Update axis range to fit curve
        lo = min(lo, x_smooth[0] - 0.5)
        hi = max(hi, x_smooth[-1] + 0.5)

        # Percentile lines as editable shapes
        if pctile_json:
            pctile_vals = json.loads(pctile_json)
            for i, p in enumerate(PERCENTILES):
                x_val = pctile_vals.get(str(p))
                if x_val is not None:
                    shapes.append(dict(
                        type="line",
                        x0=x_val, x1=x_val,
                        y0=0, y1=y_peak * 1.05,
                        line=dict(color=PCTILE_COLORS[i], width=2, dash="dash"),
                        editable=True,
                        name=f"P{p}",
                    ))
                    fig.add_annotation(
                        x=x_val, y=y_peak * 1.1,
                        text=f"P{p}",
                        showarrow=False,
                        font=dict(size=11, color=PCTILE_COLORS[i]),
                    )

    fig.update_layout(
        xaxis=dict(title="Ability / Difficulty (logits)", range=[lo, hi]),
        yaxis=dict(title="Relative Density", range=[0, 1]),
        template="plotly_white",
        margin=dict(t=30),
        showlegend=True,
        shapes=shapes,
        dragmode="drawopenpath",
        newshape=dict(line=dict(color="#dc3545", width=3)),
    )

    return fig


# ── 4. Sync dragged percentile lines ─────────────────────────────────────────

@callback(
    Output("percentile-values", "data", allow_duplicate=True),
    Output("percentile-table-container", "children", allow_duplicate=True),
    Input("person-dist-chart", "relayoutData"),
    State("percentile-values", "data"),
    State("fitted-dist-data", "data"),
    prevent_initial_call=True,
)
def sync_dragged_percentiles(relayout_data, pctile_json, fitted_json):
    if not relayout_data or not pctile_json:
        return no_update, no_update

    pctile_vals = json.loads(pctile_json)
    updated = False

    # Detect shape drag: shapes[N].x0, shapes[N].x1
    for key, val in relayout_data.items():
        match = re.match(r'shapes\[(\d+)\]\.x0', key)
        if match:
            idx = int(match.group(1))
            if idx < len(PERCENTILES):
                p = str(PERCENTILES[idx])
                pctile_vals[p] = round(float(val), 2)
                updated = True

    if not updated:
        return no_update, no_update

    return json.dumps(pctile_vals), _build_percentile_table(pctile_vals)


# ── 5. Render percentile table (also triggered by fit) ────────────────────────

@callback(
    Output("percentile-table-container", "children"),
    Input("percentile-values", "data"),
    prevent_initial_call=True,
)
def render_percentile_table(pctile_json):
    if not pctile_json:
        return ""
    pctile_vals = json.loads(pctile_json)
    return _build_percentile_table(pctile_vals)


def _build_percentile_table(pctile_vals):
    rows = []
    for p in PERCENTILES:
        val = pctile_vals.get(str(p), "—")
        rows.append(html.Tr([
            html.Td(f"P{p}", className="fw-bold"),
            html.Td(f"{val}" if val != "—" else "—"),
        ]))
    return dbc.Table([
        html.Thead(html.Tr([html.Th("Percentile"), html.Th("Ability (logits)")])),
        html.Tbody(rows),
    ], bordered=True, striped=True, size="sm", className="mt-2")


# ── 6. Save distribution ─────────────────────────────────────────────────────

@callback(
    Output("store-person-dist", "data"),
    Output("store-completed-steps", "data", allow_duplicate=True),
    Output("step6-feedback", "children"),
    Input("btn-save-dist", "n_clicks"),
    State("fitted-dist-data", "data"),
    State("percentile-values", "data"),
    State("drawn-path-data", "data"),
    State("store-completed-steps", "data"),
    prevent_initial_call=True,
)
def save_distribution(n_clicks, fitted_json, pctile_json, path_data, completed):
    if not fitted_json or not pctile_json:
        return no_update, no_update, dbc.Alert(
            "Fit a distribution first.", color="warning")

    result = json.loads(fitted_json)
    pctile_vals = json.loads(pctile_json)

    # Parse drawn points for backward compat
    drawn_x, drawn_y = [], []
    if path_data:
        try:
            drawn_x, drawn_y = parse_svg_path(path_data)
        except Exception:
            pass

    dist_data = {
        "drawn_x": drawn_x,
        "drawn_y": drawn_y,
        "x_smooth": result["x_smooth"],
        "y_smooth": result["y_smooth"],
        "cdf_smooth": result["cdf_smooth"],
        "percentiles": {str(p): pctile_vals.get(str(p)) for p in PERCENTILES},
    }

    completed = completed or []
    if 6 not in completed:
        completed = sorted(set(completed + [6]))

    return json.dumps(dist_data), completed, dbc.Alert(
        "Distribution saved.", color="success")
