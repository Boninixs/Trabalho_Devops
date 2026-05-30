from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    aggregate_id: UUID
    aggregate_version: int = Field(default=0, ge=0)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: UUID
    causation_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class BrokerMessage(BaseModel):
    envelope: EventEnvelope
    routing_key: str
    exchange_name: str = "domain.events"
    headers: dict[str, Any] = Field(default_factory=dict)

