"""Indicadores do painel. Respeita a visibilidade do usuário (gestores veem tudo)."""
from collections import Counter, defaultdict
from datetime import timedelta, timezone
from statistics import median

from ..models import TipoEvento
from ..models.base import agora
from . import demanda_service
from .fluxo import Status

try:
    from zoneinfo import ZoneInfo

    FUSO_LOCAL = ZoneInfo("America/Sao_Paulo")
except Exception:
    FUSO_LOCAL = timezone(timedelta(hours=-3))

# Período das métricas de desempenho: chave da URL -> (rótulo, dias; None = tudo)
PERIODOS = {
    "30": ("Últimos 30 dias", 30),
    "90": ("Últimos 90 dias", 90),
    "365": ("Últimos 12 meses", 365),
    "tudo": ("Todo o período", None),
}
PERIODO_PADRAO = "90"

# Etapas em que a demanda espera ou é trabalhada, na ordem do fluxo
ETAPAS_MEDIDAS = (Status.AGUARDANDO_ACEITE, Status.NAO_INICIADA, Status.EM_ANDAMENTO, Status.EM_REVISAO)

# Evento do histórico -> etapa em que a demanda entra (a atribuição é tratada à parte)
_ETAPA_DO_EVENTO = {
    TipoEvento.CRIACAO: Status.NOVA,
    TipoEvento.ACEITE: Status.NAO_INICIADA,
    TipoEvento.INICIO: Status.EM_ANDAMENTO,
    TipoEvento.RECUSA: Status.RECUSADA,
    TipoEvento.ENVIO_REVISAO: Status.EM_REVISAO,
    TipoEvento.DEVOLUCAO: Status.EM_ANDAMENTO,
    TipoEvento.APROVACAO: Status.CONCLUIDA,
    TipoEvento.CANCELAMENTO: Status.CANCELADA,
}


def _data_local(momento):
    """Datas/horas são gravadas em UTC; o prazo é uma data no horário de Brasília."""
    return momento.replace(tzinfo=timezone.utc).astimezone(FUSO_LOCAL).date()


def _linha_do_tempo(demanda):
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

    # Fluxo antigo (antes de "Não iniciada"): o aceite já levava direto a "Em andamento"
    for i, (etapa, momento) in enumerate(marcos[:-1]):
        if etapa == Status.NAO_INICIADA and marcos[i + 1][0] == Status.EM_REVISAO:
            marcos[i] = (Status.EM_ANDAMENTO, momento)
    return marcos


def _tempo_por_etapa(demanda):
    """{etapa: timedelta} somando todas as passagens da demanda por cada etapa."""
    tempos = defaultdict(timedelta)
    marcos = _linha_do_tempo(demanda)
    for (etapa, entrada), (_proxima, saida) in zip(marcos, marcos[1:]):
        tempos[etapa] += saida - entrada
    return tempos


def _dias(duracao):
    return duracao.total_seconds() / 86400


def formatar_dias(dias):
    if dias is None:
        return "—"
    if dias < 1:
        return f"{round(dias * 24)} h"
    return f"{dias:.1f}".replace(".", ",") + (" dia" if round(dias, 1) == 1 else " dias")


def _concluidas_entre(demandas, inicio, fim):
    return [
        d for d in demandas
        if d.status == Status.CONCLUIDA and d.concluido_em
        and (inicio is None or d.concluido_em >= inicio) and d.concluido_em < fim
    ]


def _entregas_no_prazo(concluidas):
    com_prazo = [d for d in concluidas if d.prazo_final]
    no_prazo = sum(1 for d in com_prazo if _data_local(d.concluido_em) <= d.prazo_final)
    return {
        "percentual": round(100 * no_prazo / len(com_prazo)) if com_prazo else None,
        "no_prazo": no_prazo,
        "com_prazo": len(com_prazo),
        "sem_prazo": len(concluidas) - len(com_prazo),
    }


def _devolucoes(demandas, inicio, fim):
    """Das validações feitas no período (aprovar ou devolver), quantas foram devoluções.
    Conta decisões, não demandas: uma entrega devolvida duas vezes pesa duas vezes."""
    por_responsavel = defaultdict(lambda: {"validacoes": 0, "devolucoes": 0})
    for d in demandas:
        nome = d.atribuido.nome if d.atribuido else "Sem responsável"
        for evento in d.historico:
            if evento.tipo not in (TipoEvento.APROVACAO, TipoEvento.DEVOLUCAO):
                continue
            if (inicio is not None and evento.criado_em < inicio) or evento.criado_em >= fim:
                continue
            por_responsavel[nome]["validacoes"] += 1
            if evento.tipo == TipoEvento.DEVOLUCAO:
                por_responsavel[nome]["devolucoes"] += 1

    def taxa(c):
        return round(100 * c["devolucoes"] / c["validacoes"]) if c["validacoes"] else None

    validacoes = sum(c["validacoes"] for c in por_responsavel.values())
    devolucoes = sum(c["devolucoes"] for c in por_responsavel.values())
    linhas = [{"nome": nome, **c, "taxa": taxa(c)} for nome, c in por_responsavel.items()]
    return {
        "validacoes": validacoes,
        "devolucoes": devolucoes,
        "taxa": taxa({"validacoes": validacoes, "devolucoes": devolucoes}),
        "por_responsavel": sorted(linhas, key=lambda l: (-l["taxa"], -l["validacoes"], l["nome"])),
    }


