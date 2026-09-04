"""
Interactive Plotly Dash dashboard for agricultural input ramp-up.

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
from agricultural_input_rampup import DEFAULT_FRACTION_FUNCTIONING  # noqa: E402
from agricultural_input_rampup import DEFAULT_STARTUP_PCT_OF_FULL  # noqa: E402
from agricultural_input_rampup import N_WEEKS  # noqa: E402
from agricultural_input_rampup import REFERENCE_ANNUAL_BUDGET_USD  # noqa: E402
from agricultural_input_rampup import allocation_summary_table  # noqa: E402
from agricultural_input_rampup import category_budget_totals  # noqa: E402
from agricultural_input_rampup import simulate_commodity  # noqa: E402

COMMODITY_BY_KEY = {c.key: c for c in COMMODITIES}
_ALLOCATION_DF = allocation_summary_table(REFERENCE_ANNUAL_BUDGET_USD)
_CATEGORY_TOTALS = category_budget_totals(REFERENCE_ANNUAL_BUDGET_USD)

# Dark theme palette (user-requested)
COLORS = {
    "regular": "#5eb8ff",
    "fast": "#ff9f6b",
    "bg": "#0b1220",
    "panel": "#141c2b",
    "plot": "#101826",
    "ink": "#e8eef8",
    "muted": "#9aa8bc",
    "accent": "#3dd6c6",
    "border": "#2a364a",
    "grid": "#2c3a52",
    "grid_minor": "#1a2436",
    "input": "#0f1724",
}

_FONT_HREF = (
    "https://fonts.googleapis.com/css2?"
    "family=DM+Sans:wght@400;500;600;700&"
    "family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap"
)
EXTERNAL_STYLES = [{"href": _FONT_HREF, "rel": "stylesheet"}]

_TABLE_STYLE_CELL = {
    "fontFamily": "DM Sans, sans-serif",
    "fontSize": 13,
    "padding": "8px 10px",
    "textAlign": "left",
    "backgroundColor": COLORS["panel"],
    "color": COLORS["ink"],
    "border": f"1px solid {COLORS['border']}",
}
_TABLE_STYLE_HEADER = {
    "fontWeight": "600",
    "backgroundColor": "#1a2436",
    "color": COLORS["ink"],
    "border": f"1px solid {COLORS['border']}",
}


def _fmt_money(value: float) -> str:
    if value >= 1e12:
        return f"${value / 1e12:.2f}T"
    if value >= 1e9:
        return f"${value / 1e9:.2f}B"
    if value >= 1e6:
        return f"${value / 1e6:.2f}M"
    return f"${value:,.0f}"


def _usd_to_billions(usd: float) -> float:
    return round(usd / 1e9, 2)


def _billions_to_usd(billions: float) -> float:
    return float(billions) * 1e9


def _axis_style(x_max: float | None = None) -> tuple[dict, dict]:
    """Shared dark-theme axes: yearly labels, soft major + minor grids."""
    xaxis = dict(
        title=dict(text="Years", standoff=12, font=dict(size=13, color=COLORS["muted"])),
        range=[-0.25, (x_max if x_max is not None else 9.5) + 0.15],
        tick0=0,
        dtick=1,
        tickangle=0,
        tickfont=dict(size=12, color=COLORS["muted"]),
        showgrid=True,
        gridcolor=COLORS["grid"],
        gridwidth=1,
        minor=dict(
            tickmode="auto",
            dtick=0.5,
            showgrid=True,
            gridcolor=COLORS["grid_minor"],
            gridwidth=0.6,
        ),
        zeroline=True,
        zerolinecolor="#4a5d78",
        zerolinewidth=1.2,
        showline=True,
        linecolor=COLORS["border"],
        mirror=True,
        ticks="outside",
        tickcolor=COLORS["border"],
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikethickness=1,
        spikecolor="#5a6f8c",
        spikedash="dot",
    )
    yaxis = dict(
        title=dict(standoff=10, font=dict(size=13, color=COLORS["muted"])),
        tickfont=dict(size=12, color=COLORS["muted"]),
        showgrid=True,
        gridcolor=COLORS["grid"],
        gridwidth=1,
        minor=dict(showgrid=True, gridcolor=COLORS["grid_minor"], gridwidth=0.6),
        zeroline=True,
        zerolinecolor="#4a5d78",
        zerolinewidth=1.2,
        showline=True,
        linecolor=COLORS["border"],
        mirror=True,
        ticks="outside",
        tickcolor=COLORS["border"],
        tickformat=".2~s",
        separatethousands=True,
    )
    return xaxis, yaxis


def _chart_layout(x_max: float | None = None, **kwargs) -> dict:
    xaxis, yaxis = _axis_style(x_max)
    base = dict(
        template="plotly_dark",
        paper_bgcolor=COLORS["panel"],
        plot_bgcolor=COLORS["plot"],
        font=dict(family="DM Sans, sans-serif", color=COLORS["ink"], size=13),
        title=dict(font=dict(size=16, color=COLORS["ink"]), x=0.01, xanchor="left"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.08,
            x=0,
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=dict(size=12, color=COLORS["muted"]),
        ),
        margin=dict(l=72, r=28, t=96, b=64),
        height=480,
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#1a2436",
            bordercolor=COLORS["border"],
            font=dict(family="DM Sans, sans-serif", size=12, color=COLORS["ink"]),
        ),
        xaxis=xaxis,
        yaxis=yaxis,
    )
    # Allow callers to deepen axis titles / ranges without wiping grid style.
    if "xaxis" in kwargs:
        merged_x = dict(xaxis)
        merged_x.update(kwargs.pop("xaxis"))
        kwargs["xaxis"] = merged_x
    if "yaxis" in kwargs:
        merged_y = dict(yaxis)
        merged_y.update(kwargs.pop("yaxis"))
        kwargs["yaxis"] = merged_y
    base.update(kwargs)
    return base


def _empty_fig(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**_chart_layout(title=title, height=420))
    return fig


def make_production_figure(result: dict[str, Any]) -> go.Figure:
    commodity = result["commodity"]
    weekly = result["weekly"]
    budget = result["budget"]
    x_max = float(weekly["Years"].max())
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=weekly["Years"],
            y=weekly["Regular new megatonnes/year"],
            mode="lines",
            name="Regular Construction",
            line=dict(color=COLORS["regular"], width=2.8, shape="hv"),
            hovertemplate="Regular: %{y:.1f} Mt/yr<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=weekly["Years"],
            y=weekly["Fast new megatonnes/year"],
            mode="lines",
            name="Fast Construction",
            line=dict(color=COLORS["fast"], width=2.8, shape="hv"),
            hovertemplate="Fast: %{y:.1f} Mt/yr<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[-0.25, 0.0],
            y=[commodity.current_mt_per_year, commodity.current_mt_per_year],
            mode="lines",
            name="Pre-disruption current (100%)",
            line=dict(color="#a8b8c8", width=2, dash="dot"),
            hovertemplate=(
                "Pre-disruption baseline: "
                f"{commodity.current_mt_per_year:g} Mt/yr<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        **_chart_layout(
            x_max=x_max,
            title=(
                f"{commodity.production_chart_title} — new factory production"
                f"<br><sup style='color:#9aa8bc'>Budget = {_fmt_money(budget)}/yr</sup>"
            ),
            yaxis=dict(
                title=dict(
                    text="New megatonnes / year",
                    standoff=10,
                    font=dict(size=13, color=COLORS["muted"]),
                )
            ),
        )
    )
    return fig


def _series_with_pre_disruption_multiple(years, multiples):
    """Prepend t<0 at 1.0 (full current), then vertical drop at t=0 to surviving baseline."""
    years = list(years)
    multiples = list(multiples)
    if not years:
        return [-0.25, 0.0], [1.0, 1.0]
    x = [-0.25, 0.0, 0.0] + years
    y = [1.0, 1.0, multiples[0]] + multiples
    return x, y


def make_multiple_figure(result: dict[str, Any]) -> go.Figure:
    commodity = result["commodity"]
    weekly = result["weekly"]
    budget = result["budget"]
    years = weekly["Years"]
    x_max = float(years.max())
    reg_x, reg_y = _series_with_pre_disruption_multiple(
        years, weekly["Regular Multiple of Current Production"]
    )
    fast_x, fast_y = _series_with_pre_disruption_multiple(
        years, weekly["Fast Multiple of Current Production"]
    )
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=reg_x,
            y=reg_y,
            mode="lines",
            name="Regular Construction",
            line=dict(color=COLORS["regular"], width=2.8),
            hovertemplate="Regular: %{y:.2f}× current<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=fast_x,
            y=fast_y,
            mode="lines",
            name="Fast Construction",
            line=dict(color=COLORS["fast"], width=2.8),
            hovertemplate="Fast: %{y:.2f}× current<extra></extra>",
        )
    )
    fig.update_layout(
        **_chart_layout(
            x_max=x_max,
            title=(
                f"{commodity.multiple_chart_title}"
                f"<br><sup style='color:#9aa8bc'>Budget = {_fmt_money(budget)}/yr</sup>"
            ),
            yaxis=dict(
                title=dict(
                    text=commodity.multiple_y_label,
                    standoff=10,
                    font=dict(size=13, color=COLORS["muted"]),
                )
            ),
        )
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
            f"End ~{horizon:.1f} yr new production (regular)",
            f"{last['Regular new megatonnes/year']:,.1f} Mt/yr",
        ),
        (
            f"End ~{horizon:.1f} yr new production (fast)",
            f"{last['Fast new megatonnes/year']:,.1f} Mt/yr",
        ),
        (
            "Multiple of current (regular)",
            f"{last['Regular Multiple of Current Production']:.2f}x",
        ),
        (
            "Multiple of current (fast)",
            f"{last['Fast Multiple of Current Production']:.2f}x",
        ),
        ("Current production baseline", f"{commodity.current_mt_per_year:g} Mt/yr"),
        ("Budget", _fmt_money(result["budget"])),
        (
            "Startup % of Fully Scaled Production",
            f"{result['startup_pct_of_full']:g}",
        ),
        (
            "fraction_functioning_after_disruption",
            f"{result['fraction_functioning']:g}",
        ),
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


def budget_input(commodity_key: str, label: str, default_usd: float) -> html.Div:
    """Budget entry in billions of USD/yr (converted to USD in the callback)."""
    default_b = _usd_to_billions(default_usd)
    return html.Div(
        [
            html.Label(label, htmlFor=f"budget-{commodity_key}"),
            dcc.Input(
                id=f"budget-{commodity_key}",
                type="number",
                value=default_b,
                min=0.01,
                step=0.1,
                debounce=True,
                className="budget-input",
                placeholder="e.g. 555.41",
            ),
            html.Div(f"Default {default_b:g} $B/yr", className="hint"),
        ],
        className="budget-field",
    )


app = Dash(
    __name__,
    external_stylesheets=EXTERNAL_STYLES,
    title="Agricultural Input Ramp-up",
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
            :root {
                --bg: #0b1220;
                --bg2: #101a2c;
                --panel: #141c2b;
                --ink: #e8eef8;
                --muted: #9aa8bc;
                --accent: #3dd6c6;
                --accent2: #5eb8ff;
                --border: #2a364a;
                --input: #0f1724;
                --danger: #ff8f8f;
            }
            body {
                margin: 0;
                min-height: 100vh;
                color: var(--ink);
                font-family: "DM Sans", sans-serif;
                background:
                    radial-gradient(1200px 600px at 10% -10%, rgba(61, 214, 198, 0.12), transparent 55%),
                    radial-gradient(900px 500px at 95% 0%, rgba(94, 184, 255, 0.14), transparent 50%),
                    linear-gradient(165deg, #0b1220 0%, #101a2c 45%, #0b1220 100%);
            }
            .page {
                max-width: 1200px;
                margin: 0 auto;
                padding: 32px 20px 56px;
            }
            .hero h1 {
                font-family: "Fraunces", serif;
                font-size: clamp(1.8rem, 3vw, 2.35rem);
                font-weight: 700;
                margin: 0 0 10px;
                letter-spacing: -0.02em;
                background: linear-gradient(120deg, #e8eef8 20%, #3dd6c6 70%, #5eb8ff 100%);
                -webkit-background-clip: text;
                background-clip: text;
                color: transparent;
            }
            .hero p {
                margin: 0;
                color: var(--muted);
                max-width: 54rem;
                line-height: 1.55;
            }
            .controls {
                margin-top: 28px;
                padding: 24px 24px 28px;
                background: rgba(20, 28, 43, 0.88);
                border: 1px solid var(--border);
                border-radius: 16px;
                box-shadow: 0 18px 50px rgba(0, 0, 0, 0.28);
                backdrop-filter: blur(8px);
            }
            .control-section + .control-section {
                margin-top: 28px;
                padding-top: 24px;
                border-top: 1px solid var(--border);
            }
            .section-title {
                margin: 0 0 14px;
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: var(--accent);
            }
            .budget-row {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 20px 18px;
                align-items: start;
            }
            .budget-field {
                display: flex;
                flex-direction: column;
                min-width: 0;
                min-height: 108px;
            }
            .budget-field label {
                display: block;
                font-weight: 600;
                margin-bottom: 8px;
                color: var(--ink);
                font-size: 0.9rem;
                line-height: 1.3;
                min-height: 2.4em;
            }
            .budget-input {
                width: 100%;
                box-sizing: border-box;
                padding: 11px 12px;
                border: 1px solid var(--border);
                border-radius: 10px;
                font-size: 1rem;
                font-family: "DM Sans", sans-serif;
                color: var(--ink) !important;
                background: var(--input);
                outline: none;
                color-scheme: dark;
                -moz-appearance: textfield;
                transition: border-color 0.15s ease, box-shadow 0.15s ease;
            }
            .budget-input::-webkit-outer-spin-button,
            .budget-input::-webkit-inner-spin-button {
                opacity: 0.55;
            }
            .budget-input:focus {
                border-color: var(--accent);
                box-shadow: 0 0 0 3px rgba(61, 214, 198, 0.18);
            }
            .hint {
                margin-top: 8px;
                font-size: 0.78rem;
                color: var(--muted);
                line-height: 1.4;
            }
            .actions {
                display: flex;
                gap: 12px;
                align-items: end;
                margin-top: 18px;
                flex-wrap: wrap;
            }
            .commodity-select {
                min-width: 280px;
            }
            .Select-control, .Select-menu-outer, .VirtualizedSelectOption,
            .Select-placeholder, .Select--single > .Select-control .Select-value {
                background: var(--input) !important;
                color: var(--ink) !important;
                border-color: var(--border) !important;
            }
            .Select-menu-outer {
                border-radius: 10px !important;
            }
            #commodity-select .Select-control {
                border-radius: 10px !important;
                min-height: 42px;
            }
            .run-btn {
                background: linear-gradient(135deg, #2bb8a8, #3dd6c6 55%, #5eb8ff);
                color: #061018;
                border: none;
                border-radius: 10px;
                padding: 12px 20px;
                font-size: 1rem;
                font-weight: 700;
                cursor: pointer;
                box-shadow: 0 8px 22px rgba(61, 214, 198, 0.25);
            }
            .run-btn:hover {
                filter: brightness(1.06);
            }
            .metrics {
                margin-top: 18px;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 10px;
            }
            .metric-card {
                background: rgba(20, 28, 43, 0.92);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 14px;
            }
            .metric-label {
                font-size: 0.76rem;
                color: var(--muted);
                margin-bottom: 6px;
                letter-spacing: 0.01em;
            }
            .metric-value {
                font-size: 1.05rem;
                font-weight: 650;
                color: var(--ink);
            }
            .charts {
                margin-top: 18px;
                display: grid;
                grid-template-columns: 1fr;
                gap: 16px;
            }
            .panel {
                background: rgba(20, 28, 43, 0.92);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 10px;
                box-shadow: 0 14px 36px rgba(0, 0, 0, 0.22);
            }
            .table-wrap {
                margin-top: 18px;
                background: rgba(20, 28, 43, 0.92);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 14px;
            }
            .table-wrap h3 {
                margin: 4px 0 12px;
                font-size: 1.05rem;
                color: var(--ink);
            }
            .status {
                margin-top: 12px;
                color: var(--muted);
                font-size: 0.9rem;
            }
            details {
                color: var(--muted);
            }
            details summary {
                cursor: pointer;
                color: var(--accent2);
                font-weight: 600;
            }
            @media (max-width: 1100px) {
                .budget-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                .budget-field { min-height: 0; }
                .budget-field label { min-height: 0; }
            }
            @media (max-width: 640px) {
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
                        html.H1("Agricultural Input Ramp-up Dashboard"),
                        html.P(
                            "N-fertilizer (NH3) is the reference template. "
                            f"The shared {_fmt_money(REFERENCE_ANNUAL_BUDGET_USD)}/yr "
                            "construction pot is split by equal-pace weights "
                            "(CAPEX $/tpa × current t/yr) across fertilizer, H2SO4, "
                            "and pesticides. Enter budgets in billion dollars per year. "
                            "Startup % / fraction_functioning defaults: 0.5 / 0.4. "
                            "Production chart shows new-factory output only."
                        ),
                        html.P(
                            (
                                "Equal-pace category totals: "
                                f"fertilizer {_fmt_money(_CATEGORY_TOTALS['fertilizer'])} "
                                f"({100 * _CATEGORY_TOTALS['fertilizer'] / REFERENCE_ANNUAL_BUDGET_USD:.1f}%), "
                                f"H2SO4 {_fmt_money(_CATEGORY_TOTALS['h2so4'])} "
                                f"({100 * _CATEGORY_TOTALS['h2so4'] / REFERENCE_ANNUAL_BUDGET_USD:.1f}%), "
                                f"pesticides {_fmt_money(_CATEGORY_TOTALS['pesticides'])} "
                                f"({100 * _CATEGORY_TOTALS['pesticides'] / REFERENCE_ANNUAL_BUDGET_USD:.1f}%)."
                            ),
                            className="hint",
                            style={"marginTop": "8px"},
                        ),
                    ],
                    className="hero",
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div("Fertilizer budgets ($B / yr)", className="section-title"),
                                html.Div(
                                    [
                                        budget_input(
                                            "nh3",
                                            "NH3 (Ammonia)",
                                            COMMODITY_BY_KEY[
                                                "nh3"
                                            ].default_annual_budget_usd,
                                        ),
                                        budget_input(
                                            "potassium",
                                            "Potassium (K)",
                                            COMMODITY_BY_KEY[
                                                "potassium"
                                            ].default_annual_budget_usd,
                                        ),
                                        budget_input(
                                            "phosphate",
                                            "Phosphate (P)",
                                            COMMODITY_BY_KEY[
                                                "phosphate"
                                            ].default_annual_budget_usd,
                                        ),
                                    ],
                                    className="budget-row",
                                ),
                            ],
                            className="control-section",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "H2SO4 & pesticide budgets ($B / yr)",
                                    className="section-title",
                                ),
                                html.Div(
                                    [
                                        budget_input(
                                            "h2so4",
                                            "Sulfuric acid (H2SO4)",
                                            COMMODITY_BY_KEY[
                                                "h2so4"
                                            ].default_annual_budget_usd,
                                        ),
                                        budget_input(
                                            "herbicide",
                                            "Herbicide",
                                            COMMODITY_BY_KEY[
                                                "herbicide"
                                            ].default_annual_budget_usd,
                                        ),
                                        budget_input(
                                            "insecticide",
                                            "Insecticide",
                                            COMMODITY_BY_KEY[
                                                "insecticide"
                                            ].default_annual_budget_usd,
                                        ),
                                        budget_input(
                                            "fungicide",
                                            "Fungicide",
                                            COMMODITY_BY_KEY[
                                                "fungicide"
                                            ].default_annual_budget_usd,
                                        ),
                                    ],
                                    className="budget-row",
                                ),
                            ],
                            className="control-section",
                        ),
                        html.Div(
                            [
                                html.Div("Scenario inputs", className="section-title"),
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Label(
                                                    "Startup % of Fully Scaled Production"
                                                ),
                                                dcc.Input(
                                                    id="startup-pct",
                                                    type="number",
                                                    value=DEFAULT_STARTUP_PCT_OF_FULL,
                                                    min=0.01,
                                                    max=1.0,
                                                    step=0.05,
                                                    debounce=True,
                                                    className="budget-input",
                                                ),
                                                html.Div(
                                                    f"Default {DEFAULT_STARTUP_PCT_OF_FULL:g} "
                                                    "(new plant starts at this share of full)",
                                                    className="hint",
                                                ),
                                            ],
                                            className="budget-field",
                                        ),
                                        html.Div(
                                            [
                                                html.Label(
                                                    "fraction_functioning_after_disruption"
                                                ),
                                                dcc.Input(
                                                    id="fraction-functioning",
                                                    type="number",
                                                    value=DEFAULT_FRACTION_FUNCTIONING,
                                                    min=0.01,
                                                    max=1.0,
                                                    step=0.05,
                                                    debounce=True,
                                                    className="budget-input",
                                                ),
                                                html.Div(
                                                    f"Default {DEFAULT_FRACTION_FUNCTIONING:g} "
                                                    "(surviving plants + new-build rate)",
                                                    className="hint",
                                                ),
                                            ],
                                            className="budget-field",
                                        ),
                                    ],
                                    className="budget-row",
                                ),
                            ],
                            className="control-section",
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
                                            style={
                                                "backgroundColor": COLORS["input"],
                                                "color": COLORS["ink"],
                                                "borderRadius": "10px",
                                            },
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
                        html.Details(
                            [
                                html.Summary(
                                    f"Equal-pace $758B allocation detail "
                                    f"(sum = {_fmt_money(REFERENCE_ANNUAL_BUDGET_USD)})"
                                ),
                                dash_table.DataTable(
                                    columns=[
                                        {"name": "Category", "id": "Category"},
                                        {"name": "Commodity", "id": "Commodity"},
                                        {
                                            "name": "Share %",
                                            "id": "SharePct",
                                            "type": "numeric",
                                            "format": {"specifier": ".2f"},
                                        },
                                        {
                                            "name": "Budget $B/yr",
                                            "id": "BudgetB",
                                            "type": "numeric",
                                            "format": {"specifier": ".2f"},
                                        },
                                    ],
                                    data=[
                                        {
                                            "Category": row["Category"],
                                            "Commodity": row["Commodity"],
                                            "SharePct": 100.0 * float(row["Share"]),
                                            "BudgetB": float(row["Budget USD/yr"])
                                            / 1e9,
                                        }
                                        for _, row in _ALLOCATION_DF.iterrows()
                                    ],
                                    style_table={
                                        "overflowX": "auto",
                                        "marginTop": "8px",
                                    },
                                    style_cell=_TABLE_STYLE_CELL,
                                    style_header=_TABLE_STYLE_HEADER,
                                ),
                            ],
                            style={"marginTop": "14px"},
                        ),
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
                            style_cell=_TABLE_STYLE_CELL,
                            style_header=_TABLE_STYLE_HEADER,
                            style_data_conditional=[
                                {
                                    "if": {"row_index": "odd"},
                                    "backgroundColor": "#1a2436",
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
    State("budget-h2so4", "value"),
    State("budget-herbicide", "value"),
    State("budget-insecticide", "value"),
    State("budget-fungicide", "value"),
    State("startup-pct", "value"),
    State("fraction-functioning", "value"),
)
def update_dashboard(
    n_clicks,
    commodity_key,
    budget_nh3_b,
    budget_k_b,
    budget_p_b,
    budget_h2so4_b,
    budget_herbicide_b,
    budget_insecticide_b,
    budget_fungicide_b,
    startup_pct,
    fraction_functioning,
):
    # UI values are billion $/yr; convert to USD for the model.
    budgets_b = {
        "nh3": budget_nh3_b,
        "potassium": budget_k_b,
        "phosphate": budget_p_b,
        "h2so4": budget_h2so4_b,
        "herbicide": budget_herbicide_b,
        "insecticide": budget_insecticide_b,
        "fungicide": budget_fungicide_b,
    }
    selected = commodity_key or "nh3"
    budget_b = budgets_b.get(selected)

    if budget_b is None:
        msg = "Enter a positive annual budget in billion dollars ($B / yr)."
        empty = _empty_fig("Waiting for budget")
        return empty, empty, [], [], msg

    try:
        budget_b = float(budget_b)
    except (TypeError, ValueError):
        empty = _empty_fig("Invalid budget")
        return empty, empty, [], [], "Budget must be a number in billion $/yr."

    if budget_b <= 0:
        msg = "Enter a positive annual budget in billion dollars ($B / yr)."
        empty = _empty_fig("Waiting for budget")
        return empty, empty, [], [], msg

    budget = _billions_to_usd(budget_b)

    if startup_pct is None:
        startup_pct = DEFAULT_STARTUP_PCT_OF_FULL
    if fraction_functioning is None:
        fraction_functioning = DEFAULT_FRACTION_FUNCTIONING

    try:
        startup_pct = float(startup_pct)
        fraction_functioning = float(fraction_functioning)
    except (TypeError, ValueError):
        empty = _empty_fig("Invalid fraction inputs")
        return (
            empty,
            empty,
            [],
            [],
            "Both fraction inputs must be numbers between 0 and 1.",
        )

    if not 0.0 < startup_pct <= 1.0 or not 0.0 < fraction_functioning <= 1.0:
        empty = _empty_fig("Invalid fraction inputs")
        return (
            empty,
            empty,
            [],
            [],
            "Startup % and fraction_functioning must each be between 0 and 1.",
        )

    commodity = COMMODITY_BY_KEY[selected]
    try:
        result = simulate_commodity(
            commodity,
            budget,
            startup_pct_of_full=startup_pct,
            fraction_functioning=fraction_functioning,
        )
    except Exception as exc:  # noqa: BLE001 - show in UI
        empty = _empty_fig("Error")
        return empty, empty, [], [], f"Error: {exc}"

    status = (
        f"Showing {commodity.label} at {_fmt_money(budget)}/yr "
        f"({budget_b:g} $B/yr), "
        f"startup%={startup_pct:g}, functioning={fraction_functioning:g} "
        f"(update #{n_clicks})."
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
    print("AGRICULTURAL INPUT RAMP-UP DASHBOARD")
    print("=" * 60)
    print(f"Starting server on http://{host}:{port}")
    print("Open that URL in your browser. Press Ctrl+C to stop.")
    app.run(debug=False, host=host, port=port)


if __name__ == "__main__":
    main()
