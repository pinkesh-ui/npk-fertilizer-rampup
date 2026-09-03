# NPK Fertilizer / Agricultural Input Ramp-up

Interactive model and dashboard for agricultural **input plant construction ramp-up**.

**Reference template:** N-type fertilizer (NH3) from the ALLFED N Fertiliser Scale-Up workbook.
All other commodities reuse that same ramp-up logic (startup %, disruption fraction, weeks-to-build
fit, wave timing, and chart semantics); only CAPEX benchmarks and plant size change.

Commodities:
- Fertilizer: **NH3 (N, reference)**, phosphate (P), potassium (K)
- Sulfuric acid (H2SO4)
- Pesticides: herbicides, insecticides, fungicides

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## What it does

Given an **Annual World Construction Budget** for each commodity, the model estimates:

- CAPEX per plant (regular vs fast / 24-7 construction)
- Plants built per year and construction wave timing
- Weekly production ramp-up (Mt/yr) and multiples of current production

Shared controls (from the N template):
- **Startup % of Fully Scaled Production** (default 0.5)
- **fraction_functioning_after_disruption** (default 0.4)

## Quick start (local dashboard)

```bash
conda env create -f environment.yml
conda activate npk-fertilizer-rampup
# or: pip install -r requirements.txt

python dashboard.py
```

Open http://127.0.0.1:8050

Enter budgets, choose a commodity, then click **Update charts**.

## Offline CLI (CSV + PNG/SVG)

```bash
python src/agricultural_input_rampup.py
```

Prompts for each commodity budget one by one and writes outputs under `result/<commodity>/`.

## Deploy online (Render)

Same pattern as other ALLFED Dash apps (e.g. irrigation optimization on Render).

1. Push this repository to GitHub (already at [pinkesh-ui/npk-fertilizer-rampup](https://github.com/pinkesh-ui/npk-fertilizer-rampup)).
2. On [Render](https://dashboard.render.com): **New → Web Service**.
3. Connect this repo.
4. Settings:
   - **Language / Runtime:** Docker
   - **Instance type:** Free (or paid if you want no sleep)
5. Create the service and wait for the build.
6. Share the URL (e.g. `https://npk-fertilizer-rampup.onrender.com`).

The `Dockerfile` runs:

```text
gunicorn dashboard:server --bind 0.0.0.0:$PORT
```

**Note:** Free Render instances sleep after idle time; the first load after sleep can take ~30–60 seconds.

### Local Docker test

```bash
docker build -t npk-fertilizer-rampup .
docker run -p 8050:8050 -e PORT=8050 npk-fertilizer-rampup
```

## Repository layout

| Path | Purpose |
|------|---------|
| `src/agricultural_input_rampup.py` | CAPEX + ramp-up model (N / P / K) |
| `dashboard.py` | Plotly Dash interactive UI |
| `requirements-dashboard.txt` | Minimal deps for Docker / Render |
| `Dockerfile` | Container image for online deploy |
| `requirements.txt` | Full local / CI dependencies |
| `environment.yml` | Conda environment |
| `tests/` | pytest suite |
| `data/`, `results/`, `docs/` | Data, outputs, documentation |

## Defaults

Shared construction pot: **$758B/yr** (`REFERENCE_ANNUAL_BUDGET_USD`), split by
equal-pace weights \(B_i \propto\) (CAPEX $/tpa) × (current t/yr) so commodities
recover their own current capacity at the same pace. NH3 remains the ramp-up
timing/chart template.

| Commodity | Default annual budget (USD) | Current production baseline |
|-----------|----------------------------|-----------------------------|
| NH3 | ~$555B (~73% of pot) | 240 Mt/yr |
| Phosphate | ~$98B | 47.8 Mt/yr |
| Potassium | ~$78B | 41.6 Mt/yr potash |
| Herbicides | ~$12B | 1.90 Mt/yr |
| Fungicides | ~$11B | 0.82 Mt/yr |
| Insecticides | ~$2.7B | 0.82 Mt/yr |
| H2SO4 | ~$2.1B | 150 Mt/yr |

Category totals ≈ fertilizer **96.4%**, pesticides **3.4%**, H2SO4 **0.3%**. Exact
defaults are computed at import time from CAPEX functions.

## License

Apache 2.0 — see `LICENSE`.
