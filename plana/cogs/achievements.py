import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

import discord
from discord.ext import commands
from loguru import logger
from pydantic import BaseModel, Field

from plana.models.achievements import (
    AchievementSetting,
    CirteriaType,
    CustomAchievement,
    UserStats,
)
from plana.services.manager import GuildManager, UserManager

if TYPE_CHECKING:
    from plana.utils.core import PlanaCore


class VoiceSession(BaseModel):
    """Model for tracking voice session times."""

    join_time: Optional[datetime] = Field(default=None, description="When user joined voice")
    mute_start: Optional[datetime] = Field(
        default=None, description="When user started being muted"
    )
    deaf_start: Optional[datetime] = Field(
        default=None, description="When user started being deafened"
    )
    stream_start: Optional[datetime] = Field(
        default=None, description="When user started streaming"
    )

    def calculate_voice_duration(self, end_time: datetime) -> int:
        """Calculate total voice duration in minutes."""
        if not self.join_time:
            return 0
        return int((end_time - self.join_time).total_seconds() / 60)

    def calculate_mute_duration(self, end_time: datetime) -> int:
        """Calculate mute duration in minutes."""
        if not self.mute_start:
            return 0
        return int((end_time - self.mute_start).total_seconds() / 60)

    def calculate_deaf_duration(self, end_time: datetime) -> int:
        """Calculate deaf duration in minutes."""
        if not self.deaf_start:
            return 0
        return int((end_time - self.deaf_start).total_seconds() / 60)

    def calculate_stream_duration(self, end_time: datetime) -> int:
        """Calculate stream duration in minutes."""
        if not self.stream_start:
            return 0
        return int((end_time - self.stream_start).total_seconds() / 60)


