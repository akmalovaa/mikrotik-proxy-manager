ARG PYTHON_VERSION=3.13.2
ARG UV_VERSION=latest

FROM ghcr.io/astral-sh/uv:$UV_VERSION AS uv

FROM python:$PYTHON_VERSION-slim

ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT="/usr/local/"
# ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --compile-bytecode --no-install-project --no-install-workspace --python-preference only-system 

COPY . .

EXPOSE 8000

CMD ["python", "-m", "mikrotik_proxy_manager"]
