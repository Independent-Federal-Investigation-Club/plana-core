from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
from discord.ext.commands import AutoShardedBot
from loguru import logger

from plana.services.manager import GuildManager
from plana.utils.context import PlanaContext
from plana.utils.helper import format_traceback
from plana.utils.translate import PlanaTranslator

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ("PlanaCore", "INTERACTION")

INTERACTION = discord.Interaction["PlanaCore"]


class PlanaCore(AutoShardedBot):
    """
    A core bot class that extends AutoShardedBot with additional functionality.
    """

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        """
        Args:
            command_prefixes (list[str]): List of command prefixes.
        """
        super().__init__(*args, **kwargs)
        self.uptime: "datetime" = datetime.now(timezone.utc)

    def handle_exception(
        self, description: str = "An error occurred", exc: Exception | None = None
    ) -> None:
        """Log exceptions with a custom description.

        Args:
            description (str): Context for the error.
            exc (Exception): The exception to log.
        """

        logger.error(f"❌ {description}: {format_traceback(err=exc, advance=True)}")

    async def run_cog_setup(self) -> None:
        """
        Recursively load cogs (including subfolders).
        """
        import os

        logger.info("Starting cog loading process...")

        cogs_loaded = 0
        for root, dirs, files in os.walk("plana/cogs"):
            for file in files:
                if file.endswith(".py"):
                    cog_path = os.path.join(root, file)
                    relative_path = cog_path.replace("/", ".").replace("\\", ".")[:-3]
                    try:
                        await self.load_extension(relative_path)
                        logger.info(f"✅ Loaded cog: {relative_path}")
                        cogs_loaded += 1
                    except Exception as e:
                        logger.error(f"❌ Failed to load cog {relative_path}: {e}")

        logger.info(f"Cog loading complete. Loaded {cogs_loaded} cogs.")

    async def setup_hook(self) -> None:
        """
        Bot's setup tasks, including cogs loading.
        """
        logger.info("Running setup hook...")
        await self.run_cog_setup()
        logger.info("Setup hook completed")

    async def on_ready(self) -> None:
        """
        Event triggered when bot is ready.
        """
        logger.info(f"🤖 Bot is ready! Logged in as {self.user}")
        logger.info(f"Bot ID: {self.user.id}")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        try:
            await self.tree.set_translator(PlanaTranslator())
            commands = await self.tree.sync()
            logger.info(f"Synced {len(commands)} commands")

        except Exception as e:
            logger.error(f"Error syncing commands: {e}")

    async def on_connect(self) -> None:
        """
        Event triggered when bot connects to Discord.
        """
        logger.info("🔗 Connected to Discord")

    async def on_disconnect(self) -> None:
        """
        Event triggered when bot disconnects from Discord.
        """
        logger.warning("🔌 Disconnected from Discord")

    async def on_resumed(self) -> None:
        """
        Event triggered when bot resumes connection.
        """
        logger.info("🔄 Connection resumed")

    async def get_prefix(bot, message: discord.Message):

        guild_setting = await GuildManager.get(message.guild.id)
        prefix = (
            guild_setting.preferences.command_prefix
            if guild_setting and guild_setting.preferences
            else "!"
        )

        logger.debug(f"Checking Prefix for guild {message.guild.id}: {prefix}")

        return prefix

    async def on_message(self, message: discord.Message) -> None:
        """
        Handle incoming messages (filtering and dispatching).
        """
        if not self.is_ready() or message.author.bot:
            return

        # Check if the bot can send messages in the channel
        can_send = isinstance(message.channel, discord.DMChannel) or getattr(
            message.channel.permissions_for(message.guild.me), "send_messages"
        )
        if not can_send:
            return

        await self.process_commands(message)

    async def process_commands(self, message: discord.Message, /) -> None:
        """
        Processes commands from incoming messages.

        Args:
            message (discord.Message): The message to process.
        """
        ctx = await self.get_context(message, cls=PlanaContext)

        if ctx.command is None:
            return

        await self.invoke(ctx)
