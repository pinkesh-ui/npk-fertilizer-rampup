"""
Build an ALLFED-format workbook (CAPEX Calcs + Ramp-up Calcs per commodity)
matching ALLFED N Fertiliser Scale-Up_code_matched.xlsx, using current model values.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.chart.series import SeriesLabel
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agricultural_input_rampup import (  # noqa: E402
    CAPEX_FUNCS,
    COMMODITIES,
    COST_CAPACITY_EXPONENT,
    DEFAULT_FRACTION_FUNCTIONING,
    DEFAULT_STARTUP_PCT_OF_FULL,
    FAST_CONSTRUCTION_COST_FACTOR,
    FAST_CONSTRUCTION_SPEED_FACTOR,
    NH3_TARGET_PLANT_SIZE_TPD,
    allocate_equal_pace_budgets,
)

TEMPLATE = Path(
    r"c:\Users\Admin\Downloads\ALLFED N Fertiliser Scale-Up_code_matched.xlsx"
)

# Short sheet-name prefixes (Excel 31-char limit)
META = {
    "nh3": {
        "prefix": "NH3",
        "title": "NH3",
        "product": "NH3",
        "size_unit": "t/day",
        "capex_note": "EuroChem Kingisepp benchmark (updated)",
    },
    "potassium": {
        "prefix": "K",
        "title": "K (Potash)",
        "product": "K",
        "size_unit": "t/day",
        "capex_note": "Banio MOP PEA benchmark",
    },
    "phosphate": {
        "prefix": "P",
        "title": "P (MAP+DAP)",
        "product": "P",
        "size_unit": "t/day",
        "capex_note": "UNIDO TSP 1978$ inflated to 2025$",
    },
    "h2so4": {
        "prefix": "H2SO4",
        "title": "H2SO4",
        "product": "H2SO4",
        "size_unit": "t/day",
        "capex_note": "UNIDO-based H2SO4 workbook",
    },
    "herbicide": {
        "prefix": "Herb",
        "title": "Herbicide",
        "product": "Herbicide",
        "size_unit": "t/yr",
        "capex_note": "Pesticide scale-up assumptions 2026",
    },
    "insecticide": {
        "prefix": "Ins",
        "title": "Insecticide",
        "product": "Insecticide",
        "size_unit": "t/yr",
        "capex_note": "Pesticide scale-up assumptions 2026",
    },
    "fungicide": {
        "prefix": "Fun",
        "title": "Fungicide",
        "product": "Fungicide",
        "size_unit": "t/yr",
        "capex_note": "Pesticide scale-up assumptions 2026",
    },
}

ORDER = [
    "nh3",
    "phosphate",
    "potassium",
    "herbicide",
    "fungicide",
    "insecticide",
    "h2so4",
]


def _replace_formulas(ws, old: str, new: str) -> None:
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and old in cell.value:
                cell.value = cell.value.replace(old, new)


def _write_capex_sheet(ws, key: str, commodity) -> float:
    """Rewrite CAPEX Calcs sheet to current model inputs; return target plant size in t/day."""
    capex = CAPEX_FUNCS[key]()
    notes = capex.notes
    meta = META[key]
    target_tpd = commodity.target_plant_size_tpd

    # Clear old content in main block (keep sheet, rewrite clean block)
    for r in range(1, 32):
        for c in range(1, 9):
            ws.cell(r, c).value = None

    ws["A1"] = f"{meta['title']} CAPEX Calcs"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = meta["capex_note"]

    ws["F11"] = "Fast construction cost factor"
    ws["H11"] = FAST_CONSTRUCTION_COST_FACTOR
    ws["F12"] = "Fast construction speed factor"
    ws["H12"] = FAST_CONSTRUCTION_SPEED_FACTOR

    if key == "nh3":
        ws["A12"] = "Reference Plant Capacity (tonnes/day)"
        ws["B12"] = notes["ref_capacity_tpd"]
        ws["A13"] = "Reference Plant CAPEX (USD)"
        ws["B13"] = notes["ref_capex_usd_2015"]
        ws["C13"] = "(2015)"
        ws["A14"] = "USD inflation conversion"
        ws["B14"] = notes["usd_inflation_conversion_2025"]
        ws["C14"] = "(2025)"
        ws["A15"] = "Source"
        ws["B15"] = (
            "https://www.process-worldwide.com/eurochem-opens-one-billion-dollar-"
            "ammonia-plant-in-kingisepp-a-836843/"
        )
        ws["A16"] = f"Target Plant Size (tonne{meta['product']}/day)"
        ws["B16"] = NH3_TARGET_PLANT_SIZE_TPD
        ws["A17"] = "Plant scale factor"
        ws["B17"] = notes["plant_scale_factor"]
        ws["C17"] = "(sheet shows 1.04)"
        ws["A18"] = "Cost-Capacity Exponent"
        ws["B18"] = COST_CAPACITY_EXPONENT
        ws["A19"] = "Target Plant CAPEX (USD)"
        ws["B19"] = capex.regular_capex_usd
        ws["D19"] = "<-- Using this estimate"
        target_tpd = NH3_TARGET_PLANT_SIZE_TPD
    elif key in ("herbicide", "insecticide", "fungicide"):
        ws["A12"] = "Reference capacity (t/yr)"
        ws["B12"] = notes["ref_capacity_tpy"]
        ws["A13"] = "Reference CAPEX (USD)"
        ws["B13"] = notes["ref_capex_usd"]
        ws["A14"] = "Target plant size (t/yr)"
        ws["B14"] = notes["target_tpy"]
        ws["A15"] = "Plant scale factor"
        ws["B15"] = notes["plant_scale_factor"]
        ws["A16"] = "Target Plant Size (tonnes/day) [= t/yr / 365]"
        ws["B16"] = target_tpd
        ws["A17"] = "Cost-Capacity Exponent"
        ws["B17"] = COST_CAPACITY_EXPONENT
        ws["A18"] = "(for reference)"
        ws["A19"] = "Target Plant CAPEX (USD)"
        ws["B19"] = capex.regular_capex_usd
        ws["D19"] = "<-- Using this estimate"
    elif key == "potassium":
        ws["A12"] = "Reference capacity (t/yr MOP)"
        ws["B12"] = notes["ref_capacity_tpy_mop"]
        ws["A13"] = "Reference CAPEX (USD)"
        ws["B13"] = notes["ref_capex_usd"]
        ws["A14"] = "Target capacity (t/yr)"
        ws["B14"] = notes["target_tpy"]
        ws["A15"] = "Plant scale factor"
        ws["B15"] = notes["plant_scale_factor"]
        ws["A16"] = "Target Plant Size (tonnes/day)"
        ws["B16"] = target_tpd
        ws["A17"] = "Cost-Capacity Exponent"
        ws["B17"] = COST_CAPACITY_EXPONENT
        ws["A19"] = "Target Plant CAPEX (USD)"
        ws["B19"] = capex.regular_capex_usd
        ws["D19"] = "<-- Using this estimate"
    elif key == "phosphate":
        ws["A12"] = "Reference capacity (t/day TSP)"
        ws["B12"] = notes["ref_capacity_tpd_tsp"]
        ws["A13"] = "Reference total investment (1978 USD)"
        ws["B13"] = notes["ref_total_investment_1978_usd"]
        ws["A14"] = "Inflation multiplier (1978→2025)"
        ws["B14"] = notes["inflation_multiplier"]
        ws["A15"] = "Reference CAPEX (2025 USD)"
        ws["B15"] = notes["ref_capex_2025_usd"]
        ws["A16"] = "Target Plant Size (tonnes/day)"
        ws["B16"] = target_tpd
        ws["A17"] = "Plant scale factor"
        ws["B17"] = notes["plant_scale_factor"]
        ws["A18"] = "Cost-Capacity Exponent"
        ws["B18"] = COST_CAPACITY_EXPONENT
        ws["A19"] = "Target Plant CAPEX (USD)"
        ws["B19"] = capex.regular_capex_usd
        ws["D19"] = "<-- Using this estimate"
    else:  # h2so4
        ws["A12"] = "Reference capacity (t/day)"
        ws["B12"] = notes["ref_capacity_tpd"]
        ws["A13"] = "Reference CAPEX (USD)"
        ws["B13"] = notes["ref_capex_usd"]
        ws["A14"] = "Cost-Capacity Exponent"
        ws["B14"] = notes["cost_capacity_exponent"]
        ws["A15"] = "Plant scale factor"
        ws["B15"] = notes["plant_scale_factor"]
        ws["A16"] = "Target Plant Size (tonnes/day)"
        ws["B16"] = notes["target_tpd"]
        target_tpd = notes["target_tpd"]
        ws["A19"] = "Target Plant CAPEX (USD)"
        ws["B19"] = capex.regular_capex_usd
        ws["D19"] = "<-- Using this estimate"

    ws["F14"] = "Fast construction (24/7) CAPEX"
    ws["H14"] = f"=H11*B19"
    ws["A21"] = "Capital efficiency"
    ws["B21"] = f"=B19/B16/365"
    ws["C21"] = "$/tpa installed"

    # Compatibility cell used by Ramp-up C13 (= F5*7)
    ws["D5"] = f"Target Plant Size (tonne{meta['product']}/day)"
    ws["F5"] = target_tpd
    return target_tpd


def _add_rampup_charts(ws, product: str) -> None:
    """Add production + multiple charts (template layout) if missing."""
    # Weekly series occupies rows 51..540 (490 weeks); helper multiple data U50:W541
    last_week_row = 540
    # Remove existing charts so re-runs are clean for copied sheets
    ws._charts = []

    prod = LineChart()
    prod.title = f"{product}/YEAR PRODUCTION RAMP-UP"
    prod.style = 10
    prod.y_axis.title = f"Megatonnes of {product}/year Produced (NEW factories)"
    prod.x_axis.title = "Years"
    prod.height = 11
    prod.width = 15
    # Categories = Years in F51:F540; series = G (regular new) and M (fast new)
    cats = Reference(ws, min_col=6, min_row=51, max_row=last_week_row)
    # G51:G / M51:M are numeric new-Mt/yr series (row 50 is a subtitle)
    data_reg = Reference(ws, min_col=7, min_row=51, max_row=last_week_row)
    prod.add_data(data_reg, titles_from_data=False)
    prod.set_categories(cats)
    data_fast = Reference(ws, min_col=13, min_row=51, max_row=last_week_row)
    prod.add_data(data_fast, titles_from_data=False)
    prod.series[0].tx = SeriesLabel(v="Regular Construction")
    prod.series[1].tx = SeriesLabel(v="Fast Construction")
    prod.series[0].graphicalProperties.line.solidFill = "4F81BD"
    prod.series[1].graphicalProperties.line.solidFill = "C0504D"
    ws.add_chart(prod, "O5")

    mult = LineChart()
    mult.title = f"MULTIPLE OF CURRENT {product} PRODUCTION RAMP-UP"
    mult.style = 12
    mult.y_axis.title = f"Multiple of Current {product} Production"
    mult.x_axis.title = "Years"
    mult.height = 12
    mult.width = 16
    # Pre-disruption helper table U49:W541
    cats2 = Reference(ws, min_col=21, min_row=50, max_row=last_week_row + 1)
    data2 = Reference(ws, min_col=22, min_row=49, max_col=23, max_row=last_week_row + 1)
    mult.add_data(data2, titles_from_data=True)
    mult.set_categories(cats2)
    mult.series[0].graphicalProperties.line.solidFill = "4F81BD"
    mult.series[1].graphicalProperties.line.solidFill = "C0504D"
    ws.add_chart(mult, "S5")


def _update_rampup_sheet(
    ws,
    key: str,
    commodity,
    budget: float,
    capex_sheet: str,
) -> None:
    meta = META[key]
    product = meta["product"]

    # Point all CAPEX refs to this commodity's CAPEX sheet
    _replace_formulas(ws, "'CAPEX Calcs'", f"'{capex_sheet}'")
    _replace_formulas(ws, "CAPEX Calcs!", f"{capex_sheet}!")

    ws["C1"] = f"{meta['title'].upper()} REGULAR CONSTRUCTION"
    ws["I1"] = f"{meta['title'].upper()} FAST CONSTRUCTION"
    ws["C2"] = budget
    ws["I2"] = budget
    ws["C14"] = DEFAULT_STARTUP_PCT_OF_FULL
    ws["I14"] = DEFAULT_STARTUP_PCT_OF_FULL
    ws["C16"] = DEFAULT_FRACTION_FUNCTIONING
    ws["I16"] = DEFAULT_FRACTION_FUNCTIONING
    ws["P4"] = commodity.current_mt_per_year
    ws["Q4"] = f"Current {product} production in million metric tonnes"

    # Column headers for multiples
    for cell_addr in ("H23", "N23", "H50", "N50"):
        if ws[cell_addr].value and "NH3" in str(ws[cell_addr].value):
            ws[cell_addr] = str(ws[cell_addr].value).replace("NH3", product)
        elif ws[cell_addr].value is None or "Multiple" in str(ws[cell_addr].value or ""):
            if cell_addr.endswith("50"):
                pass
            else:
                ws[cell_addr] = f"Multiple of Current {product} Production"

    ws["H23"] = f"Multiple of Current {product} Production"
    ws["N23"] = f"Multiple of Current {product} Production"
    ws["H50"] = f"Multiple of Current {product} Production"
    ws["N50"] = f"Multiple of Current {product} Production"

    # Notes block
    ws["U1"] = "CODE-MATCHED (current model)"
    ws["U2"] = (
        f"C16/I16 = {DEFAULT_FRACTION_FUNCTIONING:g}; "
        f"startup% = {DEFAULT_STARTUP_PCT_OF_FULL:g}; "
        f"budget = equal-pace default"
    )
    ws["U3"] = "Multiple = (new Mt/yr + surviving Mt/yr) / current Mt/yr"
    ws["U4"] = "Surviving Mt/yr in C22/I22"
    ws["U5"] = (
        f"Multiple chart uses U50:W (1.0 before t=0, then drops to "
        f"{DEFAULT_FRACTION_FUNCTIONING:g})"
    )
    ws["U6"] = "Production chart (G/M) = NEW factory Mt/yr only (starts at 0)"

    _add_rampup_charts(ws, product)


def main() -> Path:
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE}")

    budgets = allocate_equal_pace_budgets()
    by_key = {c.key: c for c in COMMODITIES}

    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "ALLFED_agricultural_inputs_scale_up_code_matched.xlsx"
    downloads = (
        Path.home() / "Downloads" / "ALLFED_agricultural_inputs_scale_up_code_matched.xlsx"
    )

    shutil.copy2(TEMPLATE, out_path)
    wb = load_workbook(out_path)

    # Rename original NH3 sheets
    wb["CAPEX Calcs"].title = "NH3 CAPEX"
    wb["Ramp-up Calcs"].title = "NH3 Ramp-up"

    # Update NH3 first
    nh3 = by_key["nh3"]
    _write_capex_sheet(wb["NH3 CAPEX"], "nh3", nh3)
    _update_rampup_sheet(
        wb["NH3 Ramp-up"], "nh3", nh3, budgets["nh3"], "NH3 CAPEX"
    )

    # Clone template pair for other commodities
    for key in ORDER:
        if key == "nh3":
            continue
        meta = META[key]
        commodity = by_key[key]
        capex_name = f"{meta['prefix']} CAPEX"
        ramp_name = f"{meta['prefix']} Ramp-up"

        # Copy from NH3 sheets (already formula-complete)
        capex_ws = wb.copy_worksheet(wb["NH3 CAPEX"])
        capex_ws.title = capex_name
        ramp_ws = wb.copy_worksheet(wb["NH3 Ramp-up"])
        ramp_ws.title = ramp_name

        _write_capex_sheet(capex_ws, key, commodity)
        # Reset ramp formulas that still point at NH3 CAPEX from the copy source
        _replace_formulas(ramp_ws, "'NH3 CAPEX'", f"'{capex_name}'")
        _replace_formulas(ramp_ws, "NH3 CAPEX!", f"{capex_name}!")
        _update_rampup_sheet(ramp_ws, key, commodity, budgets[key], capex_name)

    # Summary sheet at front
    if "Summary" in wb.sheetnames:
        del wb["Summary"]
    ws = wb.create_sheet("Summary", 0)
    ws["A1"] = "ALLFED agricultural input scale-up — code-matched workbook"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A3"] = "Each commodity has: CAPEX sheet + Ramp-up sheet (same layout as N template)."
    ws["A4"] = "Budgets = equal-pace share of $758B pot. Defaults: startup%=0.5, functioning=0.4."
    ws["A6"] = "Key"
    ws["B6"] = "Commodity"
    ws["C6"] = "Budget USD/yr"
    ws["D6"] = "Budget $B/yr"
    ws["E6"] = "Current Mt/yr"
    ws["F6"] = "CAPEX sheet"
    ws["G6"] = "Ramp-up sheet"
    for c in range(1, 8):
        ws.cell(6, c).font = Font(bold=True)

    for r, key in enumerate(ORDER, 7):
        com = by_key[key]
        meta = META[key]
        bud = budgets[key]
        ws.cell(r, 1, key)
        ws.cell(r, 2, com.label)
        ws.cell(r, 3, bud).number_format = '"$"#,##0'
        ws.cell(r, 4, bud / 1e9).number_format = "0.00"
        ws.cell(r, 5, com.current_mt_per_year)
        ws.cell(r, 6, f"{meta['prefix']} CAPEX")
        ws.cell(r, 7, f"{meta['prefix']} Ramp-up")

    ws["A15"] = "Open any '* Ramp-up' tab for parameters, wave table, weekly series, and charts."
    for col in range(1, 8):
        ws.column_dimensions[get_column_letter(col)].width = 18
    ws.column_dimensions["B"].width = 42

    # Reorder: Summary, then each commodity CAPEX/Ramp-up pair
    desired = ["Summary"]
    for key in ORDER:
        p = META[key]["prefix"]
        desired.extend([f"{p} CAPEX", f"{p} Ramp-up"])
    for i, name in enumerate(desired):
        wb.move_sheet(name, offset=i - wb.sheetnames.index(name))

    wb.save(out_path)
    shutil.copy2(out_path, downloads)
    print(out_path)
    print(downloads)
    print("sheets:", wb.sheetnames)
    return out_path


if __name__ == "__main__":
    main()
