from ..extensions import db
from .base import agora


class ComentarioDemanda(db.Model):
    """Comentário livre de um usuário na demanda. A remoção é lógica (removido_em)."""

    __tablename__ = "comentarios_demanda"

    id = db.Column(db.Integer, primary_key=True)
    demanda_id = db.Column(
        db.Integer, db.ForeignKey("demandas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)
    editado_em = db.Column(db.DateTime, nullable=True)
    removido_em = db.Column(db.DateTime, nullable=True)

    demanda = db.relationship("Demanda", back_populates="comentarios")
    usuario = db.relationship("Usuario")
