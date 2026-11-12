"""Máquina de estados da demanda.

Fluxo principal:
    A atribuir → Aguardando aceite → Não iniciada → Em andamento → Em validação → Concluída

Desvios:
    Aguardando aceite → Recusada (com justificativa; volta para quem atribuiu)
    Em validação → Em andamento (devolvida para ajustes)
    qualquer status não final → Cancelada
"""
from .erros import TransicaoInvalida


class Status:
    NOVA = "NOVA"
    AGUARDANDO_ACEITE = "AGUARDANDO_ACEITE"
    NAO_INICIADA = "NAO_INICIADA"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    EM_REVISAO = "EM_REVISAO"
    CONCLUIDA = "CONCLUIDA"
    RECUSADA = "RECUSADA"
    CANCELADA = "CANCELADA"

    ROTULOS = {
        NOVA: "A atribuir",
        AGUARDANDO_ACEITE: "Aguardando aceite",
        NAO_INICIADA: "Não iniciada",
        EM_ANDAMENTO: "Em andamento",
        EM_REVISAO: "Em validação",
        CONCLUIDA: "Concluída",
        RECUSADA: "Recusada",
        CANCELADA: "Cancelada",
    }

    # Ordem das colunas no quadro kanban (Cancelada não aparece no quadro)
    COLUNAS_QUADRO = (NOVA, RECUSADA, AGUARDANDO_ACEITE, NAO_INICIADA, EM_ANDAMENTO, EM_REVISAO, CONCLUIDA)

    FINAIS = frozenset({CONCLUIDA, CANCELADA})
    TODOS = (NOVA, AGUARDANDO_ACEITE, NAO_INICIADA, EM_ANDAMENTO, EM_REVISAO, CONCLUIDA, RECUSADA, CANCELADA)

    @classmethod
    def rotulo(cls, status):
        return cls.ROTULOS.get(status, status)


class Acao:
    ATRIBUIR = "atribuir"
    ACEITAR = "aceitar"
    INICIAR = "iniciar"
    RECUSAR = "recusar"
    ENVIAR_REVISAO = "enviar_revisao"
    APROVAR = "aprovar"
    DEVOLVER = "devolver"
    CANCELAR = "cancelar"

    TODAS = (ATRIBUIR, ACEITAR, INICIAR, RECUSAR, ENVIAR_REVISAO, APROVAR, DEVOLVER, CANCELAR)


_NAO_FINAIS = frozenset(Status.TODOS) - Status.FINAIS

# ação -> (status de origem permitidos, status de destino)
TRANSICOES = {
    Acao.ATRIBUIR: (
        frozenset({Status.NOVA, Status.RECUSADA, Status.AGUARDANDO_ACEITE, Status.NAO_INICIADA, Status.EM_ANDAMENTO}),
        Status.AGUARDANDO_ACEITE,
    ),
    Acao.ACEITAR: (frozenset({Status.AGUARDANDO_ACEITE}), Status.NAO_INICIADA),
    Acao.INICIAR: (frozenset({Status.NAO_INICIADA}), Status.EM_ANDAMENTO),
    Acao.RECUSAR: (frozenset({Status.AGUARDANDO_ACEITE}), Status.RECUSADA),
    Acao.ENVIAR_REVISAO: (frozenset({Status.EM_ANDAMENTO}), Status.EM_REVISAO),
    Acao.APROVAR: (frozenset({Status.EM_REVISAO}), Status.CONCLUIDA),
    Acao.DEVOLVER: (frozenset({Status.EM_REVISAO}), Status.EM_ANDAMENTO),
    Acao.CANCELAR: (_NAO_FINAIS, Status.CANCELADA),
}

# Movimentos permitidos por arrastar e soltar no quadro (origem, destino) -> ação.
# Atribuir, recusar e cancelar exigem informações extras e são feitos na tela da demanda.
ACOES_POR_ARRASTE = {
    (Status.AGUARDANDO_ACEITE, Status.NAO_INICIADA): Acao.ACEITAR,
    (Status.NAO_INICIADA, Status.EM_ANDAMENTO): Acao.INICIAR,
    (Status.EM_ANDAMENTO, Status.EM_REVISAO): Acao.ENVIAR_REVISAO,
    (Status.EM_REVISAO, Status.CONCLUIDA): Acao.APROVAR,
    (Status.EM_REVISAO, Status.EM_ANDAMENTO): Acao.DEVOLVER,
}


def transicao_permitida(acao, status_atual):
    origens, _destino = TRANSICOES[acao]
    return status_atual in origens


def proximo_status(acao, status_atual):
    """Retorna o status resultante da ação, ou lança TransicaoInvalida."""
    if acao not in TRANSICOES:
        raise TransicaoInvalida(f"Ação desconhecida: {acao}")
    origens, destino = TRANSICOES[acao]
    if status_atual not in origens:
        raise TransicaoInvalida(
            f"Não é possível '{acao.replace('_', ' ')}' uma demanda com status "
            f"'{Status.rotulo(status_atual)}'."
        )
    return destino


def acao_por_arraste(origem, destino):
    """Retorna a ação correspondente a arrastar o card de 'origem' para 'destino'."""
    acao = ACOES_POR_ARRASTE.get((origem, destino))
    if acao is None:
        raise TransicaoInvalida(
            f"Não é possível mover de '{Status.rotulo(origem)}' para '{Status.rotulo(destino)}' "
            "arrastando. Use as ações na tela da demanda."
        )
    return acao
