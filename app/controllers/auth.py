from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..forms import CadastroForm, LoginForm, MinhaDivisaoForm, TrocarSenhaForm
from ..services import usuario_service
from ..services.erros import RegraNegocioError

bp = Blueprint("auth", __name__)


def _destino_seguro(proximo):
    """Evita redirecionamento para outro site (open redirect)."""
    if not proximo:
        return None
    url = urlparse(proximo)
    if url.netloc or url.scheme or not proximo.startswith("/"):
        return None
    return proximo


# Rotas liberadas enquanto o usuário ainda não informou a divisão.
ROTAS_SEM_DIVISAO = {"auth.minha_divisao", "auth.logout", "static"}


@bp.before_app_request
def exigir_divisao():
    if (
        current_user.is_authenticated
        and request.endpoint not in ROTAS_SEM_DIVISAO
        and usuario_service.precisa_informar_divisao(current_user)
    ):
        return redirect(url_for("auth.minha_divisao"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("demandas.quadro"))
    form = LoginForm()
    if form.validate_on_submit():
        usuario = usuario_service.autenticar(form.email.data, form.senha.data)
        if usuario:
            login_user(usuario, remember=form.lembrar.data)
            return redirect(_destino_seguro(request.args.get("next")) or url_for("demandas.quadro"))
        elif usuario_service.aguardando_aprovacao(form.email.data, form.senha.data):
            flash("Seu cadastro ainda aguarda a aprovação de um Gerente.", "warning")
        else:
            flash("E-mail ou senha inválidos.", "danger")
    return render_template("auth/login.html", form=form)


@bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for("demandas.quadro"))
    form = CadastroForm()
    if form.validate_on_submit():
        try:
            usuario_service.autocadastrar(form.nome.data, form.email.data, form.senha.data, form.divisao.data)
            flash("Cadastro enviado! Você poderá entrar assim que um Gerente aprovar o acesso.", "success")
            return redirect(url_for("auth.login"))
        except RegraNegocioError as erro:
            flash(erro.mensagem, "danger")
    return render_template("auth/cadastro.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/minha-senha", methods=["GET", "POST"])
@login_required
def minha_senha():
    form = TrocarSenhaForm()
    if form.validate_on_submit():
        try:
            usuario_service.alterar_propria_senha(current_user, form.senha_atual.data, form.nova_senha.data)
            flash("Senha alterada com sucesso.", "success")
            return redirect(url_for("demandas.quadro"))
        except RegraNegocioError as erro:
            flash(erro.mensagem, "danger")
    return render_template("auth/minha_senha.html", form=form)


@bp.route("/minha-divisao", methods=["GET", "POST"])
@login_required
def minha_divisao():
    form = MinhaDivisaoForm(obj=current_user)
    if form.validate_on_submit():
        try:
            usuario_service.definir_propria_divisao(current_user, form.divisao.data)
            flash("Divisão registrada.", "success")
            return redirect(url_for("demandas.quadro"))
        except RegraNegocioError as erro:
            flash(erro.mensagem, "danger")
    return render_template("auth/minha_divisao.html", form=form)
