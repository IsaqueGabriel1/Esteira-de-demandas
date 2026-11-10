"""Carga inicial das demandas do Plano de Trabalho (app/seed_data/plano_de_trabalho.csv).

Roda pelo "flask seed" somente quando a base ainda não tem nenhuma demanda, ou seja,
na primeira inicialização. Depois disso as demandas são mantidas pelo sistema, e editar
ou cancelar uma delas não faz a carga recriá-la.
"""
import csv
from pathlib import Path

from ..models import Demanda, Eixo
from . import demanda_service, divisao_service
from .erros import RegraNegocioError

ARQUIVO_PLANO = Path(__file__).resolve().parent.parent / "seed_data" / "plano_de_trabalho.csv"


def ler_plano(caminho=ARQUIVO_PLANO):
    """Lê o CSV (separador ';', UTF-8) e devolve a lista de linhas como dicionários."""
    with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
        return [
            {chave: " ".join((valor or "").split()) for chave, valor in linha.items()}
            for linha in csv.DictReader(arquivo, delimiter=";")
            if any((valor or "").strip() for valor in linha.values())
        ]


def _validar(linhas):
    """Confere todas as linhas antes de gravar qualquer uma, para não deixar a carga pela metade."""
    eixos = {e.numero: e.id for e in Eixo.query.all()}
    divisoes = set(divisao_service.siglas_para_demandas())
    erros = []
    for n, linha in enumerate(linhas, start=2):  # linha 1 é o cabeçalho
        try:
            numero = int(linha["eixo"])
        except (KeyError, ValueError):
            numero = None
        if numero not in eixos:
            erros.append(f"linha {n}: eixo inválido ({linha.get('eixo')!r})")
        if not linha.get("acao"):
            erros.append(f"linha {n}: ação vazia")
        if not linha.get("produto"):
            erros.append(f"linha {n}: produto vazio")
        if linha.get("divisao") not in divisoes:
            erros.append(f"linha {n}: divisão não cadastrada ({linha.get('divisao')!r})")
    if erros:
        raise RegraNegocioError("Plano de trabalho com erros:\n  " + "\n  ".join(erros))
    return eixos


def carregar_plano_trabalho(criador, caminho=ARQUIVO_PLANO):
    """Cria as demandas do plano como 'Nova', em nome do 'criador' (o Gerente administrador).

    Retorna quantas foram criadas (0 se a base já tinha demandas).
    """
    if Demanda.query.first():
        return 0

    linhas = ler_plano(caminho)
    eixos = _validar(linhas)
    for linha in linhas:
        demanda_service.criar(
            criador,
            {
                "eixo_id": eixos[int(linha["eixo"])],
                "acao": linha["acao"],
                "produto": linha["produto"],
                "divisao": linha["divisao"],
            },
        )
    return len(linhas)
