# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dependências úteis para sinais/daemon
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential tini \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV APP_PORT=8000
EXPOSE 8000

# tini trata sinais (stop/restart) corretamente
CMD ["tini","-g","--","gunicorn","-w","3","-b","0.0.0.0:8000","wsgi:app"]
