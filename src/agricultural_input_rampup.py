"""
Agricultural fertilizer construction ramp-up model (N / P / K).

Reproduces CAPEX + Ramp-up calculations from:
  - Agricultural input ramp-up speed (3).xlsx                  → NH3 / N
  - potassium_fertilizer_ramp_up_speed_with_refs (1).xlsx     → Potash / K
  - phosphate_fertilizer_ramp_up_speed_with_refs_fixed_...xlsx → Phosphate / P

Prompts for Annual World Construction Budget for each commodity one by one,
then writes CSVs and PNG+SVG graphs into result/<commodity>/.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# matplotlib is only needed for offline PNG/SVG export (not the Dash dashboard)

# Shared construction / scaling assumptions (same across the three workbooks)
TARGET_PLANT_SIZE_TPD = 2000.0
COST_CAPACITY_EXPONENT = 0.7
FAST_CONSTRUCTION_COST_FACTOR = 1.47
FAST_CONSTRUCTION_SPEED_FACTOR = 0.32
STARTUP_FRACTION = 0.5
PLANNING_TIME_WEEKS = 4.0
N_WAVES = 12
N_WEEKS = 490  # Excel weekly series: weeks 1..490

OUTPUT_DIR = Path(__file__).resolve().parent
RESULT_DIR = OUTPUT_DIR / "result"


@dataclass(frozen=True)
class CommodityConfig:
    key: str
    label: str
    product_short: str
    current_mt_per_year: float
    default_annual_budget_usd: float
    production_chart_title: str
    multiple_chart_title: str
    multiple_y_label: str


@dataclass
class CapexResult:
    regular_capex_usd: float
    fast_capex_usd: float
    capital_efficiency_usd_per_tpa: float
    notes: dict[str, float]


@dataclass
class ScenarioParams:
    name: str
    capex_per_plant: float
    weeks_to_build: float
    plants_per_year: float
    plants_per_wave: float
    waves_per_year: float
    plants_per_week: float
    time_to_construct_wave_years: float
    startup_time_weeks: float
    startup_time_years: float
    planning_time_years: float
    scaled_production_tpw: float
    startup_production_tpw: float
    corrected_capex: float


def compute_nh3_capex() -> CapexResult:
    """From Agricultural input ramp-up speed CAPEX Calcs!B19 / H14."""
    ref_capacity_tpd = 1800.0
    ref_capex_eur = 323_000_000.0
    euro_inflation_2012_to_2025 = 1.3855340403694834
    eur_to_usd = 1.16
    scale = TARGET_PLANT_SIZE_TPD / ref_capacity_tpd
    regular = ref_capex_eur * euro_inflation_2012_to_2025 * eur_to_usd * (scale ** COST_CAPACITY_EXPONENT)
    fast = FAST_CONSTRUCTION_COST_FACTOR * regular
    return CapexResult(
        regular_capex_usd=regular,
        fast_capex_usd=fast,
        capital_efficiency_usd_per_tpa=regular / TARGET_PLANT_SIZE_TPD / 365.0,
        notes={
            "ref_capacity_tpd": ref_capacity_tpd,
            "ref_capex_eur_2012": ref_capex_eur,
            "euro_inflation_2012_to_2025": euro_inflation_2012_to_2025,
            "eur_to_usd": eur_to_usd,
            "plant_scale_factor": scale,
        },
    )


def compute_potassium_capex() -> CapexResult:
    """From potassium workbook CAPEX Calcs!B19 / H14 (Banio MOP PEA benchmark)."""
    ref_capacity_tpy = 800_000.0
    ref_capex_usd = 480_000_000.0
    target_tpy = TARGET_PLANT_SIZE_TPD * 365.0
    scale = target_tpy / ref_capacity_tpy
    regular = ref_capex_usd * (scale ** COST_CAPACITY_EXPONENT)
    fast = FAST_CONSTRUCTION_COST_FACTOR * regular
    return CapexResult(
        regular_capex_usd=regular,
        fast_capex_usd=fast,
        capital_efficiency_usd_per_tpa=regular / target_tpy,
        notes={
            "ref_capacity_tpy_mop": ref_capacity_tpy,
            "ref_capex_usd": ref_capex_usd,
            "target_tpy": target_tpy,
            "plant_scale_factor": scale,
        },
    )


def compute_phosphate_capex() -> CapexResult:
    """From phosphate workbook CAPEX Calcs!B19 / H14 (UNIDO TSP, 1978$→2025$)."""
    cpi_1978 = 65.2
    cpi_2025 = 321.051
    inflation = cpi_2025 / cpi_1978
    ref_capacity_tpd = 1200.0
    ref_total_investment_1978_usd = 70_000_000.0
    ref_capex_2025 = ref_total_investment_1978_usd * inflation
    scale = TARGET_PLANT_SIZE_TPD / ref_capacity_tpd
    regular = ref_capex_2025 * (scale ** COST_CAPACITY_EXPONENT)
    fast = FAST_CONSTRUCTION_COST_FACTOR * regular
    return CapexResult(
        regular_capex_usd=regular,
        fast_capex_usd=fast,
        capital_efficiency_usd_per_tpa=regular / TARGET_PLANT_SIZE_TPD / 365.0,
        notes={
            "cpi_1978": cpi_1978,
            "cpi_2025": cpi_2025,
            "inflation_multiplier": inflation,
            "ref_capacity_tpd_tsp": ref_capacity_tpd,
            "ref_total_investment_1978_usd": ref_total_investment_1978_usd,
            "ref_capex_2025_usd": ref_capex_2025,
            "plant_scale_factor": scale,
        },
    )


COMMODITIES: list[CommodityConfig] = [
    CommodityConfig(
        key="nh3",
        label="NH3 (Ammonia / N)",
        product_short="NH3",
        current_mt_per_year=240.0,
        default_annual_budget_usd=758_000_000_000.0,
        production_chart_title="NH3/YEAR PRODUCTION RAMP-UP",
        multiple_chart_title="MULTIPLE OF CURRENT NH3 PRODUCTION RAMP-UP",
        multiple_y_label="Multiple of current NH3 production",
    ),
    CommodityConfig(
        key="potassium",
        label="Potassium Fertilizer (K / Potash / MOP)",
        product_short="K",
        current_mt_per_year=41.6,
        default_annual_budget_usd=758_000_000_000.0 * 0.4,
        production_chart_title="K FERTILIZER/YEAR PRODUCTION RAMP-UP",
        multiple_chart_title="MULTIPLE OF CURRENT POTASH PRODUCTION RAMP-UP",
        multiple_y_label="Multiple of current potash production",
    ),
    CommodityConfig(
        key="phosphate",
        label="Phosphate Fertilizer (P / TSP / MAP+DAP)",
        product_short="P",
        current_mt_per_year=47.8,
        default_annual_budget_usd=758_000_000_000.0 * 0.4,
        production_chart_title="MAP+DAP/YEAR PRODUCTION RAMP-UP",
        multiple_chart_title="MULTIPLE OF CURRENT MAP+DAP PRODUCTION RAMP-UP",
        multiple_y_label="Multiple of current MAP+DAP production",
    ),
]

CAPEX_FUNCS = {
    "nh3": compute_nh3_capex,
    "potassium": compute_potassium_capex,
    "phosphate": compute_phosphate_capex,
}


def weeks_to_build_from_corrected_capex(corrected_capex: float) -> float:
    """Facility-cost construction duration (Excel: 10.774*LN(0.8*G6)-121.45)."""
    return 10.774 * math.log(0.8 * corrected_capex) - 121.45


def build_scenario(
    name: str,
    annual_budget: float,
    capex_per_plant: float,
    weeks_to_build: float,
) -> ScenarioParams:
    corrected_capex = capex_per_plant * (1.0 - 0.091 - 0.066)
    plants_per_year = annual_budget / capex_per_plant
    waves_per_year = 52.0 / weeks_to_build
    plants_per_wave = plants_per_year / waves_per_year
    plants_per_week = plants_per_year / 52.0

    scaled_production_tpw = TARGET_PLANT_SIZE_TPD * 7.0
    startup_production_tpw = STARTUP_FRACTION * scaled_production_tpw

    return ScenarioParams(
        name=name,
        capex_per_plant=capex_per_plant,
        weeks_to_build=weeks_to_build,
        plants_per_year=plants_per_year,
        plants_per_wave=plants_per_wave,
        waves_per_year=waves_per_year,
        plants_per_week=plants_per_week,
        time_to_construct_wave_years=weeks_to_build / 52.0,
        startup_time_weeks=weeks_to_build / 4.0,
        startup_time_years=(weeks_to_build / 4.0) / 52.0,
        planning_time_years=PLANNING_TIME_WEEKS / 52.0,
        scaled_production_tpw=scaled_production_tpw,
        startup_production_tpw=startup_production_tpw,
        corrected_capex=corrected_capex,
    )


def build_wave_table(
    scenario: ScenarioParams,
    current_mt_per_year: float,
    n_waves: int = N_WAVES,
) -> pd.DataFrame:
    rows: list[dict] = []
    prev_full_tpw = 0.0

    for wave in range(1, n_waves + 1):
        plants = scenario.plants_per_wave * wave

        if wave == 1:
            startup_tpw = scenario.startup_production_tpw * plants
        else:
            startup_tpw = prev_full_tpw + scenario.startup_production_tpw * scenario.plants_per_wave
        startup_years = scenario.time_to_construct_wave_years * wave + scenario.planning_time_years
        startup_mtpy = startup_tpw / 1_000_000.0 * 52.0
        rows.append(
            {
                "Wave": wave,
                "Production Level": "startup production",
                "Plants": plants,
                "tonnes/week": startup_tpw,
                "Weeks": startup_years * 52.0,
                "Years": startup_years,
                "Megatonnes/year": startup_mtpy,
                "Multiple of Current Production": startup_mtpy / current_mt_per_year + 1.0,
            }
        )

        full_tpw = plants * scenario.scaled_production_tpw
        full_years = startup_years + scenario.startup_time_years
        full_mtpy = full_tpw / 1_000_000.0 * 52.0
        rows.append(
            {
                "Wave": wave,
                "Production Level": "full production",
                "Plants": plants,
                "tonnes/week": full_tpw,
                "Weeks": full_years * 52.0,
                "Years": full_years,
                "Megatonnes/year": full_mtpy,
                "Multiple of Current Production": full_mtpy / current_mt_per_year + 1.0,
            }
        )
        prev_full_tpw = full_tpw

    return pd.DataFrame(rows)


def _step_lookup(week: float, thresholds: np.ndarray, values: np.ndarray) -> float:
    if week < thresholds[0]:
        return 0.0
    idx = int(np.searchsorted(thresholds, week, side="right") - 1)
    idx = max(0, min(idx, len(values) - 1))
    return float(values[idx])


def build_weekly_series(
    regular_waves: pd.DataFrame,
    fast_waves: pd.DataFrame,
    current_mt_per_year: float,
    n_weeks: int = N_WEEKS,
) -> pd.DataFrame:
    # Regular plant IFS in the workbooks covers waves 1..6 (enough for ~490 weeks)
    reg_plant_milestones = regular_waves[regular_waves["Production Level"] == "startup production"].iloc[:6]
    reg_prod_milestones = regular_waves.iloc[:12]  # through wave 6 full
    fast_plant_milestones = fast_waves[fast_waves["Production Level"] == "startup production"]
    fast_prod_milestones = fast_waves

    reg_plant_weeks = reg_plant_milestones["Weeks"].to_numpy(dtype=float)
    reg_plant_vals = reg_plant_milestones["Plants"].to_numpy(dtype=float)
    reg_prod_weeks = reg_prod_milestones["Weeks"].to_numpy(dtype=float)
    reg_prod_vals = reg_prod_milestones["tonnes/week"].to_numpy(dtype=float)

    fast_plant_weeks = fast_plant_milestones["Weeks"].to_numpy(dtype=float)
    fast_plant_vals = fast_plant_milestones["Plants"].to_numpy(dtype=float)
    fast_prod_weeks = fast_prod_milestones["Weeks"].to_numpy(dtype=float)
    fast_prod_vals = fast_prod_milestones["tonnes/week"].to_numpy(dtype=float)

    rows: list[dict] = []
    for week in range(1, n_weeks + 1):
        years = week / 52.0

        reg_plants = _step_lookup(week, reg_plant_weeks, reg_plant_vals)
        reg_tpw = _step_lookup(week, reg_prod_weeks, reg_prod_vals)
        reg_mtpy = reg_tpw / 1_000_000.0 * 52.0
        reg_mult = reg_mtpy / current_mt_per_year + 1.0

        fast_plants = _step_lookup(week, fast_plant_weeks, fast_plant_vals)
        fast_tpw = _step_lookup(week, fast_prod_weeks, fast_prod_vals)
        fast_mtpy = fast_tpw / 1_000_000.0 * 52.0
        fast_mult = fast_mtpy / current_mt_per_year + 1.0

        rows.append(
            {
                "Weeks": week,
                "Years": years,
                "Regular Plants": reg_plants,
                "Regular tonnes/week": reg_tpw,
                "Regular megatonnes/year": reg_mtpy,
                "Regular Multiple of Current Production": reg_mult,
                "Fast Plants": fast_plants,
                "Fast tonnes/week": fast_tpw,
                "Fast megatonnes/year": fast_mtpy,
                "Fast Multiple of Current Production": fast_mult,
            }
        )
    return pd.DataFrame(rows)


def _save_figure(fig, out_dir: Path, stem: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / f"{stem}.png"
    svg_path = out_dir / f"{stem}.svg"
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    return [png_path, svg_path]


def _style_axes(ax) -> None:
    """X every 3 months (0.25 yr); Y every 0.25 on the displayed scientific scale."""
    from matplotlib.ticker import MultipleLocator

    ax.xaxis.set_major_locator(MultipleLocator(0.25))
    y0, y1 = ax.get_ylim()
    span = max(y1 - y0, abs(y1), 1e-12)
    exp = int(np.floor(np.log10(span)))
    ax.yaxis.set_major_locator(MultipleLocator(0.25 * (10 ** exp)))
    ax.tick_params(axis="x", labelrotation=90, labelsize=7)
    ax.grid(True, which="major", alpha=0.3)


def plot_graphs(
    commodity: CommodityConfig,
    weekly: pd.DataFrame,
    annual_budget: float,
    out_dir: Path,
) -> list[Path]:
    import matplotlib.pyplot as plt

    paths: list[Path] = []
    years = weekly["Years"].to_numpy()
    budget_label = f"Budget = ${annual_budget:,.0f}/yr"
    stem = commodity.key

    fig1, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(years, weekly["Regular megatonnes/year"], label="Regular Construction", linewidth=2)
    ax1.plot(years, weekly["Fast megatonnes/year"], label="Fast Construction", linewidth=2)
    ax1.set_title(f"{commodity.production_chart_title}\n({budget_label})")
    ax1.set_xlabel("Years")
    ax1.set_ylabel("megatonnes/year")
    ax1.legend()
    _style_axes(ax1)
    fig1.tight_layout()
    paths.extend(_save_figure(fig1, out_dir, f"{stem}_production_rampup"))

    fig2, ax2 = plt.subplots(figsize=(12, 6))
    ax2.plot(
        years,
        weekly["Regular Multiple of Current Production"],
        label="Regular Construction",
        linewidth=2,
    )
    ax2.plot(
        years,
        weekly["Fast Multiple of Current Production"],
        label="Fast Construction",
        linewidth=2,
    )
    ax2.set_title(f"{commodity.multiple_chart_title}\n({budget_label})")
    ax2.set_xlabel("Years")
    ax2.set_ylabel(commodity.multiple_y_label)
    ax2.legend()
    _style_axes(ax2)
    fig2.tight_layout()
    paths.extend(_save_figure(fig2, out_dir, f"{stem}_multiple_rampup"))

    fig3, axes = plt.subplots(1, 2, figsize=(16, 6))
    axes[0].plot(years, weekly["Regular megatonnes/year"], label="Regular", linewidth=2)
    axes[0].plot(years, weekly["Fast megatonnes/year"], label="Fast", linewidth=2)
    axes[0].set_title(commodity.production_chart_title)
    axes[0].set_xlabel("Years")
    axes[0].set_ylabel("megatonnes/year")
    axes[0].legend()
    _style_axes(axes[0])

    axes[1].plot(years, weekly["Regular Multiple of Current Production"], label="Regular", linewidth=2)
    axes[1].plot(years, weekly["Fast Multiple of Current Production"], label="Fast", linewidth=2)
    axes[1].set_title(commodity.multiple_chart_title)
    axes[1].set_xlabel("Years")
    axes[1].set_ylabel(commodity.multiple_y_label)
    axes[1].legend()
    _style_axes(axes[1])

    fig3.suptitle(f"{commodity.label} ({budget_label})", fontsize=12)
    fig3.tight_layout()
    paths.extend(_save_figure(fig3, out_dir, f"{stem}_rampup_combined"))

    plt.close("all")
    return paths


def prompt_annual_budget(commodity: CommodityConfig) -> float:
    default = commodity.default_annual_budget_usd
    print("-" * 72)
    print(f"Annual World Construction Budget — {commodity.label}")
    print(f"(press Enter for default ${default:,.0f})")
    raw = input("> ").strip().replace(",", "").replace("$", "")
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise SystemExit(f"Invalid number for {commodity.label}: {raw!r}") from exc
    if value <= 0:
        raise SystemExit(f"Budget for {commodity.label} must be positive.")
    return value


def simulate_commodity(commodity: CommodityConfig, annual_budget: float) -> dict:
    """
    Run CAPEX + ramp-up for one commodity (no file I/O).

    Returns dict with: commodity, budget, capex, regular, fast, summary,
    regular_waves, fast_waves, weekly.
    """
    if annual_budget <= 0:
        raise ValueError("annual_budget must be positive")

    capex = CAPEX_FUNCS[commodity.key]()
    regular_weeks = weeks_to_build_from_corrected_capex(
        capex.regular_capex_usd * (1.0 - 0.091 - 0.066)
    )
    fast_weeks = regular_weeks * FAST_CONSTRUCTION_SPEED_FACTOR

    regular = build_scenario("Regular Construction", annual_budget, capex.regular_capex_usd, regular_weeks)
    fast = build_scenario("Fast Construction", annual_budget, capex.fast_capex_usd, fast_weeks)

    sanity_plants = (
        commodity.current_mt_per_year * 1_000_000.0 / (TARGET_PLANT_SIZE_TPD * 365.25)
    )

    summary = pd.DataFrame(
        [
            {"Parameter": "Commodity", "Regular": commodity.label, "Fast": commodity.label},
            {
                "Parameter": "Annual World Construction Budget (USD)",
                "Regular": annual_budget,
                "Fast": annual_budget,
            },
            {
                "Parameter": "Total Capital Investment Per Plant (USD)",
                "Regular": regular.capex_per_plant,
                "Fast": fast.capex_per_plant,
            },
            {
                "Parameter": "Corrected CAPEX for construction time method (USD)",
                "Regular": regular.corrected_capex,
                "Fast": fast.corrected_capex,
            },
            {
                "Parameter": "Number of Plants Per Year",
                "Regular": regular.plants_per_year,
                "Fast": fast.plants_per_year,
            },
            {
                "Parameter": "Weeks to Build at Facility Costs",
                "Regular": regular.weeks_to_build,
                "Fast": fast.weeks_to_build,
            },
            {
                "Parameter": "Waves Per Year",
                "Regular": regular.waves_per_year,
                "Fast": fast.waves_per_year,
            },
            {
                "Parameter": "Plants Per Wave",
                "Regular": regular.plants_per_wave,
                "Fast": fast.plants_per_wave,
            },
            {
                "Parameter": "Plants Per Week",
                "Regular": regular.plants_per_week,
                "Fast": fast.plants_per_week,
            },
            {
                "Parameter": "Single Facility Scaled Production (tonnes/week)",
                "Regular": regular.scaled_production_tpw,
                "Fast": fast.scaled_production_tpw,
            },
            {
                "Parameter": "Startup % of Fully Scaled Production",
                "Regular": STARTUP_FRACTION,
                "Fast": STARTUP_FRACTION,
            },
            {
                "Parameter": "Current production (Mt/yr)",
                "Regular": commodity.current_mt_per_year,
                "Fast": commodity.current_mt_per_year,
            },
            {
                "Parameter": "Sanity: plants needed for current production @ 2000 t/d",
                "Regular": sanity_plants,
                "Fast": sanity_plants,
            },
        ]
    )

    regular_waves = build_wave_table(regular, commodity.current_mt_per_year)
    fast_waves = build_wave_table(fast, commodity.current_mt_per_year)
    weekly = build_weekly_series(regular_waves, fast_waves, commodity.current_mt_per_year)

    return {
        "commodity": commodity,
        "budget": annual_budget,
        "capex": capex,
        "regular": regular,
        "fast": fast,
        "summary": summary,
        "regular_waves": regular_waves,
        "fast_waves": fast_waves,
        "weekly": weekly,
    }


def run_commodity(commodity: CommodityConfig, annual_budget: float, result_root: Path) -> list[Path]:
    out_dir = result_root / commodity.key
    out_dir.mkdir(parents=True, exist_ok=True)

    result = simulate_commodity(commodity, annual_budget)
    capex = result["capex"]
    regular = result["regular"]
    fast = result["fast"]
    summary = result["summary"]
    regular_waves = result["regular_waves"]
    fast_waves = result["fast_waves"]
    weekly = result["weekly"]

    summary_path = out_dir / "summary_parameters.csv"
    capex_path = out_dir / "capex_parameters.csv"
    regular_waves_path = out_dir / "wave_milestones_regular.csv"
    fast_waves_path = out_dir / "wave_milestones_fast.csv"
    weekly_path = out_dir / "weekly_timeseries.csv"

    summary.to_csv(summary_path, index=False)
    pd.DataFrame(
        [
            {
                "regular_capex_usd": capex.regular_capex_usd,
                "fast_capex_usd": capex.fast_capex_usd,
                "capital_efficiency_usd_per_tpa": capex.capital_efficiency_usd_per_tpa,
                **capex.notes,
            }
        ]
    ).to_csv(capex_path, index=False)
    regular_waves.to_csv(regular_waves_path, index=False)
    fast_waves.to_csv(fast_waves_path, index=False)
    weekly.to_csv(weekly_path, index=False)

    graph_paths = plot_graphs(commodity, weekly, annual_budget, out_dir)

    last = weekly.iloc[-1]
    print(f"\n=== {commodity.label} ===")
    print(f"Budget                         : ${annual_budget:,.0f}")
    print(f"Regular CAPEX / plant          : ${regular.capex_per_plant:,.0f}")
    print(f"Fast CAPEX / plant             : ${fast.capex_per_plant:,.0f}")
    print(f"Regular plants / year          : {regular.plants_per_year:,.1f}")
    print(f"Fast plants / year             : {fast.plants_per_year:,.1f}")
    print(f"Regular weeks to build         : {regular.weeks_to_build:,.2f}")
    print(f"Fast weeks to build            : {fast.weeks_to_build:,.2f}")
    print(
        f"End (~{N_WEEKS/52:.1f} yr) Regular : {last['Regular megatonnes/year']:,.1f} Mt/yr "
        f"({last['Regular Multiple of Current Production']:.2f}x)"
    )
    print(
        f"End (~{N_WEEKS/52:.1f} yr) Fast    : {last['Fast megatonnes/year']:,.1f} Mt/yr "
        f"({last['Fast Multiple of Current Production']:.2f}x)"
    )

    saved = [summary_path, capex_path, regular_waves_path, fast_waves_path, weekly_path, *graph_paths]
    for p in saved:
        print(f"  saved: {p}")
    return saved


def main() -> None:
    print("=" * 72)
    print("Agricultural Fertilizer Ramp-up Speed — N / P / K")
    print("=" * 72)
    print("Enter Annual World Construction Budget for each commodity one by one.")
    print()

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    budgets: dict[str, float] = {}
    for commodity in COMMODITIES:
        budgets[commodity.key] = prompt_annual_budget(commodity)

    print("\nRunning all three models...\n")
    for commodity in COMMODITIES:
        run_commodity(commodity, budgets[commodity.key], RESULT_DIR)

    print("\nDone. Graphs (PNG + SVG) and CSVs are under:")
    print(f"  {RESULT_DIR}")


if __name__ == "__main__":
    main()
