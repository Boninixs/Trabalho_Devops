from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import (
    InvalidRecoveryCaseTransitionError,
    RecoveryCaseConflictError,
)
from app.models.case_event import CaseEvent
from app.models.outbox import OutboxEvent
from app.models.processed_event import ProcessedEvent
from app.models.recovery_case import RecoveryCase, RecoveryCaseStatus
from app.models.saga_step import SagaStep, SagaStepStatus
from app.schemas.events import EventEnvelope
from app.schemas.recovery_case import RecoveryCaseCancelRequest, RecoveryCaseCompleteRequest
from app.services.recovery_case_service import (
    cancel_recovery_case,
    complete_recovery_case,
    consume_match_accepted,
    ensure_found_item_is_available_for_case,
)
from tests.conftest import FakeItemRecoveryClient


class FakeSession:
    def __init__(self) -> None:
        self.added_objects = []
        self.committed = False
        self.flushed = False
        self.refreshed = False
        self.rolled_back = False

    def add(self, obj):
        self.added_objects.append(obj)

    def flush(self):
        self.flushed = True

    def commit(self):
        self.committed = True

    def refresh(self, _obj):
        self.refreshed = True

    def rollback(self):
        self.rolled_back = True


def build_match_accepted_event() -> EventEnvelope:
    now = datetime.now(timezone.utc)
    match_id = uuid4()
    return EventEnvelope.model_validate(
        {
            "event_id": str(uuid4()),
            "event_type": "MatchAccepted",
            "aggregate_id": str(match_id),
            "aggregate_version": 1,
            "occurred_at": now.isoformat(),
            "correlation_id": str(uuid4()),
            "causation_id": None,
            "payload": {
                "id": str(match_id),
                "lost_item_id": str(uuid4()),
                "found_item_id": str(uuid4()),
                "score": 80,
                "criteria_snapshot_json": {"eligible": True},
                "status": "ACCEPTED",
                "decided_by_user_id": str(uuid4()),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        },
    )


def build_recovery_case(status: RecoveryCaseStatus = RecoveryCaseStatus.IN_PROGRESS) -> RecoveryCase:
    now = datetime.now(timezone.utc)
    return RecoveryCase(
        id=uuid4(),
        match_id=uuid4(),
        lost_item_id=uuid4(),
        found_item_id=uuid4(),
        status=status,
        opened_by_user_id=uuid4(),
        cancellation_reason=None,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )


def test_consume_match_accepted_opens_case_and_records_saga(monkeypatch) -> None:
    session = FakeSession()
    item_client = FakeItemRecoveryClient()
    envelope = build_match_accepted_event()

    monkeypatch.setattr("app.services.recovery_case_service.has_been_processed", lambda *_args: False)
    monkeypatch.setattr(
        "app.services.recovery_case_service.get_recovery_case_by_match_id",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.recovery_case_service.get_active_case_for_found_item",
        lambda *_args, **_kwargs: None,
    )

    recovery_case = consume_match_accepted(session, envelope, item_client)

    assert recovery_case.status == RecoveryCaseStatus.IN_PROGRESS
    assert item_client.open_calls
    assert session.committed is True
    assert any(isinstance(obj, SagaStep) and obj.step_status == SagaStepStatus.SUCCEEDED for obj in session.added_objects)
    assert any(isinstance(obj, CaseEvent) and obj.event_type == "RecoveryCaseOpened" for obj in session.added_objects)
    assert any(isinstance(obj, OutboxEvent) and obj.event_type == "RecoveryCaseOpened" for obj in session.added_objects)
    assert any(isinstance(obj, ProcessedEvent) for obj in session.added_objects)


def test_found_item_cannot_enter_two_active_cases(monkeypatch) -> None:
    active_case = build_recovery_case()

    monkeypatch.setattr(
        "app.services.recovery_case_service.get_active_case_for_found_item",
        lambda *_args, **_kwargs: active_case,
    )

    with pytest.raises(RecoveryCaseConflictError, match="caso ativo"):
        ensure_found_item_is_available_for_case(FakeSession(), active_case.found_item_id)


def test_consume_match_accepted_marks_failed_open_for_retry(monkeypatch) -> None:
    session = FakeSession()
    item_client = FakeItemRecoveryClient()
    item_client.fail_open = True
    envelope = build_match_accepted_event()

    monkeypatch.setattr("app.services.recovery_case_service.has_been_processed", lambda *_args: False)
    monkeypatch.setattr(
        "app.services.recovery_case_service.get_recovery_case_by_match_id",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.recovery_case_service.get_active_case_for_found_item",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(Exception, match="falha simulada na abertura"):
        consume_match_accepted(session, envelope, item_client)

    case = next(obj for obj in session.added_objects if isinstance(obj, RecoveryCase))
    step = next(obj for obj in session.added_objects if isinstance(obj, SagaStep))
    assert case.status == RecoveryCaseStatus.CANCELLED
    assert case.cancellation_reason.startswith("OPEN_FAILED:")
    assert step.step_status == SagaStepStatus.FAILED


def test_cancel_recovery_case_compensates_status(monkeypatch) -> None:
    session = FakeSession()
    item_client = FakeItemRecoveryClient()
    recovery_case = build_recovery_case()

    monkeypatch.setattr(
        "app.services.recovery_case_service.retrieve_recovery_case",
        lambda *_args, **_kwargs: recovery_case,
    )

    result = cancel_recovery_case(
        session,
        recovery_case.id,
        RecoveryCaseCancelRequest(actor_user_id=uuid4(), reason="Cancelado pelo operador"),
        item_client,
    )

    assert result.status == RecoveryCaseStatus.CANCELLED
    assert item_client.cancel_calls[0].target_status == "MATCHED"
    assert any(isinstance(obj, OutboxEvent) and obj.event_type == "RecoveryCaseCancelled" for obj in session.added_objects)


def test_complete_recovery_case_sets_completed_at(monkeypatch) -> None:
    session = FakeSession()
    item_client = FakeItemRecoveryClient()
    recovery_case = build_recovery_case()

    monkeypatch.setattr(
        "app.services.recovery_case_service.retrieve_recovery_case",
        lambda *_args, **_kwargs: recovery_case,
    )

    result = complete_recovery_case(
        session,
        recovery_case.id,
        RecoveryCaseCompleteRequest(actor_user_id=uuid4(), reason="Item devolvido"),
        item_client,
    )

    assert result.status == RecoveryCaseStatus.COMPLETED
    assert result.completed_at is not None
    assert any(isinstance(obj, OutboxEvent) and obj.event_type == "RecoveryCaseCompleted" for obj in session.added_objects)


def test_complete_cancelled_case_is_invalid(monkeypatch) -> None:
    recovery_case = build_recovery_case(status=RecoveryCaseStatus.CANCELLED)

    monkeypatch.setattr(
        "app.services.recovery_case_service.retrieve_recovery_case",
        lambda *_args, **_kwargs: recovery_case,
    )

    with pytest.raises(InvalidRecoveryCaseTransitionError, match="cancelado não pode ser concluído"):
        complete_recovery_case(
            FakeSession(),
            recovery_case.id,
            RecoveryCaseCompleteRequest(actor_user_id=uuid4(), reason="Inválido"),
            FakeItemRecoveryClient(),
        )
