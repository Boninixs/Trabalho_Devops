"""
Esse arquivo é responsável pelos serviços relacionados ao controle de eventos processados.
"""
from sqlalchemy.orm import Session

from app.models.processed_event import ProcessedEvent
from app.repositories.processed_event_repository import (
    add_processed_event,
    is_event_processed,
)
from app.schemas.events import EventEnvelope


def has_been_processed(session: Session, envelope: EventEnvelope) -> bool:
    """
    Verifica se um evento já foi processado.
    Args:
        session: Sessão do banco de dados.
        envelope: Envelope do evento recebido.
    Returns:
        True se o evento já foi processado, False caso não tenha sido.
    """
    return is_event_processed(session, envelope.event_id)


def register_processed_event(
    session: Session,
    envelope: EventEnvelope,
) -> ProcessedEvent:
    """
    Registra um evento como processado.
    Args:
        session: Sessão do banco de dados.
        envelope: Envelope do evento recebido.
    Returns:
        Instância do evento processado persistido.
    """
    processed_event = ProcessedEvent(
        event_id=envelope.event_id,
        event_type=envelope.event_type,
        aggregate_id=envelope.aggregate_id,
    )
    return add_processed_event(session, processed_event)

