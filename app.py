"""PreTxT — Pre-administration Test Difficulty Estimation.

Dash app entry point: layout, stores, navigation.
"""

import os
import sys
import webbrowser
import threading

import dash
from dash import html, dcc, callback, Input, Output, State, ALL, no_update
import dash_bootstrap_components as dbc

# When frozen by PyInstaller, resolve paths relative to the bundle directory
if getattr(sys, "frozen", False):
    _BASE_DIR = sys._MEIPASS
    os.chdir(_BASE_DIR)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from components.step_indicator import make_step_indicator

# Import page layouts
from pages import (
    step01_upload,
    step02_paired_comparisons,
    step03_spot_check,
    step04_btl_model,
    step05_item_distribution,
    step06_person_distribution,
    step07_discrimination,
    step08_person_set,
    step09_rasch,
    step10_reports,
)

# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="PreTxT",
)

PAGE_LAYOUTS = {
    1: step01_upload.layout,
    2: step02_paired_comparisons.layout,
    3: step03_spot_check.layout,
    4: step04_btl_model.layout,
    5: step05_item_distribution.layout,
    6: step06_person_distribution.layout,
    7: step07_discrimination.layout,
    8: step08_person_set.layout,
    9: step09_rasch.layout,
    10: step10_reports.layout,
}

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
app.layout = dbc.Container([
    # Header
    dbc.Navbar(
        dbc.Container([
            dbc.NavbarBrand([
                html.Span("PreTxT", className="fw-bold me-2"),
                html.Small("Pre-administration Test Difficulty Estimation", className="text-muted"),
            ]),
        ], fluid=True),
        color="white",
        className="border-bottom mb-3",
    ),

    # Session stores
    dcc.Store(id="store-current-step", data=1, storage_type="session"),
    dcc.Store(id="store-completed-steps", data=[], storage_type="session"),
    dcc.Store(id="store-items", data=None, storage_type="session"),
    dcc.Store(id="store-api-key", data=None, storage_type="local"),
    dcc.Store(id="store-comparisons", data=None, storage_type="session"),
    dcc.Store(id="store-btl-results", data=None, storage_type="session"),
    dcc.Store(id="store-person-dist", data=None, storage_type="session"),
    dcc.Store(id="store-discrimination", data=None, storage_type="session"),
    dcc.Store(id="store-response-matrix", data=None, storage_type="session"),
    dcc.Store(id="store-abilities", data=None, storage_type="session"),
    dcc.Store(id="store-tam-results", data=None, storage_type="session"),

    # Step indicator
    html.Div(id="step-indicator-container"),

    # Page content
    html.Div(id="page-content", className="page-content"),

    # Navigation buttons (static — callbacks toggle disabled/hidden)
    html.Div([
        dbc.Button("← Back", id="btn-prev-step", color="outline-secondary", className="me-auto",
                   style={"visibility": "hidden"}),
        dbc.Button("Next →", id="btn-next-step", color="primary", disabled=True),
    ], className="nav-buttons"),

], fluid=True, className="pb-5")


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
@callback(
    Output("step-indicator-container", "children"),
    Input("store-current-step", "data"),
    Input("store-completed-steps", "data"),
)
def update_step_indicator(current, completed):
    return make_step_indicator(current or 1, completed or [])


@callback(
    Output("page-content", "children"),
    Input("store-current-step", "data"),
)
def update_page(step):
    step = step or 1
    return PAGE_LAYOUTS.get(step, html.Div("Unknown step"))


@callback(
    Output("btn-prev-step", "style"),
    Output("btn-next-step", "disabled"),
    Input("store-current-step", "data"),
    Input("store-completed-steps", "data"),
)
def update_nav_buttons(step, completed):
    step = step or 1
    completed = completed or []

    prev_style = {"visibility": "visible"} if step > 1 else {"visibility": "hidden"}
    next_disabled = not (step < 10 and step in completed)

    return prev_style, next_disabled


@callback(
    Output("store-current-step", "data"),
    Input("btn-prev-step", "n_clicks"),
    Input("btn-next-step", "n_clicks"),
    Input({"type": "step-circle", "index": ALL}, "n_clicks"),
    State("store-current-step", "data"),
    State("store-completed-steps", "data"),
    prevent_initial_call=True,
)
def navigate(prev_clicks, next_clicks, circle_clicks, current, completed):
    current = current or 1
    completed = completed or []
    triggered = dash.ctx.triggered_id

    if triggered == "btn-prev-step" and prev_clicks and current > 1:
        return current - 1
    elif triggered == "btn-next-step" and next_clicks and current < 10 and current in completed:
        return current + 1
    elif isinstance(triggered, dict) and triggered.get("type") == "step-circle":
        idx = triggered["index"]
        # Only act on real clicks — ignore re-renders that fire with n_clicks=None
        actual_clicks = circle_clicks[idx - 1] if circle_clicks else None
        if not actual_clicks:
            return no_update
        target = idx
        if target == current:
            return no_update
        if target in completed or (target == current + 1 and current in completed):
            return target

    return no_update


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    is_frozen = getattr(sys, "frozen", False)
    port = 8050

    if is_frozen:
        # Auto-open browser after a short delay when running as .exe
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()

    app.run(debug=not is_frozen, port=port)
