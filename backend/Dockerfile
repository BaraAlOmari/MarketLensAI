# MarketLens API (FastAPI). Build from backend/: docker build -t marketlens-api .
# Settings come from environment variables at run time; no .env or key is copied in.
FROM python:3.11.17-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first (pinned in pyproject.toml), so code changes reuse this layer.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY app ./app

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin marketlens
USER 10001

EXPOSE 8000
# One worker: the per-IP rate limiter counts in process memory (sessions are in Postgres).
# The client IP comes from X-Forwarded-For (FORWARDED_HOPS), not uvicorn's proxy handling.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-server-header"]
