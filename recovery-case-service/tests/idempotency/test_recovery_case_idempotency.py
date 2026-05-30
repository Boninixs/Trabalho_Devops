from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import RecoveryCaseConflictError
from app.models.recovery_case import RecoveryCase, RecoveryCaseStatus
from app.repositories.recovery_case_repository import list_recovery_cases
from app.schemas.events import EventEnvelope
from app.services.recovery_case_service import consume_match_accepted


pytestmark = pytest.mark.idempotency


def build_match_accepted_event(
    *,
    event_id=None,
    match_id=None,
    lost_item_id=None,
    found_item_id=None,
) -> EventEnvelope:
    now = datetime.now(timezone.utc)
    match_id = match_id or uuid4()
    return EventEnvelope.model_validate(
        {
            "event_id": str(event_id or uuid4()),
            "event_type": "MatchAccepted",
            "aggregate_id": str(match_id),
            "aggregate_version": 1,
            "occurred_at": now.isoformat(),
            "correlation_id": str(uuid4()),
            "causation_id": None,
            "payload": {
                "id": str(match_id),
                "lost_item_id": str(lost_item_id or uuid4()),
                "found_item_id": str(found_item_id or uuid4()),
                "score": 90,
                "criteria_snapshot_json": {"eligible": True},
                "status": "ACCEPTED",
                "decided_by_user_id": str(uuid4()),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        },
    )


def test_reprocessing_same_matchaccepted_does_not_duplicate_case(postgres_session, fake_item_client) -> None:
    event_id = uuid4()
    envelope = build_match_accepted_event(event_id=event_id)

    first_case = consume_match_accepted(postgres_session, envelope, fake_item_client)
    second_case = consume_match_accepted(postgres_session, envelope, fake_item_client)

    cases = list_recovery_cases(postgres_session, status=None)
    assert len(cases) == 1
    assert first_case.id == second_case.id


def test_found_item_can_only_be_in_one_active_case(postgres_session, fake_item_client) -> None:
    found_item_id = uuid4()
    consume_match_accepted(
        postgres_session,
        build_match_accepted_event(found_item_id=found_item_id),
        fake_item_client,
    )

    with pytest.raises(RecoveryCaseConflictError, match="caso ativo"):
        consume_match_accepted(
            postgres_session,
            build_match_accepted_event(found_item_id=found_item_id),
            fake_item_client,
        )


def test_partial_unique_index_blocks_second_active_case_for_found_item(postgres_session) -> None:
    recovery_case_one = RecoveryCase(
        id=uuid4(),
        match_id=uuid4(),
        lost_item_id=uuid4(),
        found_item_id=uuid4(),
        status=RecoveryCaseStatus.IN_PROGRESS,
        opened_by_user_id=uuid4(),
        cancellation_reason=None,
        completed_at=None,
    )
    recovery_case_two = RecoveryCase(
        id=uuid4(),
        match_id=uuid4(),
        lost_item_id=uuid4(),
        found_item_id=recovery_case_one.found_item_id,
        status=RecoveryCaseStatus.OPEN,
        opened_by_user_id=uuid4(),
        cancellation_reason=None,
        completed_at=None,
    )

    postgres_session.add(recovery_case_one)
    postgres_session.commit()

    postgres_session.add(recovery_case_two)
    with pytest.raises(IntegrityError):
        postgres_session.commit()
