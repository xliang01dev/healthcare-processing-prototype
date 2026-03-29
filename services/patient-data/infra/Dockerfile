FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./pyproject.toml ./pyproject.toml
COPY ./uv.lock ./uv.lock

RUN --mount=type=cache,target=/root/.cache/pip \
    uv sync --frozen --no-install-project --no-dev

COPY ./shared /app/shared
COPY ./services/patient-data /app

RUN --mount=type=cache,target=/root/.cache/pip \
    uv sync --frozen --no-dev

ARG INCLUDE_DEBUG
RUN if [ "$INCLUDE_DEBUG" = "debugpy" ]; then \
    uv sync --frozen --no-install-project --group debug; \
fi

ARG APP_PORT=8002
ENV APP_PORT=$APP_PORT
EXPOSE $APP_PORT

CMD .venv/bin/uvicorn main:app --host 0.0.0.0 --port $APP_PORT --workers 1 --timeout-keep-alive 60
