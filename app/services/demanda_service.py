"""Regras de negócio das demandas: criação, edição, atribuição, fluxo de status,
priorização GUT, visibilidade e consultas.

Todas as funções que alteram dados recebem o usuário que está agindo,
validam permissões e registram o histórico. Os controllers apenas chamam
estas funções e tratam RegraNegocioError.
"""
from datetime import date, timedelta

from sqlalchemy import and_, func, or_

from ..extensions import db
from ..models import ComentarioDemanda, Demanda, Eixo, HistoricoDemanda, LeituraComentarios, TipoEvento, Usuario, demanda_apoio
from ..models.base import agora
from . import divisao_service, gut, permissoes
from .erros import PermissaoNegada, RegraNegocioError
from .perfis import Perfil
from .fluxo import Acao, Status, acao_por_arraste, proximo_status, transicao_permitida

TAMANHO_MINIMO_JUSTIFICATIVA = 10
TAMANHO_MAXIMO_PASTA_REDE = 500
TAMANHO_MAXIMO_COMENTARIO = 4000
# Quantos dias antes do prazo a demanda aparece no sino como "vence em breve"
DIAS_AVISO_PRAZO = 3


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def _registrar(demanda, usuario, tipo, descricao, dados=None):
    evento = HistoricoDemanda(
        demanda=demanda, usuario_id=usuario.id, tipo=tipo, descricao=descricao, dados=dados
    )
    db.session.add(evento)
    return evento


def _texto_obrigatorio(valor, nome):
    texto = (valor or "").strip()
    if not texto:
        raise RegraNegocioError(f"O campo '{nome}' é obrigatório.")
    return texto


def _justificativa(valor, nome="justificativa"):
    texto = (valor or "").strip()
    if len(texto) < TAMANHO_MINIMO_JUSTIFICATIVA:
        raise RegraNegocioError(
            f"Informe a {nome} com pelo menos {TAMANHO_MINIMO_JUSTIFICATIVA} caracteres."
        )
    return texto


def _validar_datas(inicio, termino):
    if inicio and termino and termino < inicio:
        raise RegraNegocioError("A data de término deve ser igual ou posterior à data de início.")


def _prazo_final():
    """Equivalente em SQL de Demanda.prazo_final."""
    return func.coalesce(Demanda.prazo_acordado, Demanda.termino)


def _buscar_eixo(eixo_id):
    eixo = db.session.get(Eixo, eixo_id) if eixo_id else None
    if not eixo or not eixo.ativo:
        raise RegraNegocioError("Selecione um eixo válido.")
    return eixo


def _buscar_usuario_ativo(usuario_id, papel="usuário"):
    usuario = db.session.get(Usuario, usuario_id) if usuario_id else None
    if not usuario or not usuario.ativo:
        raise RegraNegocioError(f"O {papel} selecionado não existe ou está inativo.")
    return usuario


def _texto_opcional(valor):
    return (valor or "").strip() or None


def _formatar_data(d):
    return d.strftime("%d/%m/%Y") if d else "—"


def _exigir_gestor(usuario, mensagem):
    if not permissoes.eh_gestor(usuario.perfil):
        raise PermissaoNegada(mensagem)


def _exigir_nao_finalizada(demanda):
    if demanda.finalizada:
        raise RegraNegocioError(f"A demanda está {demanda.status_rotulo.lower()} e não pode ser alterada.")


def _eh_atribuido(usuario, demanda):
    return demanda.atribuido_id is not None and demanda.atribuido_id == usuario.id


# ---------------------------------------------------------------------------
# GUT
# ---------------------------------------------------------------------------

def _aplicar_gut(usuario, demanda, gravidade, urgencia, tendencia):
    """Valida e grava os pesos, recalculando P. Registra histórico se algo mudou."""
    novos = (gravidade, urgencia, tendencia)
    if all(v is None for v in novos):
        return False
    if any(v is None for v in novos):
        raise RegraNegocioError("Informe os três pesos GUT (Gravidade, Urgência e Tendência).")

    g = gut.validar_peso(gravidade, "Gravidade")
    u = gut.validar_peso(urgencia, "Urgência")
    t = gut.validar_peso(tendencia, "Tendência")
    antigos = (demanda.gravidade, demanda.urgencia, demanda.tendencia)
    if antigos == (g, u, t):
        return False

    prioridade_antiga = demanda.prioridade
    demanda.gravidade, demanda.urgencia, demanda.tendencia = g, u, t
    demanda.prioridade = gut.calcular_prioridade(g, u, t)

    if prioridade_antiga is None:
        descricao = f"Pesos definidos: G={g}, U={u}, T={t} (P={demanda.prioridade})."
    else:
        descricao = (
            f"Pesos alterados de G={antigos[0]}, U={antigos[1]}, T={antigos[2]} (P={prioridade_antiga}) "
            f"para G={g}, U={u}, T={t} (P={demanda.prioridade})."
        )
    _registrar(
        demanda, usuario, TipoEvento.GUT, descricao,
        {
            "antes": {"g": antigos[0], "u": antigos[1], "t": antigos[2], "p": prioridade_antiga},
            "depois": {"g": g, "u": u, "t": t, "p": demanda.prioridade},
        },
    )
    return True


