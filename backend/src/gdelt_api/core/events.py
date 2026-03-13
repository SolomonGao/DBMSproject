"""Event bus for decoupled component communication."""

import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine

from gdelt_api.core.logging import get_logger

logger = get_logger(__name__)


class Event:
    """Base event class."""
    
    def __init__(self, name: str, data: dict[str, Any] | None = None) -> None:
        self.name = name
        self.data = data or {}


EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Simple async event bus implementation."""
    
    def __init__(self) -> None:
        self._handlers: defaultdict[str, list[EventHandler]] = defaultdict(list)
    
    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event."""
        self._handlers[event_name].append(handler)
        logger.debug("handler_subscribed", event=event_name, handler=handler.__name__)
    
    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        """Unsubscribe a handler from an event."""
        if event_name in self._handlers:
            self._handlers[event_name] = [
                h for h in self._handlers[event_name] if h != handler
            ]
    
    async def emit(self, event: Event) -> None:
        """Emit an event to all subscribers."""
        handlers = self._handlers.get(event.name, [])
        if not handlers:
            return
        
        logger.debug("event_emitting", event=event.name, handler_count=len(handlers))
        
        tasks = [handler(event) for handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "event_handler_failed",
                    event=event.name,
                    handler=handlers[i].__name__,
                    error=str(result),
                )


# Global event bus instance
event_bus = EventBus()
