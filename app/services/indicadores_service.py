"""Indicadores do painel. Respeita a visibilidade do usuário (gestores veem tudo)."""
from collections import Counter, defaultdict
from datetime import timedelta, timezone
from statistics import median

from ..models import TipoEvento
from ..models.base import agora
from . import demanda_service, tempos
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

ETAPAS_MEDIDAS = tempos.ETAPAS_MEDIDAS
formatar_dias = tempos.formatar_dias


def _data_local(momento):
    """Datas/horas são gravadas em UTC; o prazo é uma data no horário de Brasília."""
    return momento.replace(tzinfo=timezone.utc).astimezone(FUSO_LOCAL).date()


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
    """Prazo, devolução e ciclo: demandas concluídas no período.
    Tempo em cada etapa: concluídas no período e demandas em aberto (a etapa atual conta até agora)."""
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

    em_aberto = [d for d in demandas if not d.finalizada]
    por_etapa = defaultdict(list)
    for d in concluidas + em_aberto:
        duracoes = tempos.tempo_por_etapa(d, ate=fim)
        for etapa in ETAPAS_MEDIDAS:
            if etapa in duracoes:
                por_etapa[etapa].append(tempos.dias(duracoes[etapa]))

    ciclos, execucoes = [], []
    for d in concluidas:
        marcos = tempos.linha_do_tempo(d)
        if marcos:
            ciclos.append(tempos.dias(marcos[-1][1] - marcos[0][1]))
        execucao = tempos.tempo_de_execucao(d)
        if execucao is not None:
            execucoes.append(tempos.dias(execucao))
    em_execucao = [tempos.tempo_de_execucao(d) for d in em_aberto]
    em_execucao = [tempos.dias(t) for t in em_execucao if t is not None]

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
        "execucao_texto": formatar_dias(median(execucoes) if execucoes else None),
        "em_execucao": len(em_execucao),
        "em_execucao_texto": formatar_dias(median(em_execucao) if em_execucao else None),
        "medidas_etapas": len(concluidas) + len(em_aberto),
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
