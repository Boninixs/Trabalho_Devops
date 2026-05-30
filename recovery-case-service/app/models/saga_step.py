import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import Base, UUIDPrimaryKeyMixin


class SagaStepStatus(str, enum.Enum):
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class SagaStep(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "saga_steps"

    case_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    step_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    step_status: Mapped[SagaStepStatus] = mapped_column(
        Enum(SagaStepStatus, name="saga_step_status", native_enum=False),
        nullable=False,
        index=True,
    )
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    response_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