def definir_gut(usuario, demanda, gravidade, urgencia, tendencia):
    if not permissoes.pode_definir_gut(usuario.perfil):
        raise PermissaoNegada("Apenas Gerente, Chefe de Divisão ou Gestor do Plano podem definir os pesos GUT.")
    _exigir_nao_finalizada(demanda)
    if None in (gravidade, urgencia, tendencia):
        raise RegraNegocioError("Informe os três pesos GUT (Gravidade, Urgência e Tendência).")
    alterou = _aplicar_gut(usuario, demanda, gravidade, urgencia, tendencia)
    db.session.commit()
    return alterou


# ---------------------------------------------------------------------------
# Pasta da rede
# ---------------------------------------------------------------------------

def pode_definir_pasta_rede(usuario, demanda):
    """Quem trabalha na demanda (responsável e apoio) atualiza a pasta na tela da demanda."""
    return (_eh_atribuido(usuario, demanda) or usuario in demanda.apoios) and not demanda.finalizada


def definir_pasta_rede(usuario, demanda, pasta_rede):
    if not (_eh_atribuido(usuario, demanda) or usuario in demanda.apoios):
        raise PermissaoNegada("Somente o responsável e os usuários de apoio podem alterar a pasta da rede.")
    _exigir_nao_finalizada(demanda)
    pasta_rede = _texto_opcional(pasta_rede)
    if pasta_rede and len(pasta_rede) > TAMANHO_MAXIMO_PASTA_REDE:
        raise RegraNegocioError(f"A pasta da rede deve ter no máximo {TAMANHO_MAXIMO_PASTA_REDE} caracteres.")
    if demanda.pasta_rede == pasta_rede:
        return False
    demanda.pasta_rede = pasta_rede
    _registrar(demanda, usuario, TipoEvento.EDICAO, "Alterado: pasta da rede.")
    db.session.commit()
    return True


# ---------------------------------------------------------------------------
# Comentários
# ---------------------------------------------------------------------------

def pode_gerenciar_comentario(usuario, comentario):
    """O autor edita e remove o próprio comentário; o gestor também pode remover."""
    return comentario.usuario_id == usuario.id


def pode_remover_comentario(usuario, comentario):
    return pode_gerenciar_comentario(usuario, comentario) or permissoes.eh_gestor(usuario.perfil)


def _texto_comentario(valor):
    texto = _texto_obrigatorio(valor, "comentário")
    if len(texto) > TAMANHO_MAXIMO_COMENTARIO:
        raise RegraNegocioError(f"O comentário deve ter no máximo {TAMANHO_MAXIMO_COMENTARIO} caracteres.")
    return texto


def _buscar_comentario(demanda, comentario_id):
    comentario = db.session.get(ComentarioDemanda, comentario_id)
    if comentario is None or comentario.demanda_id != demanda.id or comentario.removido_em:
        raise RegraNegocioError("Comentário não encontrado.")
    return comentario


def comentar(usuario, demanda, texto):
    """Qualquer pessoa que vê a demanda pode comentar, inclusive nas finalizadas."""
    if not pode_ver(usuario, demanda):
        raise PermissaoNegada("Você não tem acesso a esta demanda.")
    comentario = ComentarioDemanda(demanda=demanda, usuario_id=usuario.id, texto=_texto_comentario(texto))
    db.session.add(comentario)
    _registrar(demanda, usuario, TipoEvento.COMENTARIO, "Adicionou um comentário.")
    db.session.commit()
    return comentario


