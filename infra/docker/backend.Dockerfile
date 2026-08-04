FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# System deps for OCR + pg (PaddleOCR wheels are manylinux; slim is fine for skeleton)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/README* ./
COPY backend/src ./src
RUN pip install --no-cache-dir .

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic

EXPOSE 8000
CMD ["uvicorn", "invoiceiq.main:app", "--host", "0.0.0.0", "--port", "8000"]
