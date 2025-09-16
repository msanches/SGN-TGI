FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Instala só curl/ca-certificates, pega o tini por HTTPS e remove curl depois
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -fsSL -o /usr/local/bin/tini https://github.com/krallin/tini/releases/download/v0.19.0/tini \
 && chmod +x /usr/local/bin/tini \
 && apt-get purge -y --auto-remove curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV APP_PORT=8000
EXPOSE 8000
CMD ["tini","-g","--","gunicorn","-w","1","-k","gthread","--threads","3", "--keep-alive","5", "-b","0.0.0.0:8000","wsgi:app"]
#CMD ["gunicorn","-w","1","-k","gthread","--threads","3","--keep-alive","5","--timeout","30", "--graceful-timeout","30","--max-requests","500","--max-requests-jitter","50","--log-level","warning","-b","0.0.0.0:8000","wsgi:app"]