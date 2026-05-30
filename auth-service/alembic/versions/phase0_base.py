"""
Esse arquivo é resposável pela criação das tabelas para a implementação do padrão Outbox.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "phase0_base"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """ 
    Cria as tabelas do Outbox, que armazena os eventos que serão publicados, e a tabela de Eventos 
    Processados , que registra os eventos que já foram processados.
    args:
        None
    return:
        None
    """
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("exchange_name", sa.String(length=255), nullable=False),
        sa.Column("routing_key", sa.String(length=255), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("publish_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outbox_events_aggregate_id",
        "outbox_events",
        ["aggregate_id"],
        unique=False,
    )
    op.create_index(
        "ix_outbox_events_event_type",
        "outbox_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_outbox_events_status",
        "outbox_events",
        ["status"],
        unique=False,
    )

    op.create_table(
        "processed_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_processed_events_aggregate_id",
        "processed_events",
        ["aggregate_id"],
        unique=False,
    )
    op.create_index(
        "ix_processed_events_event_type",
        "processed_events",
        ["event_type"],
        unique=False,
    )

def downgrade() -> None:
    """
    Reverte as mudanças que foram deitas no upgrade, retirando os indices criados e as tabelas do 
    Outbox e Eventos Processados.
    args:
        None
    return:
        None
    """
    op.drop_index("ix_processed_events_event_type", table_name="processed_events")
    op.drop_index("ix_processed_events_aggregate_id", table_name="processed_events")
    op.drop_table("processed_events")
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_index("ix_outbox_events_event_type", table_name="outbox_events")
    op.drop_index("ix_outbox_events_aggregate_id", table_name="outbox_events")
    op.drop_table("outbox_events")
