FROM python:3.12-slim

WORKDIR /app

# Install system dependencies required by PostgreSQL driver, OpenCV, and Tesseract OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY contracts /app/contracts
COPY brand_kit /app/brand_kit
COPY engine /app/engine
COPY scripts /app/scripts
COPY api /app/api

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "cd /app/api && alembic upgrade head && cd /app && uvicorn api.src.main:app --host 0.0.0.0 --port 8000"]
