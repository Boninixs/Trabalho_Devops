""""
Esse arquivo é responsável por fornecer funções para interagir com a tabela de OutboxEvent no banco de dados. 
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.outbox import OutboxEvent


def add_outbox_event(session: Session, outbox_event: OutboxEvent) -> OutboxEvent:
    """"
    Adiciona um novo evento à tabela de OutboxEvent.
    args:
        session: Sessão do banco de dados.
        outbox_event: Instância do OutboxEvent a ser adicionada.
    returns:
        OutboxEvent: A instância do OutboxEvent persistida no banco de dados.
    """
    session.add(outbox_event)
    return outbox_event


def list_pending_outbox_events(
    session: Session,
    limit: int = 100,
) -> list[OutboxEvent]:
    """"
    Lista os eventos pendentes na tabela de OutboxEvent, ordenados por data de ocorrência.
    Args:
        session (Session): A sessão do banco de dados.
        limit: O número máximo de eventos a serem retornados. 
    Returns:
        list[OutboxEvent]: Uma lista de eventos pendentes.
    """
    statement = (
        select(OutboxEvent)
        .where(OutboxEvent.status == "PENDING")
        .order_by(OutboxEvent.occurred_at)
        .limit(limit)
    )
    return list(session.scalars(statement))


def mark_outbox_event_published(session: Session, event_id: UUID) -> OutboxEvent | None:
    """"
    marca um evento como publicado na tabela de OutboxEvent, atualizando seu status para "PUBLISHED" e 
    incrementando o número de tentativas de publicação.
    args:
        session: Sessão do banco de dados.
        event_id: O ID do evento a ser marcado como publicado.
    returns:
        OutboxEvent | None: A instância do OutboxEvent atualizada, ou None se não.
    """
    outbox_event = session.get(OutboxEvent, event_id)
    if outbox_event is None:
        return None

    outbox_event.status = "PUBLISHED"
    outbox_event.publish_attempts += 1
    return outbox_event

