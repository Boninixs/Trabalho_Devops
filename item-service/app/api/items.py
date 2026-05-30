from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.exceptions import (
    InvalidItemTransitionError,
    InvalidItemUpdateError,
    ItemNotFoundError,
)
from app.db.session import get_db
from app.mappers.item_mapper import to_item_history_response, to_item_response
from app.models.item import Classification, ItemStatus
from app.schemas.item import (
    ItemCreateRequest,
    ItemFilters,
    ItemResponse,
    ItemStatusHistoryResponse,
    ItemStatusUpdateRequest,
    ItemUpdateRequest,
)
from app.services.item_service import (
    create_item,
    list_item_history,
    list_items,
    retrieve_item,
    update_item,
    update_item_status,
)

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item_endpoint(
    payload: ItemCreateRequest,
    db: Session = Depends(get_db),
) -> ItemResponse:
    item = create_item(db, payload)
    return to_item_response(item)


@router.get("", response_model=list[ItemResponse])
def list_items_endpoint(
    classification: Classification | None = Query(default=None),
    category: str | None = Query(default=None),
    color: str | None = Query(default=None),
    location: str | None = Query(default=None),
    status_filter: ItemStatus | None = Query(default=None, alias="status"),
    reporter_user_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ItemResponse]:
    filters = ItemFilters(
        classification=classification,
        category=category,
        color=color,
        location=location,
        status=status_filter,
        reporter_user_id=reporter_user_id,
    )
    return [to_item_response(item) for item in list_items(db, filters)]


@router.get("/{item_id}", response_model=ItemResponse)
def get_item_endpoint(item_id: UUID, db: Session = Depends(get_db)) -> ItemResponse:
    try:
        item = retrieve_item(db, item_id)
    except ItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return to_item_response(item)


@router.patch("/{item_id}", response_model=ItemResponse)
def patch_item_endpoint(
    item_id: UUID,
    payload: ItemUpdateRequest,
    db: Session = Depends(get_db),
) -> ItemResponse:
    try:
        item = update_item(db, item_id, payload)
    except ItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidItemUpdateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return to_item_response(item)


@router.patch("/{item_id}/status", response_model=ItemResponse)
def patch_item_status_endpoint(
    item_id: UUID,
    payload: ItemStatusUpdateRequest,
    db: Session = Depends(get_db),
) -> ItemResponse:
    try:
        item = update_item_status(db, item_id, payload)
    except ItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidItemTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return to_item_response(item)


@router.get("/{item_id}/history", response_model=list[ItemStatusHistoryResponse])
def get_item_history_endpoint(
    item_id: UUID,
    db: Session = Depends(get_db),
) -> list[ItemStatusHistoryResponse]:
    try:
        history_entries = list_item_history(db, item_id)
    except ItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [to_item_history_response(entry) for entry in history_entries]