def editar_comentario(usuario, demanda, comentario_id, texto):
    comentario = _buscar_comentario(demanda, comentario_id)
    if not pode_gerenciar_comentario(usuario, comentario):
        raise PermissaoNegada("Somente o autor pode editar o comentário.")
    texto = _texto_comentario(texto)
    if texto == comentario.texto:
        return False
    comentario.texto = texto
    comentario.editado_em = agora()
    db.session.commit()
    return True


def remover_comentario(usuario, demanda, comentario_id):
    comentario = _buscar_comentario(demanda, comentario_id)
    if not pode_remover_comentario(usuario, comentario):
        raise PermissaoNegada("Somente o autor ou um gestor pode remover o comentário.")
    comentario.removido_em = agora()
    _registrar(demanda, usuario, TipoEvento.COMENTARIO, f"Removeu um comentário de {comentario.usuario.nome}.")
    db.session.commit()


def comentarios_nao_lidos(usuario):
    """[(demanda, quantidade)] com comentários de outras pessoas ainda não lidos, nas demandas
    em que o usuário é responsável ou apoio. As mais recentes primeiro."""
    leitura = and_(LeituraComentarios.demanda_id == Demanda.id, LeituraComentarios.usuario_id == usuario.id)
    return (
        db.session.query(Demanda, func.count(ComentarioDemanda.id))
        .join(ComentarioDemanda, ComentarioDemanda.demanda_id == Demanda.id)
        .outerjoin(LeituraComentarios, leitura)
        .filter(or_(Demanda.atribuido_id == usuario.id, Demanda.apoios.any(Usuario.id == usuario.id)))
        .filter(ComentarioDemanda.usuario_id != usuario.id, ComentarioDemanda.removido_em.is_(None))
        .filter(or_(LeituraComentarios.lido_em.is_(None), ComentarioDemanda.criado_em > LeituraComentarios.lido_em))
        .group_by(Demanda.id)
        .order_by(func.max(ComentarioDemanda.criado_em).desc())
        .all()
    )


def proximas_a_vencer(usuario):
    """Demandas em aberto do usuário (responsável ou apoio) cujo prazo vence de hoje até
    DIAS_AVISO_PRAZO dias. As que vencem primeiro vêm antes."""
    hoje = date.today()
    return (
        Demanda.query
        .filter(or_(Demanda.atribuido_id == usuario.id, Demanda.apoios.any(Usuario.id == usuario.id)))
        .filter(Demanda.status.notin_(tuple(Status.FINAIS)))
        .filter(_prazo_final().between(hoje, hoje + timedelta(days=DIAS_AVISO_PRAZO)))
        .order_by(_prazo_final(), Demanda.id)
        .all()
    )


def marcar_comentarios_lidos(usuario, demanda):
    leitura = LeituraComentarios.query.filter_by(usuario_id=usuario.id, demanda_id=demanda.id).first()
    if leitura is None:
        db.session.add(LeituraComentarios(usuario_id=usuario.id, demanda_id=demanda.id))
    else:
        leitura.lido_em = agora()
    db.session.commit()


# ---------------------------------------------------------------------------
# Prazo acordado
# ---------------------------------------------------------------------------

def pode_definir_prazo_acordado(usuario, demanda):
    return _eh_atribuido(usuario, demanda) and not demanda.finalizada


def definir_prazo_acordado(usuario, demanda, prazo_acordado):
    """Só o responsável pela demanda define o prazo acordado (vazio = volta a valer o término)."""
    if not _eh_atribuido(usuario, demanda):
        raise PermissaoNegada("Somente o responsável pela demanda pode definir o prazo acordado.")
    _exigir_nao_finalizada(demanda)
    if demanda.inicio and prazo_acordado and prazo_acordado < demanda.inicio:
        raise RegraNegocioError("O prazo acordado deve ser igual ou posterior à data de início.")
    if demanda.prazo_acordado == prazo_acordado:
        return False
    _registrar(
        demanda, usuario, TipoEvento.EDICAO,
        f"Prazo acordado: {_formatar_data(demanda.prazo_acordado)} → {_formatar_data(prazo_acordado)}.",
    )
    demanda.prazo_acordado = prazo_acordado
    db.session.commit()
    return True


# ---------------------------------------------------------------------------
# Usuários de apoio
# ---------------------------------------------------------------------------

