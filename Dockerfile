# --- build the React bundle ---------------------------------------------
FROM node:20-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json* ./
# dev deps are needed here -- vite is the build tool
RUN npm ci --ignore-scripts || npm install --ignore-scripts
COPY frontend/ ./
RUN npm run build

# --- run FastAPI, serving the API and that bundle from one origin --------
FROM python:3.12-slim
WORKDIR /app

# Default suits a host with a mounted volume (Railway). Hosts without a disk
# (Render free) override DATABASE_URL with a Postgres URL instead.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_URL=sqlite:////data/calories.db

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=ui /ui/dist ./frontend/dist

# Railway mounts its volume here; the DB lives on it so data survives deploys.
RUN mkdir -p /data

# EXPOSE must agree with the port actually bound: some platforms probe the
# exposed port rather than the one they set in $PORT, and a mismatch shows up
# as "service unavailable" with no logs at all. 10000 is Render's default.
EXPOSE 10000
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
