"""Registra tentativas de login e páginas acessadas (tela de uso do sistema).

Revision ID: 0011_registro_de_uso
Revises: 0010_leituras_comentarios
"""
import sqlalchemy as sa
from alembic import op

revision = "0011_registro_de_uso"
down_revision = "0010_leituras_comentarios"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tentativas_login",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(120), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sucesso", sa.Boolean(), nullable=False),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tentativas_login_usuario_id", "tentativas_login", ["usuario_id"])
    op.create_index("ix_tentativas_login_criado_em", "tentativas_login", ["criado_em"])

    op.create_table(
        "acessos_pagina",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint", sa.String(80), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_acessos_pagina_usuario_id", "acessos_pagina", ["usuario_id"])
    op.create_index("ix_acessos_pagina_criado_em", "acessos_pagina", ["criado_em"])


def downgrade():
    op.drop_index("ix_acessos_pagina_criado_em", table_name="acessos_pagina")
    op.drop_index("ix_acessos_pagina_usuario_id", table_name="acessos_pagina")
    op.drop_table("acessos_pagina")
    op.drop_index("ix_tentativas_login_criado_em", table_name="tentativas_login")
    op.drop_index("ix_tentativas_login_usuario_id", table_name="tentativas_login")
    op.drop_table("tentativas_login")
