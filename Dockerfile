FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libsodium-dev \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc libffi-dev libsodium-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . .

web: uvicorn CCOIN.main:app --host 0.0.0.0 --port $PORT
