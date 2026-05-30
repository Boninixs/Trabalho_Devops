from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item_status_history import ItemStatusHistory


def add_history_entry(
    session: Session,
    history_entry: ItemStatusHistory,
) -> ItemStatusHistory:
    session.add(history_entry)
    return history_entry


def list_history_for_item(session: Session, item_id: UUID) -> list[ItemStatusHistory]:
    statement = (
        select(ItemStatusHistory)
        .where(ItemStatusHistory.item_id == item_id)
        .order_by(ItemStatusHistory.occurred_at.asc())
    )
    return list(session.scalars(statement))

