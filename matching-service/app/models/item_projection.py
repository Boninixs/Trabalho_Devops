"""
Esse arquivo é responsável por definir o modelo de dados para a projeção de itens.
"""
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import Base


class ItemClassification(str, enum.Enum):
    """"
    Enum para classificar os itens como perdidos ou encontrados.    
    """
    LOST = "LOST"
    FOUND = "FOUND"


class ExternalItemStatus(str, enum.Enum):
    """"
    Enum para representar o status dos itens na perspectiva externa.
    """
    AVAILABLE = "AVAILABLE"
    MATCHED = "MATCHED"
    IN_RECOVERY = "IN_RECOVERY"
    RECOVERED = "RECOVERED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"


class ItemProjection(Base):
    """"
    Modelo de dados para a projeção de itens, que é utilizado para armazenar as informações dos itens perdidos 
    e encontrados no serviço de matching.
    """
    __tablename__ = "item_projections"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    classification: Mapped[ItemClassification] = mapped_column(
        Enum(ItemClassification, name="item_classification", native_enum=False),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(100), nullable=False)
    location_description: Mapped[str] = mapped_column(String(255), nullable=False)
    approximate_date: Mapped[date] = mapped_column(Date, nullable=False)
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[ExternalItemStatus] = mapped_column(
        Enum(ExternalItemStatus, name="item_status", native_enum=False),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_event_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

