FROM public.ecr.aws/awsguru/aws-lambda-adapter:1.0.0 AS lambda-adapter
FROM python:3.12-slim

WORKDIR /app

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache

# Node.js + Playwright MCP + Chromium for browser tools.
RUN apt-get update \
    && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @playwright/mcp@0.0.75 \
    && rm -rf /var/lib/apt/lists/*

RUN npx -y playwright install --with-deps chromium

RUN pip install uv

# Workspace root — install discovery package with LLM/MCP deps only.
# metrics is required because alphalens-shared depends on alphalens-metrics.
COPY pyproject.toml uv.lock ./
COPY database ./database
COPY shared ./shared
COPY metrics ./metrics
COPY discovery ./discovery

RUN uv sync --frozen --package alphalens-discovery --group llm

ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app/discovery

COPY --from=lambda-adapter /lambda-adapter /opt/extensions/lambda-adapter

ENV AWS_LWA_PORT=8000

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
