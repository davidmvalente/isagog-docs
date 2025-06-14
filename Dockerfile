# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including curl for health checks
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install poetry

# Configure poetry: don't create virtual env (we're in container)
RUN poetry config virtualenvs.create false

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

RUN touch README.md

# Install dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY main.py .

COPY src /app/src


