"""
Interactive Plotly Dash dashboard for N / P / K fertilizer ramp-up.

Usage:
    python dashboard.py
    Then open http://127.0.0.1:8050

For Render / gunicorn:
    gunicorn dashboard:server --bind 0.0.0.0:$PORT
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dash_table, dcc, html

# Allow `python dashboard.py` from repo root (model lives in src/)
_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agricultural_input_rampup import COMMODITIES  # noqa: E402
from agricultural_input_rampup import N_WEEKS  # noqa: E402
from agricultural_input_rampup import simulate_commodity  # noqa: E402

COMMODITY_BY_KEY = {c.key: c for c in COMMODITIES}

COLORS = {
    "regular": "#1f6aa5",
    "fast": "#c45c26",
    "bg": "#f7f4ef",
    "panel": "#ffffff",
    "ink": "#1c1b19",
    "muted": "#5c574f",
    "accent": "#2f5d50",
    "border": "#d9d2c5",
}

_FONT_HREF = (
    "https://fonts.googleapis.com/css2?"
    "family=IBM+Plex+Sans:wght@400;500;600&"
    "family=IBM+Plex+Serif:wght@600&display=swap"
)
EXTERNAL_STYLES = [{"href": _FONT_HREF, "rel": "stylesheet"}]


def _fmt_money(value: float) -> str:
    if value >= 1e12:
        return f"${value / 1e12:.2f}T"
    if value >= 1e9:
        return f"${value / 1e9:.2f}B"
    if value >= 1e6:
        return f"${value / 1e6:.2f}M"
    return f"${value:,.0f}"


def _empty_fig(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        template="plotly_white",
        paper_bgcolor=COLORS["panel"],
        plot_bgcolor=COLORS["panel"],
        font=dict(family="IBM Plex Sans, sans-serif", color=COLORS["ink"]),
        margin=dict(l=50, r=20, t=60, b=50),
        height=420,
    )
    return fig


def make_production_figure(result: dict[str, Any]) -> go.Figure:
    commodity = result["commodity"]
    weekly = result["weekly"]
    budget = result["budget"]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=weekly["Years"],
            y=weekly["Regular megatonnes/year"],
            mode="lines",
            name="Regular Construction",
            line=dict(color=COLORS["regular"], width=2.5, shape="hv"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=weekly["Years"],
            y=weekly["Fast megatonnes/year"],
            mode="lines",
            name="Fast Construction",
            line=dict(color=COLORS["fast"], width=2.5, shape="hv"),
        )
    )
    fig.update_layout(
        title=f"{commodity.production_chart_title}<br><sup>Budget = {_fmt_money(budget)}/yr</sup>",
        xaxis_title="Years",
        yaxis_title="megatonnes/year",
        template="plotly_white",
        paper_bgcolor=COLORS["panel"],
        plot_bgcolor=COLORS["panel"],
        font=dict(family="IBM Plex Sans, sans-serif", color=COLORS["ink"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=60, r=20, t=80, b=50),
        height=440,
        xaxis=dict(dtick=0.25, tickangle=-90, showgrid=True, gridcolor="#ece7de"),
        yaxis=dict(showgrid=True, gridcolor="#ece7de", tickformat=".2~s"),
    )
    return fig


def make_multiple_figure(result: dict[str, Any]) -> go.Figure:
    commodity = result["commodity"]
    weekly = result["weekly"]
    budget = result["budget"]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=weekly["Years"],
            y=weekly["Regular Multiple of Current Production"],
            mode="lines",
            name="Regular Construction",
            line=dict(color=COLORS["regular"], width=2.5, shape="hv"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=weekly["Years"],
            y=weekly["Fast Multiple of Current Production"],
            mode="lines",
            name="Fast Construction",
            line=dict(color=COLORS["fast"], width=2.5, shape="hv"),
        )
    )
    fig.update_layout(
        title=f"{commodity.multiple_chart_title}<br><sup>Budget = {_fmt_money(budget)}/yr</sup>",
        xaxis_title="Years",
        yaxis_title=commodity.multiple_y_label,
        template="plotly_white",
        paper_bgcolor=COLORS["panel"],
        plot_bgcolor=COLORS["panel"],
        font=dict(family="IBM Plex Sans, sans-serif", color=COLORS["ink"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=60, r=20, t=80, b=50),
        height=440,
        xaxis=dict(dtick=0.25, tickangle=-90, showgrid=True, gridcolor="#ece7de"),
        yaxis=dict(showgrid=True, gridcolor="#ece7de", tickformat=".2~s"),
    )
    return fig


def make_metrics(result: dict[str, Any]) -> list:
    commodity = result["commodity"]
    regular = result["regular"]
    fast = result["fast"]
    weekly = result["weekly"]
    last = weekly.iloc[-1]
    horizon = N_WEEKS / 52.0

    cards = [
        ("CAPEX / plant (regular)", _fmt_money(regular.capex_per_plant)),
        ("CAPEX / plant (fast)", _fmt_money(fast.capex_per_plant)),
        ("Plants / year (regular)", f"{regular.plants_per_year:,.1f}"),
        ("Plants / year (fast)", f"{fast.plants_per_year:,.1f}"),
        ("Weeks to build (regular)", f"{regular.weeks_to_build:,.2f}"),
        ("Weeks to build (fast)", f"{fast.weeks_to_build:,.2f}"),
        (
            f"End ~{horizon:.1f} yr production (regular)",
            f"{last['Regular megatonnes/year']:,.1f} Mt/yr",
        ),
        (
            f"End ~{horizon:.1f} yr production (fast)",
            f"{last['Fast megatonnes/year']:,.1f} Mt/yr",
        ),
        (
            "Multiple of current (regular)",
            f"{last['Regular Multiple of Current Production']:.2f}×",
        ),
        (
            "Multiple of current (fast)",
            f"{last['Fast Multiple of Current Production']:.2f}×",
        ),
        ("Current production baseline", f"{commodity.current_mt_per_year:g} Mt/yr"),
        ("Budget", _fmt_money(result["budget"])),
    ]

    return [
        html.Div(
            [
                html.Div(label, className="metric-label"),
                html.Div(value, className="metric-value"),
            ],
            className="metric-card",
        )
        for label, value in cards
    ]


def summary_table_data(result: dict[str, Any]) -> list[dict]:
    df = result["summary"].copy()

    def _cell(v: Any) -> str:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if abs(v) >= 1e6:
                return f"{v:,.2f}"
            return f"{v:g}"
        return str(v)

    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "Parameter": row["Parameter"],
                "Regular": _cell(row["Regular"]),
                "Fast": _cell(row["Fast"]),
            }
        )
    return rows


def budget_input(commodity_key: str, label: str, default: float) -> html.Div:
    return html.Div(
        [
            html.Label(label, htmlFor=f"budget-{commodity_key}"),
            dcc.Input(
                id=f"budget-{commodity_key}",
                type="number",
                value=default,
                min=1,
                step=1e9,
                debounce=True,
                className="budget-input",
            ),
            html.Div(f"Default {_fmt_money(default)}/yr", className="hint"),
        ],
        className="budget-field",
    )


app = Dash(
    __name__, external_stylesheets=EXTERNAL_STYLES, title="NPK Fertilizer Ramp-up"
)
server = app.server

app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                margin: 0;
                background: #f7f4ef;
                color: #1c1b19;
                font-family: "IBM Plex Sans", sans-serif;
            }
            .page {
                max-width: 1200px;
                margin: 0 auto;
                padding: 28px 20px 48px;
            }
            .hero h1 {
                font-family: "IBM Plex Serif", serif;
                font-size: 2rem;
                margin: 0 0 8px;
                color: #2f5d50;
            }
            .hero p {
                margin: 0;
                color: #5c574f;
                max-width: 52rem;
                line-height: 1.45;
            }
            .controls {
                margin-top: 24px;
                padding: 18px;
                background: #ffffff;
                border: 1px solid #d9d2c5;
            }
            .budget-row {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 16px;
            }
            .budget-field label {
                display: block;
                font-weight: 600;
                margin-bottom: 6px;
            }
            .budget-input {
                width: 100%;
                box-sizing: border-box;
                padding: 10px 12px;
                border: 1px solid #d9d2c5;
                border-radius: 0;
                font-size: 1rem;
                background: #fff;
            }
            .hint {
                margin-top: 4px;
                font-size: 0.8rem;
                color: #5c574f;
            }
            .actions {
                display: flex;
                gap: 12px;
                align-items: end;
                margin-top: 16px;
                flex-wrap: wrap;
            }
            .commodity-select {
                min-width: 260px;
            }
            .run-btn {
                background: #2f5d50;
                color: #fff;
                border: none;
                padding: 11px 18px;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
            }
            .run-btn:hover { background: #24483e; }
            .metrics {
                margin-top: 18px;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 10px;
            }
            .metric-card {
                background: #ffffff;
                border: 1px solid #d9d2c5;
                padding: 12px;
            }
            .metric-label {
                font-size: 0.78rem;
                color: #5c574f;
                margin-bottom: 4px;
            }
            .metric-value {
                font-size: 1.05rem;
                font-weight: 600;
            }
            .charts {
                margin-top: 18px;
                display: grid;
                grid-template-columns: 1fr;
                gap: 16px;
            }
            .panel {
                background: #ffffff;
                border: 1px solid #d9d2c5;
                padding: 8px;
            }
            .table-wrap {
                margin-top: 18px;
                background: #ffffff;
                border: 1px solid #d9d2c5;
                padding: 12px;
            }
            .table-wrap h3 {
                margin: 4px 0 12px;
                font-size: 1.05rem;
            }
            .status {
                margin-top: 10px;
                color: #5c574f;
                font-size: 0.9rem;
            }
            @media (max-width: 900px) {
                .budget-row { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""

app.layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [
                        html.H1("Fertilizer Ramp-up Dashboard"),
                        html.P(
                            "Set Annual World Construction Budget for NH3, "
                            "potassium, and phosphate, then explore regular "
                            "vs fast construction ramp-up curves."
                        ),
                    ],
                    className="hero",
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                budget_input(
                                    "nh3",
                                    "NH3 (Ammonia) budget (USD/yr)",
                                    COMMODITY_BY_KEY["nh3"].default_annual_budget_usd,
                                ),
                                budget_input(
                                    "potassium",
                                    "Potassium (K) budget (USD/yr)",
                                    COMMODITY_BY_KEY[
                                        "potassium"
                                    ].default_annual_budget_usd,
                                ),
                                budget_input(
                                    "phosphate",
                                    "Phosphate (P) budget (USD/yr)",
                                    COMMODITY_BY_KEY[
                                        "phosphate"
                                    ].default_annual_budget_usd,
                                ),
                            ],
                            className="budget-row",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Label("Commodity to display"),
                                        dcc.Dropdown(
                                            id="commodity-select",
                                            options=[
                                                {"label": c.label, "value": c.key}
                                                for c in COMMODITIES
                                            ],
                                            value="nh3",
                                            clearable=False,
                                            className="commodity-select",
                                        ),
                                    ]
                                ),
                                html.Button(
                                    "Update charts",
                                    id="run-btn",
                                    n_clicks=0,
                                    className="run-btn",
                                ),
                            ],
                            className="actions",
                        ),
                        html.Div(id="status", className="status"),
                    ],
                    className="controls",
                ),
                html.Div(id="metrics", className="metrics"),
                html.Div(
                    [
                        html.Div(dcc.Graph(id="production-chart"), className="panel"),
                        html.Div(dcc.Graph(id="multiple-chart"), className="panel"),
                    ],
                    className="charts",
                ),
                html.Div(
                    [
                        html.H3("Scenario parameters"),
                        dash_table.DataTable(
                            id="summary-table",
                            columns=[
                                {"name": "Parameter", "id": "Parameter"},
                                {"name": "Regular", "id": "Regular"},
                                {"name": "Fast", "id": "Fast"},
                            ],
                            data=[],
                            style_table={"overflowX": "auto"},
                            style_cell={
                                "fontFamily": "IBM Plex Sans, sans-serif",
                                "fontSize": 13,
                                "padding": "8px 10px",
                                "border": f"1px solid {COLORS['border']}",
                            },
                            style_header={
                                "fontWeight": 600,
                                "backgroundColor": "#efeae1",
                            },
                            style_data_conditional=[
                                {
                                    "if": {"row_index": "odd"},
                                    "backgroundColor": "#faf8f4",
                                }
                            ],
                        ),
                    ],
                    className="table-wrap",
                ),
            ],
            className="page",
        )
    ]
)


@app.callback(
    Output("production-chart", "figure"),
    Output("multiple-chart", "figure"),
    Output("metrics", "children"),
    Output("summary-table", "data"),
    Output("status", "children"),
    Input("run-btn", "n_clicks"),
    Input("commodity-select", "value"),
    State("budget-nh3", "value"),
    State("budget-potassium", "value"),
    State("budget-phosphate", "value"),
)
def update_dashboard(n_clicks, commodity_key, budget_nh3, budget_k, budget_p):
    budgets = {
        "nh3": budget_nh3,
        "potassium": budget_k,
        "phosphate": budget_p,
    }
    selected = commodity_key or "nh3"
    budget = budgets.get(selected)

    if budget is None or float(budget) <= 0:
        msg = "Enter a positive Annual World Construction Budget."
        empty = _empty_fig("Waiting for budget")
        return empty, empty, [], [], msg

    commodity = COMMODITY_BY_KEY[selected]
    try:
        result = simulate_commodity(commodity, float(budget))
    except Exception as exc:  # noqa: BLE001 - show in UI
        empty = _empty_fig("Error")
        return empty, empty, [], [], f"Error: {exc}"

    status = (
        f"Showing {commodity.label} at {_fmt_money(float(budget))}/yr "
        f"(update #{n_clicks}). Change commodity or budgets, then click Update charts."
    )
    return (
        make_production_figure(result),
        make_multiple_figure(result),
        make_metrics(result),
        summary_table_data(result),
        status,
    )


def main() -> None:
    host = os.environ.get("DASH_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", os.environ.get("DASH_PORT", "8050")))
    print("=" * 60)
    print("NPK FERTILIZER RAMP-UP DASHBOARD")
    print("=" * 60)
    print(f"Starting server on http://{host}:{port}")
    print("Open that URL in your browser. Press Ctrl+C to stop.")
    app.run(debug=False, host=host, port=port)


if __name__ == "__main__":
    main()
