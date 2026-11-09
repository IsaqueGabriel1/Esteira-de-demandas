"""Adiciona a divisão (SR, GGO, DPO ou DIO) ao usuário.

Revision ID: 0004_divisao_usuario
Revises: 0003_pasta_rede_demanda
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_divisao_usuario"
down_revision = "0003_pasta_rede_demanda"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("usuarios", sa.Column("divisao", sa.String(length=10), nullable=True))


def downgrade():
    op.drop_column("usuarios", "divisao")
