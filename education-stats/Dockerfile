FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils libreoffice-writer-nogui \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY . .
ENV SOURCE_DIR=/source CACHE_DIR=/app/.cache
CMD ["uv", "run", "python", "-m", "etl.run", "extract"]
