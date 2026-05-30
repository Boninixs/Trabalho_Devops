import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import Base, UUIDPrimaryKeyMixin
from app.models.item import ItemStatus


class ItemStatusHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "item_status_history"

    item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[ItemStatus | None] = mapped_column(
        Enum(ItemStatus, name="item_status", native_enum=False),
        nullable=True,
    )
    to_status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus, name="item_status", native_enum=False),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

