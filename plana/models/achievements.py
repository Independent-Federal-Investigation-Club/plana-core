from typing import Union, Optional, List, Self

from enum import StrEnum

from datetime import datetime
from pydantic import Field
from plana.utils.helper import make_api_request

from .message import Message
from .base import PlanaModel, SnowflakeId


class UserStats(PlanaModel):
    """Model for tracking comprehensive user activity statistics."""

    # Message Statistics
    message_count: int = Field(default=0, description="Total messages sent")
    character_count: int = Field(default=0, description="Total characters typed")
    word_count: int = Field(default=0, description="Total words typed")
    attachment_count: int = Field(default=0, description="Total attachments shared")
    link_count: int = Field(default=0, description="Total links shared")

    # User Mentions
    mention_given: int = Field(default=0, description="Total user mentions made")
    mention_received: int = Field(default=0, description="Total user mentions received")

    # Reaction Statistics
    reactions_given: int = Field(default=0, description="Total reactions given to others")
    reactions_received: int = Field(default=0, description="Total reactions received")

    # Voice Activity Statistics
    voice_minutes: int = Field(default=0, description="Total minutes in voice channels")
    mute_minutes: int = Field(default=0, description="Minutes spent muted")
    deafen_minutes: int = Field(default=0, description="Minutes spent deafened")
    stream_minutes: int = Field(default=0, description="Minutes spent streaming")

    # Social Interactions
    threads_created: int = Field(default=0, description="Total threads created")
    threads_participated: int = Field(default=0, description="Total threads participated in")
    slash_commands_used: int = Field(default=0, description="Total slash commands used")

    # Moderation Stats (if user has mod permissions)
    messages_deleted: int = Field(default=0, description="Messages deleted by user (if mod)")

    # Achievement tracking
    unlocked_achievements: List[str] = Field(
        default_factory=list, description="List of unlocked achievement names"
    )

    def get_activity_score(self) -> float:
        """Calculate a comprehensive activity score."""
        # Weighted score based on different activities
        score = (
            self.message_count * 1.0
            + self.reactions_given * 0.5
            + self.reactions_received * 0.3
            + (self.voice_minutes / 60) * 2.0  # Convert to hours
            + self.threads_created * 5.0
            + self.slash_commands_used * 0.8
        )
        return round(score, 2)


class CirteriaType(StrEnum):
    """Enumeration for different achievement criteria types."""

    MESSAGE_COUNT = "message_count"
    CHARACTER_COUNT = "character_count"
    WORD_COUNT = "word_count"
    ATTACHMENT_COUNT = "attachment_count"
    LINK_COUNT = "link_count"
    MENTION_GIVEN = "mention_given"
    MENTION_RECEIVED = "mention_received"
    REACTIONS_GIVEN = "reactions_given"
    REACTIONS_RECEIVED = "reactions_received"
    VOICE_MINUTES = "voice_minutes"
    MUTE_MINUTES = "mute_minutes"
    DEAFEN_MINUTES = "deafen_minutes"
    STREAM_MINUTES = "stream_minutes"
    THREADS_CREATED = "threads_created"
    THREADS_PARTICIPATED = "threads_participated"
    SLASH_COMMANDS_USED = "slash_commands_used"


class CustomAchievement(PlanaModel):
    """Model for custom achievements."""

    name: str = Field(description="Name of the achievement", max_length=100)
    icon_url: Optional[str] = Field(default=None, description="URL of the icon for the achievement")
    criteria_type: Optional[CirteriaType] = Field(
        description="Type of criteria for the achievement",
    )
    criteria_value: int = Field(
        description="Value for the criteria to unlock the achievement", ge=1
    )
    role_rewards: Optional[List[SnowflakeId]] = Field(
        default_factory=list, description="List of role IDs to assign when achievement is unlocked"
    )
    xp_reward: Optional[int] = Field(
        default=0, description="XP reward for unlocking the achievement", ge=0
    )
    coins_reward: Optional[int] = Field(
        default=0, description="Coins reward for unlocking the achievement", ge=0
    )


class AchievementSetting(PlanaModel):
    """Model for guild achievement system configuration."""

    id: Optional[SnowflakeId] = Field(default=None, description="ID of the guild")
    enabled: Optional[bool] = Field(
        default=False, description="Whether achievement system is enabled"
    )

    # Channel settings
    achievement_channel_id: Optional[SnowflakeId] = Field(
        default=None, description="Channel ID for achievement messages"
    )

    custom_achievements: Optional[List[CustomAchievement]] = Field(
        default_factory=list, description="List of custom achievements configured for the guild"
    )

    # Message content
    achievement_message: Optional[Message] = Field(
        default=None, description="Achievement message template"
    )

    updated_at: Optional[datetime] = Field(default=None, description="Timestamp of last update")

    @staticmethod
    async def get(guild_id: int) -> Union[Self | None]:
        response = await make_api_request(url=f"/guilds/{guild_id}/achievements", method="GET")
        if not response:
            return await AchievementSetting.create(guild_id=guild_id)
        return AchievementSetting(**response)

    @staticmethod
    async def create(guild_id: int, data: dict = {}) -> Union[Self | None]:
        response = await make_api_request(
            f"/guilds/{guild_id}/achievements", method="POST", json=data
        )
        if not response:
            return
        return AchievementSetting(**response)

    @staticmethod
    async def update(guild_id: int, data: dict = {}) -> Union[Self | None]:
        response = await make_api_request(
            f"/guilds/{guild_id}/achievements", method="PATCH", json=data
        )
        if not response:
            return
        return AchievementSetting(**response)

    @staticmethod
    async def delete(guild_id: int) -> None:
        await make_api_request(f"/guilds/{guild_id}/achievements", method="DELETE")

    async def save(self) -> Union[Self | None]:
        return await AchievementSetting.update(
            self.id, data=self.model_dump(mode="json", exclude_unset=True)
        )
