from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.recovery_case import ACTIVE_RECOVERY_CASE_STATUSES, RecoveryCase, RecoveryCaseStatus


def add_recovery_case(session: Session, recovery_case: RecoveryCase) -> RecoveryCase:
    session.add(recovery_case)
    return recovery_case


def get_recovery_case_by_id(session: Session, case_id: UUID) -> RecoveryCase | None:
    return session.get(RecoveryCase, case_id)


def get_recovery_case_by_match_id(session: Session, match_id: UUID) -> RecoveryCase | None:
    statement = select(RecoveryCase).where(RecoveryCase.match_id == match_id)
    return session.scalar(statement)


def get_active_case_for_found_item(
    session: Session,
    found_item_id: UUID,
) -> RecoveryCase | None:
    statement = (
        select(RecoveryCase)
        .where(RecoveryCase.found_item_id == found_item_id)
        .where(RecoveryCase.status.in_(ACTIVE_RECOVERY_CASE_STATUSES))
    )
    return session.scalar(statement)


def list_recovery_cases(
    session: Session,
    *,
    status: RecoveryCaseStatus | None = None,
    match_id: UUID | None = None,
    lost_item_id: UUID | None = None,
    found_item_id: UUID | None = None,
) -> list[RecoveryCase]:
    statement: Select[tuple[RecoveryCase]] = select(RecoveryCase)
    if status is not None:
        statement = statement.where(RecoveryCase.status == status)
    if match_id is not None:
        statement = statement.where(RecoveryCase.match_id == match_id)
    if lost_item_id is not None:
        statement = statement.where(RecoveryCase.lost_item_id == lost_item_id)
    if found_item_id is not None:
        statement = statement.where(RecoveryCase.found_item_id == found_item_id)

    statement = statement.order_by(RecoveryCase.created_at.desc())
    return list(session.scalars(statement))
