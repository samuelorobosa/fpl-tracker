FROM python:3.12-slim

WORKDIR /app

# Install deps first so Docker can cache this layer between code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Snapshots get written here — mount this as a volume so they persist
# across container restarts (see docker-compose.yml)
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
