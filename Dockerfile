FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway injects PORT. Do NOT hardcode.
# Production boot contract:
# 1) apply Alembic migrations before the app starts
# 2) fail fast if the database schema cannot be reconciled
# 3) then start the API
CMD ["sh","-c","python scripts/preflight_alembic_version.py && alembic upgrade head && uvicorn --log-config logging_uvicorn_stdout.json app.main:app --host 0.0.0.0 --port ${PORT:-8080} --timeout-keep-alive ${UVICORN_TIMEOUT_KEEP_ALIVE:-75}"]
