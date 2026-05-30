from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.models.item import Classification, Item, ItemStatus
from app.models.outbox import OutboxEvent
from app.schemas.item import ItemCreateRequest, ItemUpdateRequest
from app.schemas.item_event import ItemCreatedEnvelope, ItemUpdatedEnvelope
from app.services.item_service import create_item, update_item


class FakeSession:
    def __init__(self):
        self.added_objects = []

    def add(self, obj):
        self.added_objects.append(obj)

    def flush(self):
        pass

    def commit(self):
        pass

    def refresh(self, _obj):
        pass


@pytest.mark.contract
def test_item_created_contract() -> None:
    session = FakeSession()
    item = create_item(
        session,
        ItemCreateRequest(
            classification=Classification.LOST,
            title="Documento",
            description="Documento perdido",
            category="Documento",
            color="Branco",
            location_description="Recepção",
            approximate_date=date(2026, 4, 10),
            reporter_user_id=uuid4(),
        ),
    )

    outbox_event = next(obj for obj in session.added_objects if isinstance(obj, OutboxEvent))
    envelope = ItemCreatedEnvelope.model_validate(
        {
            "event_id": outbox_event.id,
            "event_type": outbox_event.event_type,
            "aggregate_id": outbox_event.aggregate_id,
            "aggregate_version": outbox_event.aggregate_version,
            "occurred_at": outbox_event.occurred_at,
            "correlation_id": outbox_event.correlation_id,
            "causation_id": outbox_event.causation_id,
            "payload": outbox_event.payload,
        },
    )

    assert envelope.event_type == "ItemCreated"
    assert envelope.aggregate_id == item.id
    assert envelope.payload.status == ItemStatus.AVAILABLE


@pytest.mark.contract
def test_item_updated_contract(monkeypatch) -> None:
    session = FakeSession()
    now = datetime.now(timezone.utc)
    item = Item(
        id=uuid4(),
        classification=Classification.FOUND,
        title="Mochila",
        description="Mochila azul encontrada",
        category="Mochila",
        color="Azul",
        location_description="Bloco B",
        approximate_date=date(2026, 4, 10),
        reporter_user_id=uuid4(),
        status=ItemStatus.AVAILABLE,
        version=1,
        created_at=now,
        updated_at=now,
    )

    monkeypatch.setattr("app.services.item_service.get_item_by_id", lambda _session, _item_id: item)

    update_item(
        session,
        item.id,
        ItemUpdateRequest(title="Mochila azul"),
    )

    outbox_event = next(obj for obj in session.added_objects if isinstance(obj, OutboxEvent))
    envelope = ItemUpdatedEnvelope.model_validate(
        {
            "event_id": outbox_event.id,
            "event_type": outbox_event.event_type,
            "aggregate_id": outbox_event.aggregate_id,
            "aggregate_version": outbox_event.aggregate_version,
            "occurred_at": outbox_event.occurred_at,
            "correlation_id": outbox_event.correlation_id,
            "causation_id": outbox_event.causation_id,
            "payload": outbox_event.payload,
        },
    )

    assert envelope.event_type == "ItemUpdated"
    assert envelope.payload.title == "Mochila azul"
    assert envelope.aggregate_version == 2
