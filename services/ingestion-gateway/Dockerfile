FROM python:3.11-slim

WORKDIR /app

COPY ingestion-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingestion-gateway/app/ /app/app/
COPY shared/ /shared/

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8004}
