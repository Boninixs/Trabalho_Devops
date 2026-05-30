""""
Esse arquivo é responsável por testar os contratos dos eventos de sugestão, aceitação e rejeição de matches. 
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.match_suggestion import MatchStatus, MatchSuggestion
from app.models.outbox import OutboxEvent
from app.schemas.match_event import (
    MatchAcceptedEnvelope,
    MatchRejectedEnvelope,
    MatchSuggestedEnvelope,
)
from app.services.matching_service import record_match_event


class FakeSession:
    """
    Sessão fake para capturar os objetos adicionados durante os testes de contrato.
    """
    def __init__(self):
        self.added_objects = []

    def add(self, obj):
        self.added_objects.append(obj)


def build_match(status: MatchStatus = MatchStatus.SUGGESTED) -> MatchSuggestion:
    """
    Função auxiliar para construir um MatchSuggestion com um status específico para os testes de contrato.  
    """
    now = datetime.now(timezone.utc)
    return MatchSuggestion(
        id=uuid4(),
        lost_item_id=uuid4(),
        found_item_id=uuid4(),
        score=70,
        criteria_snapshot_json={"eligible": True},
        status=status,
        decided_by_user_id=uuid4() if status != MatchStatus.SUGGESTED else None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.contract
def test_match_suggested_contract() -> None:
    """
    Testa o contrato do evento de sugestão de match.
    """
    session = FakeSession()
    match = build_match(MatchStatus.SUGGESTED)

    record_match_event(session, match, event_type="MatchSuggested")

    outbox_event = next(obj for obj in session.added_objects if isinstance(obj, OutboxEvent))
    envelope = MatchSuggestedEnvelope.model_validate(
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

    assert envelope.event_type == "MatchSuggested"
    assert envelope.payload.status == MatchStatus.SUGGESTED


@pytest.mark.contract
def test_match_accepted_contract() -> None:
    """
    Testa o contrato do evento de aceitação de match.
    """
    session = FakeSession()
    match = build_match(MatchStatus.ACCEPTED)

    record_match_event(session, match, event_type="MatchAccepted")

    outbox_event = next(obj for obj in session.added_objects if isinstance(obj, OutboxEvent))
    envelope = MatchAcceptedEnvelope.model_validate(
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

    assert envelope.event_type == "MatchAccepted"
    assert envelope.payload.status == MatchStatus.ACCEPTED


@pytest.mark.contract
def test_match_rejected_contract() -> None:
    """
    Testa o contrato do evento de rejeição de match.
    """
    session = FakeSession()
    match = build_match(MatchStatus.REJECTED)

    record_match_event(session, match, event_type="MatchRejected")

    outbox_event = next(obj for obj in session.added_objects if isinstance(obj, OutboxEvent))
    envelope = MatchRejectedEnvelope.model_validate(
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

    assert envelope.event_type == "MatchRejected"
    assert envelope.payload.status == MatchStatus.REJECTED
