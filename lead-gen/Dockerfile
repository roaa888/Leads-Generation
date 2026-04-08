# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --silent
COPY frontend/ ./
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

# Install Python deps into the system interpreter (not a venv)
COPY backend/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copy backend source
COPY backend/ .

# Copy built frontend — FastAPI serves this in production
COPY --from=frontend /build/dist ./static

EXPOSE 8000
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
