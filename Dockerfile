# tty-theme FastAPI — production-ready image
# Identical behaviour in Docker Compose (local) and Cloud Run (production).

FROM python:3.11-slim

# Non-root user
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

WORKDIR /app

# Install uv
RUN pip install uv --no-cache-dir

# Copy dependency files first (cache layer)
COPY pyproject.toml uv.lock ./

# Install production dependencies only
RUN uv sync --frozen --no-dev --extra api

# Copy application source
COPY api/       ./api/
COPY cache/     ./cache/
COPY generator/ ./generator/
COPY image/     ./image/
COPY modes/     ./modes/
COPY providers/ ./providers/
COPY security/  ./security/
COPY themes/    ./themes/
COPY schema/    ./schema/

# Owned by non-root user
RUN chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
