from flask import Blueprint

professors_bp = Blueprint(
    "professors",
    __name__,
    url_prefix="/professors",
    template_folder="templates",
    static_folder=None,
)

from . import routes  # noqa
