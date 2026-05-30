""""
Esse arquivo é responsável por gerenciar a fila de eventos a serem publicados no RabbitMQ. 
"""
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
    """"
    Enfileira um evento para publicação no RabbitMQ.
    args:        
        session: A sessão do banco de dados.
        envelope: O envelope do evento a ser enfileirado.
        routing_key: A chave de roteamento para o evento.
        exchange_name: O nome da exchange para o evento.
        headers: Cabeçalhos adicionais para o evento (opcional).
    returns:     
        O objeto OutboxEvent criado.
    """
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
    """"
    Enfileira uma mensagem de broker para publicação no RabbitMQ.
    args:        
        session: A sessão do banco de dados.
        message: A mensagem de broker a ser enfileirada.
    returns:     
        O objeto OutboxEvent criado.
    """
    return enqueue_event(
        session=session,
        envelope=message.envelope,
        routing_key=message.routing_key,
        exchange_name=message.exchange_name,
        headers=message.headers,
    )

