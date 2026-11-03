from ..extensions import db


class Eixo(db.Model):
    """Eixo temático da demanda. Fica em tabela para permitir ajustes sem mexer no código."""

    __tablename__ = "eixos"

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False, unique=True)
    nome = db.Column(db.String(200), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    @property
    def rotulo(self):
        return f"EIXO {self.numero} — {self.nome}"

    @property
    def sigla(self):
        return f"E{self.numero}"

    def __repr__(self):
        return f"<Eixo {self.numero}>"
