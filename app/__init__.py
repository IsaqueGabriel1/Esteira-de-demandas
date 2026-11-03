"""Application factory do Sistema de Gestão de Demandas (Esteira de Pedidos)."""
import os

from flask import Flask


def create_app(nome_config=None):
    """Cria e configura a aplicação Flask.

    nome_config: "development", "production" ou "testing".
    Se não informado, usa a variável de ambiente APP_CONFIG (padrão: development).
    """
    # Imports aqui dentro para que os módulos de regras puras (app.services.gut,
    # app.services.fluxo, app.services.permissoes) possam ser importados sem
    # carregar Flask-SQLAlchemy e demais extensões.
    from config import configuracoes

    from .extensions import csrf, db, login_manager, migrate

    nome_config = nome_config or os.environ.get("APP_CONFIG", "development")
    app = Flask(__name__)
    app.config.from_object(configuracoes[nome_config])

    if nome_config == "production" and app.config["SECRET_KEY"].startswith("dev-"):
        raise RuntimeError("Defina SECRET_KEY no arquivo .env antes de rodar em produção.")

    if app.config.get("BEHIND_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(os.path.dirname(app.root_path), "migrations"))
    csrf.init_app(app)
    login_manager.init_app(app)

    from . import models  # noqa: F401  (registra os models no metadata)
    from .models import Usuario

    @login_manager.user_loader
    def carregar_usuario(usuario_id):
        usuario = db.session.get(Usuario, int(usuario_id))
        return usuario if usuario and usuario.ativo else None

    from .controllers import registrar_blueprints

    registrar_blueprints(app)

    from .template_helpers import registrar_helpers

    registrar_helpers(app)

    from .cli import registrar_comandos

    registrar_comandos(app)

    return app
