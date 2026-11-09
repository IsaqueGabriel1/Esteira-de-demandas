"""Amplia a coluna divisão da demanda para comportar "GGO/DPO/DIO".

Revision ID: 0005_amplia_divisao_demanda
Revises: 0004_divisao_usuario
"""
import sqlalchemy as sa
from alembic import op

revision = "0005_amplia_divisao_demanda"
down_revision = "0004_divisao_usuario"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("demandas") as batch_op:
        batch_op.alter_column(
            "divisao", existing_type=sa.String(length=10), type_=sa.String(length=20), existing_nullable=True
        )


def downgrade():
    with op.batch_alter_table("demandas") as batch_op:
        batch_op.alter_column(
            "divisao", existing_type=sa.String(length=20), type_=sa.String(length=10), existing_nullable=True
        )
