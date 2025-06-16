# Dockerfile
FROM python:3.11-slim

WORKDIR /app

ARG GITHUB_TOKEN

# Install system dependencies including curl for health checks
RUN apt-get update && apt-get install -y \
    curl git \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install poetry

# Configure poetry: don't create virtual env (we're in container)
RUN poetry config virtualenvs.create false

RUN git config --global url."https://oauth2:${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/"

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

RUN touch README.md

# Install dependencies
RUN poetry install --no-interaction --no-ansi

# Copy application code
COPY isagog_docs /app/isagog_docs


