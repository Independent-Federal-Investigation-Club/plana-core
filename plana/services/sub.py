import os
import traceback
from enum import Enum
from typing import Any, Callable, Dict, Optional
from datetime import datetime, timezone

import redis.asyncio as aioredis
from redis.asyncio.client import PubSub

from loguru import logger
from pydantic import BaseModel, Field

from plana.models.message import Message


def get_redis_url() -> str:
    """
    Get the Redis URL from environment variables.
    """
    from dotenv import load_dotenv

    load_dotenv()

    url = os.getenv("REDIS_URL")
    password = os.getenv("PLANA_PASSWORD")

    return f"redis://:{password}@{url}" if password else url or "redis://localhost:6379"


class PlanaEvents(str, Enum):
    """Message event types for Redis pub/sub."""

    MESSAGE_CREATE = "MESSAGE_CREATE"
    MESSAGE_UPDATE = "MESSAGE_UPDATE"
    MESSAGE_DELETE = "MESSAGE_DELETE"
    COMMAND_REGISTER = "COMMAND_REGISTER"
    COMMAND_UNREGISTER = "COMMAND_UNREGISTER"
    GUILD_CONFIG_REFRESH = "GUILD_CONFIG_REFRESH"


class GuildConfigEventData(BaseModel):
    """Event data for command registration and unregistration."""

    name: str


class EventPayload(BaseModel):
    """Event data wrapper for event events."""

    event: PlanaEvents
    guild_id: int
    data: Optional[Message | GuildConfigEventData] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        use_enum_values = True


class RedisEventSubscriber:
    """
    Redis subscriber for events.

    Simple, focused class that only handles subscribing to events.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client: Optional[aioredis.Redis] = None
        self.pubsub: Optional[PubSub] = None
        self._handlers: Dict[PlanaEvents, Callable] = {}
        self._running = False

    async def connect(self) -> None:
        """Connect to aioredis."""
        if self.redis_client is None:
            self.redis_client = aioredis.from_url(self.redis_url)
            self.pubsub = self.redis_client.pubsub()
            logger.info("Subscriber connected to Redis")

    async def disconnect(self) -> None:
        """Disconnect from aioredis."""
        if self.pubsub:
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Subscriber disconnected from Redis")

    def register_handler(self, event: PlanaEvents, handler: Callable) -> None:
        """Register an event handler."""
        self._handlers[event] = handler
        logger.info(f"Registered handler for {event}")

    async def subscribe_to_guilds(self, guild_ids: Optional[list[int]] = None) -> None:
        """Subscribe to events for specific guilds or all guilds."""
        if not self.pubsub:
            await self.connect()

        if guild_ids is None:
            # Subscribe to all guild events using pattern
            pattern = "events:*"
            await self.pubsub.psubscribe(pattern)
            logger.info(f"Subscribed to all guilds with pattern: {pattern}")
        else:
            # Subscribe to specific guilds
            for guild_id in guild_ids:
                channel = f"events:{guild_id}"
                await self.pubsub.subscribe(channel)
                logger.info(f"Subscribed to {channel}")

            logger.info(f"Subscribed to {len(guild_ids)} guild(s)")

    async def start_listening(self) -> None:
        """Start listening for events."""
        if not self.pubsub:
            raise RuntimeError("Not connected to Redis")

        self._running = True
        logger.info("Started listening for events")

        async for event in self.pubsub.listen():
            if not self._running:
                break

            # Handle both regular events and pattern events
            if event["type"] in ["message", "pmessage"]:
                await self._handle_event(event)

    async def stop_listening(self) -> None:
        """Stop listening for events."""
        self._running = False
        logger.info("Stopped listening for events")

    async def _handle_event(self, event: Dict[str, Any]) -> None:
        """Handle incoming Redis event."""
        try:
            logger.debug(f"Received event: {event}")
            # Handle both string and bytes data
            data = event["data"]
            if isinstance(data, bytes):
                data = data.decode("utf-8")

            event_data = EventPayload.model_validate_json(data)
            handler = self._handlers.get(event_data.event)

            if not handler:
                return

            await handler(event_data)

        except Exception as e:
            logger.error(f"Failed to handle event: {e}, {traceback.format_exc()}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop_listening()
        await self.disconnect()