class PlanaAchievements(commands.Cog):
    """
    Cog containing User Stats tracking and user achievements.
    """

    def __init__(self, core: "PlanaCore") -> None:
        self.core: "PlanaCore" = core
        self.name = "achievements"
        self.description = "Event handlers for tracking user achievements."

        # Dictionary to track voice sessions using VoiceSession model
        self.voice_sessions: Dict[Tuple[int, int], VoiceSession] = {}

    async def is_achievement_system_enabled(self, guild_id: int) -> bool:
        """Check if achievement system is enabled for a guild."""
        achievement_settings = await self.get_achievements_settings(guild_id)
        return achievement_settings and achievement_settings.enabled

    async def get_or_create_user_stats(self, guild_id: int, user_id: int) -> UserStats:
        """Get user stats or create new ones if they don't exist."""
        user_stats = await self.get_user_stats(guild_id, user_id)
        return user_stats or UserStats()

    def _count_links_in_message(self, content: str) -> int:
        """Count HTTP/HTTPS links in message content."""
        url_pattern = r"https?://[^\s]+"
        return len(re.findall(url_pattern, content))

    async def _update_mentioned_users_stats(self, message: discord.Message) -> None:
        """Update mention_received stats for all mentioned users."""
        for mentioned_user in message.mentions:
            if not mentioned_user.bot:
                mentioned_stats = await self.get_or_create_user_stats(
                    message.guild.id, mentioned_user.id
                )
                mentioned_stats.mention_received += 1
                await self.update_user_stats(message.guild.id, mentioned_user.id, mentioned_stats)

    async def _check_and_unlock_achievements(
        self, guild_id: int, user_id: int, user_stats: UserStats
    ) -> None:
        """Check if user has unlocked any achievements and grant rewards."""
        achievement_settings = await self.get_achievements_settings(guild_id)
        if not achievement_settings or not achievement_settings.custom_achievements:
            return

        guild = self.core.get_guild(guild_id)
        if not guild:
            return

        member = guild.get_member(user_id)
        if not member:
            return

        # Get user's current unlocked achievements
        unlocked_achievements = user_stats.unlocked_achievements

        for achievement in achievement_settings.custom_achievements:
            # Skip if already unlocked
            if achievement.name in unlocked_achievements:
                continue

            # Check if criteria is met
            if await self._is_achievement_criteria_met(achievement, user_stats):
                await self._grant_achievement_rewards(guild, member, achievement)
                await self._mark_achievement_as_unlocked(guild_id, user_id, achievement.name)
                await self._send_achievement_notification(
                    guild, member, achievement, achievement_settings
                )

    async def _is_achievement_criteria_met(
        self, achievement: CustomAchievement, user_stats: UserStats
    ) -> bool:
        """Check if achievement criteria is met based on user stats."""
        if not achievement.criteria_type:
            return False

        # Get the corresponding stat value from user_stats
        stat_value = getattr(user_stats, achievement.criteria_type.value, 0)
        return stat_value >= achievement.criteria_value

    async def _grant_achievement_rewards(
        self, guild: discord.Guild, member: discord.Member, achievement: CustomAchievement
    ) -> None:
        """Grant rewards for unlocked achievement."""
        try:
            # Grant role rewards
            if achievement.role_rewards:
                roles_to_add = []
                for role_id in achievement.role_rewards:
                    role = guild.get_role(role_id)
                    if role and role not in member.roles:
                        roles_to_add.append(role)

                if roles_to_add:
                    await member.add_roles(
                        *roles_to_add, reason=f"Achievement unlocked: {achievement.name}"
                    )
                    logger.info(
                        f"Granted roles {[r.name for r in roles_to_add]} to {member.name} for achievement: {achievement.name}"
                    )

            # TODO: Grant XP and coins rewards
            # This would require integration with your XP/coins system
            if achievement.xp_reward and achievement.xp_reward > 0:
                # await self._grant_xp(guild.id, member.id, achievement.xp_reward)
                logger.info(
                    f"Would grant {achievement.xp_reward} XP to {member.name} for achievement: {achievement.name}"
                )

            if achievement.coins_reward and achievement.coins_reward > 0:
                # await self._grant_coins(guild.id, member.id, achievement.coins_reward)
                logger.info(
                    f"Would grant {achievement.coins_reward} coins to {member.name} for achievement: {achievement.name}"
                )

        except Exception as e:
            logger.error(f"Error granting rewards for achievement {achievement.name}: {e}")

    async def _send_achievement_notification(
        self,
        guild: discord.Guild,
        member: discord.Member,
        achievement: CustomAchievement,
        settings: AchievementSetting,
    ) -> None:
        """Send achievement unlock notification."""
        try:
            # Create achievement unlock embed
            embed = discord.Embed(
                title="🎉 Achievement Unlocked!",
                description=f"**{member.display_name}** has unlocked the achievement: **{achievement.name}**",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow(),
            )

            if achievement.icon_url:
                embed.set_thumbnail(url=achievement.icon_url)

            embed.add_field(
                name="Criteria",
                value=f"{achievement.criteria_type.value.replace('_', ' ').title()}: {achievement.criteria_value:,}",
                inline=True,
            )

            # Add reward information
            rewards = []
            if achievement.role_rewards:
                role_names = [
                    guild.get_role(role_id).name
                    for role_id in achievement.role_rewards
                    if guild.get_role(role_id)
                ]
                if role_names:
                    rewards.append(f"Roles: {', '.join(role_names)}")

            if achievement.xp_reward and achievement.xp_reward > 0:
                rewards.append(f"XP: {achievement.xp_reward:,}")

            if achievement.coins_reward and achievement.coins_reward > 0:
                rewards.append(f"Coins: {achievement.coins_reward:,}")

            if rewards:
                embed.add_field(
                    name="Rewards",
                    value="\n".join(rewards),
                    inline=True,
                )

            embed.set_footer(text=f"Achievement System • {guild.name}")

            # Send to achievement channel if configured
            if settings.achievement_channel_id:
                channel = guild.get_channel(settings.achievement_channel_id)
                if channel and isinstance(channel, discord.TextChannel):
                    await channel.send(embed=embed)
                else:
                    # Fallback to system channel or first available text channel
                    await self._send_to_fallback_channel(guild, embed)
            else:
                await self._send_to_fallback_channel(guild, embed)

        except Exception as e:
            logger.error(f"Error sending achievement notification: {e}")

    async def _send_to_fallback_channel(self, guild: discord.Guild, embed: discord.Embed) -> None:
        """Send achievement notification to fallback channel."""
        # Try system channel first
        if guild.system_channel:
            try:
                await guild.system_channel.send(embed=embed)
                return
            except discord.Forbidden:
                pass

        # Find first available text channel
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                try:
                    await channel.send(embed=embed)
                    return
                except discord.Forbidden:
                    continue

    async def _get_user_unlocked_achievements(self, guild_id: int, user_id: int) -> List[str]:
        """Get list of achievement names that user has already unlocked."""
        # TODO: Implement this based on your data storage
        # For now, return empty list - you might want to store this in UserStats or separate model
        # unlocked_achievements = await UserManager.get_property(
        #     guild_id=guild_id,
        #     user_id=user_id,
        #     model=UnlockedAchievements,  # You might want to create this model
        # )
        # return unlocked_achievements.achievement_names if unlocked_achievements else []
        return []

    async def _mark_achievement_as_unlocked(
        self, guild_id: int, user_id: int, achievement_name: str
    ) -> None:
        """Mark achievement as unlocked for user."""
        # TODO: Implement this based on your data storage
        # You might want to store this in UserStats or create a separate model
        # unlocked_achievements = await self._get_user_unlocked_achievements(guild_id, user_id)
        # unlocked_achievements.append(achievement_name)
        # await UserManager.update_property(
        #     guild_id=guild_id,
        #     user_id=user_id,
        #     data={"unlocked_achievements": unlocked_achievements},
        # )
        logger.info(
            f"Marked achievement '{achievement_name}' as unlocked for user {user_id} in guild {guild_id}"
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Track message statistics when a user sends a message."""
        if message.author.bot or not message.guild:
            return

        if not await self.is_achievement_system_enabled(message.guild.id):
            return

        try:
            user_stats = await self.get_or_create_user_stats(message.guild.id, message.author.id)

            # Update message statistics
            user_stats.message_count += 1
            user_stats.character_count += len(message.content)
            user_stats.word_count += len(message.content.split())
            user_stats.attachment_count += len(message.attachments)
            user_stats.link_count += self._count_links_in_message(message.content)
            user_stats.mention_given += len(message.mentions)

            # Track thread participation
            if isinstance(message.channel, discord.Thread):
                user_stats.threads_participated += 1

            await self.update_user_stats(message.guild.id, message.author.id, user_stats)
            await self._update_mentioned_users_stats(message)

            # Check and unlock achievements
            await self._check_and_unlock_achievements(
                message.guild.id, message.author.id, user_stats
            )

            # Check and unlock achievements
            await self._check_and_unlock_achievements(
                message.guild.id, message.author.id, user_stats
            )

        except Exception as e:
            self.core.handle_exception("Error tracking message statistics", e)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Track reaction statistics when a user adds a reaction."""
        if not payload.guild_id:
            return

        if not await self.is_achievement_system_enabled(payload.guild_id):
            return

        try:
            guild = self.core.get_guild(payload.guild_id)
            if not guild:
                return

            user = guild.get_member(payload.user_id)
            if not user or user.bot:
                return

            # Update stats for user giving the reaction
            user_stats = await self.get_or_create_user_stats(payload.guild_id, payload.user_id)
            user_stats.reactions_given += 1
            await self.update_user_stats(payload.guild_id, payload.user_id, user_stats)

            # Update stats for user receiving the reaction
            await self._update_reaction_recipient_stats(payload, guild, increment=True)

            # Check and unlock achievements for the user giving the reaction
            await self._check_and_unlock_achievements(payload.guild_id, payload.user_id, user_stats)

        except Exception as e:
            self.core.handle_exception("Error tracking reaction add statistics", e)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        """Track reaction statistics when a user removes a reaction."""
        if not payload.guild_id:
            return

        if not await self.is_achievement_system_enabled(payload.guild_id):
            return

        try:
            guild = self.core.get_guild(payload.guild_id)
            if not guild:
                return

            user = guild.get_member(payload.user_id)
            if not user or user.bot:
                return

            # Update stats for user removing the reaction
            user_stats = await self.get_or_create_user_stats(payload.guild_id, payload.user_id)
            user_stats.reactions_given = max(0, user_stats.reactions_given - 1)
            await self.update_user_stats(payload.guild_id, payload.user_id, user_stats)

            # Update stats for user who was receiving the reaction
            await self._update_reaction_recipient_stats(payload, guild, increment=False)

        except Exception as e:
            self.core.handle_exception("Error tracking reaction remove statistics", e)

    async def _update_reaction_recipient_stats(
        self, payload: discord.RawReactionActionEvent, guild: discord.Guild, increment: bool
    ) -> None:
        """Update reaction recipient statistics."""
        channel = guild.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
            if not message.author or message.author.bot:
                return

            recipient_stats = await self.get_or_create_user_stats(
                payload.guild_id, message.author.id
            )

            if increment:
                recipient_stats.reactions_received += 1
            else:
                recipient_stats.reactions_received = max(0, recipient_stats.reactions_received - 1)

            await self.update_user_stats(payload.guild_id, message.author.id, recipient_stats)

            # Check achievements for reaction recipient
            await self._check_and_unlock_achievements(
                payload.guild_id, message.author.id, recipient_stats
            )

        except discord.NotFound:
            pass

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        """Track voice activity statistics with accurate time tracking."""
        if member.bot:
            return

        if not await self.is_achievement_system_enabled(member.guild.id):
            return

        try:
            user_key = (member.guild.id, member.id)
            current_time = datetime.now(timezone.utc)

            # Handle voice state changes
            if before.channel is None and after.channel is not None:
                # User joined voice channel
                await self._handle_voice_join(user_key, current_time, after)

            elif before.channel is not None and after.channel is None:
                # User left voice channel
                await self._handle_voice_leave(member, user_key, current_time)

            elif before.channel is not None and after.channel is not None:
                # User still in voice but state changed
                await self._handle_voice_state_change(member, user_key, current_time, before, after)

        except Exception as e:
            self.core.handle_exception("Error tracking voice state statistics", e)

    async def _handle_voice_join(
        self, user_key: Tuple[int, int], current_time: datetime, voice_state: discord.VoiceState
    ) -> None:
        """Handle user joining voice channel."""
        self.voice_sessions[user_key] = VoiceSession(
            join_time=current_time,
            mute_start=current_time if voice_state.self_mute else None,
            deaf_start=current_time if voice_state.self_deaf else None,
            stream_start=current_time if voice_state.self_stream else None,
        )

    async def _handle_voice_leave(
        self, member: discord.Member, user_key: Tuple[int, int], current_time: datetime
    ) -> None:
        """Handle user leaving voice channel."""
        if user_key not in self.voice_sessions:
            return

        session = self.voice_sessions[user_key]
        user_stats = await self.get_or_create_user_stats(member.guild.id, member.id)

        # Calculate and add all durations
        user_stats.voice_minutes += session.calculate_voice_duration(current_time)
        user_stats.mute_minutes += session.calculate_mute_duration(current_time)
        user_stats.deafen_minutes += session.calculate_deaf_duration(current_time)
        user_stats.stream_minutes += session.calculate_stream_duration(current_time)

        await self.update_user_stats(member.guild.id, member.id, user_stats)
        del self.voice_sessions[user_key]

        # Check and unlock achievements for voice activity
        await self._check_and_unlock_achievements(member.guild.id, member.id, user_stats)

    async def _handle_voice_state_change(
        self,
        member: discord.Member,
        user_key: Tuple[int, int],
        current_time: datetime,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Handle voice state changes while user is in voice."""
        if user_key not in self.voice_sessions:
            return

        session = self.voice_sessions[user_key]
        user_stats = await self.get_or_create_user_stats(member.guild.id, member.id)

        # Handle mute state changes
        if before.self_mute != after.self_mute:
            if after.self_mute:
                session.mute_start = current_time
            else:
                user_stats.mute_minutes += session.calculate_mute_duration(current_time)
                session.mute_start = None

        # Handle deafen state changes
        if before.self_deaf != after.self_deaf:
            if after.self_deaf:
                session.deaf_start = current_time
            else:
                user_stats.deafen_minutes += session.calculate_deaf_duration(current_time)
                session.deaf_start = None

        # Handle streaming state changes
        if before.self_stream != after.self_stream:
            if after.self_stream:
                session.stream_start = current_time
            else:
                user_stats.stream_minutes += session.calculate_stream_duration(current_time)
                session.stream_start = None

        await self.update_user_stats(member.guild.id, member.id, user_stats)

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        """Track thread creation statistics."""
        if not thread.owner or thread.owner.bot:
            return

        if not await self.is_achievement_system_enabled(thread.guild.id):
            return

        try:
            user_stats = await self.get_or_create_user_stats(thread.guild.id, thread.owner.id)
            user_stats.threads_created += 1
            await self.update_user_stats(thread.guild.id, thread.owner.id, user_stats)

            # Check and unlock achievements for thread creation
            await self._check_and_unlock_achievements(thread.guild.id, thread.owner.id, user_stats)

        except Exception as e:
            self.core.handle_exception("Error tracking thread creation statistics", e)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """Track slash command usage statistics."""
        if not interaction.guild or not interaction.user or interaction.user.bot:
            return

        if not await self.is_achievement_system_enabled(interaction.guild.id):
            return

        try:
            # Only track application command interactions (slash commands)
            if interaction.type == discord.InteractionType.application_command:
                user_stats = await self.get_or_create_user_stats(
                    interaction.guild.id, interaction.user.id
                )
                user_stats.slash_commands_used += 1
                await self.update_user_stats(interaction.guild.id, interaction.user.id, user_stats)

                # Check and unlock achievements for slash command usage
                await self._check_and_unlock_achievements(
                    interaction.guild.id, interaction.user.id, user_stats
                )

        except Exception as e:
            self.core.handle_exception("Error tracking slash command statistics", e)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """Track message deletion statistics for moderators."""
        if not message.guild:
            return

        if not await self.is_achievement_system_enabled(message.guild.id):
            return

        try:
            # Check audit logs to see who deleted the message
            async for entry in message.guild.audit_logs(
                action=discord.AuditLogAction.message_delete, limit=1
            ):
                if entry.target.id == message.author.id and not entry.user.bot:
                    # A moderator deleted someone's message
                    mod_stats = await self.get_or_create_user_stats(message.guild.id, entry.user.id)
                    mod_stats.messages_deleted += 1
                    await self.update_user_stats(message.guild.id, entry.user.id, mod_stats)
                    break

        except (discord.Forbidden, discord.HTTPException):
            # No access to audit logs or other error
            pass
        except Exception as e:
            self.core.handle_exception("Error tracking message deletion statistics", e)

    async def get_achievements_settings(self, guild_id: int) -> Union["AchievementSetting", None]:
        """Fetch the achievement settings from cache for a specific guild."""
        manager = await GuildManager.get(guild_id)
        return manager.achievements if manager else None

    async def get_user_stats(self, guild_id: int, user_id: int) -> Optional[UserStats]:
        """Fetch user stats from cache for a specific user in a guild."""
        return await UserManager.get_property(
            guild_id=guild_id,
            user_id=user_id,
            model=UserStats,
        )

    async def update_user_stats(self, guild_id: int, user_id: int, stats: UserStats) -> None:
        """Update user stats for a specific user in a guild."""
        await UserManager.update_property(
            guild_id=guild_id,
            user_id=user_id,
            data=stats,
        )


async def setup(core: "PlanaCore"):
    try:
        await core.add_cog(PlanaAchievements(core))
    except Exception as e:
        core.handle_exception(
            "An error occurred while adding PlanaEvents cog",
            e,
        )
