from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidItemTransitionError, ItemNotFoundError
from app.db.session import get_db
from app.mappers.item_mapper import to_item_response
from app.schemas.item import (
    RecoveryCancelRequest,
    RecoveryCompleteRequest,
    RecoveryOpenRequest,
    RecoveryOperationResponse,
)
from app.services.item_service import cancel_recovery, complete_recovery, open_recovery

router = APIRouter(prefix="/internal/recovery", tags=["internal-recovery"])


@router.post("/open", response_model=RecoveryOperationResponse)
def open_recovery_endpoint(
    payload: RecoveryOpenRequest,
    db: Session = Depends(get_db),
) -> RecoveryOperationResponse:
    try:
        items = open_recovery(db, payload)
    except (ItemNotFoundError, InvalidItemTransitionError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RecoveryOperationResponse(
        operation="open",
        items=[to_item_response(item) for item in items],
    )


@router.post("/cancel", response_model=RecoveryOperationResponse)
def cancel_recovery_endpoint(
    payload: RecoveryCancelRequest,
    db: Session = Depends(get_db),
) -> RecoveryOperationResponse:
    try:
        items = cancel_recovery(db, payload)
    except (ItemNotFoundError, InvalidItemTransitionError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RecoveryOperationResponse(
        operation="cancel",
        items=[to_item_response(item) for item in items],
    )


@router.post("/complete", response_model=RecoveryOperationResponse)
def complete_recovery_endpoint(
    payload: RecoveryCompleteRequest,
    db: Session = Depends(get_db),
) -> RecoveryOperationResponse:
    try:
        items = complete_recovery(db, payload)
    except (ItemNotFoundError, InvalidItemTransitionError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RecoveryOperationResponse(
        operation="complete",
        items=[to_item_response(item) for item in items],
    )

