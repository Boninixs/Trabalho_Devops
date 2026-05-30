from datetime import date
from uuid import uuid4

import pytest


pytestmark = pytest.mark.integration


def build_item_payload(classification: str = "LOST") -> dict:
    return {
        "classification": classification,
        "title": "Carteira marrom",
        "description": "Carteira perdida no corredor central",
        "category": "Carteira",
        "color": "Marrom",
        "location_description": "Corredor central",
        "approximate_date": str(date(2026, 4, 10)),
        "reporter_user_id": str(uuid4()),
    }


def test_post_items_creates_item(integration_client) -> None:
    response = integration_client.post("/items", json=build_item_payload())

    assert response.status_code == 201
    payload = response.json()
    assert payload["classification"] == "LOST"
    assert payload["status"] == "AVAILABLE"
    assert payload["version"] == 1


def test_get_items_lists_and_filters(integration_client) -> None:
    integration_client.post("/items", json=build_item_payload("LOST"))
    integration_client.post("/items", json=build_item_payload("FOUND"))

    response = integration_client.get("/items", params={"classification": "FOUND"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["classification"] == "FOUND"


def test_get_item_by_id_returns_item(integration_client) -> None:
    create_response = integration_client.post("/items", json=build_item_payload())
    item_id = create_response.json()["id"]

    response = integration_client.get(f"/items/{item_id}")

    assert response.status_code == 200
    assert response.json()["id"] == item_id


def test_patch_item_updates_partial_fields(integration_client) -> None:
    create_response = integration_client.post("/items", json=build_item_payload())
    item_id = create_response.json()["id"]

    response = integration_client.patch(
        f"/items/{item_id}",
        json={"title": "Carteira marrom atualizada", "color": "Preta"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Carteira marrom atualizada"
    assert payload["color"] == "Preta"
    assert payload["version"] == 2


def test_patch_item_status_persists_history(integration_client) -> None:
    create_response = integration_client.post("/items", json=build_item_payload())
    item_id = create_response.json()["id"]

    status_response = integration_client.patch(
        f"/items/{item_id}/status",
        json={
            "status": "MATCHED",
            "reason": "Match confirmado",
            "actor_user_id": str(uuid4()),
        },
    )
    history_response = integration_client.get(f"/items/{item_id}/history")

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "MATCHED"
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) == 2
    assert history[-1]["to_status"] == "MATCHED"


def test_internal_recovery_endpoints_update_status(integration_client) -> None:
    lost_response = integration_client.post("/items", json=build_item_payload("LOST"))
    found_response = integration_client.post("/items", json=build_item_payload("FOUND"))
    lost_id = lost_response.json()["id"]
    found_id = found_response.json()["id"]

    lost_status = integration_client.patch(
        f"/items/{lost_id}/status",
        json={"status": "MATCHED", "reason": "Pré-match"},
    )
    found_status = integration_client.patch(
        f"/items/{found_id}/status",
        json={"status": "MATCHED", "reason": "Pré-match"},
    )

    open_response = integration_client.post(
        "/internal/recovery/open",
        json={"item_ids": [lost_id, found_id], "reason": "Caso aberto"},
    )
    cancel_response = integration_client.post(
        "/internal/recovery/cancel",
        json={
            "item_ids": [lost_id, found_id],
            "reason": "Caso cancelado",
            "target_status": "AVAILABLE",
        },
    )
    reopen_response = integration_client.post(
        "/internal/recovery/open",
        json={"item_ids": [lost_id, found_id], "reason": "Caso reaberto"},
    )
    complete_response = integration_client.post(
        "/internal/recovery/complete",
        json={"item_ids": [lost_id, found_id], "reason": "Caso concluído"},
    )

    assert lost_status.status_code == 200
    assert found_status.status_code == 200
    assert open_response.status_code == 200
    assert all(item["status"] == "IN_RECOVERY" for item in open_response.json()["items"])
    assert cancel_response.status_code == 200
    assert all(item["status"] == "AVAILABLE" for item in cancel_response.json()["items"])
    assert reopen_response.status_code == 200
    assert complete_response.status_code == 200
    assert all(item["status"] == "RECOVERED" for item in complete_response.json()["items"])

