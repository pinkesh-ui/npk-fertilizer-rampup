# NPK Fertilizer Ramp-up Speed

Interactive model and dashboard for **NH3 (N)**, **phosphate (P)**, and **potassium (K)** fertilizer plant construction ramp-up under an annual world construction budget.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## What it does

Given an **Annual World Construction Budget** for each commodity, the model estimates:

- CAPEX per plant (regular vs fast / 24-7 construction)
- Plants built per year and construction wave timing
- Weekly production ramp-up (Mt/yr) and multiples of current production

Logic matches the Excel workbooks for agricultural NH3, potassium (MOP), and phosphate (UNIDO TSP) ramp-up calcs.

## Quick start (local dashboard)

```bash
conda env create -f environment.yml
conda activate npk-fertilizer-rampup
# or: pip install -r requirements.txt

python dashboard.py
```

Open http://127.0.0.1:8050

Enter budgets for NH3, K, and P, choose a commodity, then click **Update charts**.

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

| Commodity | Default annual budget (USD) | Current production baseline |
|-----------|----------------------------|-----------------------------|
| NH3 | 758e9 | 240 Mt/yr |
| Potassium | 758e9 × 0.4 | 41.6 Mt/yr potash |
| Phosphate | 758e9 × 0.4 | 47.8 Mt/yr |

## License

Apache 2.0 — see `LICENSE`.