def _definir_apoios(usuario, demanda, apoio_ids):
    ids = {int(i) for i in (apoio_ids or []) if i}
    if demanda.atribuido_id and demanda.atribuido_id in ids:
        raise RegraNegocioError("O usuário atribuído não pode ser também usuário de apoio.")

    apoios = []
    for apoio_id in sorted(ids):
        apoios.append(_buscar_usuario_ativo(apoio_id, "usuário de apoio"))

    antigos = {u.id for u in demanda.apoios}
    if antigos == ids:
        return
    demanda.apoios = apoios
    nomes = ", ".join(u.nome for u in apoios) or "nenhum"
    _registrar(
        demanda, usuario, TipoEvento.APOIO, f"Usuários de apoio: {nomes}.",
        {"antes": sorted(antigos), "depois": sorted(ids)},
    )


# ---------------------------------------------------------------------------
# Atribuição
# ---------------------------------------------------------------------------

def _validar_permissao_atribuicao(usuario, destino):
    if permissoes.pode_atribuir(usuario.perfil, destino.perfil, para_si=destino.id == usuario.id):
        return
    if not permissoes.pode_atribuir_alguem(usuario.perfil):
        raise PermissaoNegada("Você não tem permissão para atribuir demandas.")
    raise PermissaoNegada(f"O {usuario.perfil_rotulo} {permissoes.descrever_atribuicao(usuario.perfil)}.")


def pendencias_para_atribuir(demanda):
    """O que falta para a demanda poder ser atribuída: prazo e priorização GUT."""
    pendencias = []
    if not demanda.prazo_final:
        pendencias.append("preencha o prazo (data de término)")
    if not demanda.tem_gut:
        pendencias.append("defina a prioridade (pesos GUT)")
    return pendencias


def _atribuir(usuario, demanda, destino):
    _validar_permissao_atribuicao(usuario, destino)
    if not transicao_permitida(Acao.ATRIBUIR, demanda.status):
        raise RegraNegocioError(
            f"Não é possível atribuir uma demanda com status '{demanda.status_rotulo}'."
        )
    if demanda.atribuido_id == destino.id and demanda.status in (Status.AGUARDANDO_ACEITE, Status.NAO_INICIADA, Status.EM_ANDAMENTO):
        return  # nada mudou
    pendencias = pendencias_para_atribuir(demanda)
    if pendencias:
        raise RegraNegocioError("Para atribuir a demanda, " + " e ".join(pendencias) + ".")

    anterior = demanda.atribuido
    demanda.atribuido = destino
    demanda.atribuido_id = destino.id
    demanda.atribuido_por = usuario
    demanda.atribuido_por_id = usuario.id
    demanda.justificativa_recusa = None
    demanda.recusado_por_id = None

    # Quem é atribuído não pode continuar como apoio
    if destino in demanda.apoios:
        demanda.apoios.remove(destino)

    if destino.id == usuario.id:
        # Gestor atribuindo a si mesmo: aceite automático
        demanda.status = Status.NAO_INICIADA
        descricao = f"{usuario.nome} assumiu a demanda (aceite automático)."
    else:
        demanda.status = proximo_status(Acao.ATRIBUIR, demanda.status)
        descricao = f"Atribuída a {destino.nome}."
        if anterior and anterior.id != destino.id:
            descricao = f"Reatribuída de {anterior.nome} para {destino.nome}."

    _registrar(
        demanda, usuario, TipoEvento.ATRIBUICAO, descricao,
        {"de": anterior.id if anterior else None, "para": destino.id},
    )


def atribuir(usuario, demanda, destino_id):
    _exigir_nao_finalizada(demanda)
    destino = _buscar_usuario_ativo(destino_id, "usuário atribuído")
    _atribuir(usuario, demanda, destino)
    db.session.commit()


# ---------------------------------------------------------------------------
# Criação e edição
# ---------------------------------------------------------------------------

