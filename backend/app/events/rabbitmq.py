import json

import aio_pika

from app.core.config import get_settings
from app.events.contracts import EventEnvelope


class RabbitMQEventBus:
    """RabbitMQ transport adapter; application code depends on EventBus, not this class."""

    async def publish(self, event: EventEnvelope) -> None:
        connection = await aio_pika.connect_robust(get_settings().rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                "forma.events", aio_pika.ExchangeType.TOPIC, durable=True
            )
            await exchange.publish(
                aio_pika.Message(
                    body=json.dumps(event.to_dict()).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=event.event_type,
            )
