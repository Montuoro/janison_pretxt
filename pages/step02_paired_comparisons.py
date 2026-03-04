"""Step 2: Run LLM paired comparisons."""

from dash import html, dcc, callback, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import json
import base64

import time as _time

from core.comparison_engine import select_pairs, count_pairs, STRATEGIES
from core.claude_comparisons import compare_pair, PROVIDERS, _parse_retry_delay

_provider_options = [{"label": v["label"], "value": k} for k, v in PROVIDERS.items()]
_strategy_options = [{"label": v["label"], "value": k} for k, v in STRATEGIES.items()]

layout = dbc.Container([
    html.H3("Step 2: Paired Comparisons", className="mb-3"),
    html.P("Use an LLM to compare item pairs and estimate relative difficulty."),

    # ── API Key section ──────────────────────────────────────────────────────
    dbc.Card(dbc.CardBody([
        html.H6("API Connection"),
        dbc.Row([
            dbc.Col([
                dbc.Label("Provider"),
                dbc.Select(
                    id="select-provider",
                    options=_provider_options,
                    value="gemini",
                ),
            ], md=3),
            dbc.Col([
                dbc.Label("API Key"),
                dbc.InputGroup([
                    dbc.Input(
                        id="input-api-key",
                        type="password",
                        placeholder="",
                        className="api-key-input",
                    ),
                    dbc.Button("Test & Save", id="btn-test-api-key", color="primary"),
                ]),
            ], md=5),
            dbc.Col([
                dbc.Label("Model"),
                dbc.Select(id="select-model", options=[], value=""),
            ], md=4),
        ]),
        html.Div(id="api-key-status", className="mt-2"),
    ]), className="mb-3"),

    # ── Pair selection strategy ──────────────────────────────────────────────
    dbc.Card(dbc.CardBody([
        html.H6("Pair Selection Strategy"),
        dbc.Row([
            dbc.Col([
                dbc.RadioItems(
                    id="select-strategy",
                    options=[
                        {"label": html.Span([
                            html.Strong(v["label"]),
                            html.Br(),
                            html.Small(v["description"], className="text-muted"),
                        ]), "value": k}
                        for k, v in STRATEGIES.items()
                    ],
                    value="chain",
                    className="mb-2",
                ),
            ], md=8),
            dbc.Col([
                html.Div(id="strategy-k-container", children=[
                    dbc.Label("Neighbours (K)", className="small"),
                    dbc.Input(id="input-chain-k", type="number", value=3, min=1, max=10, step=1, size="sm"),
                    html.Small("Higher K = more pairs, better accuracy", className="text-muted"),
                ]),
            ], md=4),
        ]),
        html.Div(id="pair-count-info", className="mt-2"),
    ]), className="mb-3"),

    # ── Additional rules ─────────────────────────────────────────────────────
    dbc.Row([
        dbc.Col([
            dbc.Label("Additional Rules / Context (optional)"),
            dbc.Textarea(
                id="input-extra-rules",
                placeholder="e.g., 'These items are for Year 3 students aged 7-8. Multi-step problems are harder than single-step.'",
                rows=3,
            ),
        ]),
    ], className="mb-3"),

    html.Div(id="comparison-info", className="mb-3"),

    dbc.Button("Run Comparisons", id="btn-run-comparisons", color="primary", size="lg", className="me-2"),
    dbc.Button("Skip (Use Sample Data)", id="btn-skip-comparisons", color="outline-secondary", className="me-2"),
    dbc.Button("Stop", id="btn-stop-comparisons", color="danger", size="sm",
               style={"display": "none"}),

    # ── Save / Load comparisons ───────────────────────────────────────────────
    html.Hr(),
    dbc.Row([
        dbc.Col([
            dbc.Button("Download Comparisons", id="btn-download-comparisons",
                       color="outline-primary", size="sm", disabled=True, className="me-2"),
            dcc.Download(id="download-comparisons"),
        ], width="auto"),
        dbc.Col([
            dcc.Upload(
                id="upload-comparisons",
                accept=".json",
                children=dbc.Button("Upload Comparisons", color="outline-success", size="sm"),
            ),
        ], width="auto"),
        dbc.Col(html.Div(id="upload-comparisons-feedback"), width="auto"),
    ], className="mb-3", align="center"),

    html.Div(id="comparison-progress-container", className="mt-3"),

    # Interval fires to process one pair at a time.
    # max_intervals gates execution: tick increments it after each pair,
    # ensuring only one tick is in-flight at a time.
    dcc.Interval(id="comparison-interval", interval=1000, disabled=True,
                 n_intervals=0, max_intervals=0),
    dcc.Store(id="comparison-queue", data=None),
    dcc.Store(id="comparison-running", data=False),
], fluid=True)


