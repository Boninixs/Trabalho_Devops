from sqlalchemy.orm import Session

from app.models.outbox import OutboxEvent
from app.repositories.outbox_repository import add_outbox_event
from app.schemas.events import BrokerMessage, EventEnvelope


def enqueue_event(
    session: Session,
    envelope: EventEnvelope,
    routing_key: str,
    exchange_name: str,
    headers: dict | None = None,
) -> OutboxEvent:
    outbox_event = OutboxEvent(
        id=envelope.event_id,
        event_type=envelope.event_type,
        aggregate_id=envelope.aggregate_id,
        aggregate_version=envelope.aggregate_version,
        exchange_name=exchange_name,
        routing_key=routing_key,
        correlation_id=envelope.correlation_id,
        causation_id=envelope.causation_id,
        payload=envelope.payload,
        headers=headers or {},
        occurred_at=envelope.occurred_at,
        status="PENDING",
        publish_attempts=0,
    )
    return add_outbox_event(session, outbox_event)


def enqueue_broker_message(session: Session, message: BrokerMessage) -> OutboxEvent:
    return enqueue_event(
        session=session,
        envelope=message.envelope,
        routing_key=message.routing_key,
        exchange_name=message.exchange_name,
        headers=message.headers,
    )

