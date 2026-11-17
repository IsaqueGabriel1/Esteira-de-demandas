from datetime import date

from flask import Blueprint, Response, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import DemandaForm
from ..models import Eixo
from ..services import demanda_service, divisao_service, exportacao_service, permissoes, usuario_service
from ..services.erros import RegraNegocioError
from ..services.fluxo import Acao, Status
from ..services.perfis import Perfil

bp = Blueprint("demandas", __name__)


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def _int(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _filtros_da_url():
    return {
        "eixo_id": _int(request.args.get("eixo")),
        "status": request.args.get("status") if request.args.get("status") in Status.TODOS else None,
        "atribuido_id": _int(request.args.get("responsavel")),
        # Divisão do cadastro do responsável (mesma regra dos Indicadores)
        "divisao_responsavel": request.args.get("divisao") or None,
        "faixa": request.args.get("faixa") or None,
        "atrasadas": request.args.get("atrasadas") == "1",
        "busca": request.args.get("busca", "").strip(),
    }


def _opcoes_filtro(filtros):
    divisao = filtros.get("divisao_responsavel")
    return {
        "eixos": Eixo.query.filter_by(ativo=True).order_by(Eixo.numero).all(),
        "usuarios": [u for u in usuario_service.listar_ativos() if not divisao or u.divisao == divisao],
        "divisoes": divisao_service.siglas_para_usuarios(atual=divisao),
    }


def _obter_ou_404(demanda_id):
    demanda = demanda_service.obter(current_user, demanda_id)
    if demanda is None:
        abort(404)
    return demanda


def _form_demanda(demanda=None):
    form = DemandaForm(obj=demanda) if demanda else DemandaForm()
    form.configurar(
        current_user,
        Eixo.query.filter_by(ativo=True).order_by(Eixo.numero).all(),
        usuario_service.listar_ativos(),
    )
    if demanda and request.method == "GET":
        form.atribuido_id.data = demanda.atribuido_id or 0
        form.apoio_ids.data = [u.id for u in demanda.apoios]
        form.gravidade.data = demanda.gravidade or 0
        form.urgencia.data = demanda.urgencia or 0
        form.tendencia.data = demanda.tendencia or 0
    return form


# ---------------------------------------------------------------------------
# Telas
# ---------------------------------------------------------------------------

@bp.route("/")
@login_required
def inicio():
    return redirect(url_for("demandas.quadro"))


@bp.route("/quadro")
@login_required
def quadro():
    filtros = _filtros_da_url()
    colunas = demanda_service.quadro(current_user, filtros)
    return render_template("demandas/quadro.html", colunas=colunas, filtros=filtros, **_opcoes_filtro(filtros))


@bp.route("/demandas")
@login_required
def lista():
    filtros = _filtros_da_url()
    filtros["incluir_canceladas"] = request.args.get("canceladas") == "1"
    demandas = demanda_service.consultar(current_user, filtros).all()

    if request.args.get("formato") == "csv":
        conteudo = exportacao_service.demandas_para_csv(demandas)
        return Response(
            conteudo,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=demandas.csv"},
        )
    return render_template("demandas/lista.html", demandas=demandas, filtros=filtros, **_opcoes_filtro(filtros))


@bp.route("/minhas")
@login_required
def minhas():
    # Usuário Comum já só vê as próprias demandas no quadro: a aba não existe para ele
    if current_user.perfil == Perfil.USUARIO:
        return redirect(url_for("demandas.quadro"))
    return render_template("demandas/minhas.html", grupos=demanda_service.minhas(current_user))


@bp.route("/demandas/nova", methods=["GET", "POST"])
@login_required
def nova():
    if not permissoes.pode_criar_demanda(current_user.perfil):
        abort(403)
    form = _form_demanda()
    if form.validate_on_submit():
        try:
            demanda = demanda_service.criar(current_user, form.para_dados())
            flash(f"Demanda #{demanda.id} criada.", "success")
            return redirect(url_for("demandas.detalhe", demanda_id=demanda.id))
        except RegraNegocioError as erro:
            db.session.rollback()
            flash(erro.mensagem, "danger")
    return render_template("demandas/form.html", form=form, demanda=None)


@bp.route("/demandas/<int:demanda_id>")
@login_required
def detalhe(demanda_id):
    demanda = _obter_ou_404(demanda_id)
    demanda_service.marcar_comentarios_lidos(current_user, demanda)
    return render_template(
        "demandas/detalhe.html",
        demanda=demanda,
        acoes=demanda_service.acoes_disponiveis(current_user, demanda),
        pode_prazo_acordado=demanda_service.pode_definir_prazo_acordado(current_user, demanda),
        pode_pasta_rede=demanda_service.pode_definir_pasta_rede(current_user, demanda),
        pendencias_atribuir=demanda_service.pendencias_para_atribuir(demanda),
        usuarios=usuario_service.listar_ativos(),
    )


@bp.route("/demandas/<int:demanda_id>/editar", methods=["GET", "POST"])
@login_required
def editar(demanda_id):
    if not permissoes.pode_editar_demanda(current_user.perfil):
        abort(403)
    demanda = _obter_ou_404(demanda_id)
    if demanda.finalizada:
        flash("Demandas concluídas ou canceladas não podem ser editadas.", "warning")
        return redirect(url_for("demandas.detalhe", demanda_id=demanda.id))
    form = _form_demanda(demanda)
    if form.validate_on_submit():
        try:
            demanda_service.editar(current_user, demanda, form.para_dados())
            flash("Demanda atualizada.", "success")
            return redirect(url_for("demandas.detalhe", demanda_id=demanda.id))
        except RegraNegocioError as erro:
            db.session.rollback()
            flash(erro.mensagem, "danger")
    return render_template("demandas/form.html", form=form, demanda=demanda)


# ---------------------------------------------------------------------------
# Ações (POST)
# ---------------------------------------------------------------------------

@bp.route("/demandas/<int:demanda_id>/acao/<acao>", methods=["POST"])
@login_required
def executar_acao(demanda_id, acao):
    demanda = _obter_ou_404(demanda_id)
    texto = request.form.get("texto", "")
    mensagens = {
        Acao.ATRIBUIR: "Demanda atribuída.",
        Acao.ACEITAR: "Você aceitou a demanda.",
        Acao.INICIAR: "Demanda iniciada.",
        Acao.RECUSAR: "Demanda recusada. Ela voltou para quem atribuiu.",
        Acao.ENVIAR_REVISAO: "Entrega enviada para revisão.",
        Acao.APROVAR: "Entrega aprovada. Demanda concluída.",
        Acao.DEVOLVER: "Entrega devolvida para ajustes.",
        Acao.RETOMAR: "A demanda voltou para Em andamento.",
        Acao.CANCELAR: "Demanda cancelada.",
    }
    if acao not in mensagens:
        abort(404)
    try:
        if acao == Acao.ATRIBUIR:
            demanda_service.atribuir(current_user, demanda, _int(request.form.get("atribuido_id")))
        elif acao == Acao.ACEITAR:
            demanda_service.aceitar(current_user, demanda)
        elif acao == Acao.INICIAR:
            demanda_service.iniciar(current_user, demanda)
        elif acao == Acao.RECUSAR:
            demanda_service.recusar(current_user, demanda, texto)
        elif acao == Acao.ENVIAR_REVISAO:
            demanda_service.enviar_revisao(current_user, demanda, texto)
        elif acao == Acao.APROVAR:
            demanda_service.aprovar(current_user, demanda, texto)
        elif acao == Acao.DEVOLVER:
            demanda_service.devolver(current_user, demanda, texto)
        elif acao == Acao.RETOMAR:
            demanda_service.retomar(current_user, demanda, texto)
        elif acao == Acao.CANCELAR:
            demanda_service.cancelar(current_user, demanda, texto)
        flash(mensagens[acao], "success")
    except RegraNegocioError as erro:
        db.session.rollback()
        flash(erro.mensagem, "danger")

    if not demanda_service.pode_ver(current_user, demanda):
        return redirect(url_for("demandas.minhas"))
    return redirect(url_for("demandas.detalhe", demanda_id=demanda.id))


@bp.route("/demandas/<int:demanda_id>/gut", methods=["POST"])
@login_required
def definir_gut(demanda_id):
    demanda = _obter_ou_404(demanda_id)
    try:
        alterou = demanda_service.definir_gut(
            current_user, demanda,
            _int(request.form.get("gravidade")),
            _int(request.form.get("urgencia")),
            _int(request.form.get("tendencia")),
        )
        flash(f"Prioridade definida: P = {demanda.prioridade}." if alterou else "Os pesos não mudaram.", "success")
    except RegraNegocioError as erro:
        db.session.rollback()
        flash(erro.mensagem, "danger")
    return redirect(url_for("demandas.detalhe", demanda_id=demanda.id))


@bp.route("/demandas/<int:demanda_id>/pasta-rede", methods=["POST"])
@login_required
def definir_pasta_rede(demanda_id):
    demanda = _obter_ou_404(demanda_id)
    try:
        alterou = demanda_service.definir_pasta_rede(current_user, demanda, request.form.get("pasta_rede"))
        flash("Pasta da rede salva." if alterou else "A pasta da rede não mudou.", "success")
    except RegraNegocioError as erro:
        db.session.rollback()
        flash(erro.mensagem, "danger")
    return redirect(url_for("demandas.detalhe", demanda_id=demanda.id))


@bp.route("/demandas/<int:demanda_id>/comentarios", methods=["POST"])
@login_required
def comentar(demanda_id):
    demanda = _obter_ou_404(demanda_id)
    try:
        demanda_service.comentar(current_user, demanda, request.form.get("texto"))
        flash("Comentário adicionado.", "success")
    except RegraNegocioError as erro:
        db.session.rollback()
        flash(erro.mensagem, "danger")
    return redirect(url_for("demandas.detalhe", demanda_id=demanda.id, _anchor="comentarios"))


@bp.route("/demandas/<int:demanda_id>/comentarios/<int:comentario_id>/editar", methods=["POST"])
@login_required
def editar_comentario(demanda_id, comentario_id):
    demanda = _obter_ou_404(demanda_id)
    try:
        alterou = demanda_service.editar_comentario(current_user, demanda, comentario_id, request.form.get("texto"))
        flash("Comentário atualizado." if alterou else "O comentário não mudou.", "success")
    except RegraNegocioError as erro:
        db.session.rollback()
        flash(erro.mensagem, "danger")
    return redirect(url_for("demandas.detalhe", demanda_id=demanda.id, _anchor="comentarios"))


@bp.route("/demandas/<int:demanda_id>/comentarios/<int:comentario_id>/remover", methods=["POST"])
@login_required
def remover_comentario(demanda_id, comentario_id):
    demanda = _obter_ou_404(demanda_id)
    try:
        demanda_service.remover_comentario(current_user, demanda, comentario_id)
        flash("Comentário removido.", "success")
    except RegraNegocioError as erro:
        db.session.rollback()
        flash(erro.mensagem, "danger")
    return redirect(url_for("demandas.detalhe", demanda_id=demanda.id, _anchor="comentarios"))


@bp.route("/demandas/<int:demanda_id>/prazo-acordado", methods=["POST"])
@login_required
def definir_prazo_acordado(demanda_id):
    demanda = _obter_ou_404(demanda_id)
    try:
        valor = (request.form.get("prazo_acordado") or "").strip()
        try:
            prazo = date.fromisoformat(valor) if valor else None
        except ValueError:
            raise RegraNegocioError("Data inválida para o prazo acordado.")
        alterou = demanda_service.definir_prazo_acordado(current_user, demanda, prazo)
        flash("Prazo acordado salvo." if alterou else "O prazo acordado não mudou.", "success")
    except RegraNegocioError as erro:
        db.session.rollback()
        flash(erro.mensagem, "danger")
    return redirect(url_for("demandas.detalhe", demanda_id=demanda.id))


@bp.route("/demandas/<int:demanda_id>/mover", methods=["POST"])
@login_required
def mover(demanda_id):
    """Endpoint do arrastar e soltar do quadro (JSON)."""
    demanda = _obter_ou_404(demanda_id)
    destino = (request.get_json(silent=True) or {}).get("status")
    if destino not in Status.TODOS:
        return jsonify(ok=False, erro="Status de destino inválido."), 400
    try:
        demanda_service.mover_por_arraste(current_user, demanda, destino)
    except RegraNegocioError as erro:
        db.session.rollback()
        return jsonify(ok=False, erro=erro.mensagem), 422
    return jsonify(ok=True, status=demanda.status, rotulo=demanda.status_rotulo)