# ── Update model list and placeholder when provider changes ──────────────────

@callback(
    Output("select-model", "options"),
    Output("select-model", "value"),
    Output("input-api-key", "placeholder"),
    Input("select-provider", "value"),
)
def update_models_for_provider(provider):
    if not provider or provider not in PROVIDERS:
        return [], "", ""
    info = PROVIDERS[provider]
    opts = [{"label": m["label"], "value": m["value"]} for m in info["models"]]
    return opts, info["default"], info["placeholder"]


# ── Show/hide K input based on strategy ──────────────────────────────────────

@callback(
    Output("strategy-k-container", "style"),
    Input("select-strategy", "value"),
)
def toggle_k_input(strategy):
    if strategy == "chain":
        return {"display": "block"}
    return {"display": "none"}


# ── Update pair count preview ────────────────────────────────────────────────

@callback(
    Output("pair-count-info", "children"),
    Input("select-strategy", "value"),
    Input("input-chain-k", "value"),
    State("store-items", "data"),
)
def update_pair_count(strategy, k, items_json):
    if not items_json:
        return ""
    df = pd.read_json(items_json, orient="split")
    n = len(df)
    k = int(k or 3)
    n_pairs = count_pairs(n, strategy=strategy, k=k)
    rr_pairs = count_pairs(n, strategy="round_robin")
    pct = (n_pairs / rr_pairs * 100) if rr_pairs > 0 else 100
    return dbc.Alert(
        f"{n} items -> {n_pairs} pairs ({pct:.0f}% of full round-robin's {rr_pairs})",
        color="info", className="py-2 mb-0",
    )


# ── Test & save API key ─────────────────────────────────────────────────────

@callback(
    Output("store-api-key", "data"),
    Output("api-key-status", "children"),
    Input("btn-test-api-key", "n_clicks"),
    State("input-api-key", "value"),
    State("select-provider", "value"),
    State("select-model", "value"),
    State("store-api-key", "data"),
    prevent_initial_call=True,
)
def test_and_save_key(n_clicks, key, provider, model, stored):
    if not key or not key.strip():
        return no_update, dbc.Alert("Please enter an API key.", color="warning", className="py-1 mb-0")
    if not provider:
        return no_update, dbc.Alert("Please select a provider.", color="warning", className="py-1 mb-0")

    try:
        from core.claude_comparisons import _CALLERS
        caller = _CALLERS[provider]
        caller(key.strip(), model or PROVIDERS[provider]["default"],
               "Reply with just the word OK.", "Test")
    except Exception as e:
        err = str(e)
        if "limit: 0" in err or "quota" in err.lower():
            msg = "API key accepted but your account has zero quota. Enable billing or try another provider."
            color = "danger"
        elif "401" in err or "auth" in err.lower() or "invalid" in err.lower():
            msg = "Invalid API key. Please check and try again."
            color = "danger"
        else:
            msg = f"Connection error: {err[:150]}"
            color = "danger"
        return no_update, dbc.Alert(msg, color=color, className="py-1 mb-0")

    stored = stored or {}
    if isinstance(stored, str):
        stored = {"anthropic": stored}
    stored[provider] = key.strip()

    return stored, dbc.Alert(
        f"Key verified and saved for {PROVIDERS[provider]['label']}.",
        color="success", className="py-1 mb-0",
    )


# ── Load saved key when switching provider ───────────────────────────────────

@callback(
    Output("input-api-key", "value"),
    Input("select-provider", "value"),
    State("store-api-key", "data"),
)
def load_api_key(provider, stored):
    if not stored or not provider:
        return ""
    if isinstance(stored, str):
        return stored if provider == "anthropic" else ""
    return stored.get(provider, "")


# ── Info banner ──────────────────────────────────────────────────────────────

@callback(
    Output("comparison-info", "children"),
    Input("store-items", "data"),
)
def show_comparison_info(items_json):
    if not items_json:
        return dbc.Alert("Please upload items in Step 1 first.", color="warning")
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# Interval-driven comparison flow: Run / Skip / Stop → queue → tick → finish
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. Start: build queue, enable interval ───────────────────────────────────

