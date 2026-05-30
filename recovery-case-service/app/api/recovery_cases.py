from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import (
    InvalidRecoveryCaseTransitionError,
    ItemServiceIntegrationError,
    RecoveryCaseConflictError,
    RecoveryCaseNotFoundError,
)
from app.db.session import get_db
from app.mappers.recovery_case_mapper import (
    to_recovery_case_detail_response,
    to_recovery_case_response,
)
from app.schemas.recovery_case import (
    RecoveryCaseCancelRequest,
    RecoveryCaseCompleteRequest,
    RecoveryCaseDetailResponse,
    RecoveryCaseFilters,
    RecoveryCaseResponse,
)
from app.services.item_service_client import ItemRecoveryClient, get_item_recovery_client
from app.services.recovery_case_service import (
    cancel_recovery_case,
    complete_recovery_case,
    list_recovery_cases,
    retrieve_recovery_case,
    retrieve_recovery_case_events,
    retrieve_recovery_case_saga_steps,
)

router = APIRouter(prefix="/recovery-cases", tags=["recovery-cases"])


@router.get("", response_model=list[RecoveryCaseResponse])
def list_recovery_cases_endpoint(
    filters: RecoveryCaseFilters = Depends(),
    db: Session = Depends(get_db),
) -> list[RecoveryCaseResponse]:
    recovery_cases = list_recovery_cases(db, filters)
    return [to_recovery_case_response(recovery_case) for recovery_case in recovery_cases]


@router.get("/{case_id}", response_model=RecoveryCaseDetailResponse)
def retrieve_recovery_case_endpoint(
    case_id: UUID,
    db: Session = Depends(get_db),
) -> RecoveryCaseDetailResponse:
    try:
        recovery_case = retrieve_recovery_case(db, case_id)
        case_events = retrieve_recovery_case_events(db, case_id)
        saga_steps = retrieve_recovery_case_saga_steps(db, case_id)
    except RecoveryCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return to_recovery_case_detail_response(recovery_case, case_events, saga_steps)


@router.post("/{case_id}/cancel", response_model=RecoveryCaseResponse)
def cancel_recovery_case_endpoint(
    case_id: UUID,
    payload: RecoveryCaseCancelRequest,
    db: Session = Depends(get_db),
    item_client: ItemRecoveryClient = Depends(get_item_recovery_client),
) -> RecoveryCaseResponse:
    try:
        recovery_case = cancel_recovery_case(db, case_id, payload, item_client)
    except RecoveryCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (RecoveryCaseConflictError, InvalidRecoveryCaseTransitionError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ItemServiceIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return to_recovery_case_response(recovery_case)


@router.post("/{case_id}/complete", response_model=RecoveryCaseResponse)
def complete_recovery_case_endpoint(
    case_id: UUID,
    payload: RecoveryCaseCompleteRequest,
    db: Session = Depends(get_db),
    item_client: ItemRecoveryClient = Depends(get_item_recovery_client),
) -> RecoveryCaseResponse:
    try:
        recovery_case = complete_recovery_case(db, case_id, payload, item_client)
    except RecoveryCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (RecoveryCaseConflictError, InvalidRecoveryCaseTransitionError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ItemServiceIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return to_recovery_case_response(recovery_case)
