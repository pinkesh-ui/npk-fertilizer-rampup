"""Basic smoke tests for the NPK ramp-up model."""

from agricultural_input_rampup import COMMODITIES, simulate_commodity


def test_commodities_present():
    keys = {c.key for c in COMMODITIES}
    assert keys == {"nh3", "potassium", "phosphate"}


def test_simulate_nh3_default_budget():
    commodity = next(c for c in COMMODITIES if c.key == "nh3")
    result = simulate_commodity(commodity, commodity.default_annual_budget_usd)
    assert result["regular"].capex_per_plant > 0
    assert result["fast"].capex_per_plant > result["regular"].capex_per_plant
    assert len(result["weekly"]) == 490
    assert result["weekly"]["Regular megatonnes/year"].iloc[-1] > 0
    assert result["startup_fraction"] == 0.5


def test_startup_fraction_scales_plants():
    commodity = next(c for c in COMMODITIES if c.key == "nh3")
    budget = commodity.default_annual_budget_usd
    half = simulate_commodity(commodity, budget, startup_fraction=0.5)
    full = simulate_commodity(commodity, budget, startup_fraction=1.0)
    assert full["regular"].plants_per_year == 2 * half["regular"].plants_per_year
