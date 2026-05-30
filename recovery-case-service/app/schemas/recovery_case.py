from datetime import datetime
from typing import Any, Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.recovery_case import RecoveryCaseStatus
from app.models.saga_step import SagaStepStatus

ReasonText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class RecoveryCaseFilters(BaseModel):
    status: RecoveryCaseStatus | None = None
    match_id: UUID | None = None
    lost_item_id: UUID | None = None
    found_item_id: UUID | None = None


class RecoveryCaseCancelRequest(BaseModel):
    actor_user_id: UUID | None = None
    reason: ReasonText | None = None
    target_status: Literal["AVAILABLE", "MATCHED"] = "MATCHED"


class RecoveryCaseCompleteRequest(BaseModel):
    actor_user_id: UUID | None = None
    reason: ReasonText | None = None


class RecoveryCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    match_id: UUID
    lost_item_id: UUID
    found_item_id: UUID
    status: RecoveryCaseStatus
    opened_by_user_id: UUID | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class CaseEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    event_type: str
    payload_json: dict[str, Any]
    occurred_at: datetime


class SagaStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    step_name: str
    step_status: SagaStepStatus
    request_payload: dict[str, Any]
    response_payload: dict[str, Any] | None
    occurred_at: datetime


class RecoveryCaseDetailResponse(RecoveryCaseResponse):
    case_events: list[CaseEventResponse] = Field(default_factory=list)
    saga_steps: list[SagaStepResponse] = Field(default_factory=list)


class RecoveryCaseEventPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    match_id: UUID
    lost_item_id: UUID
    found_item_id: UUID
    status: RecoveryCaseStatus
    opened_by_user_id: UUID | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