@callback(
    Output("comparison-queue", "data"),
    Output("comparison-interval", "disabled"),
    Output("comparison-interval", "n_intervals"),
    Output("comparison-interval", "max_intervals"),
    Output("comparison-running", "data"),
    Output("btn-run-comparisons", "disabled"),
    Output("btn-skip-comparisons", "disabled"),
    Output("btn-stop-comparisons", "style"),
    Output("store-comparisons", "data"),
    Output("store-completed-steps", "data", allow_duplicate=True),
    Output("comparison-progress-container", "children"),
    Input("btn-run-comparisons", "n_clicks"),
    Input("btn-skip-comparisons", "n_clicks"),
    Input("btn-stop-comparisons", "n_clicks"),
    State("store-items", "data"),
    State("select-provider", "value"),
    State("input-api-key", "value"),
    State("select-model", "value"),
    State("select-strategy", "value"),
    State("input-chain-k", "value"),
    State("input-extra-rules", "value"),
    State("store-completed-steps", "data"),
    State("comparison-running", "data"),
    prevent_initial_call=True,
)
def start_or_skip_comparisons(run_clicks, skip_clicks, stop_clicks,
                              items_json, provider, api_key, model,
                              strategy, chain_k, extra_rules,
                              completed, is_running):
    triggered = ctx.triggered_id
    completed = completed or []
    no_change = no_update

    # ── Stop button ──────────────────────────────────────────────────────
    if triggered == "btn-stop-comparisons":
        return (None, True, 0, 0, False, False, False, {"display": "none"},
                no_change, no_change,
                dbc.Alert("Comparisons stopped by user.", color="warning"))

    # ── Skip button ──────────────────────────────────────────────────────
    if triggered == "btn-skip-comparisons":
        if not items_json:
            return (no_change, no_change, no_change, no_change, no_change,
                    no_change, no_change, no_change, no_change, no_change,
                    dbc.Alert("Upload items first.", color="danger"))

        df = pd.read_json(items_json, orient="split")
        items = df.to_dict("records")
        strategy = strategy or "chain"
        chain_k = int(chain_k or 3)
        pairs = [(int(i), int(j)) for i, j in select_pairs(len(items), strategy=strategy, k=chain_k)]

        comparisons = []
        for i, j in pairs:
            harder = "B" if j > i else "A"
            comparisons.append({
                "item_a_id": items[i]["item_id"],
                "item_b_id": items[j]["item_id"],
                "item_a_idx": int(i), "item_b_idx": int(j),
                "harder": harder, "confidence": 3,
                "reasoning": "Skipped - using item order heuristic",
            })
        if 2 not in completed:
            completed = sorted(set(completed + [2]))

        return (None, True, 0, 0, False, False, False, {"display": "none"},
                json.dumps(comparisons), completed,
                dbc.Alert(f"Generated {len(comparisons)} heuristic comparisons (skipped LLM).", color="info"))

    # ── Run button ───────────────────────────────────────────────────────
    if triggered == "btn-run-comparisons":
        if not items_json:
            return (no_change, no_change, no_change, no_change, no_change,
                    no_change, no_change, no_change, no_change, no_change,
                    dbc.Alert("Upload items first.", color="danger"))
        df = pd.read_json(items_json, orient="split")
        items = df.to_dict("records")
        strategy = strategy or "chain"
        chain_k = int(chain_k or 3)
        pairs = [(int(i), int(j)) for i, j in select_pairs(len(items), strategy=strategy, k=chain_k)]

        queue = {
            "pairs": pairs,
            "items": items,
            "provider": provider,
            "api_key": api_key,
            "model": model,
            "extra_rules": extra_rules or "",
            "results": [],
            "errors": [],
            "total": len(pairs),
            "fatal_error": None,
        }

        # disabled=False, n_intervals=0, max_intervals=1 → fires exactly once
        return (json.dumps(queue), False, 0, 1, True,
                True, True, {"display": "inline-block"},
                no_change, no_change,
                _render_progress(0, len(pairs), []))

    # Fallback
    return (no_change,) * 11


# ── 2. Tick: process one pair per interval tick ──────────────────────────────
#
# max_intervals gates execution: the interval only fires when
# n_intervals < max_intervals.  Start sets max_intervals=1 so exactly one
# tick fires.  After processing a pair, tick sets max_intervals = n_intervals+1,
# allowing exactly one more fire.  Because the browser applies all outputs
# atomically before the interval checks again, the next tick always reads
# the UPDATED queue state.

