from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    InvalidRecoveryCaseTransitionError,
    ItemServiceIntegrationError,
    RecoveryCaseConflictError,
    RecoveryCaseNotFoundError,
)
from app.mappers.recovery_case_mapper import to_recovery_case_event_payload
from app.messaging.idempotency import has_been_processed, register_processed_event
from app.messaging.outbox import enqueue_broker_message
from app.messaging.topology import ROUTING_KEYS
from app.models.case_event import CaseEvent
from app.models.recovery_case import (
    ACTIVE_RECOVERY_CASE_STATUSES,
    RecoveryCase,
    RecoveryCaseStatus,
)
from app.models.saga_step import SagaStep, SagaStepStatus
from app.repositories.case_event_repository import add_case_event, list_case_events
from app.repositories.recovery_case_repository import (
    add_recovery_case,
    get_active_case_for_found_item,
    get_recovery_case_by_id,
    get_recovery_case_by_match_id,
    list_recovery_cases as list_recovery_cases_repository,
)
from app.repositories.saga_step_repository import add_saga_step, list_saga_steps
from app.schemas.events import BrokerMessage, EventEnvelope
from app.schemas.item_service import (
    ItemRecoveryCancelRequest,
    ItemRecoveryCompleteRequest,
    ItemRecoveryOpenRequest,
)
from app.schemas.match_event import MatchAcceptedEnvelope
from app.schemas.recovery_case import (
    RecoveryCaseCancelRequest,
    RecoveryCaseCompleteRequest,
    RecoveryCaseFilters,
)
from app.services.item_service_client import ItemRecoveryClient

OPEN_FAILURE_PREFIX = "OPEN_FAILED:"
OPEN_STEP_NAME = "item_service.open_recovery"
CANCEL_STEP_NAME = "item_service.cancel_recovery"
COMPLETE_STEP_NAME = "item_service.complete_recovery"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def list_recovery_cases(session: Session, filters: RecoveryCaseFilters) -> list[RecoveryCase]:
    return list_recovery_cases_repository(
        session,
        status=filters.status,
        match_id=filters.match_id,
        lost_item_id=filters.lost_item_id,
        found_item_id=filters.found_item_id,
    )


def retrieve_recovery_case(session: Session, case_id: UUID) -> RecoveryCase:
    recovery_case = get_recovery_case_by_id(session, case_id)
    if recovery_case is None:
        raise RecoveryCaseNotFoundError(f"Recovery case {case_id} não encontrado")
    return recovery_case


def retrieve_recovery_case_events(session: Session, case_id: UUID) -> list[CaseEvent]:
    retrieve_recovery_case(session, case_id)
    return list_case_events(session, case_id)


def retrieve_recovery_case_saga_steps(session: Session, case_id: UUID) -> list[SagaStep]:
    retrieve_recovery_case(session, case_id)
    return list_saga_steps(session, case_id)


