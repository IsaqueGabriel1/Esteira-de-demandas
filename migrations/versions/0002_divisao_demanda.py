"""Adiciona a divisão (DIO, DPO ou DIO/DPO) à demanda.

Revision ID: 0002_divisao_demanda
Revises: 0001_inicial
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_divisao_demanda"
down_revision = "0001_inicial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("demandas", sa.Column("divisao", sa.String(length=10), nullable=True))
    op.create_index("ix_demandas_divisao", "demandas", ["divisao"])


def downgrade():
    op.drop_index("ix_demandas_divisao", table_name="demandas")
    op.drop_column("demandas", "divisao")
