"""Registra até quando cada usuário leu os comentários de cada demanda (sino da navbar).

Revision ID: 0010_leituras_comentarios
Revises: 0009_comentarios_demanda
"""
import sqlalchemy as sa
from alembic import op

revision = "0010_leituras_comentarios"
down_revision = "0009_comentarios_demanda"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "leituras_comentarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("demanda_id", sa.Integer(), sa.ForeignKey("demandas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lido_em", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("usuario_id", "demanda_id"),
    )
    op.create_index("ix_leituras_comentarios_demanda_id", "leituras_comentarios", ["demanda_id"])


def downgrade():
    op.drop_index("ix_leituras_comentarios_demanda_id", table_name="leituras_comentarios")
    op.drop_table("leituras_comentarios")
