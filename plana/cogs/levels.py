import time
import random
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Any
from venv import logger

import discord
from discord import app_commands
from discord.ext import commands, tasks

from plana.models.levels import (
    AnnouncementType,
    LevelSetting,
    UserLevelData,
)

from plana.services.manager import UserManager, GuildManager
from plana.utils.context import PlanaContext
from plana.utils.translate import Tr, PlanaLocaleStr

if TYPE_CHECKING:
    from plana.utils.core import PlanaCore


class PlanaLevels(commands.Cog):
    """Comprehensive level system with XP tracking, role rewards, and leaderboards."""

    def __init__(self, core: "PlanaCore") -> None:
        self.core: "PlanaCore" = core
        self.name = "levels"
        self.description = "Manage server leveling system with XP, role rewards, and leaderboards"

        self.config_cache: Dict[int, LevelSetting | None] = {}

        # User cooldowns for XP gain
        self.user_cooldowns: Dict[Tuple[int, int], float] = {}

        # Start background tasks
        self.cleanup_cooldowns_task.start()

    def cog_unload(self) -> None:
        """Clean up tasks when cog is unloaded."""
        self.cleanup_cooldowns_task.cancel()

    @tasks.loop(minutes=5)
    async def cleanup_cooldowns_task(self):
        """Clean up expired cooldowns to prevent memory leaks."""
        current_time = time.time()
        expired_cooldowns = [
            key
            for key, last_time in self.user_cooldowns.items()
            if current_time - last_time > 300  # 5 minutes
        ]

        for key in expired_cooldowns:
            del self.user_cooldowns[key]

    @cleanup_cooldowns_task.before_loop
    async def before_tasks(self):
        """Wait until bot is ready before starting tasks."""
        await self.core.wait_until_ready()

    async def get_level_config(self, guild_id: int) -> LevelSetting | None:
        """Get level configuration for a guild with caching."""
        guild_configs = await GuildManager.get(guild_id)
        return guild_configs.levels if guild_configs else None

    def calculate_xp_gain(
        self, message: discord.Message, config: LevelSetting, user_roles: List[int]
    ) -> int:
        """Calculate XP gain for a message."""
        base_xp = config.xp_per_message

        # Apply message length bonus
        if config.message_length_bonus:
            length_bonus = min(len(message.content) // 50, 10)  # Max 10 bonus XP
            base_xp += length_bonus

        # Apply role boosters
        multiplier = 1.0
        for booster in config.xp_boosters:
            if booster.role_id in user_roles:
                multiplier = max(multiplier, booster.multiplier)

        # Add some randomness (±20%)
        randomness = random.uniform(0.8, 1.2)

        final_xp = int(base_xp * multiplier * randomness)
        return min(final_xp, config.max_xp_per_message)

    def should_gain_xp(
        self, message: discord.Message, config: LevelSetting, user_roles: List[int]
    ) -> bool:
        """Check if user should gain XP from this message."""
        # Check if levels are enabled
        if not config.enabled:
            return False

        # Check if user is a bot and bots are ignored
        if message.author.bot:
            return False

        # Check cooldown
        key = (message.guild.id, message.author.id)
        current_time = time.time()
        if key in self.user_cooldowns:
            if current_time - self.user_cooldowns[key] < config.xp_cooldown:
                return False

        # Check target XP roles
        if config.target_xp_roles_mode == False:
            # Blacklist mode: don't gain XP if user has any blacklisted role
            if any(role_id in config.target_xp_roles for role_id in user_roles):
                return False
        else:
            # Whitelist mode: only gain XP if user has at least one whitelisted role
            if not any(role_id in config.target_xp_roles for role_id in user_roles):
                return False

        # Check target XP channels
        if config.target_xp_channels_mode == False:
            # Blacklist mode: don't gain XP in blacklisted channels
            if message.channel.id in config.target_xp_channels:
                return False
        else:
            # Whitelist mode: only gain XP in whitelisted channels
            if message.channel.id not in config.target_xp_channels:
                return False

        return True

    async def handle_xp_gain(
        self, guild_id: int, user_id: int, xp_gain: int, message_count: int = 1
    ) -> Tuple[int, int]:
        """Handle XP gain for a user."""
        config = await self.get_level_config(guild_id)
        user_data: UserLevelData = await UserManager.get_property(
            guild_id=guild_id, user_id=user_id, model=UserLevelData
        )
        if not user_data:
            return

        # Update XP and messages sent
        user_data.xp += xp_gain
        user_data.messages_sent += message_count

        old_level = user_data.level
        new_level = config.calculate_level_from_xp(user_data.xp)
        user_data.level = new_level

        await UserManager.update_property(guild_id, user_id, data=user_data)

        return old_level, new_level

    async def handle_level_up(self, message: discord.Message, new_level: int):
        """Handle level up announcement and role rewards."""
        config = await self.get_level_config(message.guild.id)

        # Handle role rewards
        await self.apply_role_rewards(message.author, new_level, config)

        # Handle announcements
        if config.announcement_type == AnnouncementType.DISABLED:
            return

        if config.announcement_message:
            content, embeds, view = await config.announcement_message._parse()
        else:
            content = f"Congratulations {message.author.mention}, you reached level {new_level}!"
            embeds = []
            view = None

        # [TODO] Handle Message formating logic with templates variables for content, embeds

        if config.announcement_type == AnnouncementType.PRIVATE_MESSAGE:
            dm_channel = await message.author.create_dm()
            return await dm_channel.send(content, embeds=embeds, view=view)
        elif config.announcement_type == AnnouncementType.CUSTOM_CHANNEL:
            if config.announcement_channel_id:
                channel = message.guild.get_channel(config.announcement_channel_id)
                if channel:
                    return await channel.send(content, embeds=embeds, view=view)

        # Default to current channel
        return await message.channel.send(content, embeds=embeds, view=view)

    async def apply_role_rewards(self, member: discord.Member, level: int, config: LevelSetting):
        """Apply role rewards for reaching a level."""
        rewards_to_apply = [reward for reward in config.role_rewards if reward.level <= level]

        if not rewards_to_apply:
            return

        try:
            # Sort rewards by level (ascending)
            rewards_to_apply.sort(key=lambda r: r.level)

            if not config.stack_rewards:
                # Remove all previous level roles
                previous_role_ids = {
                    reward.role_id for reward in config.role_rewards if reward.level < level
                }
                roles_to_remove = [role for role in member.roles if role.id in previous_role_ids]
                if roles_to_remove:
                    await member.remove_roles(
                        *roles_to_remove, reason=f"Level {level} role reward (non-stacking)"
                    )

            # Add the highest level role(s)
            if config.stack_rewards:
                # Add all applicable roles
                roles_to_add = []
                for reward in rewards_to_apply:
                    role = member.guild.get_role(reward.role_id)
                    if role and role not in member.roles:
                        roles_to_add.append(role)

                if roles_to_add:
                    await member.add_roles(*roles_to_add, reason=f"Level {level} role reward")
            else:
                # Add only the highest level role
                highest_reward = rewards_to_apply[-1]
                role = member.guild.get_role(highest_reward.role_id)
                if role and role not in member.roles:
                    await member.add_roles(role, reason=f"Level {level} role reward")

        except discord.Forbidden:
            pass  # Bot doesn't have permission to manage roles

    async def get_leaderboard(self, guild_id: int):
        """Get the server leaderboard."""
        # Fetch all user data
        users = await UserManager.get_all(guild_id)
        if not users:
            return []

        leaderboard = []
        for user in users:
            level_data: UserLevelData = await UserManager.get_property(
                guild_id=guild_id, user_id=user.user_id, model=UserLevelData
            )
            level_data.user_id = user.user_id
            leaderboard.append(level_data)

        leaderboard.sort(reverse=True)
        return leaderboard

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle XP gain from messages."""
        # Basic checks
        if not message.guild or not message.content.strip():
            return

        if message.author.bot:
            return

        # Get configuration
        config = await self.get_level_config(message.guild.id)
        if not config:
            return

        # Get user roles
        user_roles = (
            [role.id for role in message.author.roles] if hasattr(message.author, "roles") else []
        )

        # Check if user should gain XP
        if not self.should_gain_xp(message, config, user_roles):
            return

        # Calculate XP gain
        xp_gain = self.calculate_xp_gain(message, config, user_roles)

        # Update cooldown
        key = (message.guild.id, message.author.id)
        self.user_cooldowns[key] = time.time()

        old_level, new_level = await self.handle_xp_gain(
            guild_id=message.guild.id, user_id=message.author.id, xp_gain=xp_gain
        )

        logger.info(f"User {message.author.id} gained {xp_gain} XP in guild {message.guild.id} ")

        # Handle level up, role rewards, and announcements
        if old_level < new_level:
            await self.handle_level_up(message, new_level)

    # User Commands
    @commands.hybrid_group(
        name=PlanaLocaleStr("levels.name"),
        description=PlanaLocaleStr("levels.description"),
    )
    @commands.guild_only()
    async def levels(self, ctx: PlanaContext) -> None:
        """Entry point for level system commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(str(ctx.command))

    @levels.command(
        name=PlanaLocaleStr("levels.rank.name"),
        description=PlanaLocaleStr("levels.rank.description"),
    )
    @app_commands.describe(member=PlanaLocaleStr("levels.rank.param.member.description"))
    @app_commands.rename(member=PlanaLocaleStr("levels.rank.param.member.name"))
    @commands.guild_only()
    async def rank(self, ctx: PlanaContext, member: Optional[discord.Member] = None) -> None:
        """Show level information for a user."""
        target = member or ctx.author
        locale = await GuildManager.get_locale(ctx)

        config = await self.get_level_config(ctx.guild.id)

        if not config or not config.enabled:
            await ctx.send(Tr.t("levels.response.disabled", locale=locale), ephemeral=True)
            return

        # Load user data
        user_data: UserLevelData = await UserManager.get_property(
            guild_id=ctx.guild.id, user_id=target.id, model=UserLevelData
        )

        # Calculate progress
        current_level_xp, next_level_xp, xp_in_current_level = user_data.calculate_level_progress(
            config
        )

        # Create embed
        embed = discord.Embed(
            title=Tr.t("levels.rank.embed.title", locale=locale, user=target.display_name),
            color=0x3498DB,
        )

        embed.add_field(
            name=Tr.t("levels.rank.embed.level", locale=locale),
            value=str(user_data.level),
            inline=True,
        )

        embed.add_field(
            name=Tr.t("levels.rank.embed.total_xp", locale=locale),
            value=f"{user_data.xp:,}",
            inline=True,
        )

        embed.add_field(
            name=Tr.t("levels.rank.embed.messages", locale=locale),
            value=f"{user_data.messages_sent:,}",
            inline=True,
        )

        progress_bar = self.create_progress_bar(xp_in_current_level, current_level_xp)
        embed.add_field(
            name=Tr.t("levels.rank.embed.progress", locale=locale),
            value=f"{progress_bar}\n{xp_in_current_level:,}/{current_level_xp:,} XP",
            inline=False,
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        await ctx.send(embed=embed)

    @levels.command(
        name=PlanaLocaleStr("levels.leaderboard.name"),
        description=PlanaLocaleStr("levels.leaderboard.description"),
    )
    @app_commands.describe(page=PlanaLocaleStr("levels.leaderboard.param.page.description"))
    @app_commands.rename(page=PlanaLocaleStr("levels.leaderboard.param.page.name"))
    @commands.guild_only()
    async def leaderboard(self, ctx: PlanaContext, page: int = 1) -> None:
        """Show the server leaderboard."""
        locale = await GuildManager.get_locale(ctx)

        config = await self.get_level_config(ctx.guild.id)

        if not config.enabled:
            await ctx.send(Tr.t("levels.response.disabled", locale=locale), ephemeral=True)
            return

        page = max(1, page)
        limit = 10
        offset = (page - 1) * limit

        try:
            leaderboard_data = await self.get_leaderboard(ctx.guild.id)
        except Exception:
            await ctx.send(Tr.t("levels.leaderboard.response.error", locale=locale), ephemeral=True)
            return

        if not leaderboard_data:
            await ctx.send(Tr.t("levels.leaderboard.response.empty", locale=locale), ephemeral=True)
            return

        embed = discord.Embed(
            title=Tr.t("levels.leaderboard.embed.title", locale=locale, guild=ctx.guild.name),
            color=0xF1C40F,
        )

        description_lines = []

        user_data: UserLevelData
        for i, user_data in enumerate(leaderboard_data):
            rank = offset + i + 1
            user = ctx.guild.get_member(user_data.user_id)
            name = user.display_name if user else f"User {user_data.user_id}"

            description_lines.append(
                f"**{rank}.** {name} - Level {user_data.level} ({user_data.xp:,} XP)"
            )

        embed.description = "\n".join(description_lines)
        embed.set_footer(text=Tr.t("levels.leaderboard.embed.footer", locale=locale, page=page))

        await ctx.send(embed=embed)

    @levels.command(
        name=PlanaLocaleStr("levels.give-xp.name"),
        description=PlanaLocaleStr("levels.give-xp.description"),
    )
    @commands.has_guild_permissions(administrator=True)
    @commands.guild_only()
    async def give_xp(self, ctx: PlanaContext, member: discord.Member, xp: int) -> None:
        """Give XP to a user."""
        # [TODO] i18n for parameters and responses
        locale = await GuildManager.get_locale(ctx)

        if xp <= 0:
            return

        old_level, new_level = await self.handle_xp_gain(
            guild_id=ctx.guild.id, user_id=member.id, xp_gain=xp, message_count=0
        )

        if old_level < new_level:
            await self.handle_level_up(ctx.message, new_level)

        await ctx.send(
            Tr.t("levels.give-xp.response.success", locale=locale, xp=xp, user=member.mention),
            ephemeral=True,
        )

    @levels.command(
        name=PlanaLocaleStr("levels.toggle.name"),
        description=PlanaLocaleStr("levels.toggle.description"),
    )
    @commands.has_guild_permissions(administrator=True)
    @commands.guild_only()
    async def toggle(self, ctx: PlanaContext) -> None:
        """Enable the level system for the server."""
        locale = await GuildManager.get_locale(ctx)

        config = await self.get_level_config(ctx.guild.id)
        if not config:
            config = await LevelSetting.create(guild_id=ctx.guild.id)

        config.enabled = not config.enabled
        await config.save()

        status = "enabled" if config.enabled else "disabled"
        await ctx.send(Tr.t(f"levels.response.{status}", locale=locale), ephemeral=True)

    def create_progress_bar(self, current: int, total: int, length: int = 20) -> str:
        """Create a text-based progress bar."""
        # [TODO] Replace it with levels card embed
        if total == 0:
            progress = 1.0
        else:
            progress = min(current / total, 1.0)

        filled_length = int(length * progress)
        bar = "█" * filled_length + "░" * (length - filled_length)
        return f"[{bar}] {progress:.1%}"


async def setup(core: "PlanaCore") -> None:
    """Add the LevelsManager cog to the provided core."""
    try:
        await core.add_cog(PlanaLevels(core))
    except Exception as e:
        core.handle_exception("Failed to load LevelsManager cog", e)
