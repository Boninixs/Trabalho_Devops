from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ItemRecoveryOpenRequest(BaseModel):
    item_ids: list[UUID] = Field(min_length=1)
    actor_user_id: UUID | None = None
    reason: str | None = None


class ItemRecoveryCancelRequest(BaseModel):
    item_ids: list[UUID] = Field(min_length=1)
    actor_user_id: UUID | None = None
    reason: str | None = None
    target_status: str = "MATCHED"


class ItemRecoveryCompleteRequest(BaseModel):
    item_ids: list[UUID] = Field(min_length=1)
    actor_user_id: UUID | None = None
    reason: str | None = None


class ItemOperationItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    classification: str
    title: str
    description: str
    category: str
    color: str
    location_description: str
    approximate_date: date
    reporter_user_id: UUID
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class ItemRecoveryOperationResponse(BaseModel):
    operation: str
    items: list[ItemOperationItemResponse]
