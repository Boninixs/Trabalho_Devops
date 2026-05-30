from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.item import Classification, ItemStatus

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]


class ItemCreateRequest(BaseModel):
    classification: Classification
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)]
    description: LongText
    category: NonEmptyText
    color: NonEmptyText
    location_description: NonEmptyText
    approximate_date: date
    reporter_user_id: UUID


class ItemUpdateRequest(BaseModel):
    title: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)] = None
    description: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)] = None
    category: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)] = None
    color: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)] = None
    location_description: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)] = None
    approximate_date: date | None = None
    reporter_user_id: UUID | None = None

    @model_validator(mode="after")
    def validate_not_empty(self) -> "ItemUpdateRequest":
        if not self.model_dump(exclude_none=True):
            raise ValueError("Pelo menos um campo deve ser informado para atualização")
        return self


class ItemStatusUpdateRequest(BaseModel):
    status: ItemStatus
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
    actor_user_id: UUID | None = None


class RecoveryOpenRequest(BaseModel):
    item_ids: list[UUID] = Field(min_length=1)
    actor_user_id: UUID | None = None
    reason: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)] = None


class RecoveryCancelRequest(BaseModel):
    item_ids: list[UUID] = Field(min_length=1)
    actor_user_id: UUID | None = None
    reason: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)] = None
    target_status: ItemStatus = ItemStatus.AVAILABLE

    @model_validator(mode="after")
    def validate_target_status(self) -> "RecoveryCancelRequest":
        if self.target_status not in {ItemStatus.AVAILABLE, ItemStatus.MATCHED}:
            raise ValueError("target_status deve ser AVAILABLE ou MATCHED")
        return self


class RecoveryCompleteRequest(BaseModel):
    item_ids: list[UUID] = Field(min_length=1)
    actor_user_id: UUID | None = None
    reason: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)] = None


class ItemFilters(BaseModel):
    classification: Classification | None = None
    category: str | None = None
    color: str | None = None
    location: str | None = None
    status: ItemStatus | None = None
    reporter_user_id: UUID | None = None


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    classification: Classification
    title: str
    description: str
    category: str
    color: str
    location_description: str
    approximate_date: date
    reporter_user_id: UUID
    status: ItemStatus
    version: int
    created_at: datetime
    updated_at: datetime


class ItemStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_id: UUID
    from_status: ItemStatus | None
    to_status: ItemStatus
    reason: str
    actor_user_id: UUID | None
    occurred_at: datetime


class RecoveryOperationResponse(BaseModel):
    operation: str
    items: list[ItemResponse]

