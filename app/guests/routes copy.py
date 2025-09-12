from flask import render_template
from flask_login import login_required
from ..utils.decorators import role_required
from . import guests_bp

@guests_bp.route("/banner")
@login_required
@role_required("convidado", "professor", "admin")
def banner():
    return render_template("guests/banner.html")
