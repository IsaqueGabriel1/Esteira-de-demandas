from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..services.perfis import Perfil
from .base import agora


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.String(20), nullable=False, default=Perfil.USUARIO)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    # Obrigatória para todos menos o Administrador; quem não tiver informa no próximo acesso.
    divisao = db.Column(db.String(20), nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    @property
    def is_active(self):  # usado pelo Flask-Login
        return bool(self.ativo)

    @property
    def perfil_rotulo(self):
        return Perfil.rotulo(self.perfil)

    @property
    def eh_gestor(self):
        return self.perfil in Perfil.GESTORES

    @property
    def iniciais(self):
        partes = [p for p in self.nome.split() if p]
        if not partes:
            return "?"
        if len(partes) == 1:
            return partes[0][:2].upper()
        return (partes[0][0] + partes[-1][0]).upper()

    def __repr__(self):
        return f"<Usuario {self.email} ({self.perfil})>"
