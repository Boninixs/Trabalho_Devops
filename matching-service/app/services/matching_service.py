from datetime import datetime, timezone
import re
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    InvalidMatchDecisionError,
    InvalidMatchError,
    MatchNotFoundError,
)
from app.mappers.match_mapper import to_match_event_payload
from app.messaging.idempotency import has_been_processed, register_processed_event
from app.messaging.outbox import enqueue_broker_message
from app.messaging.topology import ROUTING_KEYS
from app.models.item_projection import ExternalItemStatus, ItemClassification, ItemProjection
from app.models.match_suggestion import MatchStatus, MatchSuggestion
from app.repositories.item_projection_repository import (
    add_item_projection,
    get_item_projection_by_id,
    get_item_projections_by_ids,
    list_candidate_item_projections,
)
from app.repositories.match_suggestion_repository import (
    add_match_suggestion,
    get_match_suggestion_by_id,
    get_match_suggestion_by_pair,
    list_match_suggestions as list_match_suggestions_repository,
    list_suggested_matches_for_item,
)
from app.schemas.events import BrokerMessage, EventEnvelope
from app.schemas.item_event import ItemCreatedEnvelope, ItemUpdatedEnvelope
from app.schemas.match import MatchDecisionRequest, MatchFilters

STOPWORDS = {
    "a",
    "o",
    "e",
    "de",
    "da",
    "do",
    "na",
    "no",
    "em",
    "um",
    "uma",
    "com",
    "para",
}
ELIGIBLE_ITEM_STATUSES = {ExternalItemStatus.AVAILABLE}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def list_match_suggestions(session: Session, filters: MatchFilters) -> list[MatchSuggestion]:
    return list_match_suggestions_repository(session, status=filters.status)


def retrieve_match_suggestion(session: Session, match_id: UUID) -> MatchSuggestion:
    suggestion = get_match_suggestion_by_id(session, match_id)
    if suggestion is None:
        raise MatchNotFoundError(f"Match {match_id} não encontrado")
    return suggestion


def consume_item_event(session: Session, envelope: EventEnvelope) -> list[MatchSuggestion]:
    typed_envelope = parse_item_event_envelope(envelope)

    if has_been_processed(session, typed_envelope):
        return []

    item_projection, is_newer_event = upsert_item_projection(session, typed_envelope)
    if is_newer_event:
        expire_invalid_matches_for_item(session, item_projection.id)
        if is_item_eligible(item_projection):
            generate_match_suggestions_for_item(session, item_projection)

    register_processed_event(session, typed_envelope)
    session.commit()
    return list_suggested_matches_for_item(session, item_projection.id)


def accept_match(
    session: Session,
    match_id: UUID,
    payload: MatchDecisionRequest,
) -> MatchSuggestion:
    suggestion = retrieve_match_suggestion(session, match_id)
    ensure_match_can_be_decided(session, suggestion)

    suggestion.status = MatchStatus.ACCEPTED
    suggestion.decided_by_user_id = payload.decided_by_user_id
    suggestion.updated_at = utc_now()
    session.flush()
    record_match_event(session, suggestion, event_type="MatchAccepted")
    session.commit()
    session.refresh(suggestion)
    return suggestion


def reject_match(
    session: Session,
    match_id: UUID,
    payload: MatchDecisionRequest,
) -> MatchSuggestion:
    suggestion = retrieve_match_suggestion(session, match_id)
    ensure_match_can_be_decided(session, suggestion)

    suggestion.status = MatchStatus.REJECTED
    suggestion.decided_by_user_id = payload.decided_by_user_id
    suggestion.updated_at = utc_now()
    session.flush()
    record_match_event(session, suggestion, event_type="MatchRejected")
    session.commit()
    session.refresh(suggestion)
    return suggestion


def parse_item_event_envelope(envelope: EventEnvelope) -> ItemCreatedEnvelope | ItemUpdatedEnvelope:
    payload = envelope.model_dump(mode="json")
    if envelope.event_type == "ItemCreated":
        return ItemCreatedEnvelope.model_validate(payload)
    if envelope.event_type == "ItemUpdated":
        return ItemUpdatedEnvelope.model_validate(payload)

    raise InvalidMatchError(f"Evento {envelope.event_type} não suportado pelo matching-service")


