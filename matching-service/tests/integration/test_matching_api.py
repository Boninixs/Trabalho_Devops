"""
Esse arquivo é responsável por testar a integração do serviço de matching.
"""
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.models.match_suggestion import MatchStatus
from app.repositories.match_suggestion_repository import list_match_suggestions
from app.schemas.events import EventEnvelope
from app.services.matching_service import consume_item_event


pytestmark = pytest.mark.integration


def build_item_event(*, event_type: str, item_id, classification: str, status: str = "AVAILABLE", version: int = 1):
    """"
    Função auxiliar para construir um EventEnvelope representando um evento de item criado ou atualizado.
    args:
        event_type: O tipo do evento.
        item_id: O ID do item relacionado ao evento.
        classification: A classificação do item.
        status: O status do item.
        version: A versão do evento.
    returns:
        Um objeto EventEnvelope com os campos preenchidos.
    """
    now = datetime.now(timezone.utc)
    return EventEnvelope.model_validate(
        {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "aggregate_id": str(item_id),
            "aggregate_version": version,
            "occurred_at": now.isoformat(),
            "correlation_id": str(uuid4()),
            "causation_id": None,
            "payload": {
                "id": str(item_id),
                "classification": classification,
                "title": "Mochila azul",
                "description": "Mochila azul encontrada com caderno",
                "category": "Mochila",
                "color": "Azul",
                "location_description": "Biblioteca central",
                "approximate_date": str(date(2026, 4, 10)),
                "reporter_user_id": str(uuid4()),
                "status": status,
                "version": version,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        },
    )


def test_consume_item_created_persists_suggestion(postgres_session) -> None:
    """
    Testa que o consumo de um evento de item criado persiste uma sugestão de match.
    """
    lost_id = uuid4()
    found_id = uuid4()

    consume_item_event(
        postgres_session,
        build_item_event(event_type="ItemCreated", item_id=lost_id, classification="LOST"),
    )
    consume_item_event(
        postgres_session,
        build_item_event(event_type="ItemCreated", item_id=found_id, classification="FOUND"),
    )

    matches = list_match_suggestions(postgres_session, status=MatchStatus.SUGGESTED)
    assert len(matches) == 1
    assert matches[0].lost_item_id == lost_id
    assert matches[0].found_item_id == found_id


def test_consume_item_updated_expires_match(postgres_session) -> None:
    """
    Testa que o consumo de um evento de item atualizado com status CANCELLED expira a sugestão de match.
    """
    lost_id = uuid4()
    found_id = uuid4()
    consume_item_event(
        postgres_session,
        build_item_event(event_type="ItemCreated", item_id=lost_id, classification="LOST"),
    )
    consume_item_event(
        postgres_session,
        build_item_event(event_type="ItemCreated", item_id=found_id, classification="FOUND"),
    )

    consume_item_event(
        postgres_session,
        build_item_event(
            event_type="ItemUpdated",
            item_id=found_id,
            classification="FOUND",
            status="CANCELLED",
            version=2,
        ),
    )

    matches = list_match_suggestions(postgres_session, status=None)
    assert len(matches) == 1
    assert matches[0].status == MatchStatus.EXPIRED


def test_match_endpoints_query_and_decide(integration_client, postgres_session) -> None:
    """
    Testa os endpoints de listagem, consulta e decisão de matches.
    """
    lost_id = uuid4()
    found_id = uuid4()
    consume_item_event(
        postgres_session,
        build_item_event(event_type="ItemCreated", item_id=lost_id, classification="LOST"),
    )
    consume_item_event(
        postgres_session,
        build_item_event(event_type="ItemCreated", item_id=found_id, classification="FOUND"),
    )
    match = list_match_suggestions(postgres_session, status=MatchStatus.SUGGESTED)[0]

    list_response = integration_client.get("/matches")
    get_response = integration_client.get(f"/matches/{match.id}")
    accept_response = integration_client.post(
        f"/matches/{match.id}/accept",
        json={"decided_by_user_id": str(uuid4())},
    )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert get_response.status_code == 200
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "ACCEPTED"
