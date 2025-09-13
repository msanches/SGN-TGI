# wsgi.py
# Tenta usar a factory pattern (create_app); se não houver, usa app global.
try:
    from app import create_app
    app = create_app()
except Exception:
    from app import app as app  # app = Flask(__name__) já existente
