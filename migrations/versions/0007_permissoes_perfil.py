"""Cria as tabelas das permissões por perfil configuráveis pelo Administrador.

Sem linhas, vale o padrão definido em app/services/permissoes.py (as regras de antes).

Revision ID: 0007_permissoes_perfil
Revises: 0006_tabela_divisoes
"""
import sqlalchemy as sa
from alembic import op

revision = "0007_permissoes_perfil"
down_revision = "0006_tabela_divisoes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "permissoes_perfil",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("perfil", sa.String(length=20), nullable=False),
        sa.Column("chave", sa.String(length=40), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("perfil", "chave"),
    )
    op.create_table(
        "historico_permissoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("perfil", sa.String(length=20), nullable=False),
        sa.Column("chave", sa.String(length=40), nullable=False),
        sa.Column("antes", sa.Boolean(), nullable=False),
        sa.Column("depois", sa.Boolean(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("historico_permissoes")
    op.drop_table("permissoes_perfil")
