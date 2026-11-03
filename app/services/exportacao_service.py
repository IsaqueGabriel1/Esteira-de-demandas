"""Exportação de listas de demandas para CSV (compatível com Excel em português)."""
import csv
import io
from datetime import timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    FUSO_LOCAL = ZoneInfo("America/Sao_Paulo")
except Exception:
    FUSO_LOCAL = timezone(timedelta(hours=-3))

CABECALHO = [
    "ID", "Eixo", "Ação", "Produto / Entrega", "Status", "Atrasada", "Início", "Término",
    "Responsável", "Apoio", "G", "U", "T", "Prioridade (P)", "Faixa", "Criada em",
]


def _data(d):
    return d.strftime("%d/%m/%Y") if d else ""


def demandas_para_csv(demandas):
    """Retorna bytes de um CSV separado por ';' com BOM UTF-8 (o Excel abre acentuado)."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    escritor.writerow(CABECALHO)
    for d in demandas:
        escritor.writerow([
            d.id,
            d.eixo.rotulo,
            d.acao,
            d.produto,
            d.status_rotulo,
            "Sim" if d.atrasada else "Não",
            _data(d.inicio),
            _data(d.termino),
            d.atribuido.nome if d.atribuido else "",
            ", ".join(u.nome for u in d.apoios),
            d.gravidade or "",
            d.urgencia or "",
            d.tendencia or "",
            d.prioridade or "",
            d.faixa[0],
            d.criado_em.replace(tzinfo=timezone.utc).astimezone(FUSO_LOCAL).strftime("%d/%m/%Y %H:%M"),
        ])
    return ("﻿" + buffer.getvalue()).encode("utf-8")
