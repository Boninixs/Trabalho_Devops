""""
Esse arquivo é responsável por fornecer funções para interagir com a tabela de ProcessedEvent no banco de dados. 
"""
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.processed_event import ProcessedEvent


def is_event_processed(session: Session, event_id: UUID) -> bool:
    """"
    Verifica se um evento já foi processado, consultando a tabela de ProcessedEvent pelo ID do evento.
    args:
        session: Sessão do banco de dados.
        event_id: O ID do evento a ser verificado.
    returns:
        bool: True se o evento já foi processado, False caso não.
    """
    return session.get(ProcessedEvent, event_id) is not None


def add_processed_event(
    session: Session,
    processed_event: ProcessedEvent,
) -> ProcessedEvent:
    """"
    Adiciona um novo evento processado à tabela de ProcessedEvent.
    """
    session.add(processed_event)
    return processed_event

