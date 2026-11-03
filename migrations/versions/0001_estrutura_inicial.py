"""Estrutura inicial: usuários, eixos, demandas, apoio e histórico

Revision ID: 0001_inicial
Revises:
Create Date: 2026-11-03 15:30:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_inicial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column("perfil", sa.String(length=20), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)

    op.create_table(
        "eixos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("numero"),
    )

    op.create_table(
        "demandas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("eixo_id", sa.Integer(), nullable=False),
        sa.Column("acao", sa.Text(), nullable=False),
        sa.Column("produto", sa.Text(), nullable=False),
        sa.Column("inicio", sa.Date(), nullable=True),
        sa.Column("termino", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("atribuido_id", sa.Integer(), nullable=True),
        sa.Column("atribuido_por_id", sa.Integer(), nullable=True),
        sa.Column("criado_por_id", sa.Integer(), nullable=False),
        sa.Column("justificativa_recusa", sa.Text(), nullable=True),
        sa.Column("recusado_por_id", sa.Integer(), nullable=True),
        sa.Column("gravidade", sa.Integer(), nullable=True),
        sa.Column("urgencia", sa.Integer(), nullable=True),
        sa.Column("tendencia", sa.Integer(), nullable=True),
        sa.Column("prioridade", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.Column("concluido_em", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["eixo_id"], ["eixos.id"]),
        sa.ForeignKeyConstraint(["atribuido_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["atribuido_por_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["criado_por_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["recusado_por_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("gravidade IS NULL OR gravidade BETWEEN 1 AND 5", name="ck_demandas_gravidade"),
        sa.CheckConstraint("urgencia IS NULL OR urgencia BETWEEN 1 AND 5", name="ck_demandas_urgencia"),
        sa.CheckConstraint("tendencia IS NULL OR tendencia BETWEEN 1 AND 5", name="ck_demandas_tendencia"),
        sa.CheckConstraint("termino IS NULL OR inicio IS NULL OR termino >= inicio", name="ck_demandas_prazo"),
    )
    op.create_index("ix_demandas_eixo_id", "demandas", ["eixo_id"])
    op.create_index("ix_demandas_status", "demandas", ["status"])
    op.create_index("ix_demandas_atribuido_id", "demandas", ["atribuido_id"])
    op.create_index("ix_demandas_prioridade", "demandas", ["prioridade"])

    op.create_table(
        "demanda_apoio",
        sa.Column("demanda_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["demanda_id"], ["demandas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("demanda_id", "usuario_id"),
    )

    op.create_table(
        "historico_demanda",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("demanda_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("dados", sa.JSON(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["demanda_id"], ["demandas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_historico_demanda_demanda_id", "historico_demanda", ["demanda_id"])


def downgrade():
    op.drop_index("ix_historico_demanda_demanda_id", table_name="historico_demanda")
    op.drop_table("historico_demanda")
    op.drop_table("demanda_apoio")
    op.drop_index("ix_demandas_prioridade", table_name="demandas")
    op.drop_index("ix_demandas_atribuido_id", table_name="demandas")
    op.drop_index("ix_demandas_status", table_name="demandas")
    op.drop_index("ix_demandas_eixo_id", table_name="demandas")
    op.drop_table("demandas")
    op.drop_table("eixos")
    op.drop_index("ix_usuarios_email", table_name="usuarios")
    op.drop_table("usuarios")