def criar(usuario, dados):
    """Cria uma demanda.

    dados: eixo_id, acao, produto, divisao, pasta_rede (opcional), inicio, termino, atribuido_id (opcional),
           apoio_ids (lista), gravidade, urgencia, tendencia (opcionais)
    """
    if not permissoes.pode_criar_demanda(usuario.perfil):
        raise PermissaoNegada("Apenas Gerente, Chefe de Divisão ou Gestor do Plano podem criar demandas.")

    eixo = _buscar_eixo(dados.get("eixo_id"))
    acao = _texto_obrigatorio(dados.get("acao"), "Ação")
    produto = _texto_obrigatorio(dados.get("produto"), "Produto / Entrega")
    divisao = divisao_service.validar_para_demanda(dados.get("divisao"))
    pasta_rede = _texto_opcional(dados.get("pasta_rede"))
    inicio, termino = dados.get("inicio"), dados.get("termino")
    _validar_datas(inicio, termino)

    destino = None
    if dados.get("atribuido_id"):
        destino = _buscar_usuario_ativo(dados["atribuido_id"], "usuário atribuído")
        _validar_permissao_atribuicao(usuario, destino)

    apoio_ids = {int(i) for i in (dados.get("apoio_ids") or []) if i}
    if destino and destino.id in apoio_ids:
        raise RegraNegocioError("O usuário atribuído não pode ser também usuário de apoio.")

    demanda = Demanda(
        eixo=eixo, acao=acao, produto=produto, divisao=divisao, pasta_rede=pasta_rede, inicio=inicio, termino=termino,
        status=Status.NOVA, criado_por_id=usuario.id,
    )
    db.session.add(demanda)
    _registrar(demanda, usuario, TipoEvento.CRIACAO, f"Demanda criada no {eixo.rotulo}.")

    _aplicar_gut(usuario, demanda, dados.get("gravidade"), dados.get("urgencia"), dados.get("tendencia"))
    if destino:
        _atribuir(usuario, demanda, destino)
    if apoio_ids:
        _definir_apoios(usuario, demanda, apoio_ids)

    db.session.commit()
    return demanda


def editar(usuario, demanda, dados):
    """Edita campos da demanda. Mesmo formato de 'dados' de criar()."""
    if not permissoes.pode_editar_demanda(usuario.perfil):
        raise PermissaoNegada("Apenas Gerente, Chefe de Divisão ou Gestor do Plano podem editar demandas.")
    _exigir_nao_finalizada(demanda)

    eixo = _buscar_eixo(dados.get("eixo_id"))
    acao = _texto_obrigatorio(dados.get("acao"), "Ação")
    produto = _texto_obrigatorio(dados.get("produto"), "Produto / Entrega")
    divisao = divisao_service.validar_para_demanda(dados.get("divisao"), atual=demanda.divisao)
    pasta_rede = _texto_opcional(dados.get("pasta_rede"))
    inicio, termino = dados.get("inicio"), dados.get("termino")
    _validar_datas(inicio, termino)

    alteracoes = []
    if demanda.eixo_id != eixo.id:
        alteracoes.append(f"eixo: {demanda.eixo.sigla} → {eixo.sigla}")
        demanda.eixo = eixo
    if demanda.acao != acao:
        alteracoes.append("ação")
        demanda.acao = acao
    if demanda.produto != produto:
        alteracoes.append("produto/entrega")
        demanda.produto = produto
    if demanda.divisao != divisao:
        alteracoes.append(f"divisão: {demanda.divisao or '—'} → {divisao}")
        demanda.divisao = divisao
    if demanda.pasta_rede != pasta_rede:
        alteracoes.append("pasta da rede")
        demanda.pasta_rede = pasta_rede
    if demanda.inicio != inicio:
        alteracoes.append(f"início: {_formatar_data(demanda.inicio)} → {_formatar_data(inicio)}")
        demanda.inicio = inicio
    if demanda.termino != termino:
        alteracoes.append(f"término: {_formatar_data(demanda.termino)} → {_formatar_data(termino)}")
        demanda.termino = termino
    if alteracoes:
        _registrar(demanda, usuario, TipoEvento.EDICAO, "Alterado: " + "; ".join(alteracoes) + ".")

    _aplicar_gut(usuario, demanda, dados.get("gravidade"), dados.get("urgencia"), dados.get("tendencia"))

    novo_atribuido_id = dados.get("atribuido_id")
    if novo_atribuido_id and novo_atribuido_id != demanda.atribuido_id:
        _atribuir(usuario, demanda, _buscar_usuario_ativo(novo_atribuido_id, "usuário atribuído"))

    _definir_apoios(usuario, demanda, dados.get("apoio_ids") or [])
    db.session.commit()
    return demanda


# ---------------------------------------------------------------------------
# Fluxo do responsável
# ---------------------------------------------------------------------------

def aceitar(usuario, demanda):
    if not _eh_atribuido(usuario, demanda):
        raise PermissaoNegada("Somente o usuário atribuído pode aceitar a demanda.")
    demanda.status = proximo_status(Acao.ACEITAR, demanda.status)
    _registrar(demanda, usuario, TipoEvento.ACEITE, f"{usuario.nome} aceitou a demanda.")
    db.session.commit()