@callback(
    Output("comparison-queue", "data", allow_duplicate=True),
    Output("comparison-progress-container", "children", allow_duplicate=True),
    Output("comparison-interval", "disabled", allow_duplicate=True),
    Output("comparison-interval", "max_intervals", allow_duplicate=True),
    Output("store-comparisons", "data", allow_duplicate=True),
    Output("store-completed-steps", "data", allow_duplicate=True),
    Output("comparison-running", "data", allow_duplicate=True),
    Output("btn-run-comparisons", "disabled", allow_duplicate=True),
    Output("btn-skip-comparisons", "disabled", allow_duplicate=True),
    Output("btn-stop-comparisons", "style", allow_duplicate=True),
    Input("comparison-interval", "n_intervals"),
    State("comparison-queue", "data"),
    State("store-completed-steps", "data"),
    prevent_initial_call=True,
)
def tick_comparison(n_intervals, queue_json, completed):
    if not queue_json:
        return (no_update, no_update, True, 0,
                no_update, no_update, no_update, no_update, no_update, no_update)

    queue = json.loads(queue_json)

    # Determine which pair to process from results already completed
    idx = len(queue.get("results") or []) + len(queue.get("errors") or [])
    total = queue["total"]
    pairs = queue["pairs"]
    items = queue["items"]
    results = queue.get("results") or []
    errors = queue.get("errors") or []

    # Already done or stopped?
    if idx >= total or queue.get("fatal_error"):
        queue["results"] = results
        queue["errors"] = errors
        return _finish(queue, completed)

    # ── Rate-limit cooldown: wait without blocking ────────────────────
    retry_after = queue.get("retry_after")
    if retry_after and _time.time() < retry_after:
        remaining = int(retry_after - _time.time()) + 1
        progress_ui = _render_progress(
            idx, total, results[-3:] if results else [],
            wait_msg=f"Rate limited — retrying in {remaining}s",
        )
        return (json.dumps(queue), progress_ui, no_update, n_intervals + 1,
                no_update, no_update, no_update, no_update, no_update, no_update)

    # Clear any expired cooldown
    queue.pop("retry_after", None)
    queue.pop("retry_count", None)

    # ── Process one pair (no retries — handle rate limits at tick level) ──
    i, j = pairs[idx]
    try:
        result = compare_pair(
            provider=queue["provider"],
            api_key=queue["api_key"],
            item_a=items[i],
            item_b=items[j],
            model=queue["model"],
            extra_rules=queue["extra_rules"],
            max_retries=0,  # don't sleep inside callback; we handle retries here
        )
        results.append({
            "item_a_id": items[i]["item_id"],
            "item_b_id": items[j]["item_id"],
            "item_a_idx": int(i), "item_b_idx": int(j),
            "harder": result["harder"],
            "confidence": result.get("confidence", 3),
            "reasoning": result.get("reasoning", ""),
        })
    except RuntimeError as e:
        queue["fatal_error"] = str(e)
        queue["results"] = results
        return _finish(queue, completed)
    except Exception as e:
        err_str = str(e)
        is_rate_limit = any(k in err_str for k in ["429", "rate", "quota", "RESOURCE_EXHAUSTED"])

        if is_rate_limit:
            retry_count = queue.get("retry_count", 0)
            if retry_count >= 10:
                # Give up after 10 consecutive rate-limit retries
                queue["fatal_error"] = f"Gave up after {retry_count} rate-limit retries: {err_str[:200]}"
                queue["results"] = results
                queue["errors"] = errors
                return _finish(queue, completed)

            wait = _parse_retry_delay(err_str, retry_count)
            queue["retry_after"] = _time.time() + wait
            queue["retry_count"] = retry_count + 1
            queue["results"] = results
            queue["errors"] = errors

            progress_ui = _render_progress(
                idx, total, results[-3:] if results else [],
                wait_msg=f"Rate limited — retrying in {int(wait)}s (attempt {retry_count + 1})",
            )
            return (json.dumps(queue), progress_ui, no_update, n_intervals + 1,
                    no_update, no_update, no_update, no_update, no_update, no_update)

        # Non-rate-limit error: record and continue
        errors.append(f"{items[i]['item_id']} vs {items[j]['item_id']}: {e}")
        if len(errors) >= 3 and len(results) == 0:
            queue["fatal_error"] = f"First {len(errors)} pairs all failed. Last error: {e}"
            queue["results"] = results
            queue["errors"] = errors
            return _finish(queue, completed)

    queue["results"] = results
    queue["errors"] = errors

    # Check if this was the last one
    if idx + 1 >= total:
        return _finish(queue, completed)

    # Allow exactly one more interval tick
    progress_ui = _render_progress(idx + 1, total, results[-3:] if results else [])
    return (json.dumps(queue), progress_ui, no_update, n_intervals + 1,
            no_update, no_update, no_update, no_update, no_update, no_update)


