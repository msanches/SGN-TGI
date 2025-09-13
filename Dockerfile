# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# Instala somente o que precisa (tini) — nada de build-essential
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -fsSL -o /usr/local/bin/tini https://github.com/krallin/tini/releases/download/v0.19.0/tini \
 && chmod +x /usr/local/bin/tini \
 && apt-get purge -y --auto-remove curl \
 && rm -rf /var/lib/apt/lists/*

# Usuário não-root
RUN useradd -m appuser
WORKDIR /app

# Requisitos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação
COPY . .

# Porta interna (gunicorn)
EXPOSE 8000

# Tini como PID 1
ENTRYPOINT ["/usr/bin/tini","-g","--"]

# Gunicorn: 1 worker + 2 threads, timeouts curtos, pouco log
CMD ["gunicorn","-w","1","-k","gthread","--threads","3","--keep-alive","5","--timeout","30", "--graceful-timeout","30","--max-requests","500","--max-requests-jitter","50","--log-level","warning","-b","0.0.0.0:8000","wsgi:app"]