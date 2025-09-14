# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEB_CONCURRENCY=2 \
    THREADS=8 \
    PORT=8000 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata curl \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 appuser
WORKDIR /app

# Runtime deps
RUN pip install --no-cache-dir \
    gunicorn==22.* \
    flask==3.* \
    markdown==3.* \
    python-frontmatter==1.* \
    bleach==6.*

# Copy the *pistlar/* contents (Docker build context is /pistlar)
COPY . /app

# App defaults (compose can override)
ENV POSTS_DIR=/data/posts \
    ASSETS_DIR=/data/assets \
    PAGE_SIZE=10 \
    SITE_TITLE="My Markdown Blog" \
    APP_MODULE="wsgi:app"

EXPOSE 8000
USER appuser

CMD gunicorn "$APP_MODULE" \
    --bind 0.0.0.0:${PORT} \
    --workers ${WEB_CONCURRENCY} \
    --threads ${THREADS} \
    --access-logfile '-' --error-logfile '-'
