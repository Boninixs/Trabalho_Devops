from app.models.case_event import CaseEvent
from app.models.recovery_case import RecoveryCase
from app.models.saga_step import SagaStep
from app.schemas.recovery_case import (
    CaseEventResponse,
    RecoveryCaseDetailResponse,
    RecoveryCaseEventPayload,
    RecoveryCaseResponse,
    SagaStepResponse,
)


def to_recovery_case_response(recovery_case: RecoveryCase) -> RecoveryCaseResponse:
    return RecoveryCaseResponse.model_validate(recovery_case)


def to_recovery_case_detail_response(
    recovery_case: RecoveryCase,
    case_events: list[CaseEvent],
    saga_steps: list[SagaStep],
) -> RecoveryCaseDetailResponse:
    return RecoveryCaseDetailResponse(
        **RecoveryCaseResponse.model_validate(recovery_case).model_dump(),
        case_events=[CaseEventResponse.model_validate(case_event) for case_event in case_events],
        saga_steps=[SagaStepResponse.model_validate(saga_step) for saga_step in saga_steps],
    )


def to_recovery_case_event_payload(recovery_case: RecoveryCase) -> RecoveryCaseEventPayload:
    return RecoveryCaseEventPayload.model_validate(recovery_case)
