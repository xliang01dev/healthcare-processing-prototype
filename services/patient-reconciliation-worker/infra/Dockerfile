FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates build-essential \
 && rm -rf /var/lib/apt/lists/*

# app lives at /app inside the container
WORKDIR /app

# Do the following if entry point script exists
# COPY ./scripts/entrypoint.sh entrypoint.sh
# Make sure the entrypoint script is executable
# RUN chmod +x *.sh

# These files are in the build context root (..), not in docker/
COPY ./pyproject.toml ./pyproject.toml
COPY ./uv.lock ./uv.lock

# Install python libs first BEFORE service code is copied to optimize builds
RUN --mount=type=cache,target=/root/.cache/pip \
    uv sync --frozen --no-install-project --no-dev

COPY ./shared /app/shared
COPY ./services/patient-reconciliation-worker /app

# Install app
RUN --mount=type=cache,target=/root/.cache/pip \
    uv sync --frozen --no-dev

# For remote debugging if debugpy is used
ARG INCLUDE_DEBUG
RUN if [ "$INCLUDE_DEBUG" = "debugpy" ]; then \
    uv sync --frozen --no-install-project --group debug; \
fi

# Expose app port
ARG APP_PORT=8008
ENV APP_PORT=$APP_PORT
EXPOSE $APP_PORT

# Run entry point if it exists
# ENTRYPOINT [ "./entrypoint.sh" ]

# Set workers to 1 when enabling debugpy to avoid issues with multiple. Set multiple workers for parallel process.
CMD .venv/bin/uvicorn main:app --host 0.0.0.0 --port $APP_PORT --workers 1 --timeout-keep-alive 60
