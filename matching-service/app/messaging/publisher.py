""""
Esse arquivo é responsável por publicar os eventos enfileirados no banco de dados para o RabbitMQ. 
"""
import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone
import json

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message

from app.core.config import get_settings
from app.core.logging import correlation_id_ctx, get_logger
from app.db.session import SessionLocal
from app.messaging.topology import (
    AUDIT_QUEUE_BINDINGS,
    DEAD_LETTER_QUEUE_BINDINGS,
    QUEUE_BINDINGS,
)
from app.models.outbox import OutboxEvent
from app.repositories.outbox_repository import (
    list_pending_outbox_events,
    mark_outbox_event_exhausted,
    mark_outbox_event_failed,
    mark_outbox_event_published,
)

logger = get_logger(__name__)
MAX_RETRY_DELAY_SECONDS = 60.0


def utc_now() -> datetime:
    """"
    Retorna a data e hora atual em UTC.
    args:
        None
    returns:
        A data e hora atual em UTC.
    """
    return datetime.now(timezone.utc)


def serialize_outbox_event(outbox_event: OutboxEvent) -> bytes:
    """"
    Serializa um evento de outbox para o formato JSON a ser publicado no RabbitMQ.
    args:
        outbox_event: O evento de outbox a ser serializado.
    returns:
        Os bytes do evento serializado em formato JSON.
    """
    envelope = {
        "event_id": str(outbox_event.id),
        "event_type": outbox_event.event_type,
        "aggregate_id": str(outbox_event.aggregate_id),
        "aggregate_version": outbox_event.aggregate_version,
        "occurred_at": outbox_event.occurred_at.isoformat(),
        "correlation_id": str(outbox_event.correlation_id),
        "causation_id": str(outbox_event.causation_id) if outbox_event.causation_id else None,
        "payload": outbox_event.payload,
    }
    return json.dumps(envelope).encode("utf-8")


class OutboxPublisher:
    """"
    Classe responsável por publicar os eventos enfileirados no banco de dados para o RabbitMQ.
    """
    def __init__(self) -> None:
        """"
        Inicializa o publisher de outbox.
        args:
            None
        returns:
            None
        """
        self._task: asyncio.Task | None = None
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None

    async def start(self) -> None:
        """
        Inicia o publisher de outbox. Ele cria uma tarefa assíncrona para publicar os eventos em loop.
        args:
            None
        returns:            
            None
        """
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run_loop(), name="matching-outbox-publisher")

    async def stop(self) -> None:
        """
        Para o publisher de outbox.
        args:
            None
        returns:
            None
        """
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        await self._close_resources()

    async def _run_loop(self) -> None:
        """"
        Loop principal de publicação de eventos. Ele tenta se conectar ao RabbitMQ e publicar os eventos.
        Em caso de falha, ele aguarda um tempo configurado antes de tentar novamente.
        args:
            None
        returns:        
            None
        """
        settings = get_settings()
        while True:
            try:
                exchange = await self._initialize()
                logger.info("outbox_publisher_started")
                while True:
                    published = await self._publish_batch(exchange)
                    if published == 0:
                        await asyncio.sleep(settings.outbox_publish_poll_interval_seconds)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("outbox_publisher_retrying")
                await self._close_resources()
                await asyncio.sleep(settings.outbox_publish_retry_delay_seconds)

    async def _initialize(self):
        """"
        Inicializa as conexões e bindings necessários para publicar os eventos no RabbitMQ.
        args:
            None
        returns:    
            A exchange configurada para publicar os eventos.
        """
        settings = get_settings()
        self._connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self._channel = await self._connection.channel(
            publisher_confirms=True,
            on_return_raises=True,
        )
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
        for queue_name, routing_keys in QUEUE_BINDINGS.items():
            queue = await self._channel.declare_queue(
                queue_name,
                durable=True,
                arguments={"x-dead-letter-exchange": settings.rabbitmq_dead_letter_exchange},
            )
            for routing_key in routing_keys:
                await queue.bind(exchange, routing_key=routing_key)
        for queue_name, routing_keys in DEAD_LETTER_QUEUE_BINDINGS.items():
            dead_letter_queue = await self._channel.declare_queue(queue_name, durable=True)
            for routing_key in routing_keys:
                await dead_letter_queue.bind(dead_letter_exchange, routing_key=routing_key)
        for queue_name, routing_keys in AUDIT_QUEUE_BINDINGS.items():
            audit_queue = await self._channel.declare_queue(queue_name, durable=True)
            for routing_key in routing_keys:
                await audit_queue.bind(exchange, routing_key=routing_key)
        return exchange

    async def _close_resources(self) -> None:
        """
        Fecha as conexões e canais abertos com o RabbitMQ.
        args:            
            None
        returns:            
            None   
        """
        if self._channel is not None and not self._channel.is_closed:
            await self._channel.close()
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()
        self._channel = None
        self._connection = None

    async def _publish_batch(self, exchange) -> int:
        """
        Publica um lote de eventos enfileirados no banco de dados para o RabbitMQ.
        args:
            exchange: A exchange do RabbitMQ para onde os eventos devem ser publicados.
        returns:
            O número de eventos publicados no lote.
        """
        settings = get_settings()
        session = SessionLocal()
        published_count = 0
        try:
            outbox_events = list_pending_outbox_events(
                session,
                limit=settings.outbox_publish_batch_size,
            )
            for outbox_event in outbox_events:
                token = correlation_id_ctx.set(str(outbox_event.correlation_id))
                try:
                    await exchange.publish(
                        Message(
                            body=serialize_outbox_event(outbox_event),
                            content_type="application/json",
                            delivery_mode=DeliveryMode.PERSISTENT,
                            headers=outbox_event.headers or {},
                        ),
                        routing_key=outbox_event.routing_key,
                        mandatory=True,
                    )
                    mark_outbox_event_published(
                        session,
                        outbox_event.id,
                        published_at=utc_now(),
                    )
                    session.commit()
                    published_count += 1
                    logger.info(
                        "outbox_event_published event_type=%s aggregate_id=%s",
                        outbox_event.event_type,
                        outbox_event.aggregate_id,
                    )
                except Exception as exc:
                    attempt_number = outbox_event.publish_attempts + 1
                    if attempt_number >= settings.outbox_publish_max_attempts:
                        mark_outbox_event_exhausted(
                            session,
                            outbox_event.id,
                            last_error=str(exc),
                        )
                        session.commit()
                        logger.exception(
                            "outbox_event_publish_exhausted event_type=%s aggregate_id=%s attempts=%s",
                            outbox_event.event_type,
                            outbox_event.aggregate_id,
                            attempt_number,
                        )
                    else:
                        retry_delay = min(
                            MAX_RETRY_DELAY_SECONDS,
                            settings.outbox_publish_retry_delay_seconds
                            * max(1, 2 ** outbox_event.publish_attempts),
                        )
                        mark_outbox_event_failed(
                            session,
                            outbox_event.id,
                            last_error=str(exc),
                            next_available_at=utc_now() + timedelta(seconds=retry_delay),
                        )
                        session.commit()
                        logger.exception(
                            "outbox_event_publish_failed event_type=%s aggregate_id=%s retry_in_seconds=%s attempt=%s",
                            outbox_event.event_type,
                            outbox_event.aggregate_id,
                            retry_delay,
                            attempt_number,
                        )
                    break
                finally:
                    correlation_id_ctx.reset(token)
        finally:
            session.close()

        return published_count