def _finish(queue, completed):
    """Finalize: save results, stop interval, re-enable buttons."""
    completed = completed or []
    results = queue.get("results", [])
    errors = queue.get("errors", [])
    total = queue.get("total", 0)
    fatal = queue.get("fatal_error")

    if fatal and len(results) == 0:
        return (None,
                dbc.Alert(f"Fatal error: {fatal}", color="danger"),
                True, 0,  # stop interval, reset max_intervals
                no_update, no_update,
                False, False, False, {"display": "none"})

    if 2 not in completed:
        completed = sorted(set(completed + [2]))

    n_ok = len(results)
    n_err = len(errors)
    parts = [dbc.Alert(
        f"Completed {n_ok}/{total} comparisons. {n_err} error(s).",
        color="success" if not errors and not fatal else "warning",
    )]
    if fatal:
        parts.append(dbc.Alert(f"Stopped early: {fatal}", color="warning"))
    if errors:
        parts.append(dbc.Alert(
            html.Div([html.P("Errors:")] + [html.P(e, className="small mb-0") for e in errors[:5]]),
            color="warning",
        ))

    return (None,
            html.Div(parts),
            True, 0,  # stop interval, reset max_intervals
            json.dumps(results) if results else no_update,
            completed,
            False, False, False, {"display": "none"})


def _render_progress(done, total, recent_results, wait_msg=None):
    """Build a progress bar + recent results display."""
    pct = int(done / total * 100) if total > 0 else 0
    children = [
        dbc.Progress(
            value=pct,
            label=f"{done}/{total} ({pct}%)",
            striped=True,
            animated=True,
            className="mb-2",
            style={"height": "25px"},
        ),
    ]
    if wait_msg:
        children.append(dbc.Alert(wait_msg, color="warning", className="py-1 mb-1"))
    else:
        children.append(html.Small(f"Processing pair {done + 1} of {total}...", className="text-muted"))
    if recent_results:
        children.append(html.Div([
            html.Div(
                f"{r['item_a_id']} vs {r['item_b_id']} → "
                f"{'A' if r['harder'] == 'A' else 'B'} harder (conf={r.get('confidence', '?')})",
                className="small text-muted",
            )
            for r in recent_results
        ], className="mt-2"))
    return html.Div(children)


# ══════════════════════════════════════════════════════════════════════════════
# Download / Upload
# ══════════════════════════════════════════════════════════════════════════════

@callback(
    Output("btn-download-comparisons", "disabled"),
    Input("store-comparisons", "data"),
)
def toggle_download_button(comparisons_json):
    if not comparisons_json:
        return True
    try:
        data = json.loads(comparisons_json)
        return not (isinstance(data, list) and len(data) > 0)
    except Exception:
        return True


@callback(
    Output("download-comparisons", "data"),
    Input("btn-download-comparisons", "n_clicks"),
    State("store-comparisons", "data"),
    prevent_initial_call=True,
)
def download_comparisons(n_clicks, comparisons_json):
    if not comparisons_json:
        return no_update
    return dict(content=comparisons_json, filename="pretxt_comparisons.json")


@callback(
    Output("store-comparisons", "data", allow_duplicate=True),
    Output("store-completed-steps", "data", allow_duplicate=True),
    Output("upload-comparisons-feedback", "children"),
    Input("upload-comparisons", "contents"),
    State("upload-comparisons", "filename"),
    State("store-completed-steps", "data"),
    prevent_initial_call=True,
)
def upload_comparisons(contents, filename, completed):
    if not contents:
        return no_update, no_update, ""

    try:
        _, encoded = contents.split(",", 1)
        raw = base64.b64decode(encoded).decode("utf-8")
        data = json.loads(raw)
    except Exception as e:
        return no_update, no_update, dbc.Alert(
            f"Could not read file: {e}", color="danger", className="py-1 mb-0")

    if not isinstance(data, list) or len(data) == 0:
        return no_update, no_update, dbc.Alert(
            "File must contain a non-empty JSON array.", color="danger", className="py-1 mb-0")

    required_keys = {"item_a_id", "item_b_id", "harder"}
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            return no_update, no_update, dbc.Alert(
                f"Entry {i} is not an object.", color="danger", className="py-1 mb-0")
        missing = required_keys - row.keys()
        if missing:
            return no_update, no_update, dbc.Alert(
                f"Entry {i} missing keys: {missing}", color="danger", className="py-1 mb-0")

    completed = completed or []
    if 2 not in completed:
        completed = sorted(set(completed + [2]))

    return json.dumps(data), completed, dbc.Alert(
        f"Loaded {len(data)} comparisons from {filename}.",
        color="success", className="py-1 mb-0")
