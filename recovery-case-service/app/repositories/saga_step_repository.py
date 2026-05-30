from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.saga_step import SagaStep


def add_saga_step(session: Session, saga_step: SagaStep) -> SagaStep:
    session.add(saga_step)
    return saga_step


def list_saga_steps(session: Session, case_id: UUID) -> list[SagaStep]:
    statement = (
        select(SagaStep)
        .where(SagaStep.case_id == case_id)
        .order_by(SagaStep.occurred_at.asc())
    )
    return list(session.scalars(statement))
