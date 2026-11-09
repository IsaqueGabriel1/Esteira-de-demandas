"""Adiciona a pasta da rede (link do trabalho realizado) à demanda.

Revision ID: 0003_pasta_rede_demanda
Revises: 0002_divisao_demanda
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_pasta_rede_demanda"
down_revision = "0002_divisao_demanda"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("demandas", sa.Column("pasta_rede", sa.String(length=500), nullable=True))


def downgrade():
    op.drop_column("demandas", "pasta_rede")