def iniciar(usuario, demanda):
    if not _eh_atribuido(usuario, demanda):
        raise PermissaoNegada("Somente o usuário atribuído pode iniciar a demanda.")
    demanda.status = proximo_status(Acao.INICIAR, demanda.status)
    _registrar(demanda, usuario, TipoEvento.INICIO, f"{usuario.nome} iniciou a demanda.")
    db.session.commit()


def recusar(usuario, demanda, justificativa):
    if not _eh_atribuido(usuario, demanda):
        raise PermissaoNegada("Somente o usuário atribuído pode recusar a demanda.")
    texto = _justificativa(justificativa, "justificativa da recusa")
    demanda.status = proximo_status(Acao.RECUSAR, demanda.status)
    demanda.justificativa_recusa = texto
    demanda.recusado_por_id = usuario.id
    demanda.atribuido_id = None
    demanda.atribuido = None
    destinatario = demanda.atribuido_por.nome if demanda.atribuido_por else "quem atribuiu"
    _registrar(
        demanda, usuario, TipoEvento.RECUSA,
        f"{usuario.nome} recusou a demanda (devolvida para {destinatario}). Justificativa: {texto}",
        {"justificativa": texto},
    )
    db.session.commit()


def enviar_revisao(usuario, demanda, comentario=None):
    if not _eh_atribuido(usuario, demanda):
        raise PermissaoNegada("Somente o usuário atribuído pode enviar a demanda para revisão.")
    demanda.status = proximo_status(Acao.ENVIAR_REVISAO, demanda.status)
    descricao = f"{usuario.nome} enviou a entrega para revisão."
    comentario = (comentario or "").strip()
    if comentario:
        descricao += f" Comentário: {comentario}"
    _registrar(demanda, usuario, TipoEvento.ENVIO_REVISAO, descricao)
    db.session.commit()


# ---------------------------------------------------------------------------
# Fluxo do gestor
# ---------------------------------------------------------------------------

def aprovar(usuario, demanda, comentario=None):
    if not permissoes.pode_revisar(usuario.perfil, _eh_atribuido(usuario, demanda)):
        raise PermissaoNegada(
            "Apenas Gerente, Chefe de Divisão ou Gestor do Plano (que não seja o responsável) podem aprovar a entrega."
        )
    demanda.status = proximo_status(Acao.APROVAR, demanda.status)
    demanda.concluido_em = agora()
    descricao = f"{usuario.nome} aprovou a entrega. Demanda concluída."
    comentario = (comentario or "").strip()
    if comentario:
        descricao += f" Comentário: {comentario}"
    _registrar(demanda, usuario, TipoEvento.APROVACAO, descricao)
    db.session.commit()


def devolver(usuario, demanda, motivo):
    if not permissoes.pode_revisar(usuario.perfil, _eh_atribuido(usuario, demanda)):
        raise PermissaoNegada(
            "Apenas Gerente, Chefe de Divisão ou Gestor do Plano (que não seja o responsável) podem devolver a entrega."
        )
    texto = _justificativa(motivo, "o motivo da devolução")
    demanda.status = proximo_status(Acao.DEVOLVER, demanda.status)
    _registrar(
        demanda, usuario, TipoEvento.DEVOLUCAO,
        f"{usuario.nome} devolveu a entrega para ajustes. Motivo: {texto}", {"motivo": texto},
    )
    db.session.commit()


def retomar(usuario, demanda, comentario=None):
    """Volta de Em validação para Em andamento. Não é uma devolução da revisão: não entra na taxa de devolução."""
    if not permissoes.pode_voltar_andamento(usuario.perfil):
        raise PermissaoNegada("Você não tem permissão para voltar a demanda para Em andamento.")
    if not pode_ver(usuario, demanda):
        raise PermissaoNegada("Você não tem acesso a esta demanda.")
    demanda.status = proximo_status(Acao.RETOMAR, demanda.status)
    descricao = f"{usuario.nome} voltou a demanda de Em validação para Em andamento."
    comentario = (comentario or "").strip()
    if comentario:
        descricao += f" Comentário: {comentario}"
    _registrar(demanda, usuario, TipoEvento.RETOMADA, descricao)
    db.session.commit()


