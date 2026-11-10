from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user

from ..extensions import db
from ..forms import DivisaoForm
from ..models import Divisao
from ..services import divisao_service
from ..services.erros import RegraNegocioError
from .decoradores import administrador_requerido

bp = Blueprint("divisoes", __name__, url_prefix="/divisoes")


@bp.route("/")
@administrador_requerido
def lista():
    return render_template(
        "divisoes/lista.html", divisoes=divisao_service.listar_todas(), uso=divisao_service.contar_uso()
    )


@bp.route("/nova", methods=["GET", "POST"])
@administrador_requerido
def nova():
    form = DivisaoForm()
    if form.validate_on_submit():
        try:
            divisao = divisao_service.criar(
                current_user, form.sigla.data, para_usuarios=form.para_usuarios.data, para_demandas=form.para_demandas.data
            )
            flash(f"Divisão {divisao.sigla} cadastrada.", "success")
            return redirect(url_for("divisoes.lista"))
        except RegraNegocioError as erro:
            db.session.rollback()
            flash(erro.mensagem, "danger")
    return render_template("divisoes/form.html", form=form, divisao=None)


@bp.route("/<int:divisao_id>/editar", methods=["GET", "POST"])
@administrador_requerido
def editar(divisao_id):
    divisao = db.session.get(Divisao, divisao_id) or abort(404)
    form = DivisaoForm(obj=divisao)
    form.sigla.data = divisao.sigla  # a sigla não é editável
    if form.validate_on_submit():
        try:
            divisao_service.atualizar(
                current_user, divisao, form.para_usuarios.data, form.para_demandas.data, form.ativa.data
            )
            flash(f"Divisão {divisao.sigla} atualizada.", "success")
            return redirect(url_for("divisoes.lista"))
        except RegraNegocioError as erro:
            db.session.rollback()
            flash(erro.mensagem, "danger")
    return render_template("divisoes/form.html", form=form, divisao=divisao)
