from __future__ import annotations

from uuid import uuid4

import pytest

from tests.e2e.conftest import (
    count_processed_events,
    create_item,
    fetch_outbox_event,
    get_item,
    list_matches,
    list_recovery_cases,
    make_headers,
    patch_item,
    patch_item_status,
    publish_duplicate_outbox_event,
    register_and_login,
    wait_until,
    wait_for_item_status,
    wait_for_match,
    wait_for_no_match,
    wait_for_outbox_status,
    wait_for_recovery_case,
)


pytestmark = pytest.mark.e2e


def test_gateway_auth_and_internal_routes(gateway_client) -> None:
    me_without_token = gateway_client.get("/api/auth/me")
    me_invalid_token = gateway_client.get(
        "/api/auth/me",
        headers=make_headers("invalid-token"),
    )
    internal_route = gateway_client.post(
        "/api/internal/recovery/open",
        json={"item_ids": [str(uuid4())]},
    )

    suffix = str(uuid4())
    correlation_id = f"corr-{suffix}"
    user, token = register_and_login(gateway_client, suffix=suffix)
    me_valid_token = gateway_client.get(
        "/api/auth/me",
        headers=make_headers(token, correlation_id=correlation_id),
    )

    assert me_without_token.status_code == 401
    assert me_invalid_token.status_code == 401
    assert internal_route.status_code == 404
    assert me_valid_token.status_code == 200
    assert me_valid_token.json()["id"] == user["id"]
    assert me_valid_token.headers["X-Correlation-ID"] == correlation_id


