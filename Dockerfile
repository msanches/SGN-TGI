FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV APP_PORT=8000
EXPOSE 8000

CMD ["gunicorn","-w","3","-b","0.0.0.0:8000","wsgi:app"]
