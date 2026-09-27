# =============================================================================
# VoxAI Backend Dockerfile
# =============================================================================
#
# CONCEPT: Multi-stage Docker Build
# -----------------------------------
# A Docker image is built in "stages". We use two stages:
#
# Stage 1 (builder): Install all dependencies. This stage is large.
# Stage 2 (runtime): Copy only what's needed from Stage 1. This is the final image.
#
# WHY? The builder stage has pip, compilers, build tools — lots of junk we
# don't need at runtime. Multi-stage keeps the final image lean and secure.
#
# Think of it like baking bread:
#   Stage 1 = Kitchen with flour, yeast, mixing bowls (messy but needed to bake)
#   Stage 2 = Just the finished bread (clean, ready to serve)

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.12-slim AS builder

# Set environment variables that affect Python behavior inside the container
ENV PYTHONDONTWRITEBYTECODE=1  \
    # Don't write .pyc cache files (saves disk space in container)
    PYTHONUNBUFFERED=1
    # Don't buffer stdout/stderr (logs appear immediately, not in batches)

WORKDIR /build

# Install system dependencies needed to compile some Python packages
# --no-install-recommends keeps it minimal
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# IMPORTANT: Copy requirements FIRST (before copying code).
# WHY? Docker caches layers. If requirements.txt hasn't changed,
# Docker reuses the cached pip install layer — much faster rebuilds.
# If we copied all code first, any code change would re-run pip install.
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install only runtime system libraries (not build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Create a non-root user for security
# NEVER run production containers as root.
# If someone exploits your app, root access = game over.
RUN useradd --create-home --shell /bin/bash voxai
USER voxai

# Copy application code (owned by voxai user)
COPY --chown=voxai:voxai . .

EXPOSE 8000

# Health check: Docker will call this every 30s to verify the container is alive
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the server
# --workers 1 for now (single process). In production: set to CPU count * 2 + 1
# --host 0.0.0.0 means "listen on all network interfaces" (required in Docker)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