def upsert_item_projection(
    session: Session,
    envelope: ItemCreatedEnvelope | ItemUpdatedEnvelope,
) -> tuple[ItemProjection, bool]:
    existing = get_item_projection_by_id(session, envelope.aggregate_id)
    payload = envelope.payload

    if existing is not None and envelope.aggregate_version <= existing.version:
        return existing, False

    if existing is None:
        existing = ItemProjection(
            id=payload.id,
            classification=payload.classification,
            title=payload.title,
            description=payload.description,
            category=payload.category,
            color=payload.color,
            location_description=payload.location_description,
            approximate_date=payload.approximate_date,
            reporter_user_id=payload.reporter_user_id,
            status=payload.status,
            version=payload.version,
            created_at=payload.created_at,
            updated_at=payload.updated_at,
            last_event_id=envelope.event_id,
            last_seen_at=envelope.occurred_at,
        )
        add_item_projection(session, existing)
        session.flush()
        return existing, True

    existing.classification = payload.classification
    existing.title = payload.title
    existing.description = payload.description
    existing.category = payload.category
    existing.color = payload.color
    existing.location_description = payload.location_description
    existing.approximate_date = payload.approximate_date
    existing.reporter_user_id = payload.reporter_user_id
    existing.status = payload.status
    existing.version = payload.version
    existing.created_at = payload.created_at
    existing.updated_at = payload.updated_at
    existing.last_event_id = envelope.event_id
    existing.last_seen_at = envelope.occurred_at
    session.flush()
    return existing, True


def expire_invalid_matches_for_item(session: Session, item_id: UUID) -> None:
    suggestions = list_suggested_matches_for_item(session, item_id)
    related_ids = {item_id}
    for suggestion in suggestions:
        related_ids.add(suggestion.lost_item_id)
        related_ids.add(suggestion.found_item_id)

    projections = get_item_projections_by_ids(session, list(related_ids))
    projections_by_id = {projection.id: projection for projection in projections}

    for suggestion in suggestions:
        lost_item = projections_by_id.get(suggestion.lost_item_id)
        found_item = projections_by_id.get(suggestion.found_item_id)
        if lost_item is None or found_item is None or not is_match_candidate_pair(lost_item, found_item)[0]:
            suggestion.status = MatchStatus.EXPIRED
            suggestion.updated_at = utc_now()


def generate_match_suggestions_for_item(
    session: Session,
    item_projection: ItemProjection,
) -> None:
    candidate_classification = (
        ItemClassification.FOUND
        if item_projection.classification == ItemClassification.LOST
        else ItemClassification.LOST
    )
    candidates = list_candidate_item_projections(
        session,
        classification=candidate_classification,
        exclude_item_id=item_projection.id,
    )

    for candidate in candidates:
        lost_item, found_item = normalize_pair(item_projection, candidate)
        is_candidate, criteria_snapshot, score = is_match_candidate_pair(lost_item, found_item)
        if not is_candidate:
            existing = get_match_suggestion_by_pair(
                session,
                lost_item_id=lost_item.id,
                found_item_id=found_item.id,
            )
            if existing is not None and existing.status == MatchStatus.SUGGESTED:
                existing.status = MatchStatus.EXPIRED
                existing.updated_at = utc_now()
            continue

        existing = get_match_suggestion_by_pair(
            session,
            lost_item_id=lost_item.id,
            found_item_id=found_item.id,
        )
        if existing is None:
            suggestion = MatchSuggestion(
                id=uuid4(),
                lost_item_id=lost_item.id,
                found_item_id=found_item.id,
                score=score,
                criteria_snapshot_json=criteria_snapshot,
                status=MatchStatus.SUGGESTED,
                decided_by_user_id=None,
            )
            add_match_suggestion(session, suggestion)
            session.flush()
            record_match_event(session, suggestion, event_type="MatchSuggested")
            continue

        if existing.status == MatchStatus.SUGGESTED:
            existing.score = score
            existing.criteria_snapshot_json = criteria_snapshot
            existing.updated_at = utc_now()
            continue

        if existing.status == MatchStatus.EXPIRED:
            existing.status = MatchStatus.SUGGESTED
            existing.score = score
            existing.criteria_snapshot_json = criteria_snapshot
            existing.decided_by_user_id = None
            existing.updated_at = utc_now()
            session.flush()
            record_match_event(session, existing, event_type="MatchSuggested")


def normalize_pair(
    item_a: ItemProjection,
    item_b: ItemProjection,
) -> tuple[ItemProjection, ItemProjection]:
    if item_a.classification == ItemClassification.LOST:
        return item_a, item_b
    return item_b, item_a


def ensure_match_can_be_decided(session: Session, suggestion: MatchSuggestion) -> None:
    if suggestion.status == MatchStatus.REJECTED:
        raise InvalidMatchDecisionError("Match já foi rejeitado")
    if suggestion.status == MatchStatus.ACCEPTED:
        raise InvalidMatchDecisionError("Match já foi aceito")
    if suggestion.status == MatchStatus.EXPIRED:
        raise InvalidMatchDecisionError("Match expirado")

    lost_item = get_item_projection_by_id(session, suggestion.lost_item_id)
    found_item = get_item_projection_by_id(session, suggestion.found_item_id)
    is_candidate, _, _ = is_match_candidate_pair(lost_item, found_item)
    if not is_candidate:
        suggestion.status = MatchStatus.EXPIRED
        suggestion.updated_at = utc_now()
        session.flush()
        session.commit()
        raise InvalidMatchDecisionError("Match inelegível para decisão")