def _carga(ativas):
    """Carga de cada responsável pela soma das prioridades GUT (P) das demandas ativas.
    Demandas sem responsável não são carga de ninguém e ficam de fora."""
    por_responsavel = defaultdict(lambda: {"ativas": 0, "pontos": 0, "sem_gut": 0, "atrasadas": 0})
    for d in ativas:
        if not d.atribuido:
            continue
        linha = por_responsavel[d.atribuido.nome]
        linha["ativas"] += 1
        linha["pontos"] += d.prioridade or 0
        linha["sem_gut"] += 0 if d.tem_gut else 1
        linha["atrasadas"] += 1 if d.atrasada else 0
    return sorted(
        ({"nome": nome, **c} for nome, c in por_responsavel.items()),
        key=lambda l: (-l["pontos"], -l["ativas"], l["nome"]),
    )


def _desempenho(demandas, periodo):
    rotulo, dias = PERIODOS[periodo]
    fim = agora()
    inicio = fim - timedelta(days=dias) if dias else None
    concluidas = _concluidas_entre(demandas, inicio, fim)

    devolucoes = _devolucoes(demandas, inicio, fim)
    devolucoes["variacao"] = None
    if dias:
        anterior = _devolucoes(demandas, inicio - timedelta(days=dias), inicio)
        if devolucoes["taxa"] is not None and anterior["taxa"] is not None:
            devolucoes["variacao"] = devolucoes["taxa"] - anterior["taxa"]

    prazo = _entregas_no_prazo(concluidas)
    prazo["variacao"] = None
    if dias:
        anterior = _entregas_no_prazo(_concluidas_entre(demandas, inicio - timedelta(days=dias), inicio))
        if prazo["percentual"] is not None and anterior["percentual"] is not None:
            prazo["variacao"] = prazo["percentual"] - anterior["percentual"]

    por_etapa = defaultdict(list)
    ciclos = []
    for d in concluidas:
        tempos = _tempo_por_etapa(d)
        for etapa in ETAPAS_MEDIDAS:
            if etapa in tempos:
                por_etapa[etapa].append(_dias(tempos[etapa]))
        marcos = _linha_do_tempo(d)
        if marcos:
            ciclos.append(_dias(marcos[-1][1] - marcos[0][1]))

    total_etapas = sum(sum(v) for v in por_etapa.values())
    etapas = []
    for etapa in ETAPAS_MEDIDAS:
        valores = por_etapa.get(etapa, [])
        mediana = median(valores) if valores else None
        etapas.append({
            "rotulo": Status.rotulo(etapa),
            "mediana": mediana,
            "mediana_texto": formatar_dias(mediana),
            "demandas": len(valores),
            "parcela": round(100 * sum(valores) / total_etapas) if total_etapas else None,
        })
    medidas = [e for e in etapas if e["mediana"] is not None]
    gargalo = max(medidas, key=lambda e: e["parcela"])["rotulo"] if medidas else None

    ciclo = median(ciclos) if ciclos else None
    return {
        "periodo": periodo,
        "periodo_rotulo": rotulo,
        "concluidas": len(concluidas),
        "prazo": prazo,
        "devolucoes": devolucoes,
        "ciclo_texto": formatar_dias(ciclo),
        "etapas": etapas,
        "gargalo": gargalo,
    }


def calcular(usuario, filtros=None, periodo=PERIODO_PADRAO):
    """filtros: atribuido_id e divisao_responsavel (mesmo formato de demanda_service.consultar)."""
    if periodo not in PERIODOS:
        periodo = PERIODO_PADRAO
    demandas = demanda_service.consultar(usuario, {**(filtros or {}), "incluir_canceladas": True}).all()
    ativas = [d for d in demandas if not d.finalizada]
    desempenho = _desempenho(demandas, periodo)
    carga = _carga(ativas)

    por_status = Counter(d.status for d in demandas)
    por_eixo = Counter(d.eixo.sigla for d in ativas)
    eixos = sorted({(d.eixo.numero, d.eixo.sigla, d.eixo.nome) for d in demandas})

    return {
        "desempenho": desempenho,
        "carga": carga,
        "ativas_sem_responsavel": sum(1 for d in ativas if not d.atribuido),
        "totais": {
            "ativas": len(ativas),
            "atrasadas": sum(1 for d in ativas if d.atrasada),
            "aguardando_aceite": por_status.get(Status.AGUARDANDO_ACEITE, 0),
            "em_revisao": por_status.get(Status.EM_REVISAO, 0),
            "sem_gut": sum(1 for d in ativas if not d.tem_gut),
            "concluidas": por_status.get(Status.CONCLUIDA, 0),
        },
        "graficos": {
            "etapas": {
                "rotulos": [e["rotulo"] for e in desempenho["etapas"]],
                "valores": [round(e["mediana"], 2) if e["mediana"] is not None else 0 for e in desempenho["etapas"]],
                "textos": [e["mediana_texto"] for e in desempenho["etapas"]],
            },
            "status": {
                "rotulos": [Status.rotulo(s) for s in Status.TODOS],
                "valores": [por_status.get(s, 0) for s in Status.TODOS],
            },
            "eixo": {
                "rotulos": [sigla for _n, sigla, _nome in eixos],
                "nomes": [nome for _n, _s, nome in eixos],
                "valores": [por_eixo.get(sigla, 0) for _n, sigla, _nome in eixos],
            },
            "carga": {
                "rotulos": [l["nome"] for l in carga],
                "valores": [l["pontos"] for l in carga],
                "ativas": [l["ativas"] for l in carga],
            },
        },
        "ranking": sorted(
            [d for d in ativas if d.tem_gut], key=lambda d: (-d.prioridade, d.prazo_final or d.criado_em.date())
        )[:10],
        "atrasadas": sorted([d for d in ativas if d.atrasada], key=lambda d: d.prazo_final)[:10],
    }
