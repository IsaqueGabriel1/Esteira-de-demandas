from ..extensions import db
from .base import agora


class TentativaLogin(db.Model):
    """Cada tentativa de login, com sucesso ou não (alimenta a tela de uso do sistema)."""

    __tablename__ = "tentativas_login"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    # Preenchido quando o e-mail digitado é de um usuário cadastrado, mesmo se a senha estiver errada
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    sucesso = db.Column(db.Boolean, nullable=False)
    ip = db.Column(db.String(45), nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora, index=True)

    usuario = db.relationship("Usuario")


class AcessoPagina(db.Model):
    """Cada página aberta por um usuário logado (só GET com resposta 200)."""

    __tablename__ = "acessos_pagina"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint = db.Column(db.String(80), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora, index=True)

    usuario = db.relationship("Usuario")
