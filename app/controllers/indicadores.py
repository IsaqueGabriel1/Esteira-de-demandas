from flask import Blueprint, render_template
from flask_login import current_user, login_required

from ..services import indicadores_service

bp = Blueprint("indicadores", __name__, url_prefix="/indicadores")


@bp.route("/")
@login_required
def painel():
    return render_template("indicadores/painel.html", dados=indicadores_service.calcular(current_user))
