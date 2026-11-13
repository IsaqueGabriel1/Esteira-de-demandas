"""Contagem de tempo das demandas, reconstruída a partir do histórico.

Cada evento do histórico marca a entrada da demanda numa etapa; o tempo de uma etapa é
o intervalo até a entrada na seguinte. Para demandas em aberto, a etapa atual conta até agora.
"""
from collections import defaultdict
from datetime import timedelta

from ..models import TipoEvento
from ..models.base import agora
from .fluxo import Status

# Etapas em que a demanda espera ou é trabalhada, na ordem do fluxo
ETAPAS_MEDIDAS = (Status.AGUARDANDO_ACEITE, Status.NAO_INICIADA, Status.EM_ANDAMENTO, Status.EM_REVISAO)

# A partir de quantos dias na mesma etapa o card do quadro sinaliza que a demanda está parada
DIAS_ALERTA_ETAPA = 7

# Evento do histórico -> etapa em que a demanda entra (a atribuição é tratada à parte)
_ETAPA_DO_EVENTO = {
    TipoEvento.CRIACAO: Status.NOVA,
    TipoEvento.ACEITE: Status.NAO_INICIADA,
    TipoEvento.INICIO: Status.EM_ANDAMENTO,
    TipoEvento.RECUSA: Status.RECUSADA,
    TipoEvento.ENVIO_REVISAO: Status.EM_REVISAO,
    TipoEvento.DEVOLUCAO: Status.EM_ANDAMENTO,
    TipoEvento.RETOMADA: Status.EM_ANDAMENTO,
    TipoEvento.APROVACAO: Status.CONCLUIDA,
    TipoEvento.CANCELAMENTO: Status.CANCELADA,
}


def linha_do_tempo(demanda):
    """[(etapa, momento em que entrou nela)], reconstruída a partir do histórico."""
    marcos = []
    for evento in sorted(demanda.historico, key=lambda h: (h.criado_em, h.id)):
        if evento.tipo == TipoEvento.ATRIBUICAO:
            auto = (evento.dados or {}).get("para") == evento.usuario_id
            etapa = Status.NAO_INICIADA if auto else Status.AGUARDANDO_ACEITE
        elif evento.tipo in _ETAPA_DO_EVENTO:
            etapa = _ETAPA_DO_EVENTO[evento.tipo]
        else:
            continue
        marcos.append((etapa, evento.criado_em))

    # Fluxo antigo (antes de "Não iniciada"): o aceite já levava direto a "Em andamento".
    # Vale para aceites seguidos de envio para validação e para a demanda ainda em andamento.
    for i, (etapa, momento) in enumerate(marcos):
        if etapa != Status.NAO_INICIADA:
            continue
        ultimo = i == len(marcos) - 1
        if (not ultimo and marcos[i + 1][0] == Status.EM_REVISAO) or (ultimo and demanda.status == Status.EM_ANDAMENTO):
            marcos[i] = (Status.EM_ANDAMENTO, momento)
    return marcos


def tempo_por_etapa(demanda, ate=None):
    """{etapa: timedelta} somando todas as passagens da demanda por cada etapa.
    Com 'ate', a etapa atual de uma demanda em aberto conta até esse momento."""
    tempos = defaultdict(timedelta)
    marcos = linha_do_tempo(demanda)
    for (etapa, entrada), (_proxima, saida) in zip(marcos, marcos[1:]):
        tempos[etapa] += saida - entrada
    if ate is not None and marcos and not demanda.finalizada:
        etapa, entrada = marcos[-1]
        tempos[etapa] += ate - entrada
    return tempos


def tempo_na_etapa_atual(demanda):
    """Há quanto tempo a demanda em aberto está no status atual (None se finalizada)."""
    marcos = linha_do_tempo(demanda)
    if demanda.finalizada or not marcos:
        return None
    return agora() - marcos[-1][1]


def inicio_da_execucao(demanda):
    """Momento em que a demanda entrou pela primeira vez em Em andamento."""
    for etapa, momento in linha_do_tempo(demanda):
        if etapa == Status.EM_ANDAMENTO:
            return momento
    return None


def tempo_de_execucao(demanda):
    """Tempo desde a primeira entrada em Em andamento até a conclusão (ou até agora, se em aberto).
    Inclui validação e eventuais devoluções. None se a demanda nunca foi iniciada."""
    inicio = inicio_da_execucao(demanda)
    if inicio is None:
        return None
    if demanda.finalizada:
        fim = linha_do_tempo(demanda)[-1][1]
    else:
        fim = agora()
    return fim - inicio


def dias(duracao):
    return duracao.total_seconds() / 86400


def formatar_dias(valor):
    """Dias (float) em texto, só dias completos: "menos de 1 dia", "1 dia", "3 dias"."""
    if valor is None:
        return "—"
    inteiros = int(valor)
    if inteiros < 1:
        return "menos de 1 dia"
    return f"{inteiros} dia" if inteiros == 1 else f"{inteiros} dias"


def formatar(duracao):
    """timedelta em texto curto, ou "—"."""
    return formatar_dias(dias(duracao)) if duracao is not None else "—"


def resumo(demanda):
    """Para a tela da demanda: tempo em cada etapa (com a atual até agora) e tempo de execução."""
    tempos = tempo_por_etapa(demanda, ate=agora())
    marcos = linha_do_tempo(demanda)
    atual = None if demanda.finalizada or not marcos else marcos[-1][0]
    return {
        "etapas": [
            {"rotulo": Status.rotulo(etapa), "texto": formatar(tempos.get(etapa)), "atual": etapa == atual}
            for etapa in ETAPAS_MEDIDAS
            if etapa in tempos
        ],
        "execucao": formatar(tempo_de_execucao(demanda)) if inicio_da_execucao(demanda) else None,
        "inicio_execucao": inicio_da_execucao(demanda),
    }
