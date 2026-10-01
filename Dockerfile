FROM ghcr.io/astral-sh/uv:0.12.3 AS uv
FROM python:3.14-slim
COPY --from=uv /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev && mkdir /workspace && chown 10001:10001 /workspace
USER 10001:10001
ENTRYPOINT ["/app/.venv/bin/kestri"]
CMD ["telegram"]
