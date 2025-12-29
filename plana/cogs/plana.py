import os
import traceback
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from loguru import logger

from plana.models.guild import Guild
from plana.services.manager import GuildDataTracker, GuildManager, UserManager
from plana.ui.embeds import error_embed_template
from plana.utils.context import PlanaContext

if TYPE_CHECKING:
    from plana.utils.core import PlanaCore


class Plana(commands.Cog):
    """Cog responsible for handling plana features, configurations, and events."""

    def __init__(self, core: "PlanaCore") -> None:
        self.core: "PlanaCore" = core
        self.name = "plana"
        self.description = "Plana features and configurations"

    def cog_load(self) -> None:
        """Initialize tasks and listeners when cog is loaded."""
        self.batch_user_update_task.start()
        self.batch_guild_update_task.start()

    def cog_unload(self) -> None:
        """Clean up tasks when cog is unloaded."""
        self.batch_user_update_task.cancel()
        self.batch_guild_update_task.cancel()

    @tasks.loop(seconds=15)
    async def batch_user_update_task(self):
        """Batch update user data to API every 15 seconds."""
        if not UserManager.dirty_users:
            return

        logger.debug("Batch updating user data...")
        try:
            await UserManager.update_dirty()
        except Exception as e:
            self.core.handle_exception("Failed to batch update user data", e)

    @tasks.loop(seconds=20)
    async def batch_guild_update_task(self):
        """Batch update guild data to API every 15 seconds."""
        if not GuildDataTracker.dirty_guilds:
            return

        logger.debug("Batch updating guild data...")
        try:
            await GuildDataTracker.update_dirty()
        except Exception as e:
            self.core.handle_exception("Failed to batch update guild data", e)

    @batch_guild_update_task.before_loop
    async def before_guild_tasks(self):
        """Wait until bot is ready before starting guild tasks."""
        await self.core.wait_until_ready()

    @batch_user_update_task.before_loop
    async def before_tasks(self):
        """Wait until bot is ready before starting tasks."""
        await self.core.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        Event handler for when the bot is ready.
        """
        self.core.uptime = discord.utils.utcnow()
        logger.info(f"Bot is ready! Uptime: {self.core.uptime}")

        # loading user data into cache
        for guild in self.core.guilds:
            try:
                pass
                await GuildManager.refresh(guild.id)
                await UserManager.init(guild.id)
                await Guild.refresh(guild)
            except Exception as e:
                self.core.handle_exception(
                    f"Failed to initialize Guild Settings and User Data for guild {guild}", e
                )

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """
        Event handler for when the bot joins a new guild.

        """
        logger.info(f"Joined a new guild: {guild.name} (ID: {guild.id})")

        try:
            await GuildManager.reset(guild_id=guild.id)
            await Guild.refresh(guild)

        except Exception as e:
            logger.error(f"Failed to load guild data for {guild.name} (ID: {guild.id}): {e}")
            return

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """
        Event handler for when the bot is removed from a guild.
        """
        logger.info(f"Left a guild: {guild.name} (ID: {guild.id})")

        settings = await GuildManager.get(guild_id=guild.id)

        if not settings or not settings.preferences:
            return

        settings.preferences.enabled = False
        await settings.preferences.save()
        await Guild.delete(guild.id)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        GuildDataTracker.mark_dirty(guild_id=after.id)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        GuildDataTracker.mark_dirty(guild_id=role.guild.id)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        GuildDataTracker.mark_dirty(guild_id=role.guild.id)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        GuildDataTracker.mark_dirty(guild_id=after.guild.id)

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, before: discord.Emoji, after: discord.Emoji) -> None:
        GuildDataTracker.mark_dirty(guild_id=after.guild.id)

    @commands.Cog.listener()
    async def on_guild_stickers_update(
        self, guild: discord.Guild, before: discord.Sticker, after: discord.Sticker
    ) -> None:
        GuildDataTracker.mark_dirty(guild_id=guild.id)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        GuildDataTracker.mark_dirty(guild_id=channel.guild.id)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        GuildDataTracker.mark_dirty(guild_id=channel.guild.id)

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ) -> None:
        GuildDataTracker.mark_dirty(guild_id=after.guild.id)

    @commands.Cog.listener()
    async def on_error(self, event_method, *args, **kwargs):
        print(f"[Unhandled Error in {event_method}]")
        traceback.print_exc()

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """
        Event handler for command errors.
        """
        await self.error_handler(ctx, error)

    @commands.Cog.listener()
    async def on_app_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """
        Event handler for application command errors.
        """
        await self.error_handler(ctx, error)

    async def error_handler(self, ctx: commands.Context, error: Exception) -> None:

        message = f"An error occurred in command '{ctx.command}'"

        if isinstance(error, commands.CommandOnCooldown):
            message = f"You are on cooldown, type: {error.type.name}"

        self.core.handle_exception(message, error)

        embed = await error_embed_template(
            ctx.guild.id,
            error,
            verbose=True if os.getenv("DEBUG") == "TRUE" else False,
        )

        embed.title = message
        await ctx.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle member join events for welcome messages."""
        await self.handle_member_welcome_goodbye(member, is_join=True)

        GuildDataTracker.mark_dirty(guild_id=member.guild.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Handle member leave events for goodbye messages."""
        await self.handle_member_welcome_goodbye(member, is_join=False)

        GuildDataTracker.mark_dirty(guild_id=member.guild.id)

    @commands.hybrid_group(
        name="plana",
        description="Manage Plana features and configurations",
    )
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    async def plana(self, ctx: PlanaContext) -> None:
        """Entry point for plana subcommands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(str(ctx.command))

    @plana.command(
        name="refresh",
        description="Refresh the Plana configuration",
    )
    @commands.has_guild_permissions(administrator=True)
    async def refresh(self, ctx: PlanaContext) -> None:
        """Refresh the Plana configuration."""
        await ctx.defer()
        try:
            await GuildManager.refresh(ctx.guild.id)
            await Guild.refresh(ctx.guild)
            await ctx.send("Plana configuration refreshed successfully!", ephemeral=True)
        except Exception as e:
            await ctx.send("Failed to refresh Plana configuration.", ephemeral=True)
            self.core.handle_exception("Failed to refresh Plana configuration", e)

    @plana.command(
        name="reset",
        description="Reset the Plana configuration to default values",
    )
    @commands.has_guild_permissions(administrator=True)
    async def reset(self, ctx: PlanaContext) -> None:
        """Reset the Plana configuration to default values."""
        await ctx.defer()
        try:
            await GuildManager.reset(ctx.guild.id)
            await Guild.refresh(ctx.guild)
            await ctx.send(
                "Plana configuration reset to default values successfully!", ephemeral=True
            )
        except Exception as e:
            await ctx.send("Failed to reset Plana configuration.", ephemeral=True)
            self.core.handle_exception("Failed to reset Plana configuration", e)

    async def handle_member_welcome_goodbye(
        self, member: discord.Member, is_join: bool = True
    ) -> None:
        """
        Handle member join or leave events for welcome/goodbye messages.
        """
        logger.info(
            f"{member.name} has {'joined' if is_join else 'left'} the server., guild: {member.guild.name} (ID: {member.guild.id})"
        )

        manager = await GuildManager.get(guild_id=member.guild.id)
        welcome_settings = manager.welcome

        if not welcome_settings or not welcome_settings.enabled:
            return

        message = welcome_settings.welcome_message if is_join else welcome_settings.goodbye_message

        # Set the guild and channel IDs for the message template
        message.guild_id = member.guild.id
        message.channel_id = (
            welcome_settings.welcome_channel_id if is_join else welcome_settings.goodbye_channel_id
        )
        await message.send(self.core)

        # handle DM to new users if enabled (only for join events)
        if not welcome_settings.dm_new_users and not welcome_settings.dm_message and not is_join:
            return

        dm_message = welcome_settings.dm_message
        dm_channel = await member.create_dm()

        content, embeds, view = await dm_message._parse()
        await dm_channel.send(
            content=content,
            embeds=embeds,
            view=view,
        )


async def setup(core: "PlanaCore") -> None:
    """Add the Plana cog to the provided core."""
    try:
        await core.add_cog(Plana(core))
    except Exception as e:
        core.handle_exception("Failed to load Plana cog", e)
