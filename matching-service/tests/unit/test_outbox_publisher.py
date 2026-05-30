import asyncio
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.messaging.publisher as publisher_module
from app.messaging.publisher import OutboxPublisher, utc_now
from app.models.outbox import OutboxEvent


class FakeSession:
    def __init__(self, event: OutboxEvent) -> None:
        self.event = event
        self.commits = 0
        self.closed = False

    def get(self, _, event_id):
        if self.event.id == event_id:
            return self.event
        return None

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        self.closed = True


class ConfirmingExchange:
    def __init__(self, event: OutboxEvent) -> None:
        self.event = event
        self.publish_calls = 0

    async def publish(self, message, routing_key: str, mandatory: bool = False) -> bool:
        self.publish_calls += 1
        assert self.event.published_at is None
        assert self.event.status in {"PENDING", "FAILED"}
        assert mandatory is True
        assert routing_key == self.event.routing_key
        assert message.body
        return True


class FailingExchange:
    async def publish(self, *_args, **_kwargs) -> bool:
        raise RuntimeError("broker indisponivel")


class FakeTopologyExchange:
    pass


class FakeQueue:
    def __init__(self, name: str) -> None:
        self.name = name
        self.bindings: list[str] = []

    async def bind(self, _exchange, routing_key: str) -> None:
        self.bindings.append(routing_key)


class FakeChannel:
    def __init__(self) -> None:
        self.is_closed = False
        self.exchange_names: list[str] = []
        self.queue_names: list[str] = []

    async def declare_exchange(self, name, *_args, **_kwargs):
        self.exchange_names.append(name)
        return FakeTopologyExchange()

    async def declare_queue(self, name, *_args, **_kwargs):
        self.queue_names.append(name)
        return FakeQueue(name)

    async def close(self) -> None:
        self.is_closed = True


class FakeConnection:
    def __init__(self, channel: FakeChannel) -> None:
        self._channel = channel
        self.channel_kwargs: dict[str, object] | None = None
        self.is_closed = False

    async def channel(self, **kwargs):
        self.channel_kwargs = kwargs
        return self._channel

    async def close(self) -> None:
        self.is_closed = True


class FakeClosable:
    def __init__(self) -> None:
        self.is_closed = False
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1
        self.is_closed = True


def build_event(*, status: str = "PENDING", publish_attempts: int = 0) -> OutboxEvent:
    now = utc_now()
    return OutboxEvent(
        id=uuid4(),
        event_type="MatchSuggested",
        aggregate_id=uuid4(),
        aggregate_version=1,
        exchange_name="domain.events",
        routing_key="match.suggested",
        correlation_id=uuid4(),
        causation_id=None,
        payload={"id": str(uuid4())},
        headers={},
        occurred_at=now,
        available_at=now,
        status=status,
        publish_attempts=publish_attempts,
    )


