from ..extensions import db
from .base import agora


class TipoEvento:
    CRIACAO = "CRIACAO"
    EDICAO = "EDICAO"
    ATRIBUICAO = "ATRIBUICAO"
    ACEITE = "ACEITE"
    RECUSA = "RECUSA"
    GUT = "GUT"
    APOIO = "APOIO"
    ENVIO_REVISAO = "ENVIO_REVISAO"
    APROVACAO = "APROVACAO"
    DEVOLUCAO = "DEVOLUCAO"
    CANCELAMENTO = "CANCELAMENTO"

    ROTULOS = {
        CRIACAO: "Criação",
        EDICAO: "Edição",
        ATRIBUICAO: "Atribuição",
        ACEITE: "Aceite",
        RECUSA: "Recusa",
        GUT: "Priorização GUT",
        APOIO: "Usuários de apoio",
        ENVIO_REVISAO: "Enviada para revisão",
        APROVACAO: "Aprovação",
        DEVOLUCAO: "Devolução",
        CANCELAMENTO: "Cancelamento",
    }
    ICONES = {
        CRIACAO: "bi-plus-circle",
        EDICAO: "bi-pencil",
        ATRIBUICAO: "bi-person-plus",
        ACEITE: "bi-check-circle",
        RECUSA: "bi-x-circle",
        GUT: "bi-bar-chart",
        APOIO: "bi-people",
        ENVIO_REVISAO: "bi-send",
        APROVACAO: "bi-patch-check",
        DEVOLUCAO: "bi-arrow-counterclockwise",
        CANCELAMENTO: "bi-slash-circle",
    }


class HistoricoDemanda(db.Model):
    """Registro de auditoria: quem fez o quê, quando, e com quais valores."""

    __tablename__ = "historico_demanda"

    id = db.Column(db.Integer, primary_key=True)
    demanda_id = db.Column(
        db.Integer, db.ForeignKey("demandas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    dados = db.Column(db.JSON, nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)

    demanda = db.relationship("Demanda", back_populates="historico")
    usuario = db.relationship("Usuario")

    @property
    def tipo_rotulo(self):
        return TipoEvento.ROTULOS.get(self.tipo, self.tipo)

    @property
    def icone(self):
        return TipoEvento.ICONES.get(self.tipo, "bi-dot")
