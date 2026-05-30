from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    InvalidItemTransitionError,
    InvalidItemUpdateError,
    ItemNotFoundError,
)
from app.mappers.item_mapper import to_item_event_payload
from app.messaging.outbox import enqueue_broker_message
from app.messaging.topology import ROUTING_KEYS
from app.models.item import Classification, Item, ItemStatus
from app.models.item_status_history import ItemStatusHistory
from app.repositories.item_repository import (
    add_item,
    get_item_by_id,
    get_items_by_ids,
    list_items as list_items_repository,
)
from app.repositories.item_status_history_repository import (
    add_history_entry,
    list_history_for_item,
)
from app.schemas.events import BrokerMessage, EventEnvelope
from app.schemas.item import (
    ItemCreateRequest,
    ItemFilters,
    ItemStatusUpdateRequest,
    ItemUpdateRequest,
    RecoveryCancelRequest,
    RecoveryCompleteRequest,
    RecoveryOpenRequest,
)

TERMINAL_STATUSES = {ItemStatus.CANCELLED, ItemStatus.CLOSED}
PUBLIC_TRANSITIONS = {
    ItemStatus.AVAILABLE: {ItemStatus.MATCHED, ItemStatus.CANCELLED, ItemStatus.CLOSED},
    ItemStatus.MATCHED: {ItemStatus.AVAILABLE, ItemStatus.CANCELLED, ItemStatus.CLOSED},
    ItemStatus.IN_RECOVERY: set(),
    ItemStatus.RECOVERED: {ItemStatus.CLOSED},
    ItemStatus.CANCELLED: set(),
    ItemStatus.CLOSED: set(),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_item_created_reason() -> str:
    return "Item created"


def get_item_or_raise(session: Session, item_id: UUID) -> Item:
    item = get_item_by_id(session, item_id)
    if item is None:
        raise ItemNotFoundError(f"Item {item_id} não encontrado")
    return item


def list_items(session: Session, filters: ItemFilters) -> list[Item]:
    return list_items_repository(session, filters)


def list_item_history(session: Session, item_id: UUID) -> list[ItemStatusHistory]:
    get_item_or_raise(session, item_id)
    return list_history_for_item(session, item_id)


def create_item(session: Session, payload: ItemCreateRequest) -> Item:
    now = utc_now()
    item = Item(
        id=uuid4(),
        classification=payload.classification,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        color=payload.color,
        location_description=payload.location_description,
        approximate_date=payload.approximate_date,
        reporter_user_id=payload.reporter_user_id,
        status=ItemStatus.AVAILABLE,
        version=1,
        created_at=now,
        updated_at=now,
    )
    add_item(session, item)
    session.flush()

    record_status_history(
        session=session,
        item=item,
        from_status=None,
        to_status=item.status,
        reason=build_item_created_reason(),
        actor_user_id=item.reporter_user_id,
        occurred_at=now,
    )
    record_item_event(session, item, event_type="ItemCreated")
    session.commit()
    session.refresh(item)
    return item


def retrieve_item(session: Session, item_id: UUID) -> Item:
    return get_item_or_raise(session, item_id)


def update_item(session: Session, item_id: UUID, payload: ItemUpdateRequest) -> Item:
    item = get_item_or_raise(session, item_id)
    changes = payload.model_dump(exclude_none=True)

    if not changes:
        raise InvalidItemUpdateError("Nenhum campo informado para atualização")

    has_effective_change = False
    for field_name, field_value in changes.items():
        if getattr(item, field_name) != field_value:
            setattr(item, field_name, field_value)
            has_effective_change = True

    if not has_effective_change:
        raise InvalidItemUpdateError("Nenhuma alteração efetiva foi informada")

    item.version += 1
    item.updated_at = utc_now()
    session.flush()
    record_item_event(session, item, event_type="ItemUpdated")
    session.commit()
    session.refresh(item)
    return item


def update_item_status(
    session: Session,
    item_id: UUID,
    payload: ItemStatusUpdateRequest,
) -> Item:
    item = get_item_or_raise(session, item_id)

    if payload.status in {ItemStatus.IN_RECOVERY, ItemStatus.RECOVERED}:
        raise InvalidItemTransitionError(
            "Status solicitado é reservado para o fluxo interno de recovery",
        )

    apply_status_transition(
        session=session,
        item=item,
        target_status=payload.status,
        reason=payload.reason,
        actor_user_id=payload.actor_user_id,
        transition_mode="public",
    )
    session.commit()
    session.refresh(item)
    return item


def open_recovery(session: Session, payload: RecoveryOpenRequest) -> list[Item]:
    items = get_items_or_raise(session, payload.item_ids)
    reason = payload.reason or "Recovery case opened"

    for item in items:
        apply_status_transition(
            session=session,
            item=item,
            target_status=ItemStatus.IN_RECOVERY,
            reason=reason,
            actor_user_id=payload.actor_user_id,
            transition_mode="internal_open",
        )

    session.commit()
    return items


def cancel_recovery(session: Session, payload: RecoveryCancelRequest) -> list[Item]:
    items = get_items_or_raise(session, payload.item_ids)
    reason = payload.reason or "Recovery case cancelled"

    for item in items:
        apply_status_transition(
            session=session,
            item=item,
            target_status=payload.target_status,
            reason=reason,
            actor_user_id=payload.actor_user_id,
            transition_mode="internal_cancel",
        )

    session.commit()
    return items


def complete_recovery(session: Session, payload: RecoveryCompleteRequest) -> list[Item]:
    items = get_items_or_raise(session, payload.item_ids)
    reason = payload.reason or "Recovery case completed"

    for item in items:
        apply_status_transition(
            session=session,
            item=item,
            target_status=ItemStatus.RECOVERED,
            reason=reason,
            actor_user_id=payload.actor_user_id,
            transition_mode="internal_complete",
        )

    session.commit()
    return items


def get_items_or_raise(session: Session, item_ids: list[UUID]) -> list[Item]:
    unique_item_ids = list(dict.fromkeys(item_ids))
    items = get_items_by_ids(session, unique_item_ids)
    item_by_id = {item.id: item for item in items}
    missing_ids = [str(item_id) for item_id in unique_item_ids if item_id not in item_by_id]
    if missing_ids:
        raise ItemNotFoundError(f"Itens não encontrados: {', '.join(missing_ids)}")

    return [item_by_id[item_id] for item_id in unique_item_ids]


def apply_status_transition(
    *,
    session: Session,
    item: Item,
    target_status: ItemStatus,
    reason: str,
    actor_user_id: UUID | None,
    transition_mode: str,
) -> None:
    current_status = item.status
    if current_status == target_status:
        raise InvalidItemTransitionError("Status informado é igual ao status atual")

    validate_transition(
        current_status=current_status,
        target_status=target_status,
        transition_mode=transition_mode,
    )

    item.status = target_status
    item.version += 1
    item.updated_at = utc_now()
    session.flush()

    record_status_history(
        session=session,
        item=item,
        from_status=current_status,
        to_status=target_status,
        reason=reason,
        actor_user_id=actor_user_id,
        occurred_at=item.updated_at,
    )
    record_item_event(session, item, event_type="ItemUpdated")


def validate_transition(
    *,
    current_status: ItemStatus,
    target_status: ItemStatus,
    transition_mode: str,
) -> None:
    if current_status in TERMINAL_STATUSES:
        raise InvalidItemTransitionError(
            "Itens CANCELLED ou CLOSED não podem voltar ao fluxo de matching",
        )

    if transition_mode == "public":
        allowed_statuses = PUBLIC_TRANSITIONS[current_status]
        if target_status not in allowed_statuses:
            raise InvalidItemTransitionError(
                f"Transição pública de {current_status.value} para {target_status.value} não é permitida",
            )
        return

    if transition_mode == "internal_open":
        if current_status not in {ItemStatus.AVAILABLE, ItemStatus.MATCHED}:
            raise InvalidItemTransitionError(
                "Abertura de recovery só é permitida para itens AVAILABLE ou MATCHED",
            )
        if target_status != ItemStatus.IN_RECOVERY:
            raise InvalidItemTransitionError("Abertura de recovery deve mover o item para IN_RECOVERY")
        return

    if transition_mode == "internal_cancel":
        if current_status != ItemStatus.IN_RECOVERY:
            raise InvalidItemTransitionError(
                "Cancelamento de recovery só é permitido para itens IN_RECOVERY",
            )
        if target_status not in {ItemStatus.AVAILABLE, ItemStatus.MATCHED}:
            raise InvalidItemTransitionError(
                "Cancelamento de recovery deve restaurar o item para AVAILABLE ou MATCHED",
            )
        return

    if transition_mode == "internal_complete":
        if current_status != ItemStatus.IN_RECOVERY:
            raise InvalidItemTransitionError(
                "Conclusão de recovery só é permitida para itens IN_RECOVERY",
            )
        if target_status != ItemStatus.RECOVERED:
            raise InvalidItemTransitionError("Conclusão de recovery deve marcar o item como RECOVERED")
        return

    raise InvalidItemTransitionError("Modo de transição desconhecido")


def record_status_history(
    *,
    session: Session,
    item: Item,
    from_status: ItemStatus | None,
    to_status: ItemStatus,
    reason: str,
    actor_user_id: UUID | None,
    occurred_at: datetime,
) -> ItemStatusHistory:
    history_entry = ItemStatusHistory(
        item_id=item.id,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        actor_user_id=actor_user_id,
        occurred_at=occurred_at,
    )
    return add_history_entry(session, history_entry)


def record_item_event(session: Session, item: Item, *, event_type: str) -> None:
    if event_type not in {"ItemCreated", "ItemUpdated"}:
        raise InvalidItemUpdateError(f"Evento {event_type} não suportado pelo item-service")

    settings = get_settings()
    routing_key = (
        ROUTING_KEYS["item_created"] if event_type == "ItemCreated" else ROUTING_KEYS["item_updated"]
    )
    payload = to_item_event_payload(item)
    correlation_id = uuid4()

    message = BrokerMessage(
        envelope=EventEnvelope(
            event_type=event_type,
            aggregate_id=item.id,
            aggregate_version=item.version,
            correlation_id=correlation_id,
            causation_id=None,
            payload=payload.model_dump(mode="json"),
        ),
        routing_key=routing_key,
        exchange_name=settings.rabbitmq_events_exchange,
    )
    enqueue_broker_message(session, message)

