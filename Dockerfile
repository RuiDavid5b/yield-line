FROM python:3.14-slim

RUN pip install --no-cache-dir "uv==0.6.10"

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

RUN uv pip install --system --no-cache -e .

ENTRYPOINT ["python", "-m"]
