"""Indicadores do painel. Respeita a visibilidade do usuário (gestores veem tudo)."""
from collections import Counter

from . import demanda_service, gut
from .fluxo import Status


def calcular(usuario):
    demandas = demanda_service.consultar(usuario, {"incluir_canceladas": True}).all()
    ativas = [d for d in demandas if not d.finalizada]

    por_status = Counter(d.status for d in demandas)
    por_eixo = Counter(d.eixo.sigla for d in ativas)
    por_responsavel = Counter(d.atribuido.nome if d.atribuido else "Sem responsável" for d in ativas)
    por_faixa = Counter(d.faixa[0] for d in ativas)

    rotulos_faixa = [f[2] for f in reversed(gut.FAIXAS)] + [gut.FAIXA_PENDENTE[0]]
    eixos = sorted({(d.eixo.numero, d.eixo.sigla, d.eixo.nome) for d in demandas})

    return {
        "totais": {
            "ativas": len(ativas),
            "atrasadas": sum(1 for d in ativas if d.atrasada),
            "aguardando_aceite": por_status.get(Status.AGUARDANDO_ACEITE, 0),
            "em_revisao": por_status.get(Status.EM_REVISAO, 0),
            "sem_gut": sum(1 for d in ativas if not d.tem_gut),
            "concluidas": por_status.get(Status.CONCLUIDA, 0),
        },
        "graficos": {
            "status": {
                "rotulos": [Status.rotulo(s) for s in Status.TODOS],
                "valores": [por_status.get(s, 0) for s in Status.TODOS],
            },
            "eixo": {
                "rotulos": [sigla for _n, sigla, _nome in eixos],
                "nomes": [nome for _n, _s, nome in eixos],
                "valores": [por_eixo.get(sigla, 0) for _n, sigla, _nome in eixos],
            },
            "responsavel": {
                "rotulos": [nome for nome, _ in por_responsavel.most_common()],
                "valores": [qtd for _, qtd in por_responsavel.most_common()],
            },
            "faixa": {
                "rotulos": rotulos_faixa,
                "valores": [por_faixa.get(r, 0) for r in rotulos_faixa],
            },
        },
        "ranking": sorted(
            [d for d in ativas if d.tem_gut], key=lambda d: (-d.prioridade, d.termino or d.criado_em.date())
        )[:10],
        "atrasadas": sorted([d for d in ativas if d.atrasada], key=lambda d: d.termino)[:10],
    }
