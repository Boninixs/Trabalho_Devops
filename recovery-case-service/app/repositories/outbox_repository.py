from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.outbox import OutboxEvent


def add_outbox_event(session: Session, outbox_event: OutboxEvent) -> OutboxEvent:
    session.add(outbox_event)
    return outbox_event


def list_pending_outbox_events(
    session: Session,
    *,
    limit: int = 100,
) -> list[OutboxEvent]:
    statement = (
        select(OutboxEvent)
        .where(or_(OutboxEvent.status == "PENDING", OutboxEvent.status == "FAILED"))
        .where(OutboxEvent.available_at <= datetime.now(timezone.utc))
        .order_by(OutboxEvent.occurred_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list(session.scalars(statement))


def mark_outbox_event_published(
    session: Session,
    event_id: UUID,
    *,
    published_at: datetime,
) -> OutboxEvent | None:
    outbox_event = session.get(OutboxEvent, event_id)
    if outbox_event is None:
        return None

    outbox_event.status = "PUBLISHED"
    outbox_event.published_at = published_at
    outbox_event.last_error = None
    outbox_event.publish_attempts += 1
    return outbox_event


def mark_outbox_event_failed(
    session: Session,
    event_id: UUID,
    *,
    last_error: str,
    next_available_at: datetime,
) -> OutboxEvent | None:
    outbox_event = session.get(OutboxEvent, event_id)
    if outbox_event is None:
        return None

    outbox_event.status = "FAILED"
    outbox_event.last_error = last_error
    outbox_event.available_at = next_available_at
    outbox_event.publish_attempts += 1
    return outbox_event


def mark_outbox_event_exhausted(
    session: Session,
    event_id: UUID,
    *,
    last_error: str,
) -> OutboxEvent | None:
    outbox_event = session.get(OutboxEvent, event_id)
    if outbox_event is None:
        return None

    outbox_event.status = "EXHAUSTED"
    outbox_event.last_error = last_error
    outbox_event.publish_attempts += 1
    return outbox_event
