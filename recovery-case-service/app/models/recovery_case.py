import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from app.models.common import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RecoveryCaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


ACTIVE_RECOVERY_CASE_STATUSES = (
    RecoveryCaseStatus.OPEN,
    RecoveryCaseStatus.IN_PROGRESS,
)


class RecoveryCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recovery_cases"
    __table_args__ = (
        Index(
            "ux_recovery_cases_found_item_active",
            "found_item_id",
            unique=True,
            postgresql_where=expression.text(
                "status IN ('OPEN', 'IN_PROGRESS')",
            ),
        ),
    )

    match_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
    )
    lost_item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    found_item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    status: Mapped[RecoveryCaseStatus] = mapped_column(
        Enum(RecoveryCaseStatus, name="recovery_case_status", native_enum=False),
        nullable=False,
        default=RecoveryCaseStatus.OPEN,
        index=True,
    )
    opened_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
