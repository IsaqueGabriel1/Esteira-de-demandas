"""Fixtures de teste. Usa SQLite em memória (não precisa do PostgreSQL)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def app():
    from app import create_app
    from app.cli import carregar_eixos
    from app.extensions import db

    app = create_app("testing")
    with app.app_context():
        db.create_all()
        carregar_eixos()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def db(app):
    from app.extensions import db as _db

    return _db


def _novo_usuario(db, nome, email, perfil):
    from app.models import Usuario

    usuario = Usuario(nome=nome, email=email, perfil=perfil, ativo=True)
    usuario.definir_senha("senha-segura-123")
    db.session.add(usuario)
    db.session.commit()
    return usuario


@pytest.fixture
def usuarios(db):
    """Um usuário de cada perfil, mais extras para testar as regras."""
    from app.services.perfis import Perfil

    return {
        "gerente": _novo_usuario(db, "Gina Gerente", "gerente@teste.gov.br", Perfil.GERENTE),
        "chefe": _novo_usuario(db, "Carlos Chefe", "chefe@teste.gov.br", Perfil.CHEFE),
        "chefe2": _novo_usuario(db, "Clara Chefe", "chefe2@teste.gov.br", Perfil.CHEFE),
        "usuario": _novo_usuario(db, "Ulisses Usuario", "usuario@teste.gov.br", Perfil.USUARIO),
        "usuario2": _novo_usuario(db, "Ursula Usuaria", "usuario2@teste.gov.br", Perfil.USUARIO),
    }


@pytest.fixture
def eixo(db):
    from app.models import Eixo

    return Eixo.query.filter_by(numero=1).first()


@pytest.fixture
def nova_demanda(eixo):
    """Fábrica: nova_demanda(criador, **campos)."""
    from app.services import demanda_service

    def _criar(criador, **campos):
        dados = {"eixo_id": eixo.id, "acao": "Inventariar bases de outorga", "produto": "Planilha de inventário"}
        dados.update(campos)
        return demanda_service.criar(criador, dados)

    return _criar


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    def _login(usuario):
        return client.post("/login", data={"email": usuario.email, "senha": "senha-segura-123"})
    return _login
