"""
Este arquivo é responsável por definir os esquemas de eventos relacionados a match, 
que serão processados e publicados pelo serviço de matching.
"""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.match_suggestion import MatchStatus
from app.schemas.events import EventEnvelope


class MatchEventPayload(BaseModel):
    """
    Esquema para representar o payload dos eventos relacionados a match.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lost_item_id: UUID
    found_item_id: UUID
    score: int
    criteria_snapshot_json: dict[str, Any]
    status: MatchStatus
    decided_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class MatchSuggestedEnvelope(EventEnvelope):
    """
    Esquema para representar o envelope do evento de sugestão de match.
    """
    event_type: Literal["MatchSuggested"]
    payload: MatchEventPayload


class MatchAcceptedEnvelope(EventEnvelope):
    """"
    Esquema para representar o envelope do evento de aceitação de match.
    """
    event_type: Literal["MatchAccepted"]
    payload: MatchEventPayload


class MatchRejectedEnvelope(EventEnvelope):
    """"
    Esquema para representar o envelope do evento de rejeição de match.
    """
    event_type: Literal["MatchRejected"]
    payload: MatchEventPayload