def consume_match_accepted(
    session: Session,
    envelope: EventEnvelope,
    item_client: ItemRecoveryClient,
) -> RecoveryCase:
    typed_envelope = parse_match_accepted_envelope(envelope)
    if has_been_processed(session, typed_envelope):
        existing_case = get_recovery_case_by_match_id(session, typed_envelope.payload.id)
        if existing_case is None:
            raise RecoveryCaseConflictError(
                f"Evento {typed_envelope.event_id} já foi processado, mas o caso não foi encontrado",
            )
        return existing_case

    existing_case = get_recovery_case_by_match_id(session, typed_envelope.payload.id)
    if existing_case is not None and not is_retryable_failed_open(existing_case):
        register_processed_event(session, typed_envelope)
        session.commit()
        return existing_case

    recovery_case = existing_case or RecoveryCase(
        id=uuid4(),
        match_id=typed_envelope.payload.id,
        lost_item_id=typed_envelope.payload.lost_item_id,
        found_item_id=typed_envelope.payload.found_item_id,
        status=RecoveryCaseStatus.OPEN,
        opened_by_user_id=typed_envelope.payload.decided_by_user_id,
        cancellation_reason=None,
        completed_at=None,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    if existing_case is None:
        ensure_found_item_is_available_for_case(session, recovery_case.found_item_id)
        add_recovery_case(session, recovery_case)
    else:
        ensure_found_item_is_available_for_case(
            session,
            recovery_case.found_item_id,
            allowed_case_id=recovery_case.id,
        )
        recovery_case.status = RecoveryCaseStatus.OPEN
        recovery_case.cancellation_reason = None
        recovery_case.updated_at = utc_now()

    request_payload = ItemRecoveryOpenRequest(
        item_ids=[recovery_case.lost_item_id, recovery_case.found_item_id],
        actor_user_id=recovery_case.opened_by_user_id,
        reason="Recovery case opened from MatchAccepted",
    )
    saga_step = start_saga_step(
        session,
        case_id=recovery_case.id,
        step_name=OPEN_STEP_NAME,
        request_payload=request_payload.model_dump(mode="json"),
    )
    session.flush()

    try:
        response = item_client.open_recovery(request_payload)
    except ItemServiceIntegrationError as exc:
        fail_saga_step(saga_step, {"error": str(exc)})
        recovery_case.status = RecoveryCaseStatus.CANCELLED
        recovery_case.cancellation_reason = f"{OPEN_FAILURE_PREFIX} {exc}"
        recovery_case.updated_at = utc_now()
        session.commit()
        raise

    finish_saga_step(saga_step, response.model_dump(mode="json"))
    recovery_case.status = RecoveryCaseStatus.IN_PROGRESS
    recovery_case.updated_at = utc_now()
    record_recovery_case_event(
        session,
        recovery_case,
        event_type="RecoveryCaseOpened",
        correlation_id=typed_envelope.correlation_id,
        causation_id=typed_envelope.event_id,
    )
    register_processed_event(session, typed_envelope)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise RecoveryCaseConflictError(
            "Já existe um caso ativo para o item FOUND informado",
        ) from exc

    session.refresh(recovery_case)
    return recovery_case


def cancel_recovery_case(
    session: Session,
    case_id: UUID,
    payload: RecoveryCaseCancelRequest,
    item_client: ItemRecoveryClient,
) -> RecoveryCase:
    recovery_case = retrieve_recovery_case(session, case_id)
    if recovery_case.status == RecoveryCaseStatus.CANCELLED:
        raise InvalidRecoveryCaseTransitionError("Recovery case já está cancelado")
    if recovery_case.status == RecoveryCaseStatus.COMPLETED:
        raise InvalidRecoveryCaseTransitionError("Recovery case concluído não pode ser cancelado")
    if recovery_case.status not in ACTIVE_RECOVERY_CASE_STATUSES:
        raise InvalidRecoveryCaseTransitionError("Recovery case não está ativo para cancelamento")

    request_payload = ItemRecoveryCancelRequest(
        item_ids=[recovery_case.lost_item_id, recovery_case.found_item_id],
        actor_user_id=payload.actor_user_id,
        reason=payload.reason or "Recovery case cancelled",
        target_status=payload.target_status,
    )
    saga_step = start_saga_step(
        session,
        case_id=recovery_case.id,
        step_name=CANCEL_STEP_NAME,
        request_payload=request_payload.model_dump(mode="json"),
    )
    session.flush()

    try:
        response = item_client.cancel_recovery(request_payload)
    except ItemServiceIntegrationError as exc:
        fail_saga_step(saga_step, {"error": str(exc)})
        session.commit()
        raise

    finish_saga_step(saga_step, response.model_dump(mode="json"))
    recovery_case.status = RecoveryCaseStatus.CANCELLED
    recovery_case.cancellation_reason = payload.reason or "Recovery case cancelled"
    recovery_case.updated_at = utc_now()
    record_recovery_case_event(
        session,
        recovery_case,
        event_type="RecoveryCaseCancelled",
        correlation_id=uuid4(),
        causation_id=None,
    )
    session.commit()
    session.refresh(recovery_case)
    return recovery_case


def complete_recovery_case(
    session: Session,
    case_id: UUID,
    payload: RecoveryCaseCompleteRequest,
    item_client: ItemRecoveryClient,
) -> RecoveryCase:
    recovery_case = retrieve_recovery_case(session, case_id)
    if recovery_case.status == RecoveryCaseStatus.CANCELLED:
        raise InvalidRecoveryCaseTransitionError("Recovery case cancelado não pode ser concluído")
    if recovery_case.status == RecoveryCaseStatus.COMPLETED:
        raise InvalidRecoveryCaseTransitionError("Recovery case já está concluído")
    if recovery_case.status != RecoveryCaseStatus.IN_PROGRESS:
        raise InvalidRecoveryCaseTransitionError("Recovery case precisa estar IN_PROGRESS para conclusão")

    request_payload = ItemRecoveryCompleteRequest(
        item_ids=[recovery_case.lost_item_id, recovery_case.found_item_id],
        actor_user_id=payload.actor_user_id,
        reason=payload.reason or "Recovery case completed",
    )
    saga_step = start_saga_step(
        session,
        case_id=recovery_case.id,
        step_name=COMPLETE_STEP_NAME,
        request_payload=request_payload.model_dump(mode="json"),
    )
    session.flush()

    try:
        response = item_client.complete_recovery(request_payload)
    except ItemServiceIntegrationError as exc:
        fail_saga_step(saga_step, {"error": str(exc)})
        session.commit()
        raise

    finish_saga_step(saga_step, response.model_dump(mode="json"))
    recovery_case.status = RecoveryCaseStatus.COMPLETED
    recovery_case.completed_at = utc_now()
    recovery_case.updated_at = recovery_case.completed_at
    record_recovery_case_event(
        session,
        recovery_case,
        event_type="RecoveryCaseCompleted",
        correlation_id=uuid4(),
        causation_id=None,
    )
    session.commit()
    session.refresh(recovery_case)
    return recovery_case


def parse_match_accepted_envelope(envelope: EventEnvelope) -> MatchAcceptedEnvelope:
    payload = envelope.model_dump(mode="json")
    if envelope.event_type != "MatchAccepted":
        raise RecoveryCaseConflictError(f"Evento {envelope.event_type} não suportado pelo recovery-case-service")
    return MatchAcceptedEnvelope.model_validate(payload)


def ensure_found_item_is_available_for_case(
    session: Session,
    found_item_id: UUID,
    *,
    allowed_case_id: UUID | None = None,
) -> None:
    active_case = get_active_case_for_found_item(session, found_item_id)
    if active_case is None:
        return
    if allowed_case_id is not None and active_case.id == allowed_case_id:
        return
    raise RecoveryCaseConflictError("Já existe um caso ativo para o item FOUND informado")


def is_retryable_failed_open(recovery_case: RecoveryCase) -> bool:
    return (
        recovery_case.status == RecoveryCaseStatus.CANCELLED
        and (recovery_case.cancellation_reason or "").startswith(OPEN_FAILURE_PREFIX)
    )


def start_saga_step(
    session: Session,
    *,
    case_id: UUID,
    step_name: str,
    request_payload: dict,
) -> SagaStep:
    saga_step = SagaStep(
        case_id=case_id,
        step_name=step_name,
        step_status=SagaStepStatus.STARTED,
        request_payload=request_payload,
        response_payload=None,
    )
    add_saga_step(session, saga_step)
    return saga_step


def finish_saga_step(saga_step: SagaStep, response_payload: dict) -> None:
    saga_step.step_status = SagaStepStatus.SUCCEEDED
    saga_step.response_payload = response_payload


def fail_saga_step(saga_step: SagaStep, response_payload: dict) -> None:
    saga_step.step_status = SagaStepStatus.FAILED
    saga_step.response_payload = response_payload


def record_recovery_case_event(
    session: Session,
    recovery_case: RecoveryCase,
    *,
    event_type: str,
    correlation_id: UUID,
    causation_id: UUID | None,
) -> None:
    if event_type not in {
        "RecoveryCaseOpened",
        "RecoveryCaseCancelled",
        "RecoveryCaseCompleted",
    }:
        raise RecoveryCaseConflictError(f"Evento {event_type} não suportado pelo recovery-case-service")

    payload = to_recovery_case_event_payload(recovery_case)
    add_case_event(
        session,
        CaseEvent(
            case_id=recovery_case.id,
            event_type=event_type,
            payload_json=payload.model_dump(mode="json"),
        ),
    )

    settings = get_settings()
    routing_key_map = {
        "RecoveryCaseOpened": ROUTING_KEYS["recovery_case_opened"],
        "RecoveryCaseCancelled": ROUTING_KEYS["recovery_case_cancelled"],
        "RecoveryCaseCompleted": ROUTING_KEYS["recovery_case_completed"],
    }
    message = BrokerMessage(
        envelope=EventEnvelope(
            event_type=event_type,
            aggregate_id=recovery_case.id,
            aggregate_version=1,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload=payload.model_dump(mode="json"),
        ),
        routing_key=routing_key_map[event_type],
        exchange_name=settings.rabbitmq_events_exchange,
    )
    enqueue_broker_message(session, message)
