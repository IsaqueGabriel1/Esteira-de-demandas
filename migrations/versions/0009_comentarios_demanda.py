"""Cria a tabela de comentários das demandas.

Revision ID: 0009_comentarios_demanda
Revises: 0008_prazo_acordado
"""
import sqlalchemy as sa
from alembic import op

revision = "0009_comentarios_demanda"
down_revision = "0008_prazo_acordado"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "comentarios_demanda",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("demanda_id", sa.Integer(), sa.ForeignKey("demandas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("editado_em", sa.DateTime(), nullable=True),
        sa.Column("removido_em", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_comentarios_demanda_demanda_id", "comentarios_demanda", ["demanda_id"])


def downgrade():
    op.drop_index("ix_comentarios_demanda_demanda_id", table_name="comentarios_demanda")
    op.drop_table("comentarios_demanda")
