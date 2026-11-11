from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..services import permissao_service, permissoes
from ..services.erros import RegraNegocioError
from .decoradores import administrador_requerido

bp = Blueprint("permissoes", __name__, url_prefix="/permissoes")


@bp.route("/")
@administrador_requerido
def matriz():
    return render_template(
        "permissoes/matriz.html",
        funcionalidades=permissoes.FUNCIONALIDADES,
        matriz=permissao_service.matriz(),
        padrao=permissoes.padrao,
        historico=permissao_service.historico(),
        rotulos={chave: rotulo for chave, rotulo, _ in permissoes.FUNCIONALIDADES},
    )


@bp.route("/", methods=["POST"])
@administrador_requerido
def salvar():
    # Cada checkbox marcado chega como "PERFIL:chave"
    ativas = {tuple(valor.split(":", 1)) for valor in request.form.getlist("ativa") if ":" in valor}
    try:
        alteradas = permissao_service.salvar(current_user, ativas)
        flash(f"Permissões salvas ({alteradas} alteração(ões)).", "success")
    except RegraNegocioError as erro:
        db.session.rollback()
        flash(erro.mensagem, "danger")
    return redirect(url_for("permissoes.matriz"))


@bp.route("/restaurar", methods=["POST"])
@administrador_requerido
def restaurar():
    alteradas = permissao_service.restaurar_padrao(current_user)
    flash(f"Permissões restauradas para o padrão ({alteradas} alteração(ões)).", "success")
    return redirect(url_for("permissoes.matriz"))
