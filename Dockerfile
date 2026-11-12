FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    MEMORY_DB_PATH=/app/data/memory.db

RUN mkdir -p /app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY README.md .

EXPOSE 8000

CMD ["uvicorn", "backend.main:api", "--host", "0.0.0.0", "--port", "8000"]
