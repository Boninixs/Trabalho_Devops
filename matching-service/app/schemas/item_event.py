"""
Esse arquivo é reponsavel por definir os esquemas de eventos relacionados a itens  
que serão processados e publicados pelo serviço de matching.
"""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.item_projection import ExternalItemStatus, ItemClassification
from app.schemas.events import EventEnvelope


class ItemEventPayload(BaseModel):
    """"
    Esquema para representar o payload dos eventos relacionados a itens.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    classification: ItemClassification
    title: str
    description: str
    category: str
    color: str
    location_description: str
    approximate_date: date
    reporter_user_id: UUID
    status: ExternalItemStatus
    version: int
    created_at: datetime
    updated_at: datetime


class ItemCreatedEnvelope(EventEnvelope):
    """"
    Esquema para representar o envelope do evento de criação de item.
    """
    event_type: Literal["ItemCreated"]
    payload: ItemEventPayload


class ItemUpdatedEnvelope(EventEnvelope):
    """"
    Esquema para representar o envelope do evento de atualização de item.
    """
    event_type: Literal["ItemUpdated"]
    payload: ItemEventPayload
