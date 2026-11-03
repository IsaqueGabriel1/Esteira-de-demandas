"""Filtros e variáveis globais disponíveis em todos os templates Jinja2."""
from datetime import date, timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    FUSO_LOCAL = ZoneInfo("America/Sao_Paulo")
except Exception:  # sem base de fusos instalada: Brasília não tem horário de verão desde 2019
    FUSO_LOCAL = timezone(timedelta(hours=-3))

from .services import gut, permissoes
from .services.fluxo import Acao, Status
from .services.perfis import Perfil


def _data_br(valor):
    if not valor:
        return "—"
    return valor.strftime("%d/%m/%Y")


def _data_hora_br(valor):
    """Datas/horas são gravadas em UTC; exibe no horário de Brasília."""
    if not valor:
        return "—"
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(FUSO_LOCAL).strftime("%d/%m/%Y %H:%M")


def registrar_helpers(app):
    app.add_template_filter(_data_br, "data_br")
    app.add_template_filter(_data_hora_br, "data_hora_br")

    # Globais (e não context_processor) para ficarem visíveis também dentro de macros importadas
    app.jinja_env.globals.update(
        Status=Status,
        Acao=Acao,
        Perfil=Perfil,
        permissoes=permissoes,
        FAIXAS_GUT=gut.FAIXAS,
        ROTULOS_PESO=gut.ROTULOS_PESO,
    )

    @app.context_processor
    def data_de_hoje():
        return {"hoje": date.today()}
