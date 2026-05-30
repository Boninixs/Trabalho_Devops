from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import InvalidMatchDecisionError
from app.models.item_projection import ExternalItemStatus, ItemClassification, ItemProjection
from app.models.match_suggestion import MatchStatus, MatchSuggestion
from app.schemas.match import MatchDecisionRequest
from app.services.matching_service import (
    ensure_match_can_be_decided,
    is_match_candidate_pair,
    tokenize,
)


def build_projection(
    *,
    classification: ItemClassification,
    status: ExternalItemStatus = ExternalItemStatus.AVAILABLE,
    category: str = "Mochila",
    color: str = "Azul",
    location_description: str = "Biblioteca central",
    approximate_date: date = date(2026, 4, 10),
    title: str = "Mochila azul",
    description: str = "Mochila encontrada com caderno dentro",
) -> ItemProjection:
    now = datetime.now(timezone.utc)
    return ItemProjection(
        id=uuid4(),
        classification=classification,
        title=title,
        description=description,
        category=category,
        color=color,
        location_description=location_description,
        approximate_date=approximate_date,
        reporter_user_id=uuid4(),
        status=status,
        version=1,
        created_at=now,
        updated_at=now,
        last_event_id=uuid4(),
        last_seen_at=now,
    )


def test_matching_only_allows_lost_and_found_pairs() -> None:
    lost_item = build_projection(classification=ItemClassification.LOST)
    another_lost = build_projection(classification=ItemClassification.LOST)

    is_candidate, criteria, score = is_match_candidate_pair(lost_item, another_lost)

    assert is_candidate is False
    assert criteria["reason"] == "pair_must_be_lost_and_found"
    assert score == 0


def test_matching_requires_same_category_and_one_extra_criterion() -> None:
    lost_item = build_projection(classification=ItemClassification.LOST)
    found_item = build_projection(
        classification=ItemClassification.FOUND,
        color="Azul",
    )

    is_candidate, criteria, score = is_match_candidate_pair(lost_item, found_item)

    assert is_candidate is True
    assert criteria["category"]["matched"] is True
    assert criteria["color"]["matched"] is True
    assert score >= 60


def test_matching_rejects_invalid_pairs_without_additional_criteria() -> None:
    lost_item = build_projection(
        classification=ItemClassification.LOST,
        color="Preto",
        location_description="Laboratório 1",
        approximate_date=date(2026, 4, 1),
        title="Óculos de grau",
        description="Óculos deixados no laboratório",
    )
    found_item = build_projection(
        classification=ItemClassification.FOUND,
        color="Vermelho",
        location_description="Auditório",
        approximate_date=date(2026, 4, 20),
        title="Chaveiro vermelho",
        description="Pequeno chaveiro metálico sem relação com o item perdido",
    )

    is_candidate, criteria, score = is_match_candidate_pair(lost_item, found_item)

    assert is_candidate is False
    assert criteria["reason"] == "missing_additional_criteria"
    assert score == 0


def test_matching_excludes_cancelled_or_closed_items() -> None:
    lost_item = build_projection(
        classification=ItemClassification.LOST,
        status=ExternalItemStatus.CANCELLED,
    )
    found_item = build_projection(classification=ItemClassification.FOUND)

    is_candidate, criteria, score = is_match_candidate_pair(lost_item, found_item)

    assert is_candidate is False
    assert criteria["reason"] == "item_not_eligible"
    assert score == 0


def test_tokenize_extracts_relevant_keywords() -> None:
    tokens = tokenize("Mochila azul encontrada na biblioteca central com notebook")

    assert "mochila" in tokens
    assert "biblioteca" in tokens
    assert "com" not in tokens


def test_invalid_decision_when_match_already_rejected() -> None:
    suggestion = MatchSuggestion(
        id=uuid4(),
        lost_item_id=uuid4(),
        found_item_id=uuid4(),
        score=70,
        criteria_snapshot_json={},
        status=MatchStatus.REJECTED,
        decided_by_user_id=uuid4(),
    )

    with pytest.raises(InvalidMatchDecisionError, match="já foi rejeitado"):
        ensure_match_can_be_decided(FakeDecisionSession(), suggestion)


class FakeDecisionSession:
    def get(self, *_args, **_kwargs):
        return None
