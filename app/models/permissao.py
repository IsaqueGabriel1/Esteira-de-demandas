from ..extensions import db
from .base import agora


class PermissaoPerfil(db.Model):
    """Funcionalidade ligada/desligada para um perfil pelo Administrador.

    Só existem linhas para o que foi alterado na tela; o resto segue o padrão
    definido em app/services/permissoes.py.
    """

    __tablename__ = "permissoes_perfil"
    __table_args__ = (db.UniqueConstraint("perfil", "chave"),)

    id = db.Column(db.Integer, primary_key=True)
    perfil = db.Column(db.String(20), nullable=False)
    chave = db.Column(db.String(40), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False)


class HistoricoPermissao(db.Model):
    """Registro de cada alteração feita na tela Permissões."""

    __tablename__ = "historico_permissoes"

    id = db.Column(db.Integer, primary_key=True)
    perfil = db.Column(db.String(20), nullable=False)
    chave = db.Column(db.String(40), nullable=False)
    antes = db.Column(db.Boolean, nullable=False)
    depois = db.Column(db.Boolean, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    usuario = db.relationship("Usuario")
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)
