# syntax=docker/dockerfile:1
FROM python:3.12-slim

# System deps (add build tools if you compile any wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Copy only dependency files first (better layer caching)
COPY pyproject.toml uv.lock* ./

# Install deps (frozen if uv.lock exists)
# --no-dev keeps image smaller; remove if you need dev deps in container
RUN uv sync --frozen --no-dev

# Copy the rest of the app
COPY . .

# Default env (override via compose env_file)
ENV HOST=0.0.0.0
ENV PORT=9000
ENV PYTHONUNBUFFERED=1

# You can replace this with gunicorn later if you prefer
CMD ["uv", "run", "python", "run.py"]
