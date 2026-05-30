"""
Esse arquivo representa o repositório para a entidade OutboxEvent, que é responsável por armazenar 
eventos que precisam ser publicados.
"""
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
    """
    Retorna uma lista de eventos pendentes ou com falha que estão disponíveis para publicação.
    args:
        session: A sessão do banco de dados.
        limit: O número máximo de eventos a serem retornados.
    returns:
        Uma lista de objetos OutboxEvent que estão prontos para serem publicados.
    """
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
    """
    Marca um evento como publicado, atualizando seu status, data de publicação e resetando o erro.
    args:        
        session: A sessão do banco de dados.
        event_id: O ID do evento a ser atualizado.
        published_at: A data e hora em que o evento foi publicado.
    returns:        
        O objeto OutboxEvent atualizado ou None se o evento não tiver.
    """
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
    """
    Marca um evento como falhado, atualizando seu status, o erro ocorrido e a próxima data disponível para tentativa.
    args:
        session: A sessão do banco de dados.
        event_id: O ID do evento a ser atualizado.
        last_error: A descrição do erro ocorrido durante a tentativa de publicação.
        next_available_at: A data e hora em que o evento estará disponível para a próxima tentativa.
    returns:
        O objeto OutboxEvent atualizado ou None se o evento não tiver.
    """
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
    """
    Marca um evento como esgotado, indicando que ele atingiu o número máximo de tentativas de publicação.
    args:
        session: A sessão do banco de dados.
        event_id: O ID do evento a ser atualizado.
        last_error: A descrição do erro ocorrido durante a última tentativa de publicação.
    returns:
        O objeto OutboxEvent atualizado ou None se o evento não tiver.
    """
    outbox_event = session.get(OutboxEvent, event_id)
    if outbox_event is None:
        return None

    outbox_event.status = "EXHAUSTED"
    outbox_event.last_error = last_error
    outbox_event.publish_attempts += 1
    return outbox_event
