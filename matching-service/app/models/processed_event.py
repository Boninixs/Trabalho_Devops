""""
Esse arquivo é responsável por definir o modelo de dados para os eventos processados.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import Base


class ProcessedEvent(Base):
    """"
    Modelo de dados para os eventos processados.
    """
    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

