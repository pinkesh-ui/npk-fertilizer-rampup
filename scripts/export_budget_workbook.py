"""
Export equal-pace budgets, CAPEX, and full ramp-up logic/charts to Excel.

Tabs:
  - Summary, Budgets by commodity, CAPEX & plant size, By category, Assumptions
  - One sheet per commodity with parameters, wave tables, weekly series, and
    production + multiple charts (regular vs fast), matching the N template layout.
"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
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
    FERTILIZER_KEYS,
    NH3_TARGET_PLANT_SIZE_TPD,
    PESTICIDE_KEYS,
    REFERENCE_ANNUAL_BUDGET_USD,
    allocate_equal_pace_budgets,
    category_budget_totals,
    simulate_commodity,
)

HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(name="Calibri", bold=True, size=14, color="1F4E79")
SECTION_FONT = Font(name="Calibri", bold=True, size=12, color="1F4E79")
NORMAL = Font(name="Calibri", size=11)
BOLD = Font(name="Calibri", bold=True, size=11)
HEADER_FILL = PatternFill("solid", fgColor="2F5D50")
SECTION_FILL = PatternFill("solid", fgColor="D6EAF8")
ALT_FILL = PatternFill("solid", fgColor="F4F6F7")
THIN = Border(
    left=Side(style="thin", color="BFBFBF"),
    right=Side(style="thin", color="BFBFBF"),
    top=Side(style="thin", color="BFBFBF"),
    bottom=Side(style="thin", color="BFBFBF"),
)

ORDER = [
    "nh3",
    "phosphate",
    "potassium",
    "herbicide",
    "fungicide",
    "insecticide",
    "h2so4",
]
PEST_TPY = {"herbicide": 600.0, "insecticide": 2100.0, "fungicide": 1100.0}
SHEET_NAMES = {
    "nh3": "NH3",
    "phosphate": "Phosphate",
    "potassium": "Potassium",
    "herbicide": "Herbicide",
    "fungicide": "Fungicide",
    "insecticide": "Insecticide",
    "h2so4": "H2SO4",
}


def style_header(ws, row: int, cols: int, start_col: int = 1) -> None:
    for c in range(start_col, start_col + cols):
        cell = ws.cell(row=row, column=c)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN


def autosize(ws, min_w: int = 10, max_w: int = 42) -> None:
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        length = 0
        for cell in col:
            if cell.value is None:
                continue
            length = max(length, min(len(str(cell.value)), 60))
        ws.column_dimensions[letter].width = max(min_w, min(max_w, length + 2))


def write_summary_tabs(wb: Workbook) -> None:
    budgets = allocate_equal_pace_budgets()
    cats = category_budget_totals()
    total = REFERENCE_ANNUAL_BUDGET_USD
    by_key = {c.key: c for c in COMMODITIES}
    cat_of = {k: "Fertilizer" for k in FERTILIZER_KEYS}
    cat_of.update({k: "Pesticides" for k in PESTICIDE_KEYS})
    cat_of["h2so4"] = "H2SO4"
    cat_totals = {
        "Fertilizer": cats["fertilizer"],
        "Pesticides": cats["pesticides"],
        "H2SO4": cats["h2so4"],
    }

    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Agricultural Input Ramp-up — Equal-pace Budget Summary"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:D1")
    ws["A3"] = "Shared construction pot (USD/yr)"
    ws["B3"] = total
    ws["B3"].number_format = '"$"#,##0'
    ws["A4"] = "Allocation rule"
    ws["B4"] = "B_i proportional to (CAPEX $/tpa) x (current t/yr)"
    ws["A5"] = "Startup % of Fully Scaled Production"
    ws["B5"] = DEFAULT_STARTUP_PCT_OF_FULL
    ws["A6"] = "fraction_functioning_after_disruption"
    ws["B6"] = DEFAULT_FRACTION_FUNCTIONING
    ws["A8"] = "Category totals"
    ws["A8"].font = SECTION_FONT
    for i, h in enumerate(
        ["Category", "Budget (USD/yr)", "Budget ($B/yr)", "Share of pot (%)"], 1
    ):
        ws.cell(row=9, column=i, value=h)
    style_header(ws, 9, 4)
    for r, (name, val) in enumerate(
        [
            ("Fertilizer", cats["fertilizer"]),
            ("Pesticides", cats["pesticides"]),
            ("H2SO4", cats["h2so4"]),
            ("TOTAL", total),
        ],
        10,
    ):
        ws.cell(row=r, column=1, value=name).font = BOLD if name == "TOTAL" else NORMAL
        ws.cell(row=r, column=2, value=val).number_format = '"$"#,##0'
        ws.cell(row=r, column=3, value=val / 1e9).number_format = "0.00"
        ws.cell(row=r, column=4, value=100 * val / total).number_format = "0.00"
        for c in range(1, 5):
            ws.cell(row=r, column=c).border = THIN
    ws["A15"] = (
        "Commodity tabs include ramp-up parameters, wave tables, weekly series, "
        "and production / multiple charts (regular vs fast)."
    )
    autosize(ws)

    ws = wb.create_sheet("Budgets by commodity")
    ws["A1"] = "Equal-pace annual construction budgets (dashboard defaults)"
    ws["A1"].font = TITLE_FONT
    headers = [
        "Category",
        "Commodity",
        "Key",
        "Current (Mt/yr)",
        "Budget (USD/yr)",
        "Budget ($B/yr)",
        "Share of pot (%)",
        "Share of category (%)",
    ]
    for i, h in enumerate(headers, 1):
        ws.cell(row=3, column=i, value=h)
    style_header(ws, 3, len(headers))
    for r, key in enumerate(ORDER, 4):
        com = by_key[key]
        cat = cat_of[key]
        bud = budgets[key]
        vals = [
            cat,
            com.label,
            key,
            com.current_mt_per_year,
            bud,
            bud / 1e9,
            100 * bud / total,
            100 * bud / cat_totals[cat],
        ]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = THIN
            if c == 5:
                cell.number_format = '"$"#,##0'
            elif c in (4, 6, 7, 8):
                cell.number_format = "0.00"
    autosize(ws)

    ws = wb.create_sheet("CAPEX & plant size")
    ws["A1"] = "CAPEX benchmarks and plant sizes"
    ws["A1"].font = TITLE_FONT
    headers = [
        "Category",
        "Commodity",
        "Key",
        "Target plant size",
        "Plant size unit",
        "Regular CAPEX (USD/plant)",
        "Fast CAPEX (USD/plant)",
        "Capital efficiency ($/tpa)",
        "Weight = $/tpa x t/yr",
    ]
    for i, h in enumerate(headers, 1):
        ws.cell(row=3, column=i, value=h)
    style_header(ws, 3, len(headers))
    for r, key in enumerate(ORDER, 4):
        com = by_key[key]
        capex = CAPEX_FUNCS[key]()
        current_tpy = com.current_mt_per_year * 1_000_000.0
        weight = capex.capital_efficiency_usd_per_tpa * current_tpy
        if key in PEST_TPY:
            size, unit = PEST_TPY[key], "t/yr"
        elif key == "nh3":
            size, unit = NH3_TARGET_PLANT_SIZE_TPD, "t/day"
        else:
            size, unit = com.target_plant_size_tpd, "t/day"
        vals = [
            cat_of[key],
            com.label,
            key,
            size,
            unit,
            capex.regular_capex_usd,
            capex.fast_capex_usd,
            capex.capital_efficiency_usd_per_tpa,
            weight,
        ]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = THIN
            if c in (6, 7, 9):
                cell.number_format = '"$"#,##0.00'
            elif c in (4, 8):
                cell.number_format = "0.00"
    autosize(ws)

    ws = wb.create_sheet("By category")
    ws["A1"] = "Budgets grouped by category"
    ws["A1"].font = TITLE_FONT
    row = 3
    for cat_name, keys in [
        ("Fertilizer", FERTILIZER_KEYS),
        ("Pesticides", PESTICIDE_KEYS),
        ("H2SO4", ("h2so4",)),
    ]:
        ws.cell(row=row, column=1, value=cat_name).font = SECTION_FONT
        row += 1
        for i, h in enumerate(
            ["Commodity", "Budget ($B/yr)", "Share of category (%)", "Share of pot (%)"],
            1,
        ):
            ws.cell(row=row, column=i, value=h)
        style_header(ws, row, 4)
        row += 1
        cat_total = sum(budgets[k] for k in keys)
        for key in keys:
            com = by_key[key]
            bud = budgets[key]
            ws.cell(row=row, column=1, value=com.label).border = THIN
            ws.cell(row=row, column=2, value=bud / 1e9).number_format = "0.00"
            ws.cell(row=row, column=2).border = THIN
            ws.cell(row=row, column=3, value=100 * bud / cat_total).number_format = "0.00"
            ws.cell(row=row, column=3).border = THIN
            ws.cell(row=row, column=4, value=100 * bud / total).number_format = "0.00"
            ws.cell(row=row, column=4).border = THIN
            row += 1
        ws.cell(row=row, column=1, value=f"{cat_name} total").font = BOLD
        ws.cell(row=row, column=2, value=cat_total / 1e9).number_format = "0.00"
        ws.cell(row=row, column=2).font = BOLD
        for c in range(1, 5):
            ws.cell(row=row, column=c).border = THIN
            ws.cell(row=row, column=c).fill = SECTION_FILL
        row += 2
    autosize(ws)

    ws = wb.create_sheet("Assumptions")
    ws["A1"] = "Shared model assumptions"
    ws["A1"].font = TITLE_FONT
    for i, h in enumerate(["Parameter", "Value", "Notes"], 1):
        ws.cell(row=3, column=i, value=h)
    style_header(ws, 3, 3)
    assumptions = [
        ("REFERENCE_ANNUAL_BUDGET_USD", total, "Shared world construction pot ($/yr)"),
        (
            "DEFAULT_STARTUP_PCT_OF_FULL",
            DEFAULT_STARTUP_PCT_OF_FULL,
            "New plant starts at this share of full output",
        ),
        (
            "DEFAULT_FRACTION_FUNCTIONING",
            DEFAULT_FRACTION_FUNCTIONING,
            "Surviving existing + new-build rate after disruption",
        ),
        ("COST_CAPACITY_EXPONENT", COST_CAPACITY_EXPONENT, "Plant cost scaling exponent"),
        (
            "FAST_CONSTRUCTION_COST_FACTOR",
            FAST_CONSTRUCTION_COST_FACTOR,
            "Fast CAPEX = factor x regular CAPEX",
        ),
        (
            "NH3_TARGET_PLANT_SIZE_TPD",
            NH3_TARGET_PLANT_SIZE_TPD,
            "EuroChem Kingisepp-scaled NH3 plant (t/day)",
        ),
        ("NH3 regular CAPEX", 1_368_630_195.13, "CAPEX Calcs B19 estimate (USD)"),
        ("NH3 USD inflation conversion (2025)", 1.33, "USD inflation conversion"),
        ("Herbicide current use 2026", 1.9902, "Mt ai/yr"),
        ("Insecticide current use 2026", 0.8232, "Mt ai/yr"),
        ("Fungicide current use 2026", 0.8624, "Mt ai/yr"),
        ("Herbicide target plant", 600, "t/yr; CAPEX $16,593,135"),
        ("Insecticide target plant", 2100, "t/yr; CAPEX $12,900,141"),
        ("Fungicide target plant", 1100, "t/yr; CAPEX $31,323,634"),
    ]
    for r, (param, value, notes) in enumerate(assumptions, 4):
        ws.cell(row=r, column=1, value=param).border = THIN
        cell = ws.cell(row=r, column=2, value=value)
        cell.border = THIN
        if isinstance(value, (int, float)) and value >= 1000:
            cell.number_format = "#,##0.##"
        ws.cell(row=r, column=3, value=notes).border = THIN
    autosize(ws)


def _write_wave_block(ws, start_row: int, start_col: int, title: str, waves) -> int:
    ws.cell(row=start_row, column=start_col, value=title).font = SECTION_FONT
    headers = [
        "Wave",
        "Production Level",
        "Plants",
        "tonnes/week",
        "Weeks",
        "Years",
        "Megatonnes/year",
        "Multiple of Current",
    ]
    header_row = start_row + 1
    for i, h in enumerate(headers):
        ws.cell(row=header_row, column=start_col + i, value=h)
    style_header(ws, header_row, len(headers), start_col=start_col)

    for i, (_, row) in enumerate(waves.iterrows(), header_row + 1):
        vals = [
            row["Wave"],
            row["Production Level"],
            row["Plants"],
            row["tonnes/week"],
            row["Weeks"],
            row["Years"],
            row["Megatonnes/year"],
            row["Multiple of Current Production"],
        ]
        for c, v in enumerate(vals):
            cell = ws.cell(row=i, column=start_col + c, value=v)
            cell.border = THIN
            cell.font = NORMAL
            if c in (2, 3, 4, 5, 6, 7):
                cell.number_format = "0.00"
    return header_row + len(waves) + 2


def write_commodity_sheet(wb: Workbook, commodity, budget: float) -> None:
    result = simulate_commodity(commodity, budget)
    regular = result["regular"]
    fast = result["fast"]
    summary = result["summary"]
    reg_waves = result["regular_waves"]
    fast_waves = result["fast_waves"]
    weekly = result["weekly"]

    ws = wb.create_sheet(SHEET_NAMES[commodity.key])
    ws["A1"] = f"{commodity.label} — ramp-up (equal-pace default budget)"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:F1")

    ws["A3"] = "Scenario parameters"
    ws["A3"].font = SECTION_FONT
    for i, h in enumerate(["Parameter", "Regular", "Fast"], 1):
        ws.cell(row=4, column=i, value=h)
    style_header(ws, 4, 3)

    for r, (_, row) in enumerate(summary.iterrows(), 5):
        ws.cell(row=r, column=1, value=row["Parameter"]).border = THIN
        c2 = ws.cell(row=r, column=2, value=row["Regular"])
        c3 = ws.cell(row=r, column=3, value=row["Fast"])
        c2.border = THIN
        c3.border = THIN
        # Format large numbers
        for cell in (c2, c3):
            if isinstance(cell.value, (int, float)) and abs(cell.value) >= 1000:
                cell.number_format = "#,##0.##"

    param_end = 4 + len(summary)
    ws.cell(row=param_end + 1, column=1, value="Sanity / baseline").font = SECTION_FONT
    ws.cell(
        row=param_end + 2,
        column=1,
        value=(
            f"Current production = {commodity.current_mt_per_year:g} Mt/yr. "
            f"Surviving baseline = {result['fraction_functioning']:g} × current. "
            f"Production chart = new-factory Mt/yr only; multiple chart = total / current."
        ),
    )

    wave_start = param_end + 4
    after_reg = _write_wave_block(
        ws, wave_start, 1, "Regular Construction — wave milestones", reg_waves
    )
    _write_wave_block(
        ws, wave_start, 10, "Fast Construction — wave milestones", fast_waves
    )

    # Weekly series for charts (placed below waves)
    weekly_start = max(after_reg, wave_start + len(reg_waves) + 4)
    ws.cell(row=weekly_start, column=1, value="Weekly series (for charts)").font = (
        SECTION_FONT
    )
    week_headers = [
        "Weeks",
        "Years",
        "Regular new Mt/yr",
        "Fast new Mt/yr",
        "Regular total Mt/yr",
        "Fast total Mt/yr",
        "Regular Multiple",
        "Fast Multiple",
    ]
    header_row = weekly_start + 1
    for i, h in enumerate(week_headers, 1):
        ws.cell(row=header_row, column=i, value=h)
    style_header(ws, header_row, len(week_headers))

    for i, (_, row) in enumerate(weekly.iterrows(), header_row + 1):
        vals = [
            int(row["Weeks"]),
            float(row["Years"]),
            float(row["Regular new megatonnes/year"]),
            float(row["Fast new megatonnes/year"]),
            float(row["Regular megatonnes/year"]),
            float(row["Fast megatonnes/year"]),
            float(row["Regular Multiple of Current Production"]),
            float(row["Fast Multiple of Current Production"]),
        ]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=i, column=c, value=v)
            if c > 1:
                cell.number_format = "0.000"

    data_end = header_row + len(weekly)

    # Production chart (new factories)
    prod = LineChart()
    prod.title = f"{commodity.product_short}/YEAR PRODUCTION RAMP-UP (New Factory)"
    prod.style = 10
    prod.y_axis.title = "new megatonnes/year"
    prod.x_axis.title = "Years"
    prod.height = 12
    prod.width = 18
    prod.legend.position = "b"
    data = Reference(ws, min_col=3, min_row=header_row, max_col=4, max_row=data_end)
    cats = Reference(ws, min_col=2, min_row=header_row + 1, max_row=data_end)
    prod.add_data(data, titles_from_data=True)
    prod.set_categories(cats)
    prod.series[0].graphicalProperties.line.solidFill = "4CC9F0"
    prod.series[1].graphicalProperties.line.solidFill = "F4A261"
    ws.add_chart(prod, "J3")

    # Multiple chart
    mult = LineChart()
    mult.title = f"MULTIPLE OF CURRENT {commodity.product_short} PRODUCTION RAMP-UP"
    mult.style = 12
    mult.y_axis.title = commodity.multiple_y_label
    mult.x_axis.title = "Years"
    mult.height = 12
    mult.width = 18
    mult.legend.position = "b"
    data2 = Reference(ws, min_col=7, min_row=header_row, max_col=8, max_row=data_end)
    mult.add_data(data2, titles_from_data=True)
    mult.set_categories(cats)
    mult.series[0].graphicalProperties.line.solidFill = "4CC9F0"
    mult.series[1].graphicalProperties.line.solidFill = "F4A261"
    ws.add_chart(mult, "J22")

    # Useful column widths for the left params/waves area
    for col in range(1, 9):
        ws.column_dimensions[get_column_letter(col)].width = 14
    ws.column_dimensions["A"].width = 48
    ws.column_dimensions["B"].width = 22


def main() -> list[Path]:
    budgets = allocate_equal_pace_budgets()
    wb = Workbook()
    write_summary_tabs(wb)

    by_key = {c.key: c for c in COMMODITIES}
    for key in ORDER:
        write_commodity_sheet(wb, by_key[key], budgets[key])

    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "agricultural_input_rampup_full.xlsx"
    downloads = Path.home() / "Downloads" / "agricultural_input_rampup_full.xlsx"
    wb.save(out_path)
    wb.save(downloads)

    # Keep a budgets-only copy name for earlier link, regenerated as full file alias
    budgets_alias = out_dir / "agricultural_input_equal_pace_budgets.xlsx"
    wb.save(budgets_alias)
    downloads_alias = Path.home() / "Downloads" / "agricultural_input_equal_pace_budgets.xlsx"
    wb.save(downloads_alias)

    print(out_path)
    print(downloads)
    return [out_path, downloads]


if __name__ == "__main__":
    main()
