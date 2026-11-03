"""Matriz GUT: Gravidade × Urgência × Tendência.

Cada peso vai de 1 a 5, e a prioridade P = G × U × T vai de 1 a 125.
"""
from .erros import RegraNegocioError

PESO_MIN = 1
PESO_MAX = 5

# (limite inferior, limite superior, rótulo, classe css)
FAIXAS = (
    (1, 27, "Baixa", "baixa"),
    (28, 63, "Média", "media"),
    (64, 125, "Alta", "alta"),
)
FAIXA_PENDENTE = ("Aguardando priorização", "pendente")

ROTULOS_PESO = {
    "gravidade": {
        1: "Sem gravidade", 2: "Pouco grave", 3: "Grave", 4: "Muito grave", 5: "Extremamente grave",
    },
    "urgencia": {
        1: "Pode esperar", 2: "Pouco urgente", 3: "Urgente, merece atenção no curto prazo",
        4: "Muito urgente", 5: "Necessita ação imediata",
    },
    "tendencia": {
        1: "Não irá mudar", 2: "Irá piorar a longo prazo", 3: "Irá piorar a médio prazo",
        4: "Irá piorar a curto prazo", 5: "Irá piorar rapidamente",
    },
}


def validar_peso(valor, nome="peso"):
    """Valida e converte um peso GUT para inteiro entre 1 e 5."""
    try:
        inteiro = int(valor)
    except (TypeError, ValueError):
        raise RegraNegocioError(f"O valor de {nome} deve ser um número inteiro de 1 a 5.")
    if not PESO_MIN <= inteiro <= PESO_MAX:
        raise RegraNegocioError(f"O valor de {nome} deve estar entre 1 e 5.")
    return inteiro


def calcular_prioridade(gravidade, urgencia, tendencia):
    """Retorna P = G × U × T, ou None se algum peso não foi informado."""
    if gravidade is None or urgencia is None or tendencia is None:
        return None
    g = validar_peso(gravidade, "Gravidade")
    u = validar_peso(urgencia, "Urgência")
    t = validar_peso(tendencia, "Tendência")
    return g * u * t


def faixa(prioridade):
    """Retorna (rótulo, classe_css) da faixa de prioridade."""
    if prioridade is None:
        return FAIXA_PENDENTE
    for minimo, maximo, rotulo, css in FAIXAS:
        if minimo <= prioridade <= maximo:
            return rotulo, css
    raise ValueError(f"Prioridade fora do intervalo: {prioridade}")


def intervalo_da_faixa(css):
    """Retorna (mínimo, máximo) de uma faixa pela sua classe css, ou None se desconhecida."""
    for minimo, maximo, _rotulo, classe in FAIXAS:
        if classe == css:
            return minimo, maximo
    return None
