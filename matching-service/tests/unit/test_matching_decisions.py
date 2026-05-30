from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import InvalidMatchDecisionError
from app.models.item_projection import ExternalItemStatus, ItemClassification, ItemProjection
from app.models.match_suggestion import MatchStatus, MatchSuggestion
from app.schemas.match import MatchDecisionRequest
from app.services.matching_service import accept_match, reject_match


class FakeSession:
    def __init__(self, suggestion: MatchSuggestion, lost_item: ItemProjection, found_item: ItemProjection):
        self.suggestion = suggestion
        self.lost_item = lost_item
        self.found_item = found_item
        self.committed = False
        self.flushed = False
        self.refreshed = False
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    def get(self, model, obj_id):
        model_name = model.__name__
        if model_name == "MatchSuggestion" and obj_id == self.suggestion.id:
            return self.suggestion
        if model_name == "ItemProjection" and obj_id == self.lost_item.id:
            return self.lost_item
        if model_name == "ItemProjection" and obj_id == self.found_item.id:
            return self.found_item
        return None

    def flush(self):
        self.flushed = True

    def commit(self):
        self.committed = True

    def refresh(self, _obj):
        self.refreshed = True

    def scalar(self, statement):
        compiled = str(statement)
        if "FROM match_suggestions" in compiled:
            return self.suggestion
        return None


def build_projection(classification: ItemClassification) -> ItemProjection:
    now = datetime.now(timezone.utc)
    return ItemProjection(
        id=uuid4(),
        classification=classification,
        title="Mochila",
        description="Mochila azul com caderno",
        category="Mochila",
        color="Azul",
        location_description="Biblioteca central",
        approximate_date=now.date(),
        reporter_user_id=uuid4(),
        status=ExternalItemStatus.AVAILABLE,
        version=1,
        created_at=now,
        updated_at=now,
        last_event_id=uuid4(),
        last_seen_at=now,
    )


def build_suggestion(lost_id, found_id, status=MatchStatus.SUGGESTED) -> MatchSuggestion:
    now = datetime.now(timezone.utc)
    return MatchSuggestion(
        id=uuid4(),
        lost_item_id=lost_id,
        found_item_id=found_id,
        score=70,
        criteria_snapshot_json={"eligible": True},
        status=status,
        decided_by_user_id=None,
        created_at=now,
        updated_at=now,
    )


def test_accept_match_updates_status(monkeypatch) -> None:
    lost_item = build_projection(ItemClassification.LOST)
    found_item = build_projection(ItemClassification.FOUND)
    suggestion = build_suggestion(lost_item.id, found_item.id)
    session = FakeSession(suggestion, lost_item, found_item)

    monkeypatch.setattr(
        "app.services.matching_service.retrieve_match_suggestion",
        lambda _session, _match_id: suggestion,
    )

    result = accept_match(
        session,
        suggestion.id,
        MatchDecisionRequest(decided_by_user_id=uuid4()),
    )

    assert result.status == MatchStatus.ACCEPTED
    assert result.decided_by_user_id is not None
    assert session.committed is True


def test_reject_match_updates_status(monkeypatch) -> None:
    lost_item = build_projection(ItemClassification.LOST)
    found_item = build_projection(ItemClassification.FOUND)
    suggestion = build_suggestion(lost_item.id, found_item.id)
    session = FakeSession(suggestion, lost_item, found_item)

    monkeypatch.setattr(
        "app.services.matching_service.retrieve_match_suggestion",
        lambda _session, _match_id: suggestion,
    )

    result = reject_match(
        session,
        suggestion.id,
        MatchDecisionRequest(decided_by_user_id=uuid4()),
    )

    assert result.status == MatchStatus.REJECTED
    assert result.decided_by_user_id is not None
    assert session.committed is True


def test_invalid_decision_for_expired_match(monkeypatch) -> None:
    lost_item = build_projection(ItemClassification.LOST)
    found_item = build_projection(ItemClassification.FOUND)
    suggestion = build_suggestion(lost_item.id, found_item.id, status=MatchStatus.EXPIRED)
    session = FakeSession(suggestion, lost_item, found_item)

    monkeypatch.setattr(
        "app.services.matching_service.retrieve_match_suggestion",
        lambda _session, _match_id: suggestion,
    )

    with pytest.raises(InvalidMatchDecisionError, match="Match expirado"):
        accept_match(
            session,
            suggestion.id,
            MatchDecisionRequest(decided_by_user_id=uuid4()),
        )
