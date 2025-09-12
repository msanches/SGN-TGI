from flask import Flask, redirect, url_for
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

    return app
