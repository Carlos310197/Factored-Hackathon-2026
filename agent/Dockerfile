# ARM64 image for AgentCore Runtime (/invocations + /ping on 8080). The same image runs the mock IdP
# (python -m bankagent.identity.app on 8081). --no-default-groups keeps the dev and resolver tooling
# (pytest, moto, scikit-learn, LightGBM, MLflow, matplotlib) out of the runtime image.
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
CMD ["uv", "run", "--frozen", "--no-default-groups", "python", "-m", "bankagent.app"]
