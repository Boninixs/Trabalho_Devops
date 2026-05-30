from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.events import EventEnvelope


class MatchAcceptedPayload(BaseModel):
    id: UUID
    lost_item_id: UUID
    found_item_id: UUID
    score: int
    criteria_snapshot_json: dict[str, Any]
    status: str
    decided_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class MatchAcceptedEnvelope(EventEnvelope):
    event_type: Literal["MatchAccepted"]
    payload: MatchAcceptedPayload
