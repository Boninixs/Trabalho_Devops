"""
O arquivo representa o repositório para a entidade ProcessedEvent.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.processed_event import ProcessedEvent


def is_event_processed(session: Session, event_id: UUID) -> bool:
    """
    Verifica se um evento com o ID fornecido já foi processado.
    args:     
        session: A sessão do banco de dados.
        event_id: O ID do evento a ser verificado.  
    returns:     
        True se o evento já tiver sido processado, False caso contrário.
    """
    return session.get(ProcessedEvent, event_id) is not None


def add_processed_event(
    session: Session,
    processed_event: ProcessedEvent,
) -> ProcessedEvent:
    """
    Adiciona um novo evento processado ao banco de dados.
    args:
        session: A sessão do banco de dados.
        processed_event: O objeto ProcessedEvent a ser adicionado.
    returns:
        O objeto ProcessedEvent adicionado.
    """
    session.add(processed_event)
    return processed_event

