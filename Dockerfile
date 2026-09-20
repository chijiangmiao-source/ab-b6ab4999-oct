# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build the React frontend
# ---------------------------------------------------------------------------
FROM node:20-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: compile the exact-integer min-cut kernel
# ---------------------------------------------------------------------------
FROM gcc:14-bookworm AS native
WORKDIR /build
COPY backend/native/solver.cpp ./solver.cpp
RUN g++ -O2 -std=c++17 -o oct_solver solver.cpp

# ---------------------------------------------------------------------------
# Stage 3: backend API runtime (no compiler shipped)
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS api-base
WORKDIR /srv
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=native /build/oct_solver ./native/oct_solver
RUN chmod +x ./native/oct_solver
# Bundle the built UI so the API image can also serve it standalone.
COPY --from=frontend /build/frontend/dist ./app/static

ENV PYTHONUNBUFFERED=1 \
    OCT_HOST=0.0.0.0 \
    OCT_PORT=8000
EXPOSE 8000

# Container-local health check (uses the stdlib; curl need not be installed).
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

CMD ["sh", "-c", "uvicorn app.main:app --host ${OCT_HOST} --port ${OCT_PORT}"]

# ---------------------------------------------------------------------------
# Stage 4: one-shot end-to-end acceptance ("docker compose run --rm verify")
# ---------------------------------------------------------------------------
FROM api-base AS verify
COPY verify/ ./verify/
# Runs after web/api are healthy; non-zero exit reports acceptance failure.
CMD ["python", "verify/e2e_acceptance.py"]

# ---------------------------------------------------------------------------
# Stage 5: web edge (static SPA + reverse proxy to the API)
# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS web
COPY --from=frontend /build/frontend/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=5s --start-period=3s --retries=5 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
