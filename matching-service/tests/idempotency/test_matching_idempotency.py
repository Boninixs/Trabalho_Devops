""""
Esse arquivo é responsável por testar a idempotência do processamento de eventos no serviço de matching. 
"""
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.models.match_suggestion import MatchStatus
from app.repositories.match_suggestion_repository import list_match_suggestions
from app.schemas.events import EventEnvelope
from app.services.matching_service import consume_item_event


pytestmark = pytest.mark.idempotency


def build_event(*, event_id: str, aggregate_id: str, classification: str, version: int = 1) -> EventEnvelope:
    """"
    Função auxiliar para construir um EventEnvelope com os campos preenchidos para os testes de idempotência.
    args:
        event_id: O ID do evento.
        aggregate_id: O ID do agregado.
        classification: A classificação do item.
        version: A versão do evento.
    returns:
        Um objeto EventEnvelope com os campos preenchidos.
    """
    now = datetime.now(timezone.utc)
    return EventEnvelope.model_validate(
        {
            "event_id": event_id,
            "event_type": "ItemCreated",
            "aggregate_id": aggregate_id,
            "aggregate_version": version,
            "occurred_at": now.isoformat(),
            "correlation_id": str(uuid4()),
            "causation_id": None,
            "payload": {
                "id": aggregate_id,
                "classification": classification,
                "title": "Bolsa preta",
                "description": "Bolsa preta encontrada",
                "category": "Bolsa",
                "color": "Preta",
                "location_description": "Recepção principal",
                "approximate_date": str(date(2026, 4, 10)),
                "reporter_user_id": str(uuid4()),
                "status": "AVAILABLE",
                "version": version,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        },
    )


def test_reprocessing_same_event_does_not_duplicate_effects(postgres_session) -> None:
    """
    Testa que o reprocessamento do mesmo evento não cria efeitos duplicados.
    """
    lost_id = str(uuid4())
    found_id = str(uuid4())
    lost_event = build_event(event_id=str(uuid4()), aggregate_id=lost_id, classification="LOST")
    found_event = build_event(event_id=str(uuid4()), aggregate_id=found_id, classification="FOUND")

    consume_item_event(postgres_session, lost_event)
    consume_item_event(postgres_session, found_event)
    consume_item_event(postgres_session, found_event)

    matches = list_match_suggestions(postgres_session, status=MatchStatus.SUGGESTED)
    assert len(matches) == 1


def test_duplicate_pair_is_not_created_twice(postgres_session) -> None:
    """
    Testa que o processamento de eventos que atualizam um item não cria pares de match duplicados.
    """
    lost_id = str(uuid4())
    found_id = str(uuid4())
    consume_item_event(
        postgres_session,
        build_event(event_id=str(uuid4()), aggregate_id=lost_id, classification="LOST"),
    )
    consume_item_event(
        postgres_session,
        build_event(event_id=str(uuid4()), aggregate_id=found_id, classification="FOUND"),
    )
    consume_item_event(
        postgres_session,
        EventEnvelope.model_validate(
            {
                **build_event(
                    event_id=str(uuid4()),
                    aggregate_id=found_id,
                    classification="FOUND",
                    version=2,
                ).model_dump(mode="json"),
                "event_type": "ItemUpdated",
            },
        ),
    )

    matches = list_match_suggestions(postgres_session, status=MatchStatus.SUGGESTED)
    assert len(matches) == 1
