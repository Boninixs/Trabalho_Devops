from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import InvalidItemTransitionError
from app.models.item import Classification, Item, ItemStatus
from app.models.item_status_history import ItemStatusHistory
from app.models.outbox import OutboxEvent
from app.schemas.item import ItemCreateRequest, ItemStatusUpdateRequest
from app.services.item_service import create_item, update_item_status


class FakeSession:
    def __init__(self):
        self.added_objects = []
        self.committed = False
        self.flushed = False
        self.refreshed = []

    def add(self, obj):
        self.added_objects.append(obj)

    def flush(self):
        self.flushed = True

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed.append(obj)


def test_create_item_sets_initial_status_and_generates_history_and_outbox() -> None:
    session = FakeSession()
    payload = ItemCreateRequest(
        classification=Classification.LOST,
        title="Carteira preta",
        description="Carteira perdida na biblioteca",
        category="Carteira",
        color="Preta",
        location_description="Biblioteca",
        approximate_date=date(2026, 4, 10),
        reporter_user_id=uuid4(),
    )

    item = create_item(session, payload)

    assert item.status == ItemStatus.AVAILABLE
    assert item.version == 1
    assert any(isinstance(obj, ItemStatusHistory) for obj in session.added_objects)
    outbox_events = [obj for obj in session.added_objects if isinstance(obj, OutboxEvent)]
    assert len(outbox_events) == 1
    assert outbox_events[0].event_type == "ItemCreated"
    assert outbox_events[0].aggregate_version == 1
    assert session.committed is True


def test_update_item_status_allows_available_to_matched_and_generates_history(monkeypatch) -> None:
    session = FakeSession()
    now = datetime.now(timezone.utc)
    item = Item(
        id=uuid4(),
        classification=Classification.FOUND,
        title="Chaveiro azul",
        description="Chaveiro encontrado no pátio",
        category="Chaves",
        color="Azul",
        location_description="Pátio central",
        approximate_date=date(2026, 4, 10),
        reporter_user_id=uuid4(),
        status=ItemStatus.AVAILABLE,
        version=1,
        created_at=now,
        updated_at=now,
    )

    monkeypatch.setattr("app.services.item_service.get_item_by_id", lambda _session, _item_id: item)

    updated_item = update_item_status(
        session,
        item.id,
        ItemStatusUpdateRequest(
            status=ItemStatus.MATCHED,
            reason="Match confirmado manualmente",
            actor_user_id=uuid4(),
        ),
    )

    assert updated_item.status == ItemStatus.MATCHED
    assert updated_item.version == 2
    assert any(isinstance(obj, ItemStatusHistory) for obj in session.added_objects)
    assert any(
        isinstance(obj, OutboxEvent) and obj.event_type == "ItemUpdated"
        for obj in session.added_objects
    )


def test_update_item_status_blocks_invalid_transition_from_cancelled(monkeypatch) -> None:
    session = FakeSession()
    now = datetime.now(timezone.utc)
    item = Item(
        id=uuid4(),
        classification=Classification.LOST,
        title="Notebook",
        description="Notebook cancelado",
        category="Eletrônico",
        color="Cinza",
        location_description="Sala 2",
        approximate_date=date(2026, 4, 10),
        reporter_user_id=uuid4(),
        status=ItemStatus.CANCELLED,
        version=2,
        created_at=now,
        updated_at=now,
    )

    monkeypatch.setattr("app.services.item_service.get_item_by_id", lambda _session, _item_id: item)

    with pytest.raises(
        InvalidItemTransitionError,
        match="Itens CANCELLED ou CLOSED não podem voltar ao fluxo de matching",
    ):
        update_item_status(
            session,
            item.id,
            ItemStatusUpdateRequest(
                status=ItemStatus.MATCHED,
                reason="Tentativa inválida",
                actor_user_id=uuid4(),
            ),
        )
