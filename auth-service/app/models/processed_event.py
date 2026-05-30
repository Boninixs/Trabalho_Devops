""""
Esse arquivo é responsável por definir o modelo de dados para a tabela processed_events, que é 
usada para rastrear quais eventos já foram processados para evitar processamento duplicado.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import Base


class ProcessedEvent(Base):
    """
    Entidade que representa um evento já processado.
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

