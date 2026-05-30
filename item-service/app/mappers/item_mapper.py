from app.models.item import Item
from app.models.item_status_history import ItemStatusHistory
from app.schemas.item import ItemResponse, ItemStatusHistoryResponse
from app.schemas.item_event import ItemEventPayload


def to_item_response(item: Item) -> ItemResponse:
    return ItemResponse.model_validate(item)


def to_item_history_response(history_entry: ItemStatusHistory) -> ItemStatusHistoryResponse:
    return ItemStatusHistoryResponse.model_validate(history_entry)


def to_item_event_payload(item: Item) -> ItemEventPayload:
    return ItemEventPayload.model_validate(item)

