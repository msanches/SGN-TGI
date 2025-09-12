from flask import Blueprint
guests_bp = Blueprint("guests", __name__, template_folder="templates")
from . import routes  # noqa