def is_item_eligible(item: ItemProjection | None) -> bool:
    if item is None:
        return False
    if item.status not in ELIGIBLE_ITEM_STATUSES:
        return False
    return item.classification in {ItemClassification.LOST, ItemClassification.FOUND}


def is_match_candidate_pair(
    lost_item: ItemProjection | None,
    found_item: ItemProjection | None,
) -> tuple[bool, dict, int]:
    if lost_item is None or found_item is None:
        return False, {"eligible": False, "reason": "missing_item_projection"}, 0
    if not is_item_eligible(lost_item) or not is_item_eligible(found_item):
        return False, {"eligible": False, "reason": "item_not_eligible"}, 0
    if lost_item.classification != ItemClassification.LOST or found_item.classification != ItemClassification.FOUND:
        return False, {"eligible": False, "reason": "pair_must_be_lost_and_found"}, 0

    same_category = normalize_value(lost_item.category) == normalize_value(found_item.category)
    if not same_category:
        return False, {"eligible": False, "reason": "category_mismatch"}, 0

    criteria_snapshot = {
        "category": {"matched": True, "weight": 40},
        "color": {"matched": False, "weight": 20},
        "location": {"matched": False, "weight": 15, "overlap": []},
        "date": {"matched": False, "weight": 15, "days_difference": None},
        "keywords": {"matched": False, "weight": 10, "overlap": []},
    }
    score = 40
    additional_matches = 0

    if normalize_value(lost_item.color) == normalize_value(found_item.color):
        criteria_snapshot["color"]["matched"] = True
        score += 20
        additional_matches += 1

    location_overlap = sorted(
        tokenize(lost_item.location_description) & tokenize(found_item.location_description),
    )
    if location_overlap:
        criteria_snapshot["location"]["matched"] = True
        criteria_snapshot["location"]["overlap"] = location_overlap
        score += 15
        additional_matches += 1

    days_difference = abs((lost_item.approximate_date - found_item.approximate_date).days)
    criteria_snapshot["date"]["days_difference"] = days_difference
    if days_difference <= 3:
        criteria_snapshot["date"]["matched"] = True
        score += 15
        additional_matches += 1
    elif days_difference <= 7:
        criteria_snapshot["date"]["matched"] = True
        score += 10
        additional_matches += 1

    keywords_overlap = sorted(
        tokenize(f"{lost_item.title} {lost_item.description}")
        & tokenize(f"{found_item.title} {found_item.description}"),
    )
    if keywords_overlap:
        criteria_snapshot["keywords"]["matched"] = True
        criteria_snapshot["keywords"]["overlap"] = keywords_overlap[:10]
        score += 10
        additional_matches += 1

    if additional_matches == 0:
        criteria_snapshot["eligible"] = False
        criteria_snapshot["reason"] = "missing_additional_criteria"
        criteria_snapshot["score"] = 0
        return False, criteria_snapshot, 0

    criteria_snapshot["eligible"] = True
    criteria_snapshot["score"] = score
    return True, criteria_snapshot, score


def normalize_value(value: str) -> str:
    return value.strip().lower()


def tokenize(value: str) -> set[str]:
    tokens = {
        token
        for token in re.findall(r"[a-zA-ZÀ-ÿ0-9]+", value.lower())
        if len(token) >= 3 and token not in STOPWORDS
    }
    return tokens


def record_match_event(session: Session, match: MatchSuggestion, *, event_type: str) -> None:
    routing_key_map = {
        "MatchSuggested": ROUTING_KEYS["match_suggested"],
        "MatchAccepted": ROUTING_KEYS["match_accepted"],
        "MatchRejected": ROUTING_KEYS["match_rejected"],
    }
    if event_type not in routing_key_map:
        raise InvalidMatchError(f"Evento {event_type} não suportado pelo matching-service")

    settings = get_settings()
    payload = to_match_event_payload(match)
    message = BrokerMessage(
        envelope=EventEnvelope(
            event_type=event_type,
            aggregate_id=match.id,
            aggregate_version=1,
            correlation_id=uuid4(),
            causation_id=None,
            payload=payload.model_dump(mode="json"),
        ),
        routing_key=routing_key_map[event_type],
        exchange_name=settings.rabbitmq_events_exchange,
    )
    enqueue_broker_message(session, message)
