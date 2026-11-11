from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user

from ..extensions import db
from ..forms import UsuarioForm
from ..models import Usuario
from ..services import permissoes, usuario_service
from ..services.erros import RegraNegocioError
from .decoradores import permissao_requerida

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")


@bp.route("/")
@permissao_requerida(permissoes.pode_gerenciar_usuarios)
def lista():
    return render_template("usuarios/lista.html", usuarios=usuario_service.listar_todos())


@bp.route("/novo", methods=["GET", "POST"])
@permissao_requerida(permissoes.pode_gerenciar_usuarios)
def novo():
    form = UsuarioForm()
    if form.validate_on_submit():
        try:
            if not form.senha.data:
                raise RegraNegocioError("Informe uma senha inicial para o usuário.")
            usuario = usuario_service.criar(
                current_user, form.nome.data, form.email.data, form.perfil.data, form.senha.data,
                divisao=form.divisao.data or None,
            )
            flash(f"Usuário {usuario.nome} criado.", "success")
            return redirect(url_for("usuarios.lista"))
        except RegraNegocioError as erro:
            db.session.rollback()
            flash(erro.mensagem, "danger")
    return render_template("usuarios/form.html", form=form, usuario=None)


@bp.route("/<int:usuario_id>/editar", methods=["GET", "POST"])
@permissao_requerida(permissoes.pode_gerenciar_usuarios)
def editar(usuario_id):
    usuario = db.session.get(Usuario, usuario_id) or abort(404)
    form = UsuarioForm(obj=usuario)
    if form.validate_on_submit():
        try:
            usuario_service.atualizar(
                current_user, usuario, form.nome.data, form.email.data, form.perfil.data,
                ativo=form.ativo.data, nova_senha=form.senha.data or None, divisao=form.divisao.data or None,
            )
            flash("Usuário atualizado.", "success")
            return redirect(url_for("usuarios.lista"))
        except RegraNegocioError as erro:
            db.session.rollback()
            flash(erro.mensagem, "danger")
    return render_template("usuarios/form.html", form=form, usuario=usuario)
