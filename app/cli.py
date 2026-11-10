"""Comandos de linha de comando (flask <comando>)."""
import click

from .extensions import db
from .models import Eixo, Usuario
from .services import carga_inicial, divisao_service
from .services.erros import RegraNegocioError
from .services.perfis import Perfil

EIXOS_PADRAO = [
    (1, "Balanço Hídrico e Suporte à Decisão"),
    (2, "Procedimentos, Padronização e Melhoria Contínua"),
    (3, "Gestão, Qualidade e Governança da Informação"),
    (4, "Sistemas, Regras de Negócio e Transformação Digital"),
    (5, "Integração, Atendimento, Capacitação e Gestão do Conhecimento"),
    (6, "Monitoramento, Indicadores e Desempenho"),
]


def carregar_eixos():
    criados = 0
    for numero, nome in EIXOS_PADRAO:
        if not Eixo.query.filter_by(numero=numero).first():
            db.session.add(Eixo(numero=numero, nome=nome, ativo=True))
            criados += 1
    db.session.commit()
    return criados


def registrar_comandos(app):
    @app.cli.command("seed")
    def seed():
        """Carga inicial: eixos, divisões, Gerente administrador e demandas do Plano de Trabalho.

        Cada parte só é criada se ainda não existir; as demandas, só se a base não tiver nenhuma.
        """
        criados = carregar_eixos()
        click.echo(f"Eixos: {criados} criado(s).")
        click.echo(f"Divisões: {divisao_service.carregar_padrao()} criada(s).")

        admin = _garantir_gerente(app)
        if admin is None:
            click.echo("ATENÇÃO: defina ADMIN_SENHA (mín. 8 caracteres) no .env para criar o Gerente inicial.")
            click.echo("Plano de trabalho: não carregado (precisa de um Gerente para registrar a criação).")
            return

        try:
            criadas = carga_inicial.carregar_plano_trabalho(admin)
        except RegraNegocioError as erro:
            raise click.ClickException(str(erro))
        if criadas:
            click.echo(f"Plano de trabalho: {criadas} demanda(s) criada(s).")
        else:
            click.echo("Plano de trabalho: a base já tem demandas, nada a fazer.")

    def _garantir_gerente(app):
        """Devolve o Gerente administrador, criando-o pelo .env se ainda não houver nenhum Gerente."""
        email = (app.config.get("ADMIN_EMAIL") or "").strip().lower()
        existente = (
            Usuario.query.filter_by(email=email, perfil=Perfil.GERENTE).first()
            or Usuario.query.filter_by(perfil=Perfil.GERENTE).order_by(Usuario.id).first()
        )
        if existente:
            click.echo("Gerente: já existe, nada a fazer.")
            return existente

        senha = app.config.get("ADMIN_SENHA")
        if not senha or len(senha) < 8:
            return None
        admin = Usuario(nome=app.config["ADMIN_NOME"], email=email, perfil=Perfil.GERENTE, ativo=True)
        admin.definir_senha(senha)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Gerente criado: {admin.email}")
        return admin

    @app.cli.command("criar-usuario")
    @click.option("--nome", prompt=True)
    @click.option("--email", prompt=True)
    @click.option("--perfil", type=click.Choice(Perfil.TODOS), default=Perfil.USUARIO, show_default=True)
    @click.password_option("--senha")
    def criar_usuario(nome, email, perfil, senha):
        """Cria um usuário pela linha de comando (útil para recuperar acesso)."""
        email = email.strip().lower()
        if Usuario.query.filter_by(email=email).first():
            raise click.ClickException("Já existe um usuário com este e-mail.")
        usuario = Usuario(nome=nome.strip(), email=email, perfil=perfil, ativo=True)
        usuario.definir_senha(senha)
        db.session.add(usuario)
        db.session.commit()
        click.echo(f"Usuário criado: {email} ({Perfil.rotulo(perfil)})")
