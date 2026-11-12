from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from ..services import divisao_service, indicadores_service, permissoes, usuario_service

bp = Blueprint("indicadores", __name__, url_prefix="/indicadores")


def _int(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


@bp.route("/")
@login_required
def painel():
    # A divisão filtrada é a do cadastro do responsável pela demanda
    filtros = {"divisao_responsavel": request.args.get("divisao") or None}
    # Quem só vê as próprias demandas não tem o que filtrar por usuário
    if permissoes.pode_ver_todas(current_user.perfil):
        filtros["atribuido_id"] = _int(request.args.get("usuario"))
    return render_template(
        "indicadores/painel.html",
        dados=indicadores_service.calcular(current_user, filtros, request.args.get("periodo")),
        periodos=indicadores_service.PERIODOS,
        filtros=filtros,
        usuarios=[u for u in usuario_service.listar_ativos()
                  if not filtros["divisao_responsavel"] or u.divisao == filtros["divisao_responsavel"]],
        divisoes=divisao_service.siglas_para_usuarios(atual=filtros["divisao_responsavel"]),
    )
