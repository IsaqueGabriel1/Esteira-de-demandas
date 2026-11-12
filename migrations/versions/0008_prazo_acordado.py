"""Adiciona o prazo acordado à demanda (definido pelo responsável; define o atraso).

Revision ID: 0008_prazo_acordado
Revises: 0007_permissoes_perfil
"""
import sqlalchemy as sa
from alembic import op

revision = "0008_prazo_acordado"
down_revision = "0007_permissoes_perfil"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("demandas", sa.Column("prazo_acordado", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("demandas", "prazo_acordado")
