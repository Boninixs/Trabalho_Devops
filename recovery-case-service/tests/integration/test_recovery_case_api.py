from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.recovery_case import RecoveryCaseStatus
from app.repositories.recovery_case_repository import list_recovery_cases
from app.schemas.events import EventEnvelope
from app.schemas.recovery_case import RecoveryCaseFilters
from app.services.recovery_case_service import consume_match_accepted


pytestmark = pytest.mark.integration


def build_match_accepted_event(*, match_id=None, lost_item_id=None, found_item_id=None) -> EventEnvelope:
    now = datetime.now(timezone.utc)
    match_id = match_id or uuid4()
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
                "lost_item_id": str(lost_item_id or uuid4()),
                "found_item_id": str(found_item_id or uuid4()),
                "score": 85,
                "criteria_snapshot_json": {"eligible": True, "score": 85},
                "status": "ACCEPTED",
                "decided_by_user_id": str(uuid4()),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        },
    )


def test_consume_match_accepted_opens_case(postgres_session, fake_item_client) -> None:
    recovery_case = consume_match_accepted(postgres_session, build_match_accepted_event(), fake_item_client)

    cases = list_recovery_cases(postgres_session, status=None)
    assert len(cases) == 1
    assert recovery_case.status == RecoveryCaseStatus.IN_PROGRESS
    assert fake_item_client.open_calls


def test_recovery_case_endpoints_list_and_detail(integration_client, postgres_session, fake_item_client) -> None:
    recovery_case = consume_match_accepted(postgres_session, build_match_accepted_event(), fake_item_client)

    list_response = integration_client.get("/recovery-cases")
    detail_response = integration_client.get(f"/recovery-cases/{recovery_case.id}")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == str(recovery_case.id)
    assert detail_response.json()["saga_steps"]


def test_cancel_endpoint_compensates_case(integration_client, postgres_session, fake_item_client) -> None:
    recovery_case = consume_match_accepted(postgres_session, build_match_accepted_event(), fake_item_client)

    response = integration_client.post(
        f"/recovery-cases/{recovery_case.id}/cancel",
        json={"actor_user_id": str(uuid4()), "reason": "Cancelamento operacional"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert fake_item_client.cancel_calls


def test_complete_endpoint_finishes_case(integration_client, postgres_session, fake_item_client) -> None:
    recovery_case = consume_match_accepted(postgres_session, build_match_accepted_event(), fake_item_client)

    response = integration_client.post(
        f"/recovery-cases/{recovery_case.id}/complete",
        json={"actor_user_id": str(uuid4()), "reason": "Entrega concluída"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["completed_at"] is not None
    assert fake_item_client.complete_calls
