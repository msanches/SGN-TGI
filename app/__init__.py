from flask import Flask, redirect, url_for, request
from .config import Config
from .extensions import db, migrate, login_manager, csrf, bcrypt
from .auth import auth_bp
from .admin import admin_bp
from .professors import professors_bp
from .guests import guests_bp
from .models import User  # garante que modelos carregam
from .commands import register_commands
import os

from app.reports import reports_bp

# __init__.py
import logging, sys, uuid
from werkzeug.exceptions import HTTPException
from flask import render_template
from .extensions import db

def setup_logging(app):
    # log no stdout (aparece no `docker compose logs -f web`)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s"))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

    # (opcional) ver eventos do pool do SQLAlchemy quando necessário
    if app.config.get("SQLALCHEMY_ECHO"):
        logging.getLogger("sqlalchemy.pool").setLevel(logging.INFO)
        logging.getLogger("sqlalchemy.pool").addHandler(handler)

def register_error_handlers(app):
    @app.teardown_request
    def _teardown_request(exc):
        # se alguma view/executor levantou exceção, limpamos a sessão
        if exc:
            db.session.rollback()
        # remove SEMPRE a sessão ao fim da request
        db.session.remove()

    @app.errorhandler(Exception)
    def _handle_any_exception(e):
        if isinstance(e, HTTPException):
            return e  # deixa 4xx/405/404 seguirem
        err_id = uuid.uuid4().hex[:8]
        app.logger.exception(f"[{err_id}] Unhandled exception")
        db.session.rollback()
        return render_template("errors/500.html", err_id=err_id), 500

def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.auto_reload = True

    from .utils.context import register_context
    register_context(app)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    bcrypt.init_app(app)
    setup_logging(app)
    register_error_handlers(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    register_commands(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(professors_bp, url_prefix="/professors")
    app.register_blueprint(guests_bp, url_prefix="/guests")
    app.register_blueprint(reports_bp)

    from flask_login import login_required, current_user
    @app.route("/")
    @login_required
    def index():
        role = getattr(current_user, 'role_value', None) or getattr(getattr(current_user, 'role', None), 'value', None) or getattr(current_user, 'role', None)
        if role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif role == 'professor':
            return redirect(url_for('professors.dashboard'))
        return redirect(url_for('guests.banner'))

    @app.context_processor
    def inject_page_label():
        labels = {
            # ADMIN
            "admin.users_list": "Usuários",
            "admin.user_form": "Usuários",
            "admin.groups_list": "Grupos",
            "admin.groups_edit": "Grupos",
            "admin.groups_new":  "Grupos",
            # PROFESSOR
            "professors.dashboard": "Dashboard",
            "professors.groups_list": "Grupos",
            "professors.offerings_list": "Ofertas",
            "professors.offering_detail": "Oferta",
            # CONVIDADO
            "guests.dashboard": "Dashboard",
            "guests.poster_eval": "Avaliar",
            "guests.my_reviews": "Avaliações",
        }
        return {"page_label": labels.get(request.endpoint)}

    return app
