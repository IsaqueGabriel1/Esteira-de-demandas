"""Uso do sistema: registra logins e páginas acessadas e monta a tela do Administrador."""
import time
from collections import Counter
from datetime import timedelta, timezone

from flask import current_app, session

from ..extensions import db
from ..models import AcessoPagina, TentativaLogin, Usuario
from ..models.base import agora
from ..template_helpers import FUSO_LOCAL

PERIODOS = {
    "7": ("Últimos 7 dias", 7),
    "30": ("Últimos 30 dias", 30),
    "90": ("Últimos 90 dias", 90),
}
PERIODO_PADRAO = "30"

# Reabrir o mesmo endereço dentro deste intervalo conta como a mesma visita
INTERVALO_VISITA = 30 * 60  # segundos

# Nome amigável das páginas; as que não estão aqui aparecem pelo nome técnico
NOMES_PAGINAS = {
    "demandas.inicio": "Início",
    "demandas.quadro": "Quadro",
    "demandas.lista": "Lista de demandas",
    "demandas.minhas": "Minhas demandas",
    "demandas.nova": "Nova demanda",
    "demandas.detalhe": "Detalhe da demanda",
    "demandas.editar": "Editar demanda",
    "indicadores.painel": "Indicadores",
    "usuarios.lista": "Usuários",
    "usuarios.novo": "Novo usuário",
    "usuarios.editar": "Editar usuário",
    "divisoes.lista": "Divisões",
    "divisoes.nova": "Nova divisão",
    "divisoes.editar": "Editar divisão",
    "permissoes.matriz": "Permissões",
    "auth.minha_senha": "Alterar senha",
    "auth.minha_divisao": "Minha divisão",
    "uso.painel": "Uso do sistema",
}


def registrar_login(email, usuario, sucesso, ip):
    """Grava a tentativa de login. Falha ao gravar não pode impedir o login."""
    email = (email or "").strip().lower()[:120]
    if usuario is None:
        usuario = Usuario.query.filter_by(email=email).first()
    try:
        db.session.add(TentativaLogin(email=email, usuario_id=usuario.id if usuario else None, sucesso=sucesso, ip=ip))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Não foi possível registrar a tentativa de login")


def registrar_acesso(usuario, endpoint, caminho):
    """Grava a página aberta, no máximo uma vez a cada INTERVALO_VISITA por
    endereço (recarregar a página não conta de novo). Falha ao gravar não pode
    quebrar a página."""
    # O controle fica na sessão do usuário para não consultar o banco a cada clique
    agora_ts = int(time.time())
    vistos = {c: ts for c, ts in session.get("acessos_vistos", {}).items() if agora_ts - ts < INTERVALO_VISITA}
    if caminho in vistos:
        return
    vistos[caminho] = agora_ts
    session["acessos_vistos"] = vistos
    try:
        db.session.add(AcessoPagina(usuario_id=usuario.id, endpoint=endpoint[:80]))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Não foi possível registrar o acesso à página")


def _dia_local(valor):
    return valor.replace(tzinfo=timezone.utc).astimezone(FUSO_LOCAL).date()


def painel(periodo=PERIODO_PADRAO):
    if periodo not in PERIODOS:
        periodo = PERIODO_PADRAO
    rotulo, dias = PERIODOS[periodo]
    inicio = agora() - timedelta(days=dias)

    tentativas = TentativaLogin.query.filter(TentativaLogin.criado_em >= inicio).all()
    acessos = AcessoPagina.query.filter(AcessoPagina.criado_em >= inicio).all()
    sucessos = [t for t in tentativas if t.sucesso]
    falhas = [t for t in tentativas if not t.sucesso]

    # Acessos por dia (horário de Brasília), incluindo os dias sem nenhum acesso
    hoje = _dia_local(agora())
    dias_periodo = [hoje - timedelta(days=n) for n in range(dias - 1, -1, -1)]
    logins_dia = Counter(_dia_local(t.criado_em) for t in sucessos)
    falhas_dia = Counter(_dia_local(t.criado_em) for t in falhas)
    pessoas_dia = {}
    for a in acessos:
        pessoas_dia.setdefault(_dia_local(a.criado_em), set()).add(a.usuario_id)

    # Último acesso: login ou página aberta, o que for mais recente (quem usa
    # "lembrar de mim" pode passar semanas sem digitar a senha)
    ultimo_login = dict(
        db.session.query(TentativaLogin.usuario_id, db.func.max(TentativaLogin.criado_em))
        .filter(TentativaLogin.sucesso.is_(True), TentativaLogin.usuario_id.isnot(None))
        .group_by(TentativaLogin.usuario_id)
    )
    ultima_pagina = dict(
        db.session.query(AcessoPagina.usuario_id, db.func.max(AcessoPagina.criado_em)).group_by(AcessoPagina.usuario_id)
    )
    usuarios = []
    for u in Usuario.query.filter_by(ativo=True).all():
        datas = [d for d in (ultimo_login.get(u.id), ultima_pagina.get(u.id)) if d]
        usuarios.append({"usuario": u, "ultimo_login": ultimo_login.get(u.id), "ultimo_acesso": max(datas) if datas else None})
    usuarios.sort(key=lambda x: (x["ultimo_acesso"] is None, -(x["ultimo_acesso"].timestamp() if x["ultimo_acesso"] else 0), x["usuario"].nome))

    contagem_paginas = Counter(a.endpoint for a in acessos)
    pessoas_pagina = {}
    for a in acessos:
        pessoas_pagina.setdefault(a.endpoint, set()).add(a.usuario_id)
    paginas = [
        {"nome": NOMES_PAGINAS.get(ep, ep), "acessos": n, "pessoas": len(pessoas_pagina[ep])}
        for ep, n in contagem_paginas.most_common()
    ]

    return {
        "periodo": periodo,
        "periodo_rotulo": rotulo,
        "resumo": {
            "logins": len(sucessos),
            "falhas": len(falhas),
            "pessoas": len({a.usuario_id for a in acessos} | {t.usuario_id for t in sucessos if t.usuario_id}),
            "paginas": len(acessos),
        },
        "usuarios": usuarios,
        "paginas": paginas,
        "falhas_recentes": sorted(falhas, key=lambda t: t.criado_em, reverse=True)[:50],
        "falhas_por_email": Counter(t.email for t in falhas).most_common(10),
        "falhas_por_ip": Counter(t.ip or "—" for t in falhas).most_common(10),
        "graficos": {
            "dias": {
                "rotulos": [d.strftime("%d/%m") for d in dias_periodo],
                "logins": [logins_dia.get(d, 0) for d in dias_periodo],
                "falhas": [falhas_dia.get(d, 0) for d in dias_periodo],
                "pessoas": [len(pessoas_dia.get(d, ())) for d in dias_periodo],
            },
        },
    }
