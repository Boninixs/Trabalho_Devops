import asyncio
from contextlib import suppress
import json

import aio_pika
from aio_pika import ExchangeType, IncomingMessage

from app.core.config import get_settings
from app.core.logging import correlation_id_ctx, get_logger
from app.db.session import SessionLocal
from app.schemas.events import EventEnvelope
from app.services.item_service_client import HttpItemRecoveryClient
from app.services.recovery_case_service import consume_match_accepted

logger = get_logger(__name__)


class MatchAcceptedConsumer:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._consume_loop(), name="recovery-case-match-consumer")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        await self._close_resources()

    async def _consume_loop(self) -> None:
        settings = get_settings()
        while True:
            try:
                queue = await self._initialize_bindings()
                logger.info("match_accepted_consumer_started")
                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        await self._process_message(message)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("match_accepted_consumer_retrying")
                await self._close_resources()
                await asyncio.sleep(settings.outbox_publish_retry_delay_seconds)

    async def _initialize_bindings(self) -> aio_pika.abc.AbstractRobustQueue:
        settings = get_settings()
        self._connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=10)

        exchange = await self._channel.declare_exchange(
            settings.rabbitmq_events_exchange,
            ExchangeType.TOPIC,
            durable=True,
        )
        dead_letter_exchange = await self._channel.declare_exchange(
            settings.rabbitmq_dead_letter_exchange,
            ExchangeType.TOPIC,
            durable=True,
        )
        queue = await self._channel.declare_queue(
            settings.rabbitmq_match_events_queue,
            durable=True,
            arguments={"x-dead-letter-exchange": settings.rabbitmq_dead_letter_exchange},
        )
        dead_letter_queue = await self._channel.declare_queue(
            f"{settings.rabbitmq_match_events_queue}.dlq",
            durable=True,
        )
        await queue.bind(exchange, routing_key="match.accepted")
        await dead_letter_queue.bind(dead_letter_exchange, routing_key="match.accepted")
        return queue

    async def _close_resources(self) -> None:
        if self._channel is not None and not self._channel.is_closed:
            await self._channel.close()
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()
        self._channel = None
        self._connection = None

    async def _process_message(self, message: IncomingMessage) -> None:
        async with message.process(requeue=False):
            envelope = EventEnvelope.model_validate(json.loads(message.body.decode("utf-8")))
            token = correlation_id_ctx.set(str(envelope.correlation_id))
            session = SessionLocal()
            try:
                consume_match_accepted(session, envelope, HttpItemRecoveryClient())
                logger.info("match_accepted_processed")
            except Exception:
                session.rollback()
                logger.exception("match_accepted_processing_failed")
                raise
            finally:
                session.close()
                correlation_id_ctx.reset(token)
