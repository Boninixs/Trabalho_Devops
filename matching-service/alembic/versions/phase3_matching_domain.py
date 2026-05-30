""""
Esse arquivo é responsável pela migração do Alembic cria as tabelas necessárias para o domínio de matching 
na fase 3 do projeto. 
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "phase3_matching_domain"
down_revision = "phase0_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """"
    Esta função é responsável por criar as tabelas item_projections e match_suggestions no banco de 
    dados e seus índices.
    args:        
        None
    returns:     
        None
    """
    classification_enum = sa.Enum(
        "LOST",
        "FOUND",
        name="item_classification",
        native_enum=False,
    )
    item_status_enum = sa.Enum(
        "AVAILABLE",
        "MATCHED",
        "IN_RECOVERY",
        "RECOVERED",
        "CANCELLED",
        "CLOSED",
        name="item_status",
        native_enum=False,
    )
    match_status_enum = sa.Enum(
        "SUGGESTED",
        "ACCEPTED",
        "REJECTED",
        "EXPIRED",
        name="match_status",
        native_enum=False,
    )
    classification_enum.create(op.get_bind(), checkfirst=True)
    item_status_enum.create(op.get_bind(), checkfirst=True)
    match_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "item_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("classification", classification_enum, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=100), nullable=False),
        sa.Column("location_description", sa.String(length=255), nullable=False),
        sa.Column("approximate_date", sa.Date(), nullable=False),
        sa.Column("reporter_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", item_status_enum, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_item_projections_category", "item_projections", ["category"], unique=False)
    op.create_index(
        "ix_item_projections_classification",
        "item_projections",
        ["classification"],
        unique=False,
    )
    op.create_index("ix_item_projections_status", "item_projections", ["status"], unique=False)

    op.create_table(
        "match_suggestions",
        sa.Column("lost_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("found_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("criteria_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", match_status_enum, nullable=False, server_default="SUGGESTED"),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.UniqueConstraint(
            "lost_item_id",
            "found_item_id",
            name="uq_match_suggestions_lost_found_pair",
        ),
    )
    op.create_index("ix_match_suggestions_lost_item_id", "match_suggestions", ["lost_item_id"], unique=False)
    op.create_index("ix_match_suggestions_found_item_id", "match_suggestions", ["found_item_id"], unique=False)
    op.create_index("ix_match_suggestions_status", "match_suggestions", ["status"], unique=False)


def downgrade() -> None:
    """"
    Esta função é responsável por remover as tabelas item_projections e match_suggestions do banco de dados,
    juntamente com os índices e tipos enumerados associados a essas tabelas.
    args:        
        None
    returns:     
        None
    """
    op.drop_index("ix_match_suggestions_status", table_name="match_suggestions")
    op.drop_index("ix_match_suggestions_found_item_id", table_name="match_suggestions")
    op.drop_index("ix_match_suggestions_lost_item_id", table_name="match_suggestions")
    op.drop_table("match_suggestions")
    op.drop_index("ix_item_projections_status", table_name="item_projections")
    op.drop_index("ix_item_projections_classification", table_name="item_projections")
    op.drop_index("ix_item_projections_category", table_name="item_projections")
    op.drop_table("item_projections")

    match_status_enum = sa.Enum(
        "SUGGESTED",
        "ACCEPTED",
        "REJECTED",
        "EXPIRED",
        name="match_status",
        native_enum=False,
    )
    item_status_enum = sa.Enum(
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
    match_status_enum.drop(op.get_bind(), checkfirst=True)
    item_status_enum.drop(op.get_bind(), checkfirst=True)
    classification_enum.drop(op.get_bind(), checkfirst=True)
