FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY core ./core
COPY api ./api
COPY bot ./bot
COPY alembic ./alembic
COPY alembic.ini main.py ./

RUN pip install --no-cache-dir .

CMD ["python", "main.py"]
