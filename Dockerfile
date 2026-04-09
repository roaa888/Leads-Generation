# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /build
COPY lead-gen/frontend/package*.json ./
RUN npm ci --silent
COPY lead-gen/frontend/ ./
RUN VITE_API_URL="" VITE_WS_URL="" npm run build

# ── Stage 2: Python backend ───────────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

COPY lead-gen/backend/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY lead-gen/backend/ .

# Built frontend → FastAPI serves it as static files
COPY --from=frontend /build/dist ./static

EXPOSE 8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONFAULTHANDLER=1

CMD ["sh", "-c", "python -c 'import main; print(\"Import OK\")' 2>&1 && uvicorn main:app --host 0.0.0.0 --port 8000 --log-level debug"]