def build_settings(**overrides):
    base = {
        "rabbitmq_url": "amqp://app:app@localhost:5672/",
        "rabbitmq_events_exchange": "domain.events",
        "rabbitmq_dead_letter_exchange": "domain.events.dlx",
        "outbox_publish_poll_interval_seconds": 3.5,
        "outbox_publish_batch_size": 10,
        "outbox_publish_retry_delay_seconds": 2.0,
        "outbox_publish_max_attempts": 3,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_publish_batch_marks_event_published_only_after_broker_confirm(monkeypatch) -> None:
    event = build_event()
    session = FakeSession(event)
    exchange = ConfirmingExchange(event)
    publisher = OutboxPublisher()

    monkeypatch.setattr(publisher_module, "SessionLocal", lambda: session)
    monkeypatch.setattr(publisher_module, "get_settings", lambda: build_settings())
    monkeypatch.setattr(publisher_module, "list_pending_outbox_events", lambda *_args, **_kwargs: [event])

    published_count = asyncio.run(publisher._publish_batch(exchange))

    assert published_count == 1
    assert exchange.publish_calls == 1
    assert event.status == "PUBLISHED"
    assert event.published_at is not None
    assert event.publish_attempts == 1
    assert session.commits == 1
    assert session.closed is True


def test_publish_batch_marks_failed_and_schedules_retry(monkeypatch) -> None:
    event = build_event()
    session = FakeSession(event)
    publisher = OutboxPublisher()
    before = utc_now()

    monkeypatch.setattr(publisher_module, "SessionLocal", lambda: session)
    monkeypatch.setattr(publisher_module, "get_settings", lambda: build_settings())
    monkeypatch.setattr(publisher_module, "list_pending_outbox_events", lambda *_args, **_kwargs: [event])

    published_count = asyncio.run(publisher._publish_batch(FailingExchange()))

    assert published_count == 0
    assert event.status == "FAILED"
    assert event.published_at is None
    assert event.publish_attempts == 1
    assert event.available_at > before
    assert session.commits == 1


def test_publish_batch_stops_retrying_after_max_attempts(monkeypatch) -> None:
    event = build_event(publish_attempts=2)
    session = FakeSession(event)
    publisher = OutboxPublisher()

    monkeypatch.setattr(publisher_module, "SessionLocal", lambda: session)
    monkeypatch.setattr(publisher_module, "get_settings", lambda: build_settings(outbox_publish_max_attempts=3))
    monkeypatch.setattr(publisher_module, "list_pending_outbox_events", lambda *_args, **_kwargs: [event])

    published_count = asyncio.run(publisher._publish_batch(FailingExchange()))

    assert published_count == 0
    assert event.status == "EXHAUSTED"
    assert event.publish_attempts == 3
    assert event.published_at is None
    assert session.commits == 1


def test_new_publisher_instance_processes_preexisting_failed_record(monkeypatch) -> None:
    event = build_event(status="FAILED", publish_attempts=1)
    event.available_at = utc_now() - timedelta(seconds=1)
    session = FakeSession(event)
    publisher = OutboxPublisher()

    monkeypatch.setattr(publisher_module, "SessionLocal", lambda: session)
    monkeypatch.setattr(publisher_module, "get_settings", lambda: build_settings())
    monkeypatch.setattr(publisher_module, "list_pending_outbox_events", lambda *_args, **_kwargs: [event])

    published_count = asyncio.run(publisher._publish_batch(ConfirmingExchange(event)))

    assert published_count == 1
    assert event.status == "PUBLISHED"
    assert event.publish_attempts == 2


def test_run_loop_uses_configured_poll_interval(monkeypatch) -> None:
    channel = FakeChannel()
    connection = FakeConnection(channel)
    sleep_calls: list[float] = []

    async def fake_connect_robust(_url: str):
        return connection

    async def fake_publish_batch(_self, _exchange) -> int:
        return 0

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        raise asyncio.CancelledError

    monkeypatch.setattr(publisher_module.aio_pika, "connect_robust", fake_connect_robust)
    monkeypatch.setattr(publisher_module, "get_settings", lambda: build_settings(outbox_publish_poll_interval_seconds=4.25))
    monkeypatch.setattr(OutboxPublisher, "_publish_batch", fake_publish_batch)
    monkeypatch.setattr(publisher_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(OutboxPublisher()._run_loop())

    assert sleep_calls == [4.25]
    assert connection.channel_kwargs == {"publisher_confirms": True, "on_return_raises": True}


def test_stop_cancels_task_and_closes_resources() -> None:
    async def exercise():
        publisher = OutboxPublisher()
        channel = FakeClosable()
        connection = FakeClosable()
        publisher._task = asyncio.create_task(asyncio.sleep(3600))
        publisher._channel = channel
        publisher._connection = connection

        await publisher.stop()
        return publisher, channel, connection

    publisher, channel, connection = asyncio.run(exercise())

    assert publisher._task is None
    assert channel.close_calls == 1
    assert connection.close_calls == 1
