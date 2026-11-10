FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY contracts /app/contracts
COPY api /app/api

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "api.src.main:app", "--host", "0.0.0.0", "--port", "8000"]

