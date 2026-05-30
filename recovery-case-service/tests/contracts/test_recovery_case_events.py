from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.outbox import OutboxEvent
from app.models.recovery_case import RecoveryCase, RecoveryCaseStatus
from app.schemas.recovery_case_event import (
    RecoveryCaseCancelledEnvelope,
    RecoveryCaseCompletedEnvelope,
    RecoveryCaseOpenedEnvelope,
)
from app.services.recovery_case_service import record_recovery_case_event


class FakeSession:
    def __init__(self) -> None:
        self.added_objects = []

    def add(self, obj):
        self.added_objects.append(obj)


def build_case(status: RecoveryCaseStatus) -> RecoveryCase:
    now = datetime.now(timezone.utc)
    return RecoveryCase(
        id=uuid4(),
        match_id=uuid4(),
        lost_item_id=uuid4(),
        found_item_id=uuid4(),
        status=status,
        opened_by_user_id=uuid4(),
        cancellation_reason="Cancelado por conflito" if status == RecoveryCaseStatus.CANCELLED else None,
        completed_at=now if status == RecoveryCaseStatus.COMPLETED else None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.contract
def test_recovery_case_opened_contract() -> None:
    session = FakeSession()
    recovery_case = build_case(RecoveryCaseStatus.IN_PROGRESS)

    record_recovery_case_event(
        session,
        recovery_case,
        event_type="RecoveryCaseOpened",
        correlation_id=uuid4(),
        causation_id=uuid4(),
    )

    outbox_event = next(obj for obj in session.added_objects if isinstance(obj, OutboxEvent))
    envelope = RecoveryCaseOpenedEnvelope.model_validate(
        {
            "event_id": outbox_event.id,
            "event_type": outbox_event.event_type,
            "aggregate_id": outbox_event.aggregate_id,
            "aggregate_version": outbox_event.aggregate_version,
            "occurred_at": outbox_event.occurred_at,
            "correlation_id": outbox_event.correlation_id,
            "causation_id": outbox_event.causation_id,
            "payload": outbox_event.payload,
        },
    )

    assert envelope.event_type == "RecoveryCaseOpened"
    assert envelope.payload.status == RecoveryCaseStatus.IN_PROGRESS


@pytest.mark.contract
def test_recovery_case_cancelled_contract() -> None:
    session = FakeSession()
    recovery_case = build_case(RecoveryCaseStatus.CANCELLED)

    record_recovery_case_event(
        session,
        recovery_case,
        event_type="RecoveryCaseCancelled",
        correlation_id=uuid4(),
        causation_id=None,
    )

    outbox_event = next(obj for obj in session.added_objects if isinstance(obj, OutboxEvent))
    envelope = RecoveryCaseCancelledEnvelope.model_validate(
        {
            "event_id": outbox_event.id,
            "event_type": outbox_event.event_type,
            "aggregate_id": outbox_event.aggregate_id,
            "aggregate_version": outbox_event.aggregate_version,
            "occurred_at": outbox_event.occurred_at,
            "correlation_id": outbox_event.correlation_id,
            "causation_id": outbox_event.causation_id,
            "payload": outbox_event.payload,
        },
    )

    assert envelope.event_type == "RecoveryCaseCancelled"
    assert envelope.payload.status == RecoveryCaseStatus.CANCELLED


@pytest.mark.contract
def test_recovery_case_completed_contract() -> None:
    session = FakeSession()
    recovery_case = build_case(RecoveryCaseStatus.COMPLETED)

    record_recovery_case_event(
        session,
        recovery_case,
        event_type="RecoveryCaseCompleted",
        correlation_id=uuid4(),
        causation_id=None,
    )

    outbox_event = next(obj for obj in session.added_objects if isinstance(obj, OutboxEvent))
    envelope = RecoveryCaseCompletedEnvelope.model_validate(
        {
            "event_id": outbox_event.id,
            "event_type": outbox_event.event_type,
            "aggregate_id": outbox_event.aggregate_id,
            "aggregate_version": outbox_event.aggregate_version,
            "occurred_at": outbox_event.occurred_at,
            "correlation_id": outbox_event.correlation_id,
            "causation_id": outbox_event.causation_id,
            "payload": outbox_event.payload,
        },
    )

    assert envelope.event_type == "RecoveryCaseCompleted"
    assert envelope.payload.status == RecoveryCaseStatus.COMPLETED
