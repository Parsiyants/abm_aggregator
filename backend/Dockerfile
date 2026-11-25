FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Зависимости уже зафиксированы в requirements.txt (сгенерирован pip-compile).
# Это даёт воспроизводимую сборку и быстрый CI.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной код (.env в образ не попадает — см. .dockerignore)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
