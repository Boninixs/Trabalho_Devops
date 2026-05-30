from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case_event import CaseEvent


def add_case_event(session: Session, case_event: CaseEvent) -> CaseEvent:
    session.add(case_event)
    return case_event


def list_case_events(session: Session, case_id: UUID) -> list[CaseEvent]:
    statement = (
        select(CaseEvent)
        .where(CaseEvent.case_id == case_id)
        .order_by(CaseEvent.occurred_at.asc())
    )
    return list(session.scalars(statement))
