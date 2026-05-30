from sqlalchemy.orm import Session

from app.models.processed_event import ProcessedEvent
from app.repositories.processed_event_repository import (
    add_processed_event,
    is_event_processed,
)
from app.schemas.events import EventEnvelope


def has_been_processed(session: Session, envelope: EventEnvelope) -> bool:
    return is_event_processed(session, envelope.event_id)


def register_processed_event(
    session: Session,
    envelope: EventEnvelope,
) -> ProcessedEvent:
    processed_event = ProcessedEvent(
        event_id=envelope.event_id,
        event_type=envelope.event_type,
        aggregate_id=envelope.aggregate_id,
    )
    return add_processed_event(session, processed_event)

