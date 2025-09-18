FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc \
    && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "CCOIN.main:app", "--bind", "0.0.0.0:8000"]
