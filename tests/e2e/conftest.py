from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
import json
import os
import time
from uuid import uuid4

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
import httpx
import psycopg
from psycopg.rows import dict_row
import pytest


@dataclass(frozen=True)
class E2ESettings:
    gateway_url: str
    rabbitmq_url: str
    item_db_url: str
    matching_db_url: str
    recovery_db_url: str
    wait_timeout_seconds: float
    poll_interval_seconds: float


def build_postgres_dsn(*, db_name: str, user: str, password: str, port: str) -> str:
    return f"postgresql://{user}:{password}@localhost:{port}/{db_name}"


def get_e2e_settings() -> E2ESettings:
    gateway_port = os.getenv("GATEWAY_HTTP_PORT", "8000")
    return E2ESettings(
        gateway_url=os.getenv("E2E_GATEWAY_URL", f"http://localhost:{gateway_port}"),
        rabbitmq_url=os.getenv("E2E_RABBITMQ_URL", "amqp://app:app@localhost:5672/"),
        item_db_url=os.getenv(
            "E2E_ITEM_DB_URL",
            build_postgres_dsn(
                db_name=os.getenv("ITEM_DB_NAME", "item_service"),
                user=os.getenv("ITEM_DB_USER", "postgres"),
                password=os.getenv("ITEM_DB_PASSWORD", "postgres"),
                port=os.getenv("ITEM_DB_PORT", "5434"),
            ),
        ),
        matching_db_url=os.getenv(
            "E2E_MATCHING_DB_URL",
            build_postgres_dsn(
                db_name=os.getenv("MATCHING_DB_NAME", "matching_service"),
                user=os.getenv("MATCHING_DB_USER", "postgres"),
                password=os.getenv("MATCHING_DB_PASSWORD", "postgres"),
                port=os.getenv("MATCHING_DB_PORT", "5435"),
            ),
        ),
        recovery_db_url=os.getenv(
            "E2E_RECOVERY_DB_URL",
            build_postgres_dsn(
                db_name=os.getenv("RECOVERY_DB_NAME", "recovery_case_service"),
                user=os.getenv("RECOVERY_DB_USER", "postgres"),
                password=os.getenv("RECOVERY_DB_PASSWORD", "postgres"),
                port=os.getenv("RECOVERY_DB_PORT", "5436"),
            ),
        ),
        wait_timeout_seconds=float(os.getenv("E2E_WAIT_TIMEOUT_SECONDS", "60")),
        poll_interval_seconds=float(os.getenv("E2E_POLL_INTERVAL_SECONDS", "1")),
    )


def wait_until(predicate, *, timeout_seconds: float, interval_seconds: float, description: str):
    deadline = time.time() + timeout_seconds
    last_value = None
    while time.time() < deadline:
        last_value = predicate()
        if last_value:
            return last_value
        time.sleep(interval_seconds)
    raise AssertionError(f"Tempo esgotado aguardando: {description}")


