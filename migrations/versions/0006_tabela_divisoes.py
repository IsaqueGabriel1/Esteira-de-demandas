"""Cria a tabela de divisões (gerenciada pelo Administrador) com as divisões atuais.

Também amplia usuarios.divisao para 20 caracteres, o mesmo tamanho da sigla.

Revision ID: 0006_tabela_divisoes
Revises: 0005_amplia_divisao_demanda
"""
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0006_tabela_divisoes"
down_revision = "0005_amplia_divisao_demanda"
branch_labels = None
depends_on = None

# (sigla, aparece para usuários, aparece nas demandas) — mesmas opções que existiam fixas no código
DIVISOES_INICIAIS = [
    ("DIO", True, True),
    ("DPO", True, True),
    ("GGO", True, True),
    ("SR", True, False),
    ("DIO/DPO", False, True),
    ("DPO/DIO", False, True),
    ("GGO/DPO/DIO", False, True),
]


def upgrade():
    divisoes = op.create_table(
        "divisoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sigla", sa.String(length=20), nullable=False, unique=True),
        sa.Column("para_usuarios", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("para_demandas", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
    )
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    op.bulk_insert(divisoes, [
        {"sigla": s, "para_usuarios": u, "para_demandas": d, "ativa": True, "criado_em": agora}
        for s, u, d in DIVISOES_INICIAIS
    ])

    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.alter_column(
            "divisao", existing_type=sa.String(length=10), type_=sa.String(length=20), existing_nullable=True
        )


def downgrade():
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.alter_column(
            "divisao", existing_type=sa.String(length=20), type_=sa.String(length=10), existing_nullable=True
        )
    op.drop_table("divisoes")
