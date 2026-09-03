"""Basic smoke tests for the agricultural input ramp-up model."""

from agricultural_input_rampup import COMMODITIES
from agricultural_input_rampup import REFERENCE_ANNUAL_BUDGET_USD
from agricultural_input_rampup import allocate_equal_pace_budgets
from agricultural_input_rampup import category_budget_totals
from agricultural_input_rampup import simulate_commodity


def test_commodities_present():
    keys = {c.key for c in COMMODITIES}
    assert keys == {
        "nh3",
        "potassium",
        "phosphate",
        "h2so4",
        "herbicide",
        "insecticide",
        "fungicide",
    }


def test_equal_pace_allocation_sums_to_reference_pot():
    budgets = allocate_equal_pace_budgets(REFERENCE_ANNUAL_BUDGET_USD)
    assert abs(sum(budgets.values()) - REFERENCE_ANNUAL_BUDGET_USD) < 1.0
    # Fertilizer dominates; NH3 is the largest single share.
    cats = category_budget_totals()
    assert cats["fertilizer"] > cats["pesticides"] > cats["h2so4"]
    assert budgets["nh3"] == max(budgets.values())
    for commodity in COMMODITIES:
        assert abs(commodity.default_annual_budget_usd - budgets[commodity.key]) < 1.0


def test_simulate_nh3_default_budget():
    commodity = next(c for c in COMMODITIES if c.key == "nh3")
    result = simulate_commodity(commodity, commodity.default_annual_budget_usd)
    assert result["regular"].capex_per_plant > 0
    assert result["fast"].capex_per_plant > result["regular"].capex_per_plant
    assert len(result["weekly"]) == 490
    assert result["weekly"]["Regular megatonnes/year"].iloc[-1] > 0
    assert result["startup_pct_of_full"] == 0.5
    assert result["fraction_functioning"] == 0.4
    assert result["startup_fraction"] == 0.4  # back-compat alias


def test_baseline_starts_at_fraction_functioning():
    commodity = next(c for c in COMMODITIES if c.key == "nh3")
    ff = 0.4
    result = simulate_commodity(
        commodity, commodity.default_annual_budget_usd, fraction_functioning=ff
    )
    weekly = result["weekly"]
    first = weekly.iloc[0]
    surviving_mt = ff * commodity.current_mt_per_year
    assert first["Regular megatonnes/year"] == surviving_mt
    assert first["Regular Multiple of Current Production"] == ff
    assert first["Fast megatonnes/year"] == surviving_mt
    assert first["Fast Multiple of Current Production"] == ff


def test_fraction_functioning_scales_plants():
    commodity = next(c for c in COMMODITIES if c.key == "nh3")
    budget = commodity.default_annual_budget_usd
    half = simulate_commodity(commodity, budget, fraction_functioning=0.4)
    full = simulate_commodity(commodity, budget, fraction_functioning=0.8)
    assert full["regular"].plants_per_year == 2 * half["regular"].plants_per_year


def test_startup_pct_scales_startup_production_not_plants():
    commodity = next(c for c in COMMODITIES if c.key == "nh3")
    budget = commodity.default_annual_budget_usd
    half = simulate_commodity(commodity, budget, startup_pct_of_full=0.5)
    full = simulate_commodity(commodity, budget, startup_pct_of_full=1.0)
    assert half["regular"].plants_per_year == full["regular"].plants_per_year
    assert (
        full["regular"].startup_production_tpw
        == 2 * half["regular"].startup_production_tpw
    )


def test_excel_nh3_plants_per_year_at_half_fraction():
    """budget/CAPEX × 0.5 ≈ 678 plants/year at full $758B NH3 budget (Excel C16=0.5)."""
    commodity = next(c for c in COMMODITIES if c.key == "nh3")
    result = simulate_commodity(
        commodity,
        REFERENCE_ANNUAL_BUDGET_USD,
        startup_pct_of_full=0.5,
        fraction_functioning=0.5,
    )
    assert 650 < result["regular"].plants_per_year < 710
    assert result["regular"].startup_production_tpw == (
        result["regular"].scaled_production_tpw * 0.5
    )


def test_h2so4_and_pesticides_use_shared_fraction_defaults():
    for key in ("h2so4", "herbicide", "insecticide", "fungicide"):
        commodity = next(c for c in COMMODITIES if c.key == key)
        result = simulate_commodity(commodity, commodity.default_annual_budget_usd)
        assert result["startup_pct_of_full"] == 0.5
        assert result["fraction_functioning"] == 0.4
        first = result["weekly"].iloc[0]
        assert first["Regular Multiple of Current Production"] == 0.4
        assert first["Regular new megatonnes/year"] == 0.0
        assert result["regular"].weeks_to_build > 0
        assert result["fast"].weeks_to_build < result["regular"].weeks_to_build
