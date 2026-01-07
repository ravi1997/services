#!/usr/bin/env bash
set -euo pipefail

# ---------- Config ----------
APP_NAME="services"
PORT="9000"
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env.docker"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"   # adjust if you need 3.11/3.10

echo "==> [1/7] Checking prerequisites..."

# docker
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found. Install Docker Engine first."
  exit 1
fi

# docker compose (plugin)
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose not available. Install docker-compose-plugin."
  exit 1
fi

# ---------- Install uv (host) ----------
echo "==> [2/7] Installing uv on host (if missing)..."
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # shellcheck disable=SC1090
  export PATH="$HOME/.local/bin:$PATH"
fi
uv --version

# ---------- Create/Update pyproject + uv.lock ----------
echo "==> [3/7] Creating/Updating pyproject.toml + uv.lock..."
if [[ ! -f pyproject.toml ]]; then
  uv init --app >/dev/null
fi

# If requirements.txt exists, import deps
if [[ -f requirements.txt ]]; then
  uv add -r requirements.txt
fi

# Ensure lock exists
uv lock

# ---------- Create Dockerfile ----------
echo "==> [4/7] Writing Dockerfile..."
cat > Dockerfile <<'EOF'
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
EOF

# ---------- Create docker-compose.yml ----------
echo "==> [5/7] Writing docker-compose.yml..."
cat > "${COMPOSE_FILE}" <<EOF
services:
  ${APP_NAME}-api:
    build: .
    container_name: ${APP_NAME}-api
    env_file:
      - ${ENV_FILE}
    ports:
      - "${PORT}:${PORT}"
    depends_on:
      - redis
    # DEV mode: bind mount so code changes reflect immediately (no rebuild needed)
    volumes:
      - .:/app
    command: ["uv", "run", "python", "run.py"]
    restart: unless-stopped

  ${APP_NAME}-worker:
    build: .
    container_name: ${APP_NAME}-worker
    env_file:
      - ${ENV_FILE}
    depends_on:
      - redis
    volumes:
      - .:/app
    # Adjust celery app path if different in your project:
    command: ["uv", "run", "celery", "-A", "app.extensions.celery", "worker", "--loglevel=info"]
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: ${APP_NAME}-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
EOF

# ---------- Create env file ----------
echo "==> [6/7] Writing ${ENV_FILE}..."
if [[ ! -f "${ENV_FILE}" ]]; then
  cat > "${ENV_FILE}" <<EOF
# App bind
HOST=0.0.0.0
PORT=${PORT}

# Redis inside compose
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# If you use flask env vars:
FLASK_ENV=development
EOF
else
  echo "NOTE: ${ENV_FILE} already exists; leaving it unchanged."
fi

# ---------- Bring up ----------
echo "==> [7/7] Building and starting containers..."
docker compose up -d --build

echo ""
echo "✅ Done."
echo "API should be on: http://<server-ip>:${PORT}"
echo "Logs: docker compose logs -f ${APP_NAME}-api"
echo "Stop: docker compose down"
