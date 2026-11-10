from ..extensions import db
from .base import agora


class Divisao(db.Model):
    """Divisão cadastrada pelo Administrador.

    Usuários e demandas guardam a sigla (texto), e não o id: por isso a sigla não pode
    ser alterada depois de criada, e a divisão é desativada em vez de excluída.
    """

    __tablename__ = "divisoes"

    id = db.Column(db.Integer, primary_key=True)
    sigla = db.Column(db.String(20), nullable=False, unique=True)
    # Onde a divisão aparece como opção
    para_usuarios = db.Column(db.Boolean, nullable=False, default=True)
    para_demandas = db.Column(db.Boolean, nullable=False, default=True)
    ativa = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)

    def __repr__(self):
        return f"<Divisao {self.sigla}>"
