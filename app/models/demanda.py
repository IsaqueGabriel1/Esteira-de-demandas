from datetime import date

from ..extensions import db
from ..services import gut
from ..services.fluxo import Status
from .base import agora

demanda_apoio = db.Table(
    "demanda_apoio",
    db.Column("demanda_id", db.Integer, db.ForeignKey("demandas.id", ondelete="CASCADE"), primary_key=True),
    db.Column("usuario_id", db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
)


class Demanda(db.Model):
    __tablename__ = "demandas"
    __table_args__ = (
        db.CheckConstraint("gravidade IS NULL OR gravidade BETWEEN 1 AND 5", name="ck_demandas_gravidade"),
        db.CheckConstraint("urgencia IS NULL OR urgencia BETWEEN 1 AND 5", name="ck_demandas_urgencia"),
        db.CheckConstraint("tendencia IS NULL OR tendencia BETWEEN 1 AND 5", name="ck_demandas_tendencia"),
        db.CheckConstraint("termino IS NULL OR inicio IS NULL OR termino >= inicio", name="ck_demandas_prazo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    eixo_id = db.Column(db.Integer, db.ForeignKey("eixos.id"), nullable=False, index=True)
    acao = db.Column(db.Text, nullable=False)
    produto = db.Column(db.Text, nullable=False)
    # Obrigatória em novas demandas; pode ficar vazia nas criadas antes de o campo existir.
    divisao = db.Column(db.String(10), nullable=True, index=True)
    # Caminho ou link da pasta na rede onde está o trabalho realizado (opcional).
    pasta_rede = db.Column(db.String(500), nullable=True)
    inicio = db.Column(db.Date, nullable=True)
    termino = db.Column(db.Date, nullable=True)

    status = db.Column(db.String(30), nullable=False, default=Status.NOVA, index=True)

    atribuido_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True, index=True)
    atribuido_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    justificativa_recusa = db.Column(db.Text, nullable=True)
    recusado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)

    gravidade = db.Column(db.Integer, nullable=True)
    urgencia = db.Column(db.Integer, nullable=True)
    tendencia = db.Column(db.Integer, nullable=True)
    # P = G × U × T. Gravado pela camada de serviços (nunca digitado) para permitir ordenação no banco.
    prioridade = db.Column(db.Integer, nullable=True, index=True)

    criado_em = db.Column(db.DateTime, nullable=False, default=agora)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=agora, onupdate=agora)
    concluido_em = db.Column(db.DateTime, nullable=True)

    eixo = db.relationship("Eixo")
    atribuido = db.relationship("Usuario", foreign_keys=[atribuido_id])
    atribuido_por = db.relationship("Usuario", foreign_keys=[atribuido_por_id])
    criado_por = db.relationship("Usuario", foreign_keys=[criado_por_id])
    recusado_por = db.relationship("Usuario", foreign_keys=[recusado_por_id])
    apoios = db.relationship("Usuario", secondary=demanda_apoio, order_by="Usuario.nome")
    historico = db.relationship(
        "HistoricoDemanda",
        back_populates="demanda",
        cascade="all, delete-orphan",
        order_by="HistoricoDemanda.id.desc()",
    )

    @property
    def status_rotulo(self):
        return Status.rotulo(self.status)

    @property
    def finalizada(self):
        return self.status in Status.FINAIS

    @property
    def atrasada(self):
        return bool(self.termino and not self.finalizada and self.termino < date.today())

    @property
    def faixa(self):
        """(rótulo, classe css) da faixa de prioridade."""
        return gut.faixa(self.prioridade)

    @property
    def tem_gut(self):
        return self.prioridade is not None

    def __repr__(self):
        return f"<Demanda #{self.id} {self.status}>"
