# Pinned to match local development (3.13). Homebrew's 3.12/3.14 builds are
# broken on this Mac, so the venv and the image should not drift apart.
FROM python:3.13-slim

# Unbuffered so logs reach Render's log stream immediately.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /srv

# Deps first, so this layer caches between code changes. Runtime deps only —
# pytest and friends live in requirements-dev.txt and are not shipped.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Snapshots must land on a mounted persistent disk, not the image. See
# render.yaml — FPL_DATA_DIR points at the mount.
ENV FPL_DATA_DIR=/var/data

# Drop privileges. The disk mount is chowned by the platform, but create the
# fallback path so a run without a mount still works.
RUN mkdir -p /var/data && useradd --create-home --uid 10001 app \
    && chown -R app:app /srv /var/data
USER app

EXPOSE 8000

# Render injects $PORT; the default keeps `docker run -p 8000:8000` working.
# One worker on purpose: snapshots are flat files, and concurrent workers
# would race each other writing them.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
