# wsgi.py
import os

# Tenta usar a factory (create_app). Se não houver, tenta achar um objeto Flask chamado "app".
try:
    from app import create_app
    app = create_app()
except Exception:
    # Fallback: se no seu pacote "app" existir um objeto Flask chamado "app"
    # (ex.: definido em app/__init__.py), vamos usá-lo.
    from app import app as app  # noqa: F401

if __name__ == "__main__":
    # Útil para rodar localmente sem gunicorn: python wsgi.py
    port = int(os.getenv("APP_PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
