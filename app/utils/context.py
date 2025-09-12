from flask_login import current_user
from ..models import Role

def register_context(app):
    @app.context_processor
    def inject_auth_flags():
        role = "guest"
        if current_user.is_authenticated:
            r = getattr(current_user, "role", None)
            role = r.value if isinstance(r, Role) else (r or "guest")
        return {
            "user_role": role,
            "is_admin": role == "admin",
            "is_professor": role == "professor",
            "is_guest": role == "guest",
        }
