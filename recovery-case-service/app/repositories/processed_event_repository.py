from uuid import UUID

from sqlalchemy.orm import Session

from app.models.processed_event import ProcessedEvent


def is_event_processed(session: Session, event_id: UUID) -> bool:
    return session.get(ProcessedEvent, event_id) is not None


def add_processed_event(
    session: Session,
    processed_event: ProcessedEvent,
) -> ProcessedEvent:
    session.add(processed_event)
    return processed_event

