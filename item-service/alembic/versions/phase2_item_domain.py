"""phase2 item domain

Revision ID: phase2_item_domain
Revises: phase0_base
Create Date: 2026-04-14 00:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "phase2_item_domain"
down_revision = "phase0_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    classification_enum = sa.Enum(
        "LOST",
        "FOUND",
        name="item_classification",
        native_enum=False,
    )
    status_enum = sa.Enum(
        "AVAILABLE",
        "MATCHED",
        "IN_RECOVERY",
        "RECOVERED",
        "CANCELLED",
        "CLOSED",
        name="item_status",
        native_enum=False,
    )
    classification_enum.create(op.get_bind(), checkfirst=True)
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "items",
        sa.Column("classification", classification_enum, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=100), nullable=False),
        sa.Column("location_description", sa.String(length=255), nullable=False),
        sa.Column("approximate_date", sa.Date(), nullable=False),
        sa.Column("reporter_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="AVAILABLE"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
    )
    op.create_index("ix_items_category", "items", ["category"], unique=False)
    op.create_index("ix_items_classification", "items", ["classification"], unique=False)
    op.create_index("ix_items_color", "items", ["color"], unique=False)
    op.create_index("ix_items_reporter_user_id", "items", ["reporter_user_id"], unique=False)
    op.create_index("ix_items_status", "items", ["status"], unique=False)

    op.create_table(
        "item_status_history",
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", status_enum, nullable=True),
        sa.Column("to_status", status_enum, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_item_status_history_item_id", "item_status_history", ["item_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_item_status_history_item_id", table_name="item_status_history")
    op.drop_table("item_status_history")
    op.drop_index("ix_items_status", table_name="items")
    op.drop_index("ix_items_reporter_user_id", table_name="items")
    op.drop_index("ix_items_color", table_name="items")
    op.drop_index("ix_items_classification", table_name="items")
    op.drop_index("ix_items_category", table_name="items")
    op.drop_table("items")

    status_enum = sa.Enum(
        "AVAILABLE",
        "MATCHED",
        "IN_RECOVERY",
        "RECOVERED",
        "CANCELLED",
        "CLOSED",
        name="item_status",
        native_enum=False,
    )
    classification_enum = sa.Enum(
        "LOST",
        "FOUND",
        name="item_classification",
        native_enum=False,
    )
    status_enum.drop(op.get_bind(), checkfirst=True)
    classification_enum.drop(op.get_bind(), checkfirst=True)
