# --no-default-groups keeps the dev and resolver tooling out of the runtime image.
FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-default-groups --no-install-project
COPY src ./src
COPY scripts ./scripts
RUN uv sync --frozen --no-default-groups
# DuckDB extensions for s3:// serving reads are installed at build time, not downloaded at runtime.
RUN uv run --frozen --no-default-groups python -c "import duckdb; c = duckdb.connect(); c.execute('INSTALL httpfs'); c.execute('INSTALL aws')"
EXPOSE 8080 8081
# --no-sync: the image is already synced
CMD ["uv", "run", "--no-sync", "python", "-m", "bankagent.app"]
