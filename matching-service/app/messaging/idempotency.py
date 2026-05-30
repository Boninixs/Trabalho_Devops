""""
Esse arquivo é responsável por garantir a idempotência no processamento de eventos. 
"""
from sqlalchemy.orm import Session

from app.models.processed_event import ProcessedEvent
from app.repositories.processed_event_repository import (
    add_processed_event,
    is_event_processed,
)
from app.schemas.events import EventEnvelope


def has_been_processed(session: Session, envelope: EventEnvelope) -> bool:
    """"
    Verifica se um evento já foi processado anteriormente.
    args:        
        session: A sessão do banco de dados.
        envelope: O envelope do evento a ser verificado.
    returns:     
        True se o evento já foi processado ou False se não.
    """
    return is_event_processed(session, envelope.event_id)


def register_processed_event(
    session: Session,
    envelope: EventEnvelope,
) -> ProcessedEvent:
    """"
    Registra um evento como processado.
    args:        
        session: A sessão do banco de dados.
        envelope: O envelope do evento a ser registrado.
    returns:     
        O objeto ProcessedEvent criado.
    """
    processed_event = ProcessedEvent(
        event_id=envelope.event_id,
        event_type=envelope.event_type,
        aggregate_id=envelope.aggregate_id,
    )
    return add_processed_event(session, processed_event)

