FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libsodium-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

RUN apt-get purge -y --auto-remove gcc libffi-dev libsodium-dev

COPY . .

EXPOSE 8000

CMD ["uvicorn", "CCOIN.main:app", "--host", "0.0.0.0", "--port", "8000"]
