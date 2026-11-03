"""Configurações da aplicação por ambiente.

Valores sensíveis vêm sempre de variáveis de ambiente (arquivo .env no Docker).
"""
import os


def _bool(nome, padrao=False):
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-chave-insegura-troque-no-env")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # token válido enquanto durar a sessão

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True

    # Dados do Gerente administrador criado pelo comando "flask seed"
    ADMIN_NOME = os.environ.get("ADMIN_NOME", "Administrador")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@agencia.gov.br")
    ADMIN_SENHA = os.environ.get("ADMIN_SENHA")

    # Quando a aplicação roda atrás do Nginx
    BEHIND_PROXY = _bool("BEHIND_PROXY", False)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "chave-de-teste"


configuracoes = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