def make_headers(token: str | None = None, *, correlation_id: str | None = None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
    return headers


def register_and_login(client: httpx.Client, *, suffix: str) -> tuple[dict, str]:
    register_payload = {
        "full_name": f"E2E User {suffix}",
        "email": f"e2e-{suffix}@example.com",
        "password": "Password123",
    }
    register_response = client.post("/api/auth/register", json=register_payload)
    assert register_response.status_code == 201, register_response.text

    login_response = client.post(
        "/api/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["access_token"]
    return register_response.json(), token


def create_item(
    client: httpx.Client,
    *,
    token: str,
    classification: str,
    reporter_user_id: str,
    category: str,
    title: str,
    description: str,
    color: str = "Azul",
    location_description: str = "Biblioteca central",
    approximate_date: str = "2026-04-10",
) -> dict:
    response = client.post(
        "/api/items",
        headers=make_headers(token),
        json={
            "classification": classification,
            "title": title,
            "description": description,
            "category": category,
            "color": color,
            "location_description": location_description,
            "approximate_date": approximate_date,
            "reporter_user_id": reporter_user_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def patch_item_status(client: httpx.Client, *, token: str, item_id: str, status: str, reason: str) -> dict:
    response = client.patch(
        f"/api/items/{item_id}/status",
        headers=make_headers(token),
        json={"status": status, "reason": reason},
    )
    assert response.status_code == 200, response.text
    return response.json()


def patch_item(client: httpx.Client, *, token: str, item_id: str, payload: dict) -> dict:
    response = client.patch(
        f"/api/items/{item_id}",
        headers=make_headers(token),
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def get_item(client: httpx.Client, *, token: str, item_id: str) -> dict:
    response = client.get(f"/api/items/{item_id}", headers=make_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


def list_matches(client: httpx.Client, *, token: str, status: str | None = None) -> list[dict]:
    params = {"status": status} if status else None
    response = client.get("/api/matches", headers=make_headers(token), params=params)
    assert response.status_code == 200, response.text
    return response.json()


def list_recovery_cases(client: httpx.Client, *, token: str, **params) -> list[dict]:
    response = client.get("/api/recovery-cases", headers=make_headers(token), params=params or None)
    assert response.status_code == 200, response.text
    return response.json()


def wait_for_match(
    client: httpx.Client,
    *,
    token: str,
    lost_item_id: str,
    found_item_id: str,
    status: str,
    settings: E2ESettings,
) -> dict:
    def predicate():
        for match in list_matches(client, token=token, status=status):
            if match["lost_item_id"] == lost_item_id and match["found_item_id"] == found_item_id:
                return match
        return None

    return wait_until(
        predicate,
        timeout_seconds=settings.wait_timeout_seconds,
        interval_seconds=settings.poll_interval_seconds,
        description=f"match {status} para LOST={lost_item_id} FOUND={found_item_id}",
    )


def wait_for_no_match(
    client: httpx.Client,
    *,
    token: str,
    lost_item_id: str,
    found_item_id: str,
    settings: E2ESettings,
) -> None:
    deadline = time.time() + settings.wait_timeout_seconds
    while time.time() < deadline:
        for match in list_matches(client, token=token):
            if match["lost_item_id"] == lost_item_id and match["found_item_id"] == found_item_id:
                raise AssertionError(
                    f"Match indevido encontrado para LOST={lost_item_id} FOUND={found_item_id}",
                )
        time.sleep(settings.poll_interval_seconds)


def wait_for_recovery_case(
    client: httpx.Client,
    *,
    token: str,
    match_id: str,
    status: str,
    settings: E2ESettings,
) -> dict:
    def predicate():
        for recovery_case in list_recovery_cases(client, token=token, match_id=match_id):
            if recovery_case["status"] == status:
                return recovery_case
        return None

    return wait_until(
        predicate,
        timeout_seconds=settings.wait_timeout_seconds,
        interval_seconds=settings.poll_interval_seconds,
        description=f"recovery case {status} para match={match_id}",
    )


def wait_for_item_status(
    client: httpx.Client,
    *,
    token: str,
    item_id: str,
    status: str,
    settings: E2ESettings,
) -> dict:
    def predicate():
        item = get_item(client, token=token, item_id=item_id)
        if item["status"] == status:
            return item
        return None

    return wait_until(
        predicate,
        timeout_seconds=settings.wait_timeout_seconds,
        interval_seconds=settings.poll_interval_seconds,
        description=f"item {item_id} com status {status}",
    )


def fetch_outbox_event(db_url: str, *, event_type: str, aggregate_id: str) -> dict:
    with psycopg.connect(db_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id::text AS event_id,
                    event_type,
                    aggregate_id::text AS aggregate_id,
                    aggregate_version,
                    occurred_at,
                    correlation_id::text AS correlation_id,
                    causation_id::text AS causation_id,
                    payload,
                    routing_key,
                    exchange_name,
                    status
                FROM outbox_events
                WHERE event_type = %s
                  AND aggregate_id = %s::uuid
                ORDER BY occurred_at DESC
                LIMIT 1
                """,
                (event_type, aggregate_id),
            )
            row = cursor.fetchone()
            assert row is not None, f"Evento {event_type} não encontrado no outbox para aggregate_id={aggregate_id}"
            return row


def wait_for_outbox_status(
    db_url: str,
    *,
    event_type: str,
    aggregate_id: str,
    status: str,
    settings: E2ESettings,
) -> dict:
    def predicate():
        try:
            event = fetch_outbox_event(
                db_url,
                event_type=event_type,
                aggregate_id=aggregate_id,
            )
        except AssertionError:
            return None
        if event["status"] == status:
            return event
        return None

    return wait_until(
        predicate,
        timeout_seconds=settings.wait_timeout_seconds,
        interval_seconds=settings.poll_interval_seconds,
        description=f"evento {event_type} com status {status} para aggregate_id={aggregate_id}",
    )


def count_processed_events(db_url: str, *, aggregate_id: str, event_id: str) -> int:
    with psycopg.connect(db_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM processed_events
                WHERE aggregate_id = %s::uuid
                  AND event_id = %s::uuid
                """,
                (aggregate_id, event_id),
            )
            return cursor.fetchone()[0]


async def _publish_duplicate_event(
    rabbitmq_url: str,
    *,
    exchange_name: str,
    routing_key: str,
    envelope: dict,
) -> None:
    connection = await aio_pika.connect_robust(rabbitmq_url)
    try:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(exchange_name, ExchangeType.TOPIC, durable=True)
        await exchange.publish(
            Message(
                body=json.dumps(envelope).encode("utf-8"),
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )
    finally:
        await connection.close()


def publish_duplicate_outbox_event(settings: E2ESettings, outbox_event: dict) -> None:
    envelope = {
        "event_id": outbox_event["event_id"],
        "event_type": outbox_event["event_type"],
        "aggregate_id": outbox_event["aggregate_id"],
        "aggregate_version": outbox_event["aggregate_version"],
        "occurred_at": outbox_event["occurred_at"].isoformat(),
        "correlation_id": outbox_event["correlation_id"],
        "causation_id": outbox_event["causation_id"],
        "payload": outbox_event["payload"],
    }
    asyncio.run(
        _publish_duplicate_event(
            settings.rabbitmq_url,
            exchange_name=outbox_event["exchange_name"],
            routing_key=outbox_event["routing_key"],
            envelope=envelope,
        ),
    )


@pytest.fixture(scope="session")
def e2e_settings() -> E2ESettings:
    return get_e2e_settings()


@pytest.fixture(scope="session", autouse=True)
def ensure_stack_ready(e2e_settings: E2ESettings) -> None:
    def health_is_ready():
        try:
            response = httpx.get(f"{e2e_settings.gateway_url}/health", timeout=2.0)
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    try:
        wait_until(
            health_is_ready,
            timeout_seconds=10,
            interval_seconds=1,
            description="gateway /health",
        )
    except AssertionError as exc:
        pytest.skip(f"Stack E2E indisponível: {exc}")


@pytest.fixture
def gateway_client(e2e_settings: E2ESettings):
    with httpx.Client(base_url=e2e_settings.gateway_url, timeout=20.0) as client:
        yield client
