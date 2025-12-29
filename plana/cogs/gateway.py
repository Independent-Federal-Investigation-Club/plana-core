import asyncio
from typing import TYPE_CHECKING

from discord.ext import commands
from loguru import logger

from plana.models.message import Message
from plana.services.manager import GuildManager, GuildSettings
from plana.services.sub import (
    EventPayload,
    GuildConfigEventData,
    PlanaEvents,
    RedisEventSubscriber,
    get_redis_url,
)
from plana.utils.core import PlanaCore

if TYPE_CHECKING:
    from plana.utils.core import PlanaCore


class PlanaGateway(commands.Cog):
    """
    Cog for handling events through the Redis Pub/Sub gateway.
    """

    def __init__(self, core: "PlanaCore") -> None:
        self.core: "PlanaCore" = core
        self.name = "gateway"
        self.description = (
            "Event handlers for managing handling events through the Redis Pub/Sub gateway"
        )
        self.subscriber: RedisEventSubscriber = None
        self._listening_task: asyncio.Task = None

    async def cog_load(self) -> None:
        """Initialize the Redis subscriber when the cog is loaded."""
        try:
            connection_string = get_redis_url()
            logger.info(f"Connecting to Redis at {connection_string}")
            self.subscriber = RedisEventSubscriber(connection_string)

            # Register event handlers
            self.subscriber.register_handler(PlanaEvents.MESSAGE_CREATE, self.handle_message_action)
            self.subscriber.register_handler(PlanaEvents.MESSAGE_DELETE, self.handle_message_action)
            self.subscriber.register_handler(PlanaEvents.MESSAGE_UPDATE, self.handle_message_action)

            self.subscriber.register_handler(
                PlanaEvents.GUILD_CONFIG_REFRESH,
                self.handle_guild_config_refresh,
            )

            # Connect to Redis
            await self.subscriber.connect()

            # Subscribe to all guilds
            await self.subscriber.subscribe_to_guilds()

            # Start listening in a background task
            self._listening_task = asyncio.create_task(self.subscriber.start_listening())

            logger.info("Gatewaycog loaded and listening for Redis events")

        except Exception as e:
            logger.error(f"Failed to initialize Redis subscriber: {e}")
            self.core.handle_exception("Failed to initialize Redis subscriber", e)

    async def cog_unload(self) -> None:
        """Clean up when the cog is unloaded."""
        try:
            if self._listening_task:
                self._listening_task.cancel()
                try:
                    await self._listening_task
                except asyncio.CancelledError:
                    pass

            if self.subscriber:
                await self.subscriber.stop_listening()
                await self.subscriber.disconnect()

            logger.info("Gatewaycog unloaded")

        except Exception as e:
            logger.error(f"Error during cog unload: {e}")

    async def handle_message_action(self, event_data: EventPayload) -> None:
        try:
            if not event_data.data:
                logger.warning(f"Received {event_data.event} event without message data")
                return

            if event_data.guild_id not in [guild.id for guild in self.core.guilds]:
                return

            # Convert to Message BaseModel if needed
            message = Message.model_validate(event_data.data)

            if event_data.event == PlanaEvents.MESSAGE_CREATE:
                discord_message = await message.send(self.core)

                # Update the message with the Discord message ID and save it
                message.message_id = discord_message.id
                await message.save()
                logger.debug(
                    f"Sent message {message.id} to channel {discord_message.channel.name} in guild {discord_message.guild.name}"
                )
            elif event_data.event == PlanaEvents.MESSAGE_UPDATE:

                discord_message = await message.edit(self.core)
                logger.debug(
                    f"Updated message {message.id} in channel {discord_message.channel.name} in guild {discord_message.guild.name}"
                )
            elif event_data.event == PlanaEvents.MESSAGE_DELETE:
                if not message._exists(self.core):
                    return

                if not message.message_id:
                    return

                channel = self.core.get_channel(message.channel_id)
                discord_message = await channel.fetch_message(message.message_id)

                await discord_message.delete()
                logger.debug(f"Deleting message {discord_message.id} in channel {channel.name}")

        except Exception as e:
            logger.error(f"Failed to handle {event_data.event}  event: {e}")
            self.core.handle_exception(f"Failed to handle {event_data.event}  event", e)

    async def handle_guild_config_refresh(self, event_data: EventPayload) -> None:
        """Handle GUILD_CONFIG_REFRESH events by refreshing the guild configuration."""
        try:
            guild = self.core.get_guild(event_data.guild_id)
            if not guild:
                return
            data = event_data.data
            if not data:
                return

            # Refresh the guild configuration
            guild_settings: GuildSettings = await GuildManager.refresh(
                guild_id=guild.id, setting_name=data.name
            )

            if data.name == "levels":
                await self._handle_command_action(
                    guild_id=guild.id,
                    command_name="levels",
                    enable=guild_settings.levels.enabled,
                )
            elif data.name == "achievements":
                await self._handle_command_action(
                    guild_id=guild.id,
                    command_name=data.name,
                    enable=guild_settings.achievements.enabled,
                )
            elif data.name == "rss":
                await self._handle_command_action(
                    guild_id=guild.id,
                    command_name="rss",
                    enable=len(guild_settings.rss_feeds) > 0,
                )

            logger.debug(f"Refreshed configuration for guild {guild.id} for {data.name}")
        except Exception as e:
            logger.error(f"Failed to handle {event_data.event} event: {e}")
            self.core.handle_exception(f"Failed to handle {event_data.event} event", e)

    async def _handle_command_action(self, guild_id: int, command_name: str, enable: bool) -> None:
        """Handle COMMAND_REGISTER events by registering the command in Discord."""
        try:

            if not guild_id or not command_name:
                return

            guild = self.core.get_guild(guild_id)
            if not guild:
                return

            commands = await self.core.tree.fetch_commands(guild=guild)
            cmd = next((c for c in commands if c.name == command_name), None)

            if not cmd:
                return

            if enable and not cmd:
                await self.core.tree.add_command(
                    name=command_name,
                    guild_id=guild.id,
                )
                logger.debug(f"Registered command {command_name} for guild {guild.id}")
            elif not enable and cmd:
                await self.core.tree.remove_command(
                    name=command_name,
                    guild_id=guild.id,
                )
                logger.debug(f"Unregistered command {command_name} for guild {guild.id}")

        except Exception as e:
            logger.error(
                f"Failed to register/unregister command {command_name} for guild {guild.id}: {e}"
            )
            self.core.handle_exception(
                f"Failed to register/unregister command {command_name} for guild {guild.id}", e
            )


async def setup(core: "PlanaCore"):
    try:
        await core.add_cog(PlanaGateway(core))
    except Exception as e:
        core.handle_exception(
            "An error occurred while adding PlanaEvents cog",
            e,
        )
