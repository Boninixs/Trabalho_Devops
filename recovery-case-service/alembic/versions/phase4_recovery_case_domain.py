"""phase4 recovery case domain

Revision ID: phase4_recovery_case_domain
Revises: phase0_base
Create Date: 2026-04-14 00:00:01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "phase4_recovery_case_domain"
down_revision = "phase0_base"
branch_labels = None
depends_on = None


recovery_case_status_enum = sa.Enum(
    "OPEN",
    "IN_PROGRESS",
    "CANCELLED",
    "COMPLETED",
    name="recovery_case_status",
    native_enum=False,
)
saga_step_status_enum = sa.Enum(
    "STARTED",
    "SUCCEEDED",
    "FAILED",
    name="saga_step_status",
    native_enum=False,
)


def upgrade() -> None:
    recovery_case_status_enum.create(op.get_bind(), checkfirst=True)
    saga_step_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "recovery_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lost_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("found_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", recovery_case_status_enum, nullable=False),
        sa.Column("opened_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", name="uq_recovery_cases_match_id"),
    )
    op.create_index("ix_recovery_cases_match_id", "recovery_cases", ["match_id"], unique=True)
    op.create_index("ix_recovery_cases_lost_item_id", "recovery_cases", ["lost_item_id"], unique=False)
    op.create_index("ix_recovery_cases_found_item_id", "recovery_cases", ["found_item_id"], unique=False)
    op.create_index("ix_recovery_cases_status", "recovery_cases", ["status"], unique=False)
    op.create_index(
        "ix_recovery_cases_opened_by_user_id",
        "recovery_cases",
        ["opened_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ux_recovery_cases_found_item_active",
        "recovery_cases",
        ["found_item_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('OPEN', 'IN_PROGRESS')"),
    )

    op.create_table(
        "case_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_events_case_id", "case_events", ["case_id"], unique=False)
    op.create_index("ix_case_events_event_type", "case_events", ["event_type"], unique=False)
    op.create_index("ix_case_events_occurred_at", "case_events", ["occurred_at"], unique=False)

    op.create_table(
        "saga_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_name", sa.String(length=128), nullable=False),
        sa.Column("step_status", saga_step_status_enum, nullable=False),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saga_steps_case_id", "saga_steps", ["case_id"], unique=False)
    op.create_index("ix_saga_steps_step_name", "saga_steps", ["step_name"], unique=False)
    op.create_index("ix_saga_steps_step_status", "saga_steps", ["step_status"], unique=False)
    op.create_index("ix_saga_steps_occurred_at", "saga_steps", ["occurred_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_saga_steps_occurred_at", table_name="saga_steps")
    op.drop_index("ix_saga_steps_step_status", table_name="saga_steps")
    op.drop_index("ix_saga_steps_step_name", table_name="saga_steps")
    op.drop_index("ix_saga_steps_case_id", table_name="saga_steps")
    op.drop_table("saga_steps")

    op.drop_index("ix_case_events_occurred_at", table_name="case_events")
    op.drop_index("ix_case_events_event_type", table_name="case_events")
    op.drop_index("ix_case_events_case_id", table_name="case_events")
    op.drop_table("case_events")

    op.drop_index("ux_recovery_cases_found_item_active", table_name="recovery_cases")
    op.drop_index("ix_recovery_cases_opened_by_user_id", table_name="recovery_cases")
    op.drop_index("ix_recovery_cases_status", table_name="recovery_cases")
    op.drop_index("ix_recovery_cases_found_item_id", table_name="recovery_cases")
    op.drop_index("ix_recovery_cases_lost_item_id", table_name="recovery_cases")
    op.drop_index("ix_recovery_cases_match_id", table_name="recovery_cases")
    op.drop_table("recovery_cases")

    saga_step_status_enum.drop(op.get_bind(), checkfirst=True)
    recovery_case_status_enum.drop(op.get_bind(), checkfirst=True)
