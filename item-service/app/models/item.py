import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Classification(str, enum.Enum):
    LOST = "LOST"
    FOUND = "FOUND"


class ItemStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    MATCHED = "MATCHED"
    IN_RECOVERY = "IN_RECOVERY"
    RECOVERED = "RECOVERED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"


class Item(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "items"

    classification: Mapped[Classification] = mapped_column(
        Enum(Classification, name="item_classification", native_enum=False),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    location_description: Mapped[str] = mapped_column(String(255), nullable=False)
    approximate_date: Mapped[date] = mapped_column(Date, nullable=False)
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus, name="item_status", native_enum=False),
        nullable=False,
        default=ItemStatus.AVAILABLE,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