def cancelar(usuario, demanda, motivo):
    if not permissoes.pode_cancelar(usuario.perfil):
        raise PermissaoNegada("Apenas Gerente, Chefe de Divisão ou Gestor do Plano podem cancelar demandas.")
    texto = _justificativa(motivo, "o motivo do cancelamento")
    demanda.status = proximo_status(Acao.CANCELAR, demanda.status)
    _registrar(
        demanda, usuario, TipoEvento.CANCELAMENTO,
        f"{usuario.nome} cancelou a demanda. Motivo: {texto}", {"motivo": texto},
    )
    db.session.commit()


def mover_por_arraste(usuario, demanda, status_destino):
    """Movimento no quadro kanban. Só são aceitos movimentos sem dados extras."""
    if status_destino == demanda.status:
        return
    acao = acao_por_arraste(demanda.status, status_destino)
    if acao == Acao.ACEITAR:
        aceitar(usuario, demanda)
    elif acao == Acao.INICIAR:
        iniciar(usuario, demanda)
    elif acao == Acao.ENVIAR_REVISAO:
        enviar_revisao(usuario, demanda)
    elif acao == Acao.APROVAR:
        aprovar(usuario, demanda)
    elif acao == Acao.DEVOLVER:
        raise RegraNegocioError("Para devolver a entrega, informe o motivo na tela da demanda.")


def acoes_disponiveis(usuario, demanda):
    """Conjunto de ações que o usuário pode executar agora (para exibir os botões)."""
    acoes = set()
    eh_atribuido = _eh_atribuido(usuario, demanda)
    perfil = usuario.perfil
    status = demanda.status

    if eh_atribuido and status == Status.AGUARDANDO_ACEITE:
        acoes.update({Acao.ACEITAR, Acao.RECUSAR})
    if eh_atribuido and status == Status.NAO_INICIADA:
        acoes.add(Acao.INICIAR)
    if eh_atribuido and status == Status.EM_ANDAMENTO:
        acoes.add(Acao.ENVIAR_REVISAO)
    if status == Status.EM_REVISAO and permissoes.pode_revisar(perfil, eh_atribuido):
        acoes.update({Acao.APROVAR, Acao.DEVOLVER})
    if status == Status.EM_REVISAO and permissoes.pode_voltar_andamento(perfil):
        acoes.add(Acao.RETOMAR)
    if permissoes.pode_atribuir_alguem(perfil) and transicao_permitida(Acao.ATRIBUIR, status):
        acoes.add(Acao.ATRIBUIR)
    if permissoes.pode_cancelar(perfil) and transicao_permitida(Acao.CANCELAR, status):
        acoes.add(Acao.CANCELAR)
    return acoes


# ---------------------------------------------------------------------------
# Visibilidade e consultas
# ---------------------------------------------------------------------------

def pode_ver(usuario, demanda):
    if permissoes.pode_ver_todas(usuario.perfil):
        return True
    if demanda.atribuido_id == usuario.id or demanda.recusado_por_id == usuario.id:
        return True
    return any(apoio.id == usuario.id for apoio in demanda.apoios)


def obter(usuario, demanda_id):
    demanda = db.session.get(Demanda, demanda_id)
    if demanda is None:
        return None
    if not pode_ver(usuario, demanda):
        raise PermissaoNegada("Você não tem acesso a esta demanda.")
    return demanda


def _base_visivel(usuario):
    consulta = Demanda.query
    if not permissoes.pode_ver_todas(usuario.perfil):
        sou_apoio = db.session.query(demanda_apoio.c.demanda_id).filter(
            demanda_apoio.c.usuario_id == usuario.id
        )
        consulta = consulta.filter(
            or_(
                Demanda.atribuido_id == usuario.id,
                Demanda.recusado_por_id == usuario.id,
                Demanda.id.in_(sou_apoio),
            )
        )
    return consulta