def test_full_flow_through_gateway_with_cancel_reopen_and_complete(gateway_client, e2e_settings) -> None:
    suffix = str(uuid4())
    user, token = register_and_login(gateway_client, suffix=suffix)
    category = f"E2E-Bag-{suffix}"

    lost_item = create_item(
        gateway_client,
        token=token,
        classification="LOST",
        reporter_user_id=user["id"],
        category=category,
        title=f"Mochila perdida {suffix}",
        description="Mochila azul com caderno e garrafa",
    )
    found_item = create_item(
        gateway_client,
        token=token,
        classification="FOUND",
        reporter_user_id=user["id"],
        category=category,
        title=f"Mochila encontrada {suffix}",
        description="Mochila azul com caderno e garrafa encontrada na biblioteca",
    )
    wait_for_outbox_status(
        e2e_settings.item_db_url,
        event_type="ItemCreated",
        aggregate_id=lost_item["id"],
        status="PUBLISHED",
        settings=e2e_settings,
    )
    wait_for_outbox_status(
        e2e_settings.item_db_url,
        event_type="ItemCreated",
        aggregate_id=found_item["id"],
        status="PUBLISHED",
        settings=e2e_settings,
    )

    match_one = wait_for_match(
        gateway_client,
        token=token,
        lost_item_id=lost_item["id"],
        found_item_id=found_item["id"],
        status="SUGGESTED",
        settings=e2e_settings,
    )
    wait_for_outbox_status(
        e2e_settings.matching_db_url,
        event_type="MatchSuggested",
        aggregate_id=match_one["id"],
        status="PUBLISHED",
        settings=e2e_settings,
    )
    match_detail = gateway_client.get(f"/api/matches/{match_one['id']}", headers=make_headers(token))
    accept_response = gateway_client.post(
        f"/api/matches/{match_one['id']}/accept",
        headers=make_headers(token),
        json={"decided_by_user_id": user["id"]},
    )

    assert match_detail.status_code == 200
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "ACCEPTED"
    wait_for_outbox_status(
        e2e_settings.matching_db_url,
        event_type="MatchAccepted",
        aggregate_id=match_one["id"],
        status="PUBLISHED",
        settings=e2e_settings,
    )

    recovery_case_one = wait_for_recovery_case(
        gateway_client,
        token=token,
        match_id=match_one["id"],
        status="IN_PROGRESS",
        settings=e2e_settings,
    )
    wait_for_outbox_status(
        e2e_settings.recovery_db_url,
        event_type="RecoveryCaseOpened",
        aggregate_id=recovery_case_one["id"],
        status="PUBLISHED",
        settings=e2e_settings,
    )
    recovery_case_detail = gateway_client.get(
        f"/api/recovery-cases/{recovery_case_one['id']}",
        headers=make_headers(token),
    )
    assert recovery_case_detail.status_code == 200
    assert recovery_case_detail.json()["match_id"] == match_one["id"]

    wait_for_item_status(
        gateway_client,
        token=token,
        item_id=lost_item["id"],
        status="IN_RECOVERY",
        settings=e2e_settings,
    )
    wait_for_item_status(
        gateway_client,
        token=token,
        item_id=found_item["id"],
        status="IN_RECOVERY",
        settings=e2e_settings,
    )

    cancel_response = gateway_client.post(
        f"/api/recovery-cases/{recovery_case_one['id']}/cancel",
        headers=make_headers(token),
        json={
            "actor_user_id": user["id"],
            "reason": "Fluxo cancelado para reabertura controlada",
            "target_status": "AVAILABLE",
        },
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "CANCELLED"
    wait_for_outbox_status(
        e2e_settings.recovery_db_url,
        event_type="RecoveryCaseCancelled",
        aggregate_id=recovery_case_one["id"],
        status="PUBLISHED",
        settings=e2e_settings,
    )

    wait_for_item_status(
        gateway_client,
        token=token,
        item_id=lost_item["id"],
        status="AVAILABLE",
        settings=e2e_settings,
    )
    wait_for_item_status(
        gateway_client,
        token=token,
        item_id=found_item["id"],
        status="AVAILABLE",
        settings=e2e_settings,
    )

    second_found_item = create_item(
        gateway_client,
        token=token,
        classification="FOUND",
        reporter_user_id=user["id"],
        category=category,
        title=f"Segunda mochila encontrada {suffix}",
        description="Mochila azul com caderno e garrafa para segundo fluxo",
    )
    match_two = wait_for_match(
        gateway_client,
        token=token,
        lost_item_id=lost_item["id"],
        found_item_id=second_found_item["id"],
        status="SUGGESTED",
        settings=e2e_settings,
    )

    accept_second = gateway_client.post(
        f"/api/matches/{match_two['id']}/accept",
        headers=make_headers(token),
        json={"decided_by_user_id": user["id"]},
    )
    assert accept_second.status_code == 200
    assert accept_second.json()["status"] == "ACCEPTED"
    wait_for_outbox_status(
        e2e_settings.matching_db_url,
        event_type="MatchAccepted",
        aggregate_id=match_two["id"],
        status="PUBLISHED",
        settings=e2e_settings,
    )

    recovery_case_two = wait_for_recovery_case(
        gateway_client,
        token=token,
        match_id=match_two["id"],
        status="IN_PROGRESS",
        settings=e2e_settings,
    )
    wait_for_outbox_status(
        e2e_settings.recovery_db_url,
        event_type="RecoveryCaseOpened",
        aggregate_id=recovery_case_two["id"],
        status="PUBLISHED",
        settings=e2e_settings,
    )

    complete_response = gateway_client.post(
        f"/api/recovery-cases/{recovery_case_two['id']}/complete",
        headers=make_headers(token),
        json={"actor_user_id": user["id"], "reason": "Entrega concluída com sucesso"},
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "COMPLETED"
    wait_for_outbox_status(
        e2e_settings.recovery_db_url,
        event_type="RecoveryCaseCompleted",
        aggregate_id=recovery_case_two["id"],
        status="PUBLISHED",
        settings=e2e_settings,
    )

    final_lost_item = wait_for_item_status(
        gateway_client,
        token=token,
        item_id=lost_item["id"],
        status="RECOVERED",
        settings=e2e_settings,
    )
    final_found_item = wait_for_item_status(
        gateway_client,
        token=token,
        item_id=second_found_item["id"],
        status="RECOVERED",
        settings=e2e_settings,
    )
    first_found_after_cancel = get_item(gateway_client, token=token, item_id=found_item["id"])

    assert final_lost_item["status"] == "RECOVERED"
    assert final_found_item["status"] == "RECOVERED"
    assert first_found_after_cancel["status"] == "AVAILABLE"


def test_duplicate_matchaccepted_reprocessing_does_not_duplicate_case(gateway_client, e2e_settings) -> None:
    suffix = str(uuid4())
    user, token = register_and_login(gateway_client, suffix=suffix)
    category = f"E2E-Duplicate-Event-{suffix}"

    lost_item = create_item(
        gateway_client,
        token=token,
        classification="LOST",
        reporter_user_id=user["id"],
        category=category,
        title=f"Carteira perdida {suffix}",
        description="Carteira preta com documentos",
        color="Preta",
    )
    found_item = create_item(
        gateway_client,
        token=token,
        classification="FOUND",
        reporter_user_id=user["id"],
        category=category,
        title=f"Carteira encontrada {suffix}",
        description="Carteira preta com documentos encontrada na recepção",
        color="Preta",
    )

    match = wait_for_match(
        gateway_client,
        token=token,
        lost_item_id=lost_item["id"],
        found_item_id=found_item["id"],
        status="SUGGESTED",
        settings=e2e_settings,
    )
    accept_response = gateway_client.post(
        f"/api/matches/{match['id']}/accept",
        headers=make_headers(token),
        json={"decided_by_user_id": user["id"]},
    )
    assert accept_response.status_code == 200

    wait_for_recovery_case(
        gateway_client,
        token=token,
        match_id=match["id"],
        status="IN_PROGRESS",
        settings=e2e_settings,
    )

    outbox_event = fetch_outbox_event(
        e2e_settings.matching_db_url,
        event_type="MatchAccepted",
        aggregate_id=match["id"],
    )
    publish_duplicate_outbox_event(e2e_settings, outbox_event)

    cases = wait_until(
        lambda: list_recovery_cases(gateway_client, token=token, match_id=match["id"]),
        timeout_seconds=e2e_settings.wait_timeout_seconds,
        interval_seconds=e2e_settings.poll_interval_seconds,
        description=f"caso único para match {match['id']}",
    )
    assert len(cases) == 1
    assert count_processed_events(
        e2e_settings.recovery_db_url,
        aggregate_id=match["id"],
        event_id=outbox_event["event_id"],
    ) == 1


def test_duplicate_match_pair_is_not_created_for_same_lost_and_found(gateway_client, e2e_settings) -> None:
    suffix = str(uuid4())
    user, token = register_and_login(gateway_client, suffix=suffix)
    category = f"E2E-Duplicate-Match-{suffix}"

    lost_item = create_item(
        gateway_client,
        token=token,
        classification="LOST",
        reporter_user_id=user["id"],
        category=category,
        title=f"Notebook perdido {suffix}",
        description="Notebook prata com adesivo azul",
        color="Prata",
    )
    found_item = create_item(
        gateway_client,
        token=token,
        classification="FOUND",
        reporter_user_id=user["id"],
        category=category,
        title=f"Notebook encontrado {suffix}",
        description="Notebook prata com adesivo azul encontrado na biblioteca",
        color="Prata",
    )

    wait_for_match(
        gateway_client,
        token=token,
        lost_item_id=lost_item["id"],
        found_item_id=found_item["id"],
        status="SUGGESTED",
        settings=e2e_settings,
    )
    patch_item(
        gateway_client,
        token=token,
        item_id=found_item["id"],
        payload={"description": "Notebook prata com adesivo azul e carregador encontrado na biblioteca"},
    )

    def predicate():
        matches = [
            match
            for match in list_matches(gateway_client, token=token)
            if match["lost_item_id"] == lost_item["id"] and match["found_item_id"] == found_item["id"]
        ]
        if len(matches) == 1:
            return matches
        return None

    pair_matches = wait_until(
        predicate,
        timeout_seconds=e2e_settings.wait_timeout_seconds,
        interval_seconds=e2e_settings.poll_interval_seconds,
        description=f"match único para pair LOST={lost_item['id']} FOUND={found_item['id']}",
    )
    assert len(pair_matches) == 1


def test_found_cannot_have_more_than_one_active_case(gateway_client, e2e_settings) -> None:
    suffix = str(uuid4())
    user, token = register_and_login(gateway_client, suffix=suffix)
    category = f"E2E-Active-Case-{suffix}"

    lost_one = create_item(
        gateway_client,
        token=token,
        classification="LOST",
        reporter_user_id=user["id"],
        category=category,
        title=f"Celular perdido 1 {suffix}",
        description="Celular preto com capa azul",
        color="Preto",
    )
    lost_two = create_item(
        gateway_client,
        token=token,
        classification="LOST",
        reporter_user_id=user["id"],
        category=category,
        title=f"Celular perdido 2 {suffix}",
        description="Celular preto com capa azul e chaveiro",
        color="Preto",
    )
    found_item = create_item(
        gateway_client,
        token=token,
        classification="FOUND",
        reporter_user_id=user["id"],
        category=category,
        title=f"Celular encontrado {suffix}",
        description="Celular preto com capa azul encontrado no corredor",
        color="Preto",
    )

    first_match = wait_for_match(
        gateway_client,
        token=token,
        lost_item_id=lost_one["id"],
        found_item_id=found_item["id"],
        status="SUGGESTED",
        settings=e2e_settings,
    )
    second_match = wait_for_match(
        gateway_client,
        token=token,
        lost_item_id=lost_two["id"],
        found_item_id=found_item["id"],
        status="SUGGESTED",
        settings=e2e_settings,
    )

    accept_first = gateway_client.post(
        f"/api/matches/{first_match['id']}/accept",
        headers=make_headers(token),
        json={"decided_by_user_id": user["id"]},
    )
    assert accept_first.status_code == 200

    active_case = wait_for_recovery_case(
        gateway_client,
        token=token,
        match_id=first_match["id"],
        status="IN_PROGRESS",
        settings=e2e_settings,
    )
    assert active_case["found_item_id"] == found_item["id"]

    def second_match_expired():
        response = gateway_client.get(
            f"/api/matches/{second_match['id']}",
            headers=make_headers(token),
        )
        assert response.status_code == 200, response.text
        if response.json()["status"] == "EXPIRED":
            return response.json()
        return None

    wait_until(
        second_match_expired,
        timeout_seconds=e2e_settings.wait_timeout_seconds,
        interval_seconds=e2e_settings.poll_interval_seconds,
        description=f"expiração do match {second_match['id']}",
    )

    accept_second = gateway_client.post(
        f"/api/matches/{second_match['id']}/accept",
        headers=make_headers(token),
        json={"decided_by_user_id": user["id"]},
    )
    assert accept_second.status_code == 400

    active_cases_for_found = list_recovery_cases(
        gateway_client,
        token=token,
        found_item_id=found_item["id"],
    )
    assert len([case for case in active_cases_for_found if case["status"] == "IN_PROGRESS"]) == 1


@pytest.mark.parametrize("terminal_status", ["CANCELLED", "CLOSED"])
def test_terminal_items_do_not_participate_in_matching(gateway_client, e2e_settings, terminal_status: str) -> None:
    suffix = str(uuid4())
    user, token = register_and_login(gateway_client, suffix=f"{terminal_status.lower()}-{suffix}")
    category = f"E2E-Terminal-{terminal_status}-{suffix}"

    terminal_item = create_item(
        gateway_client,
        token=token,
        classification="FOUND",
        reporter_user_id=user["id"],
        category=category,
        title=f"Item terminal {suffix}",
        description="Item terminal com identificação visual",
        color="Verde",
    )
    patch_item_status(
        gateway_client,
        token=token,
        item_id=terminal_item["id"],
        status=terminal_status,
        reason=f"Marcado como {terminal_status} para teste E2E",
    )
    lost_item = create_item(
        gateway_client,
        token=token,
        classification="LOST",
        reporter_user_id=user["id"],
        category=category,
        title=f"Item perdido {suffix}",
        description="Item verde com identificação visual",
        color="Verde",
    )

    wait_for_no_match(
        gateway_client,
        token=token,
        lost_item_id=lost_item["id"],
        found_item_id=terminal_item["id"],
        settings=e2e_settings,
    )
