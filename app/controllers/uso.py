from flask import Blueprint, render_template, request

from ..services import uso_service
from .decoradores import administrador_requerido

bp = Blueprint("uso", __name__, url_prefix="/uso")


@bp.route("/")
@administrador_requerido
def painel():
    return render_template(
        "uso/painel.html",
        dados=uso_service.painel(request.args.get("periodo", uso_service.PERIODO_PADRAO)),
        periodos=uso_service.PERIODOS,
    )