def consultar(usuario, filtros=None):
    """Consulta demandas visíveis ao usuário, aplicando filtros e ordenando por prioridade.

    filtros: eixo_id, status, atribuido_id, divisao, divisao_responsavel, faixa ('alta'|'media'|'baixa'|'pendente'),
             atrasadas (bool), busca (texto), incluir_canceladas (bool)
    """
    filtros = filtros or {}
    consulta = _base_visivel(usuario)

    if filtros.get("eixo_id"):
        consulta = consulta.filter(Demanda.eixo_id == filtros["eixo_id"])
    if filtros.get("status"):
        consulta = consulta.filter(Demanda.status == filtros["status"])
    elif not filtros.get("incluir_canceladas"):
        consulta = consulta.filter(Demanda.status != Status.CANCELADA)
    if filtros.get("atribuido_id"):
        consulta = consulta.filter(Demanda.atribuido_id == filtros["atribuido_id"])
    if filtros.get("divisao"):
        consulta = consulta.filter(Demanda.divisao == filtros["divisao"])
    if filtros.get("divisao_responsavel"):
        # Divisão do cadastro do responsável (não a informada na demanda)
        consulta = consulta.filter(Demanda.atribuido.has(Usuario.divisao == filtros["divisao_responsavel"]))

    faixa = filtros.get("faixa")
    if faixa == "pendente":
        consulta = consulta.filter(Demanda.prioridade.is_(None))
    elif faixa:
        intervalo = gut.intervalo_da_faixa(faixa)
        if intervalo:
            consulta = consulta.filter(Demanda.prioridade.between(*intervalo))

    if filtros.get("atrasadas"):
        consulta = consulta.filter(
            _prazo_final() < date.today(), Demanda.status.notin_(list(Status.FINAIS))
        )

    busca = (filtros.get("busca") or "").strip()
    if busca:
        termo = f"%{busca}%"
        condicoes = [Demanda.acao.ilike(termo), Demanda.produto.ilike(termo)]
        if busca.lstrip("#").isdigit():
            condicoes.append(Demanda.id == int(busca.lstrip("#")))
        consulta = consulta.filter(or_(*condicoes))

    return consulta.order_by(
        Demanda.prioridade.desc().nullslast(),
        _prazo_final().asc().nullslast(),
        Demanda.id.asc(),
    )


DIAS_CONCLUIDAS_NO_QUADRO = 30


def quadro(usuario, filtros=None):
    """Demandas agrupadas por coluna do kanban. Concluídas: apenas as dos últimos 30 dias."""
    filtros = dict(filtros or {})
    filtros.pop("status", None)
    colunas = {status: [] for status in Status.COLUNAS_QUADRO}
    # Usuário Comum não atribui demandas: a coluna "A atribuir" fica oculta para ele
    if usuario.perfil == Perfil.USUARIO:
        del colunas[Status.NOVA]
    limite = agora() - timedelta(days=DIAS_CONCLUIDAS_NO_QUADRO)
    for demanda in consultar(usuario, filtros).all():
        if demanda.status not in colunas:
            continue
        if demanda.status == Status.CONCLUIDA and demanda.concluido_em and demanda.concluido_em < limite:
            continue
        colunas[demanda.status].append(demanda)
    return colunas


def _da_divisao(usuario, demanda):
    """A demanda é da divisão do usuário? Aceita divisões compostas, como "DPO/DIO"."""
    return bool(usuario.divisao) and usuario.divisao in (demanda.divisao or "").split("/")


def minhas(usuario):
    """Painel pessoal: o que precisa da atenção do usuário.
    Gestor do Plano: além das próprias, só vê demandas da sua divisão (vale apenas nesta tela)."""
    nao_finais = Demanda.status.notin_(list(Status.FINAIS))
    ordem = (Demanda.prioridade.desc().nullslast(), _prazo_final().asc().nullslast())

    resultado = {
        "pendentes_aceite": Demanda.query.filter(
            Demanda.atribuido_id == usuario.id, Demanda.status == Status.AGUARDANDO_ACEITE
        ).order_by(*ordem).all(),
        "atribuidas": Demanda.query.filter(
            Demanda.atribuido_id == usuario.id, nao_finais, Demanda.status != Status.AGUARDANDO_ACEITE
        ).order_by(*ordem).all(),
        "apoio": Demanda.query.filter(
            Demanda.apoios.any(Usuario.id == usuario.id), nao_finais
        ).order_by(*ordem).all(),
    }
    if permissoes.pode_atribuir_alguem(usuario.perfil):
        resultado["recusadas"] = Demanda.query.filter(
            Demanda.status == Status.RECUSADA, Demanda.atribuido_por_id == usuario.id
        ).order_by(*ordem).all()
    if permissoes.permitido(usuario.perfil, "revisar"):
        revisao = Demanda.query.filter(Demanda.status == Status.EM_REVISAO).order_by(*ordem).all()
        resultado["revisao"] = [
            d for d in revisao if permissoes.pode_revisar(usuario.perfil, _eh_atribuido(usuario, d))
        ]
        if usuario.perfil == Perfil.GESTOR_PLANO:
            resultado["revisao"] = [
                d for d in resultado["revisao"] if _eh_atribuido(usuario, d) or _da_divisao(usuario, d)
            ]
    return resultado
