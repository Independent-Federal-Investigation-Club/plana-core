import re
from typing import TYPE_CHECKING, Callable

import discord
from discord import app_commands
from discord.ext import commands

from plana.utils.context import PlanaContext
from plana.utils.translate import Tr, PlanaLocaleStr

from plana.services.manager import GuildManager

if TYPE_CHECKING:
    from plana.utils.core import PlanaCore


class PlanaMessage(commands.Cog):
    def __init__(self, core: "PlanaCore") -> None:
        self.core: "PlanaCore" = core
        self.name = "message"
        self.description = "Manage and moderate messages within your server"

    @commands.hybrid_group(
        name=PlanaLocaleStr("message.prune.name"),
        description=PlanaLocaleStr("message.prune.description"),
    )
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    async def prune(self, ctx: PlanaContext) -> None:
        """Entry point for prune subcommands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(str(ctx.command))

    async def _bulk_delete_messages(
        self,
        ctx: PlanaContext,
        limit: int,
        predicate: Callable[[discord.Message], bool],
        *,
        before: int | None = None,
        after: int | None = None,
        reply_ephemeral: bool = True,
    ) -> discord.Message:
        """
        Bulk delete messages that match a predicate within a given limit.

        Args:
            ctx: The command context
            limit: The maximum number of messages to check or delete
            predicate: Condition for removal
            before: Process messages before this message ID
            after: Process messages after this message ID
            reply_ephemeral: Whether to send ephemeral confirmation

        Returns:
            Status message sent to the channel (or ephemeral)
        """
        await ctx.defer()
        locale = await GuildManager.get_locale(ctx)

        if limit > 2000:
            return await ctx.send(
                Tr.t(
                    "message.prune.response.too_many_messages",
                    locale=locale,
                    limit=limit,
                ),
                ephemeral=True,
            )

        before_obj = discord.Object(id=before) if before else ctx.message
        after_obj = discord.Object(id=after) if after else None

        try:
            channel = ctx.channel
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                return await ctx.send(
                    Tr.t("message.prune.response.invalid_channel", locale=locale),
                    ephemeral=True,
                )

            deleted = await channel.purge(
                limit=limit, before=before_obj, after=after_obj, check=predicate
            )

        except discord.Forbidden:
            return await ctx.send(
                Tr.t("message.prune.response.forbidden", locale=locale),
                ephemeral=True,
            )
        except discord.HTTPException as e:
            return await ctx.send(
                Tr.t("message.prune.response.http_exception", locale=locale, error=str(e)),
                ephemeral=True,
            )
        except discord.DiscordException as exception:
            return await ctx.send(
                Tr.t(
                    "message.prune.response.generic_exception",
                    locale=locale,
                    error=str(exception),
                ),
                ephemeral=True,
            )

        deleted_count = len(deleted)
        return await ctx.send(
            Tr.t("message.prune.response.success", locale=locale, count=deleted_count),
            ephemeral=reply_ephemeral,
            delete_after=4.0,
        )

    @prune.command(
        name=PlanaLocaleStr("message.prune.embeds.name"),
        description=PlanaLocaleStr("message.prune.embeds.description"),
    )
    @app_commands.describe(limit=PlanaLocaleStr("message.prune.param.limit.description"))
    @app_commands.rename(limit=PlanaLocaleStr("message.prune.param.limit.name"))
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def embeds(self, ctx: PlanaContext, limit: int = 100) -> None:
        """Remove messages that contain embeds."""
        await self._bulk_delete_messages(ctx, limit, lambda msg: bool(msg.embeds))

    @prune.command(
        name=PlanaLocaleStr("message.prune.files.name"),
        description=PlanaLocaleStr("message.prune.files.description"),
    )
    @app_commands.describe(limit=PlanaLocaleStr("message.prune.param.limit.description"))
    @app_commands.rename(limit=PlanaLocaleStr("message.prune.param.limit.name"))
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def files(self, ctx: PlanaContext, limit: int = 100) -> None:
        """Remove messages that contain file attachments."""
        await self._bulk_delete_messages(ctx, limit, lambda msg: bool(msg.attachments))

    @prune.command(
        name=PlanaLocaleStr("message.prune.mentions.name"),
        description=PlanaLocaleStr("message.prune.mentions.description"),
    )
    @app_commands.describe(limit=PlanaLocaleStr("message.prune.param.limit.description"))
    @app_commands.rename(limit=PlanaLocaleStr("message.prune.param.limit.name"))
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def mentions(self, ctx: PlanaContext, limit: int = 100) -> None:
        """Remove messages that @mention users or roles."""
        await self._bulk_delete_messages(
            ctx, limit, lambda msg: bool(msg.mentions or msg.role_mentions)
        )

    @prune.command(
        name=PlanaLocaleStr("message.prune.images.name"),
        description=PlanaLocaleStr("message.prune.images.description"),
    )
    @app_commands.describe(limit=PlanaLocaleStr("message.prune.param.limit.description"))
    @app_commands.rename(limit=PlanaLocaleStr("message.prune.param.limit.name"))
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def images(self, ctx: PlanaContext, limit: int = 100) -> None:
        """Remove messages that contain embeds or file attachments."""
        await self._bulk_delete_messages(
            ctx, limit, lambda msg: bool(msg.embeds or msg.attachments)
        )

    @prune.command(
        name=PlanaLocaleStr("message.prune.all.name"),
        description=PlanaLocaleStr("message.prune.all.description"),
    )
    @app_commands.describe(limit=PlanaLocaleStr("message.prune.param.limit.description"))
    @app_commands.rename(limit=PlanaLocaleStr("message.prune.param.limit.name"))
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def remove_all(self, ctx: PlanaContext, limit: int = 100) -> None:
        """Remove all messages within the specified limit."""
        await self._bulk_delete_messages(ctx, limit, lambda msg: True)

    @prune.command(
        name=PlanaLocaleStr("message.prune.user.name"),
        description=PlanaLocaleStr("message.prune.user.description"),
    )
    @app_commands.describe(
        member=PlanaLocaleStr("message.prune.param.member.description"),
        limit=PlanaLocaleStr("message.prune.param.limit.description"),
    )
    @app_commands.rename(
        member=PlanaLocaleStr("message.prune.param.member.name"),
        limit=PlanaLocaleStr("message.prune.param.limit.name"),
    )
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def user(self, ctx: PlanaContext, member: discord.Member, limit: int = 100) -> None:
        """Remove messages from a specific user."""
        await self._bulk_delete_messages(ctx, limit, lambda msg: msg.author == member)

    @prune.command(
        name=PlanaLocaleStr("message.prune.contains.name"),
        description=PlanaLocaleStr("message.prune.contains.description"),
    )
    @app_commands.describe(substr=PlanaLocaleStr("message.prune.param.substr.description"))
    @app_commands.rename(substr=PlanaLocaleStr("message.prune.param.substr.name"))
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def contains(self, ctx: PlanaContext, *, substr: str) -> None:
        """Remove messages containing a specific substring (≥3 bytes)."""
        locale = await GuildManager.get_locale(ctx)

        if len(substr) < 3:
            await ctx.send(Tr.t("message.prune.contains.response.too_short", locale=locale))
            return

        await self._bulk_delete_messages(ctx, 100, lambda msg: substr in msg.content)

    @prune.command(
        name=PlanaLocaleStr("message.prune.bots.name"),
        description=PlanaLocaleStr("message.prune.bots.description"),
    )
    @app_commands.describe(
        limit=PlanaLocaleStr("message.prune.param.limit.description"),
        prefix=PlanaLocaleStr("message.prune.param.prefix.description"),
    )
    @app_commands.rename(
        limit=PlanaLocaleStr("message.prune.param.limit.name"),
        prefix=PlanaLocaleStr("message.prune.param.prefix.name"),
    )
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def bots(self, ctx: PlanaContext, limit: int = 100, prefix: str | None = None) -> None:
        """Remove bot messages or messages starting with a defined prefix."""
        # Use provided prefix or default to bot's command prefix
        if prefix:
            prefixes = [prefix]
        else:
            # Get the bot's command_prefix and ensure it's a list
            bot_prefix = self.core.command_prefix
            if callable(bot_prefix):
                try:
                    bot_prefix = bot_prefix(self.core, ctx.message)
                except Exception:
                    bot_prefix = ["!"]  # fallback if callable fails

            # Handle different prefix types safely
            if isinstance(bot_prefix, str):
                prefixes = [bot_prefix]
            elif isinstance(bot_prefix, list):
                prefixes = [str(p) for p in bot_prefix]
            else:
                prefixes = ["!"]  # fallback

        def is_bot_or_prefixed(msg: discord.Message) -> bool:
            return (msg.webhook_id is None and msg.author.bot) or msg.content.startswith(
                tuple(prefixes)
            )

        await self._bulk_delete_messages(ctx, limit, is_bot_or_prefixed)

    @prune.command(
        name=PlanaLocaleStr("message.prune.users.name"),
        description=PlanaLocaleStr("message.prune.users.description"),
    )
    @app_commands.describe(limit=PlanaLocaleStr("message.prune.param.limit.description"))
    @app_commands.rename(limit=PlanaLocaleStr("message.prune.param.limit.name"))
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def users(self, ctx: PlanaContext, limit: int = 100) -> None:
        """Remove the specified number of user (non-bot) messages."""
        await self._bulk_delete_messages(ctx, limit, lambda msg: not msg.author.bot)

    @prune.command(
        name=PlanaLocaleStr("message.prune.emojis.name"),
        description=PlanaLocaleStr("message.prune.emojis.description"),
    )
    @app_commands.describe(limit=PlanaLocaleStr("message.prune.param.limit.description"))
    @app_commands.rename(limit=PlanaLocaleStr("message.prune.param.limit.name"))
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def emojis(self, ctx: PlanaContext, limit: int = 100) -> None:
        """Remove messages containing custom emojis or general Unicode emojis."""
        emoji_pattern = re.compile(r"<a?:(.*?):(\d{17,21})>|[\u263a-\U0001f645]")
        await self._bulk_delete_messages(
            ctx, limit, lambda msg: bool(emoji_pattern.search(msg.content))
        )

    @prune.command(
        name=PlanaLocaleStr("message.prune.reactions.name"),
        description=PlanaLocaleStr("message.prune.reactions.description"),
    )
    @app_commands.describe(limit=PlanaLocaleStr("message.prune.param.limit.description"))
    @app_commands.rename(limit=PlanaLocaleStr("message.prune.param.limit.name"))
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def reactions(self, ctx: PlanaContext, limit: int = 100) -> None:
        """Clear reactions on messages within the specified limit."""
        locale = await GuildManager.get_locale(ctx)

        if limit > 2000:
            await ctx.send(
                Tr.t(
                    "message.prune.response.too_many_messages",
                    locale=locale,
                    limit=limit,
                ),
                ephemeral=True,
            )
            return

        total_reactions = 0
        async for message in ctx.history(limit=limit, before=ctx.message):
            if message.reactions:
                total_reactions += sum(r.count for r in message.reactions)
                await message.clear_reactions()

        await ctx.send(
            Tr.t(
                "message.prune.reactions.response.cleared",
                locale=locale,
                total_reactions=total_reactions,
            ),
            ephemeral=True,
        )

    @prune.command(
        name=PlanaLocaleStr("message.prune.pinned.name"),
        description=PlanaLocaleStr("message.prune.pinned.description"),
    )
    @app_commands.describe(limit=PlanaLocaleStr("message.prune.param.limit.description"))
    @app_commands.rename(limit=PlanaLocaleStr("message.prune.param.limit.name"))
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def pinned(self, ctx: PlanaContext, limit: int = 100) -> None:
        """Remove pinned messages from the channel within the specified limit."""
        pinned_ids = {msg.id for msg in await ctx.channel.pins()}
        await self._bulk_delete_messages(ctx, limit, lambda msg: msg.id in pinned_ids)

    @prune.command(
        name=PlanaLocaleStr("message.prune.regex.name"),
        description=PlanaLocaleStr("message.prune.regex.description"),
    )
    @app_commands.describe(
        pattern=PlanaLocaleStr("message.prune.param.pattern.description"),
        limit=PlanaLocaleStr("message.prune.param.limit.description"),
    )
    @app_commands.rename(
        pattern=PlanaLocaleStr("message.prune.param.pattern.name"),
        limit=PlanaLocaleStr("message.prune.param.limit.name"),
    )
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def regex(self, ctx: PlanaContext, pattern: str, limit: int = 100) -> None:
        """Remove messages that match a specific regex pattern."""
        try:
            compiled_pattern = re.compile(pattern)
        except re.error as e:
            locale = await GuildManager.get_locale(ctx)
            await ctx.send(
                Tr.t(
                    "message.prune.regex.response.invalid_pattern",
                    locale=locale,
                    error=str(e),
                ),
                ephemeral=True,
            )
            return

        await self._bulk_delete_messages(
            ctx, limit, lambda msg: bool(compiled_pattern.search(msg.content))
        )

    @prune.command(
        name=PlanaLocaleStr("message.prune.invites.name"),
        description=PlanaLocaleStr("message.prune.invites.description"),
    )
    @app_commands.describe(limit=PlanaLocaleStr("message.prune.param.limit.description"))
    @app_commands.rename(limit=PlanaLocaleStr("message.prune.param.limit.name"))
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def invites(self, ctx: PlanaContext, limit: int = 100) -> None:
        """Remove messages that contain Discord invite links."""
        invite_pattern = re.compile(r"(discord\.gg/|discordapp\.com/invite/)\S+")
        await self._bulk_delete_messages(
            ctx, limit, lambda msg: bool(invite_pattern.search(msg.content))
        )

    @prune.command(
        name=PlanaLocaleStr("message.prune.urls.name"),
        description=PlanaLocaleStr("message.prune.urls.description"),
    )
    @app_commands.describe(limit=PlanaLocaleStr("message.prune.param.limit.description"))
    @app_commands.rename(limit=PlanaLocaleStr("message.prune.param.limit.name"))
    @commands.has_guild_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def urls(self, ctx: PlanaContext, limit: int = 100) -> None:
        """Remove messages that contain external URLs."""
        url_pattern = re.compile(r"https?://\S+")
        await self._bulk_delete_messages(
            ctx, limit, lambda msg: bool(url_pattern.search(msg.content))
        )

    @prune.command(
        name=PlanaLocaleStr("message.prune.self.name"),
        description=PlanaLocaleStr("message.prune.self.description"),
    )
    @app_commands.describe(
        limit=PlanaLocaleStr("message.prune.self.param.limit.description"),
        server_wide=PlanaLocaleStr("message.prune.self.param.server_wide.description"),
    )
    @app_commands.rename(
        limit=PlanaLocaleStr("message.prune.self.param.limit.name"),
        server_wide=PlanaLocaleStr("message.prune.self.param.server_wide.name"),
    )
    @commands.cooldown(1, 60, commands.BucketType.user)  # 1 minute cooldown per user
    @commands.guild_only()
    async def self_cleanup(
        self, ctx: PlanaContext, limit: int = 50, server_wide: bool = False
    ) -> None:
        """Delete your own messages from the current channel or server. No manage_messages permission required."""
        await ctx.defer()
        locale = await GuildManager.get_locale(ctx)

        # Validate limit
        if limit > 500:
            await ctx.send(
                Tr.t(
                    "message.prune.response.too_many_messages",
                    locale=locale,
                    limit=limit,
                ),
                ephemeral=True,
            )
            return

        if server_wide:
            await self._cleanup_server_wide(ctx, limit, locale)
        else:
            await self._cleanup_current_channel(ctx, limit, locale)

    async def _cleanup_server_wide(self, ctx: PlanaContext, limit: int, locale: str) -> None:
        """Clean up user's messages across the entire server."""
        total_deleted = 0
        channels_processed = 0
        remaining_limit = limit

        # Get all accessible channels (text channels and threads)
        accessible_channels = []

        # Add text channels
        for channel in ctx.guild.text_channels:
            if self._can_access_channel(channel):
                accessible_channels.append(channel)

        # Add all active threads from the guild
        for thread in ctx.guild.threads:
            if self._can_access_channel(thread):
                accessible_channels.append(thread)

        # Also get archived threads from each text channel
        for channel in ctx.guild.text_channels:
            if self._can_access_channel(channel):
                try:
                    async for thread in channel.archived_threads(limit=None):
                        if self._can_access_channel(thread):
                            accessible_channels.append(thread)
                except (discord.Forbidden, discord.HTTPException):
                    continue

        # Sort channels to process current channel first
        accessible_channels.sort(key=lambda ch: ch.id != ctx.channel.id)

        # Process channels respecting the global limit
        for channel in accessible_channels:
            if remaining_limit <= 0:
                break

            try:
                # Calculate messages to delete from this channel (not just check)
                # We need to track actual deletions vs messages checked
                messages_to_check = min(remaining_limit * 2, 100)  # Check more than we need

                deleted = await channel.purge(
                    limit=messages_to_check,
                    check=lambda msg: msg.author == ctx.author,
                    before=ctx.message if channel == ctx.channel else None,
                )

                if deleted:
                    deleted_count = len(deleted)
                    # Respect the global deletion limit
                    if deleted_count > remaining_limit:
                        # This shouldn't happen with purge, but safety check
                        deleted_count = remaining_limit

                    total_deleted += deleted_count
                    remaining_limit -= deleted_count
                    channels_processed += 1

            except (discord.Forbidden, discord.HTTPException):
                continue  # Skip channels we can't access

        # Send response
        if total_deleted > 0:
            await ctx.send(
                Tr.t(
                    "message.prune.self.response.server_wide_success",
                    locale=locale,
                    count=total_deleted,
                    channels=channels_processed,
                ),
                ephemeral=True,
                delete_after=5.0,
            )
        else:
            await ctx.send(
                Tr.t("message.prune.self.response.no_messages", locale=locale),
                ephemeral=True,
            )

    async def _cleanup_current_channel(self, ctx: PlanaContext, limit: int, locale: str) -> None:
        """Clean up user's messages from the current channel only."""
        # Ensure we're in a valid channel type
        if not isinstance(ctx.channel, (discord.TextChannel, discord.Thread)):
            await ctx.send(
                Tr.t("message.prune.response.invalid_channel", locale=locale),
                ephemeral=True,
            )
            return

        try:
            deleted = await ctx.channel.purge(
                limit=limit,
                check=lambda msg: msg.author == ctx.author,
                before=ctx.message,
            )

            if deleted:
                message = Tr.t(
                    "message.prune.self.response.success",
                    locale=locale,
                    count=len(deleted),
                )
            else:
                message = Tr.t("message.prune.self.response.no_messages", locale=locale)

            await ctx.send(message, ephemeral=True, delete_after=5.0)

        except discord.Forbidden:
            await ctx.send(
                Tr.t("message.prune.response.forbidden", locale=locale),
                ephemeral=True,
            )
        except discord.HTTPException as e:
            await ctx.send(
                Tr.t(
                    "message.prune.response.http_exception",
                    locale=locale,
                    error=str(e),
                ),
                ephemeral=True,
            )

    def _can_access_channel(self, channel: discord.abc.GuildChannel) -> bool:
        """Check if the bot can read message history and manage messages in a channel."""
        permissions = channel.permissions_for(channel.guild.me)
        return permissions.read_message_history and permissions.manage_messages


async def setup(core: "PlanaCore") -> None:
    """Add the MessageManager cog to the provided core."""
    try:
        await core.add_cog(PlanaMessage(core))
    except Exception as e:
        core.handle_exception("Failed to load MessageManager cog", e)
