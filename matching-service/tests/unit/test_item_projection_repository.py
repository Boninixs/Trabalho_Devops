from datetime import date, datetime, timezone
from uuid import uuid4

from app.models.item_projection import ExternalItemStatus, ItemClassification, ItemProjection
from app.repositories.item_projection_repository import add_item_projection


class FakeSession:
    def __init__(self) -> None:
        self.added = []

    def add(self, obj) -> None:
        self.added.append(obj)


def build_projection() -> ItemProjection:
    now = datetime.now(timezone.utc)
    return ItemProjection(
        id=uuid4(),
        classification=ItemClassification.LOST,
        title="Mochila azul",
        description="Mochila azul com caderno",
        category="Mochila",
        color="Azul",
        location_description="Biblioteca central",
        approximate_date=date(2026, 4, 10),
        reporter_user_id=uuid4(),
        status=ExternalItemStatus.AVAILABLE,
        version=1,
        created_at=now,
        updated_at=now,
        last_event_id=uuid4(),
        last_seen_at=now,
    )


def test_add_item_projection_adds_projection_to_session() -> None:
    session = FakeSession()
    projection = build_projection()

    result = add_item_projection(session, projection)

    assert result is projection
    assert session.added == [projection]
