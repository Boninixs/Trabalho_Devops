from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.item import Classification, Item, ItemStatus
from app.schemas.item import ItemFilters


def add_item(session: Session, item: Item) -> Item:
    session.add(item)
    return item


def get_item_by_id(session: Session, item_id: UUID) -> Item | None:
    return session.get(Item, item_id)


def get_items_by_ids(session: Session, item_ids: list[UUID]) -> list[Item]:
    statement = select(Item).where(Item.id.in_(item_ids)).order_by(Item.created_at.asc())
    return list(session.scalars(statement))


def list_items(session: Session, filters: ItemFilters) -> list[Item]:
    statement: Select[tuple[Item]] = select(Item)

    if filters.classification is not None:
        statement = statement.where(Item.classification == filters.classification)
    if filters.category is not None:
        statement = statement.where(Item.category.ilike(f"%{filters.category}%"))
    if filters.color is not None:
        statement = statement.where(Item.color.ilike(f"%{filters.color}%"))
    if filters.location is not None:
        statement = statement.where(
            Item.location_description.ilike(f"%{filters.location}%"),
        )
    if filters.status is not None:
        statement = statement.where(Item.status == filters.status)
    if filters.reporter_user_id is not None:
        statement = statement.where(Item.reporter_user_id == filters.reporter_user_id)

    statement = statement.order_by(Item.created_at.desc())
    return list(session.scalars(statement))

