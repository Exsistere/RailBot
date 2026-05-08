FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:$PATH"
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen

COPY . .

CMD sh -c "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
