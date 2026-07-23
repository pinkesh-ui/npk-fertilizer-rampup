# Lightweight deploy for the NPK fertilizer ramp-up dashboard (Render / Docker)
FROM python:3.12-slim

WORKDIR /app

COPY requirements-dashboard.txt .
RUN pip install --no-cache-dir -r requirements-dashboard.txt

# Flatten model + dashboard into /app for simple imports
COPY src/agricultural_input_rampup.py ./agricultural_input_rampup.py
COPY dashboard.py ./dashboard.py

ENV DASH_HOST=0.0.0.0
ENV PORT=8050
ENV PYTHONUNBUFFERED=1

EXPOSE 8050

CMD ["sh", "-c", "gunicorn dashboard:server --bind 0.0.0.0:${PORT:-8050} --workers 1 --threads 4 --timeout 120"]
