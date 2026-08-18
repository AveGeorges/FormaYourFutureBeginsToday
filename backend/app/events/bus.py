from typing import Protocol

from app.events.contracts import EventEnvelope


class EventBus(Protocol):
    async def publish(self, event: EventEnvelope) -> None: ...
