from functools import wraps
from flask_login import current_user
from flask import abort

def _role_val(x):
    try:
        return x.value  # Enum -> string
    except Exception:
        return x        # já é string

def role_required(*roles):
    roles_norm = {_role_val(r) for r in roles}
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not current_user.is_authenticated:
                return abort(401)
            user_role = _role_val(getattr(current_user, 'role', None))
            if user_role not in roles_norm:
                return abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco