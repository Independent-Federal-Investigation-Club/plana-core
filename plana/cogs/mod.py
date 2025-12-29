import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from plana.services.manager import GuildManager
from plana.utils.context import PlanaContext
from plana.utils.translate import PlanaLocaleStr, Tr

if TYPE_CHECKING:
    from plana.utils.core import PlanaCore


class PlanaModeration(commands.Cog):
    """Cog responsible for handling moderation commands and server management."""

    def __init__(self, core: "PlanaCore") -> None:
        self.core: "PlanaCore" = core
        self.name = "moderation"
        self.description = "Moderation commands for managing server members"

    def _parse_duration(self, duration_str: str) -> Optional[timedelta]:
        """
        Parse duration string into timedelta object.

        Args:
            duration_str: Duration string like "1d", "2h", "30m", "1w"

        Returns:
            timedelta object or None if parsing fails
        """
        if not duration_str:
            return

        # Regex pattern to match duration format
        pattern = r"^(\d+)([smhdw])$"
        match = re.match(pattern, duration_str.lower())

        if not match:
            return

        amount, unit = match.groups()
        amount = int(amount)

        unit_mapping = {
            "s": timedelta(seconds=amount),
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
            "w": timedelta(weeks=amount),
        }

        return unit_mapping.get(unit)

    def _format_duration(self, duration: timedelta) -> str:
        """Format timedelta into human-readable string."""
        total_seconds = int(duration.total_seconds())
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds and not (days or hours):
            parts.append(f"{seconds}s")

        return " ".join(parts) if parts else "0s"

    async def _get_mute_role(self, guild: discord.Guild | None) -> Optional[discord.Role]:
        """Get the configured mute role for the guild."""
        # This would typically fetch from database/config
        # For now, look for a role named "Muted"
        if guild is None:
            return
        for role in guild.roles:
            if role.name.lower() in ["muted", "mute"]:
                return role
        return

    async def _dm_user(self, user: discord.Member | discord.User, embed: discord.Embed) -> bool:
        """Attempt to send a DM to a user."""
        try:
            await user.send(embed=embed)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False

    async def _log_moderation_action(
        self, guild: discord.Guild | None, action_type: str, data: dict
    ) -> None:
        """Log moderation action to database."""
        # This would typically save to database
        # Implementation depends on your database schema
        if guild is None:
            return
        pass

    @commands.hybrid_command(
        name=PlanaLocaleStr("moderation.ban.name"),
        description=PlanaLocaleStr("moderation.ban.description"),
    )
    @app_commands.describe(
        member=PlanaLocaleStr("moderation.ban.param.member.description"),
        reason=PlanaLocaleStr("moderation.ban.param.reason.description"),
        duration=PlanaLocaleStr("moderation.ban.param.duration.description"),
        delete_days=PlanaLocaleStr("moderation.ban.param.delete_days.description"),
    )
    @app_commands.rename(
        member=PlanaLocaleStr("moderation.ban.param.member.name"),
        reason=PlanaLocaleStr("moderation.ban.param.reason.name"),
        duration=PlanaLocaleStr("moderation.ban.param.duration.name"),
        delete_days=PlanaLocaleStr("moderation.ban.param.delete_days.name"),
    )
    @commands.guild_only()
    @commands.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def ban(
        self,
        ctx: PlanaContext,
        member: discord.Member,
        reason: str = "No reason provided",
        duration: Optional[str] = None,
        delete_days: int = 0,
    ) -> None:
        """Ban a member from the server with optional duration."""
        await ctx.defer()
        locale = await GuildManager.get_locale(ctx)

        # Validation checks
        if member == ctx.author:
            await ctx.send(
                Tr.t("moderation.ban.response.cannot_ban_self", locale=locale), ephemeral=True
            )
            return

        if member == ctx.guild.owner:
            await ctx.send(
                Tr.t("moderation.ban.response.cannot_ban_owner", locale=locale), ephemeral=True
            )
            return

        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send(
                Tr.t("moderation.ban.response.hierarchy_error", locale=locale), ephemeral=True
            )
            return

        if member.top_role >= ctx.guild.me.top_role:
            await ctx.send(
                Tr.t("moderation.ban.response.bot_hierarchy_error", locale=locale), ephemeral=True
            )
            return

        # Check if already banned
        try:
            await ctx.guild.fetch_ban(member)
            await ctx.send(
                Tr.t("moderation.ban.response.already_banned", locale=locale, member=str(member)),
                ephemeral=True,
            )
            return
        except discord.NotFound:
            pass  # Not banned, continue

        # Parse duration if provided
        duration_delta = None
        if duration:
            duration_delta = self._parse_duration(duration)
            if not duration_delta:
                await ctx.send(
                    Tr.t("moderation.ban.response.invalid_duration", locale=locale),
                    ephemeral=True,
                )
                return

        # Validate delete_days
        delete_days = max(0, min(7, delete_days))

        try:
            # Send DM notification before banning
            embed = discord.Embed(
                title="You have been banned",
                description=f"**Server:** {ctx.guild.name}\n**Reason:** {reason}",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc),
            )
            if duration_delta:
                embed.add_field(
                    name="Duration", value=self._format_duration(duration_delta), inline=False
                )
            await self._dm_user(member, embed)

            # Execute ban
            await member.ban(
                reason=f"{reason} | Moderator: {ctx.author}", delete_message_days=delete_days
            )

            # Log action
            await self._log_moderation_action(
                ctx.guild,
                "ban",
                {
                    "user_id": member.id,
                    "moderator_id": ctx.author.id,
                    "reason": reason,
                    "duration": duration_delta.total_seconds() if duration_delta else None,
                    "delete_days": delete_days,
                },
            )

            # Send success response
            if duration_delta:
                await ctx.send(
                    Tr.t(
                        "moderation.ban.response.success_temp",
                        locale=locale,
                        member=str(member),
                        duration=self._format_duration(duration_delta),
                        reason=reason,
                    )
                )
            else:
                await ctx.send(
                    Tr.t(
                        "moderation.ban.response.success",
                        locale=locale,
                        member=str(member),
                        reason=reason,
                    )
                )

        except discord.Forbidden:
            await ctx.send(Tr.t("moderation.ban.response.forbidden", locale=locale), ephemeral=True)
        except discord.HTTPException as e:
            await ctx.send(
                Tr.t("moderation.ban.response.error", locale=locale, error=str(e)), ephemeral=True
            )

    @commands.hybrid_command(
        name=PlanaLocaleStr("moderation.unban.name"),
        description=PlanaLocaleStr("moderation.unban.description"),
    )
    @app_commands.describe(
        user=PlanaLocaleStr("moderation.unban.param.user.description"),
        reason=PlanaLocaleStr("moderation.unban.param.reason.description"),
    )
    @app_commands.rename(
        user=PlanaLocaleStr("moderation.unban.param.user.name"),
        reason=PlanaLocaleStr("moderation.unban.param.reason.name"),
    )
    @commands.guild_only()
    @commands.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def unban(self, ctx: PlanaContext, user: str, reason: str = "No reason provided") -> None:
        """Unban a user from the server."""
        await ctx.defer()
        locale = await GuildManager.get_locale(ctx)

        # Try to parse user ID or username
        user_obj = None

        # Try user ID first
        if user.isdigit():
            try:
                user_obj = await self.core.fetch_user(int(user))
            except discord.NotFound:
                pass

        # If not found, try searching ban list
        if not user_obj:
            try:
                bans = [ban async for ban in ctx.guild.bans()]
                for ban in bans:
                    if (
                        user.lower() in ban.user.name.lower()
                        or user == str(ban.user)
                        or user == str(ban.user.id)
                    ):
                        user_obj = ban.user
                        break
            except discord.Forbidden:
                await ctx.send(
                    Tr.t("moderation.unban.response.forbidden", locale=locale), ephemeral=True
                )
                return

        if not user_obj:
            await ctx.send(
                Tr.t("moderation.unban.response.user_not_found", locale=locale), ephemeral=True
            )
            return

        try:
            # Check if user is actually banned
            await ctx.guild.fetch_ban(user_obj)

            # Unban the user
            await ctx.guild.unban(user_obj, reason=f"{reason} | Moderator: {ctx.author}")

            # Log action
            await self._log_moderation_action(
                ctx.guild,
                "unban",
                {"user_id": user_obj.id, "moderator_id": ctx.author.id, "reason": reason},
            )

            await ctx.send(
                Tr.t(
                    "moderation.unban.response.success",
                    locale=locale,
                    user=str(user_obj),
                    reason=reason,
                )
            )

        except discord.NotFound:
            await ctx.send(
                Tr.t("moderation.unban.response.not_banned", locale=locale, user=user),
                ephemeral=True,
            )
        except discord.Forbidden:
            await ctx.send(
                Tr.t("moderation.unban.response.forbidden", locale=locale), ephemeral=True
            )
        except discord.HTTPException as e:
            await ctx.send(
                Tr.t("moderation.unban.response.error", locale=locale, error=str(e)),
                ephemeral=True,
            )

    @commands.hybrid_command(
        name=PlanaLocaleStr("moderation.kick.name"),
        description=PlanaLocaleStr("moderation.kick.description"),
    )
    @app_commands.describe(
        member=PlanaLocaleStr("moderation.kick.param.member.description"),
        reason=PlanaLocaleStr("moderation.kick.param.reason.description"),
    )
    @app_commands.rename(
        member=PlanaLocaleStr("moderation.kick.param.member.name"),
        reason=PlanaLocaleStr("moderation.kick.param.reason.name"),
    )
    @commands.guild_only()
    @commands.has_guild_permissions(kick_members=True)
    @commands.bot_has_guild_permissions(kick_members=True)
    async def kick(
        self, ctx: PlanaContext, member: discord.Member, reason: str = "No reason provided"
    ) -> None:
        """Kick a member from the server."""
        await ctx.defer()
        locale = await GuildManager.get_locale(ctx)

        # Validation checks
        if member == ctx.author:
            await ctx.send(
                Tr.t("moderation.kick.response.cannot_kick_self", locale=locale), ephemeral=True
            )
            return

        if member == ctx.guild.owner:
            await ctx.send(
                Tr.t("moderation.kick.response.cannot_kick_owner", locale=locale), ephemeral=True
            )
            return

        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send(
                Tr.t("moderation.kick.response.hierarchy_error", locale=locale), ephemeral=True
            )
            return

        if member.top_role >= ctx.guild.me.top_role:
            await ctx.send(
                Tr.t("moderation.kick.response.bot_hierarchy_error", locale=locale),
                ephemeral=True,
            )
            return

        try:
            # Send DM notification before kicking
            embed = discord.Embed(
                title="You have been kicked",
                description=f"**Server:** {ctx.guild.name}\n**Reason:** {reason}",
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc),
            )
            await self._dm_user(member, embed)

            # Execute kick
            await member.kick(reason=f"{reason} | Moderator: {ctx.author}")

            # Log action
            await self._log_moderation_action(
                ctx.guild,
                "kick",
                {"user_id": member.id, "moderator_id": ctx.author.id, "reason": reason},
            )

            await ctx.send(
                Tr.t(
                    "moderation.kick.response.success",
                    locale=locale,
                    member=str(member),
                    reason=reason,
                )
            )

        except discord.Forbidden:
            await ctx.send(
                Tr.t("moderation.kick.response.forbidden", locale=locale), ephemeral=True
            )
        except discord.HTTPException as e:
            await ctx.send(
                Tr.t("moderation.kick.response.error", locale=locale, error=str(e)),
                ephemeral=True,
            )

    @commands.hybrid_command(
        name=PlanaLocaleStr("moderation.timeout.name"),
        description=PlanaLocaleStr("moderation.timeout.description"),
    )
    @app_commands.describe(
        member=PlanaLocaleStr("moderation.timeout.param.member.description"),
        duration=PlanaLocaleStr("moderation.timeout.param.duration.description"),
        reason=PlanaLocaleStr("moderation.timeout.param.reason.description"),
    )
    @app_commands.rename(
        member=PlanaLocaleStr("moderation.timeout.param.member.name"),
        duration=PlanaLocaleStr("moderation.timeout.param.duration.name"),
        reason=PlanaLocaleStr("moderation.timeout.param.reason.name"),
    )
    @commands.guild_only()
    @commands.has_guild_permissions(moderate_members=True)
    @commands.bot_has_guild_permissions(moderate_members=True)
    async def timeout(
        self,
        ctx: PlanaContext,
        member: discord.Member,
        duration: str,
        reason: str = "No reason provided",
    ) -> None:
        """Timeout a member (Discord's built-in timeout feature)."""
        await ctx.defer()
        locale = await GuildManager.get_locale(ctx)

        if member == ctx.guild.owner:
            await ctx.send(
                Tr.t("moderation.timeout.response.cannot_timeout_owner", locale=locale),
                ephemeral=True,
            )
            return

        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send(
                Tr.t("moderation.timeout.response.hierarchy_error", locale=locale), ephemeral=True
            )
            return

        if member.top_role >= ctx.guild.me.top_role:
            await ctx.send(
                Tr.t("moderation.timeout.response.bot_hierarchy_error", locale=locale),
                ephemeral=True,
            )
            return

        # Parse duration
        duration_delta = self._parse_duration(duration)
        if not duration_delta or duration_delta > timedelta(days=28):
            await ctx.send(
                Tr.t("moderation.timeout.response.invalid_duration", locale=locale),
                ephemeral=True,
            )
            return

        # Check if already timed out
        if member.is_timed_out():  # type: ignore
            await ctx.send(
                Tr.t(
                    "moderation.timeout.response.already_timed_out",
                    locale=locale,
                    member=str(member),
                ),
                ephemeral=True,
            )
            return

        try:
            # Send DM notification before timeout
            embed = discord.Embed(
                title="You have been timed out",
                description=f"**Server:** {ctx.guild.name}\n**Reason:** {reason}\n**Duration:** {self._format_duration(duration_delta)}",
                color=discord.Color.yellow(),
                timestamp=datetime.now(timezone.utc),
            )
            await self._dm_user(member, embed)

            # Execute timeout
            until = datetime.now(timezone.utc) + duration_delta
            await member.timeout(until, reason=f"{reason} | Moderator: {ctx.author}")

            # Log action
            await self._log_moderation_action(
                ctx.guild,
                "timeout",
                {
                    "user_id": member.id,
                    "moderator_id": ctx.author.id,
                    "reason": reason,
                    "duration": duration_delta.total_seconds(),
                    "until": until.isoformat(),
                },
            )

            await ctx.send(
                Tr.t(
                    "moderation.timeout.response.success",
                    locale=locale,
                    member=str(member),
                    duration=self._format_duration(duration_delta),
                    reason=reason,
                )
            )

        except discord.Forbidden:
            await ctx.send(
                Tr.t("moderation.timeout.response.forbidden", locale=locale), ephemeral=True
            )
        except discord.HTTPException as e:
            await ctx.send(
                Tr.t("moderation.timeout.response.error", locale=locale, error=str(e)),
                ephemeral=True,
            )

    @commands.hybrid_command(
        name=PlanaLocaleStr("moderation.untimeout.name"),
        description=PlanaLocaleStr("moderation.untimeout.description"),
    )
    @app_commands.describe(
        member=PlanaLocaleStr("moderation.untimeout.param.member.description"),
        reason=PlanaLocaleStr("moderation.untimeout.param.reason.description"),
    )
    @app_commands.rename(
        member=PlanaLocaleStr("moderation.untimeout.param.member.name"),
        reason=PlanaLocaleStr("moderation.untimeout.param.reason.name"),
    )
    @commands.guild_only()
    @commands.has_guild_permissions(moderate_members=True)
    @commands.bot_has_guild_permissions(moderate_members=True)
    async def untimeout(
        self, ctx: PlanaContext, member: discord.Member, reason: str = "No reason provided"
    ) -> None:
        """Remove timeout from a member."""
        await ctx.defer()
        locale = await GuildManager.get_locale(ctx)

        if not member.is_timed_out():
            await ctx.send(
                Tr.t(
                    "moderation.untimeout.response.not_timed_out", locale=locale, member=str(member)
                ),
                ephemeral=True,
            )
            return

        try:
            # Remove timeout
            await member.timeout(None, reason=f"{reason} | Moderator: {ctx.author}")

            # Log action
            await self._log_moderation_action(
                ctx.guild,
                "untimeout",
                {"user_id": member.id, "moderator_id": ctx.author.id, "reason": reason},
            )

            await ctx.send(
                Tr.t(
                    "moderation.untimeout.response.success",
                    locale=locale,
                    member=str(member),
                    reason=reason,
                )
            )

        except discord.Forbidden:
            await ctx.send(
                Tr.t("moderation.untimeout.response.forbidden", locale=locale), ephemeral=True
            )
        except discord.HTTPException as e:
            await ctx.send(
                Tr.t("moderation.untimeout.response.error", locale=locale, error=str(e)),
                ephemeral=True,
            )

    @commands.hybrid_command(
        name=PlanaLocaleStr("moderation.warn.name"),
        description=PlanaLocaleStr("moderation.warn.description"),
    )
    @app_commands.describe(
        member=PlanaLocaleStr("moderation.warn.param.member.description"),
        reason=PlanaLocaleStr("moderation.warn.param.reason.description"),
    )
    @app_commands.rename(
        member=PlanaLocaleStr("moderation.warn.param.member.name"),
        reason=PlanaLocaleStr("moderation.warn.param.reason.name"),
    )
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def warn(self, ctx: PlanaContext, member: discord.Member, *, reason: str) -> None:
        """Issue a warning to a member."""
        await ctx.defer()
        locale = await GuildManager.get_locale(ctx)

        if member.bot:
            await ctx.send(
                Tr.t("moderation.warn.response.cannot_warn_bots", locale=locale), ephemeral=True
            )
            return

        try:
            # Send DM notification
            embed = discord.Embed(
                title="You have received a warning",
                description=f"**Server:** {ctx.guild.name}\n**Reason:** {reason}",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc),
            )
            await ctx.send(content=f"{member.mention}", embed=embed)

            # Log warning action (would typically save to database)
            await self._log_moderation_action(
                ctx.guild,
                "warn",
                {"user_id": member.id, "moderator_id": ctx.author.id, "reason": reason},
            )

        except Exception as e:
            await ctx.send(
                Tr.t("moderation.warn.response.error", locale=locale, error=str(e)),
                ephemeral=True,
            )

    @commands.hybrid_command(
        name=PlanaLocaleStr("moderation.warnings.name"),
        description=PlanaLocaleStr("moderation.warnings.description"),
    )
    @app_commands.describe(
        member=PlanaLocaleStr("moderation.warnings.param.member.description"),
    )
    @app_commands.rename(
        member=PlanaLocaleStr("moderation.warnings.param.member.name"),
    )
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def warnings(self, ctx: PlanaContext, member: discord.Member) -> None:
        """View warnings for a member."""
        await ctx.defer()
        locale = await GuildManager.get_locale(ctx)

        try:
            # This would typically fetch from database
            # For now, return placeholder response
            warnings_list = []  # Placeholder - would be actual warnings from DB

            if not warnings_list:
                await ctx.send(
                    Tr.t(
                        "moderation.warnings.response.no_warnings",
                        locale=locale,
                        member=str(member),
                    ),
                    ephemeral=True,
                )
                return

            # Build embed with warnings
            embed = discord.Embed(
                title=Tr.t("moderation.warnings.response.title", locale=locale, member=str(member)),
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc),
            )

            # Add warning entries (placeholder)
            for i, warning in enumerate(warnings_list[:10], 1):  # Limit to 10 warnings
                embed.add_field(
                    name=f"Warning #{i}",
                    value=Tr.t(
                        "moderation.warnings.response.warning_entry",
                        locale=locale,
                        id=i,
                        date=warning.get("date", "Unknown"),
                        moderator=warning.get("moderator", "Unknown"),
                        reason=warning.get("reason", "No reason"),
                    ),
                    inline=False,
                )

            embed.set_footer(
                text=Tr.t(
                    "moderation.warnings.response.total", locale=locale, count=len(warnings_list)
                )
            )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(
                Tr.t("moderation.warnings.response.error", locale=locale, error=str(e)),
                ephemeral=True,
            )

    @commands.hybrid_command(
        name=PlanaLocaleStr("moderation.clearwarns.name"),
        description=PlanaLocaleStr("moderation.clearwarns.description"),
    )
    @app_commands.describe(
        member=PlanaLocaleStr("moderation.clearwarns.param.member.description"),
        reason=PlanaLocaleStr("moderation.clearwarns.param.reason.description"),
    )
    @app_commands.rename(
        member=PlanaLocaleStr("moderation.clearwarns.param.member.name"),
        reason=PlanaLocaleStr("moderation.clearwarns.param.reason.name"),
    )
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def clearwarns(
        self, ctx: PlanaContext, member: discord.Member, reason: str = "No reason provided"
    ) -> None:
        """Clear all warnings for a member."""
        await ctx.defer()
        locale = await GuildManager.get_locale(ctx)

        try:
            # This would typically clear from database
            # For now, return placeholder response
            cleared_count = 0  # Placeholder - would be actual count

            if cleared_count == 0:
                await ctx.send(
                    Tr.t(
                        "moderation.clearwarns.response.no_warnings",
                        locale=locale,
                        member=str(member),
                    ),
                    ephemeral=True,
                )
                return

            # Log action
            await self._log_moderation_action(
                ctx.guild,
                "clearwarns",
                {
                    "user_id": member.id,
                    "moderator_id": ctx.author.id,
                    "reason": reason,
                    "cleared_count": cleared_count,
                },
            )

            await ctx.send(
                Tr.t(
                    "moderation.clearwarns.response.success",
                    locale=locale,
                    count=cleared_count,
                    member=str(member),
                    reason=reason,
                )
            )

        except Exception as e:
            await ctx.send(
                Tr.t("moderation.clearwarns.response.error", locale=locale, error=str(e)),
                ephemeral=True,
            )

    @commands.hybrid_command(
        name=PlanaLocaleStr("moderation.mute.name"),
        description=PlanaLocaleStr("moderation.mute.description"),
    )
    @app_commands.describe(
        member=PlanaLocaleStr("moderation.mute.param.member.description"),
        duration=PlanaLocaleStr("moderation.mute.param.duration.description"),
        reason=PlanaLocaleStr("moderation.mute.param.reason.description"),
    )
    @app_commands.rename(
        member=PlanaLocaleStr("moderation.mute.param.member.name"),
        duration=PlanaLocaleStr("moderation.mute.param.duration.name"),
        reason=PlanaLocaleStr("moderation.mute.param.reason.name"),
    )
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def mute(
        self,
        ctx: PlanaContext,
        member: discord.Member,
        duration: Optional[str] = None,
        reason: str = "No reason provided",
    ) -> None:
        """Mute a member by assigning the muted role."""
        await ctx.defer()
        locale = await GuildManager.get_locale(ctx)

        # Get mute role
        mute_role = await self._get_mute_role(ctx.guild)
        if not mute_role:
            await ctx.send(
                Tr.t("moderation.mute.response.no_mute_role", locale=locale), ephemeral=True
            )
            return

        # Validation checks
        if member == ctx.author:
            await ctx.send(
                Tr.t("moderation.mute.response.cannot_mute_self", locale=locale), ephemeral=True
            )
            return

        if member == ctx.guild.owner:
            await ctx.send(
                Tr.t("moderation.mute.response.cannot_mute_owner", locale=locale), ephemeral=True
            )
            return

        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send(
                Tr.t("moderation.mute.response.hierarchy_error", locale=locale), ephemeral=True
            )
            return

        if member.top_role >= ctx.guild.me.top_role:
            await ctx.send(
                Tr.t("moderation.mute.response.bot_hierarchy_error", locale=locale),
                ephemeral=True,
            )
            return

        if mute_role in member.roles:
            await ctx.send(
                Tr.t("moderation.mute.response.already_muted", locale=locale, member=str(member)),
                ephemeral=True,
            )
            return

        # Parse duration if provided
        duration_delta = None
        if duration:
            duration_delta = self._parse_duration(duration)
            if not duration_delta:
                await ctx.send(
                    Tr.t("moderation.mute.response.invalid_duration", locale=locale),
                    ephemeral=True,
                )
                return

        try:
            # Send DM notification before muting
            embed = discord.Embed(
                title="You have been muted",
                description=f"**Server:** {ctx.guild.name}\n**Reason:** {reason}",
                color=discord.Color.dark_gray(),
                timestamp=datetime.now(timezone.utc),
            )
            if duration_delta:
                embed.add_field(
                    name="Duration", value=self._format_duration(duration_delta), inline=False
                )
            await self._dm_user(member, embed)

            # Add mute role
            await member.add_roles(mute_role, reason=f"{reason} | Moderator: {ctx.author}")

            # Log action
            await self._log_moderation_action(
                ctx.guild,
                "mute",
                {
                    "user_id": member.id,
                    "moderator_id": ctx.author.id,
                    "reason": reason,
                    "duration": duration_delta.total_seconds() if duration_delta else None,
                },
            )

            # Send success response
            if duration_delta:
                await ctx.send(
                    Tr.t(
                        "moderation.mute.response.success_temp",
                        locale=locale,
                        member=str(member),
                        duration=self._format_duration(duration_delta),
                        reason=reason,
                    )
                )
            else:
                await ctx.send(
                    Tr.t(
                        "moderation.mute.response.success",
                        locale=locale,
                        member=str(member),
                        reason=reason,
                    )
                )

        except discord.Forbidden:
            await ctx.send(
                Tr.t("moderation.mute.response.forbidden", locale=locale), ephemeral=True
            )
        except discord.HTTPException as e:
            await ctx.send(
                Tr.t("moderation.mute.response.error", locale=locale, error=str(e)),
                ephemeral=True,
            )

    @commands.hybrid_command(
        name=PlanaLocaleStr("moderation.unmute.name"),
        description=PlanaLocaleStr("moderation.unmute.description"),
    )
    @app_commands.describe(
        member=PlanaLocaleStr("moderation.unmute.param.member.description"),
        reason=PlanaLocaleStr("moderation.unmute.param.reason.description"),
    )
    @app_commands.rename(
        member=PlanaLocaleStr("moderation.unmute.param.member.name"),
        reason=PlanaLocaleStr("moderation.unmute.param.reason.name"),
    )
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def unmute(
        self, ctx: PlanaContext, member: discord.Member, reason: str = "No reason provided"
    ) -> None:
        """Unmute a member by removing the muted role."""
        await ctx.defer()
        locale = await GuildManager.get_locale(ctx)

        # Get mute role
        mute_role = await self._get_mute_role(ctx.guild)
        if not mute_role:
            await ctx.send(
                Tr.t("moderation.unmute.response.no_mute_role", locale=locale), ephemeral=True
            )
            return

        if mute_role not in member.roles:
            await ctx.send(
                Tr.t("moderation.unmute.response.not_muted", locale=locale, member=str(member)),
                ephemeral=True,
            )
            return

        try:
            # Remove mute role
            await member.remove_roles(mute_role, reason=f"{reason} | Moderator: {ctx.author}")

            # Log action
            await self._log_moderation_action(
                ctx.guild,
                "unmute",
                {"user_id": member.id, "moderator_id": ctx.author.id, "reason": reason},
            )

            await ctx.send(
                Tr.t(
                    "moderation.unmute.response.success",
                    locale=locale,
                    member=str(member),
                    reason=reason,
                )
            )

        except discord.Forbidden:
            await ctx.send(
                Tr.t("moderation.unmute.response.forbidden", locale=locale), ephemeral=True
            )
        except discord.HTTPException as e:
            await ctx.send(
                Tr.t("moderation.unmute.response.error", locale=locale, error=str(e)),
                ephemeral=True,
            )


async def setup(core: "PlanaCore") -> None:
    """Add the ModerationManager cog to the provided core."""
    try:
        await core.add_cog(PlanaModeration(core))
    except Exception as e:
        core.handle_exception("Failed to load ModerationManager cog", e)
