FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml ./

RUN uv sync

COPY . .

CMD sh -c "uv run streamlit run app.py --server.port ${PORT:-8501} --server.address 0.0.0.0"