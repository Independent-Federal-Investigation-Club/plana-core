# Models for the Plana Level System
from datetime import datetime
from enum import Enum
from typing import List, Optional, Self, Union

from pydantic import Field

from plana.models.user import UserDataField
from plana.utils.helper import make_api_request

from .base import PlanaModel, SnowflakeId
from .message import Message


class AnnouncementType(str, Enum):
    """Enum for level up announcement types."""

    DISABLED = "disabled"
    CURRENT_CHANNEL = "current_channel"
    PRIVATE_MESSAGE = "private_message"
    CUSTOM_CHANNEL = "custom_channel"


class RoleReward(PlanaModel):
    """Model for role rewards at specific levels."""

    level: int = Field(description="Level required to earn this role")
    role_ids: List[SnowflakeId] = Field(
        default_factory=list, description="List of Discord role IDs to assign"
    )


class XPBooster(PlanaModel):
    """Model for XP rate boosters."""

    role_id: SnowflakeId = Field(description="Discord role ID that gets the boost")
    multiplier: float = Field(default=1.0, description="XP multiplier (e.g., 1.5 for 50% bonus)")


class LevelSetting(PlanaModel):
    """Model for guild level system configuration."""

    id: Optional[SnowflakeId] = Field(default=None, description="Discord guild ID")

    # Basic settings
    enabled: Optional[bool] = Field(
        default=False, description="Whether the level system is enabled"
    )
    xp_per_message: Optional[int] = Field(
        default=15, description="Base XP earned per message", ge=1, le=100
    )
    xp_cooldown: Optional[int] = Field(
        default=5, description="Cooldown between XP gains in seconds", ge=0, le=300
    )

    # Level calculation
    base_xp: Optional[int] = Field(
        default=100, description="XP required for level 1", ge=50, le=1000
    )
    xp_multiplier: Optional[float] = Field(
        default=1.2, description="Multiplier for each level", ge=1.0, le=3.0
    )

    # Announcements
    announcement_type: Optional[AnnouncementType] = Field(
        default=AnnouncementType.CURRENT_CHANNEL, description="How to announce level ups"
    )
    announcement_channel_id: Optional[SnowflakeId] = Field(
        default=None, description="Channel ID for custom announcements"
    )
    announcement_message: Optional[Message] = Field(
        default=None,
        description="Custom level up message",
        max_length=500,
    )

    # Role rewards
    role_rewards: Optional[List[RoleReward]] = Field(
        default_factory=list, description="Role rewards for reaching levels"
    )

    # XP boosters
    xp_boosters: Optional[List[XPBooster]] = Field(
        default_factory=list, description="XP multipliers for specific roles"
    )

    # No-XP roles
    target_xp_roles: Optional[List[SnowflakeId]] = Field(
        default_factory=list, description="Roles that will either gain or not gain XP"
    )
    target_xp_roles_mode: Optional[bool] = Field(
        default=False,
        description="Whether target_xp_roles is whitelist (gain) or blacklist (not gain)",
    )

    # No-XP channels
    target_xp_channels: Optional[List[SnowflakeId]] = Field(
        default_factory=list, description="Channels where XP isn't gained"
    )
    target_xp_channels_mode: Optional[bool] = Field(
        default=False,
        description="Whether target_xp_channels is whitelist (gain) or blacklist (not gain)",
    )

    # Advanced settings
    stack_rewards: Optional[bool] = Field(
        default=True, description="Whether to stack role rewards or replace them"
    )
    message_length_bonus: Optional[bool] = Field(
        default=True, description="Whether longer messages give more XP"
    )
    max_xp_per_message: Optional[int] = Field(
        default=25, description="Maximum XP that can be earned from a single message", ge=1, le=200
    )

    updated_at: Optional[datetime] = Field(default=None, description="Timestamp of last update")

    @staticmethod
    async def get(guild_id: int) -> Union["LevelSetting", None]:
        """Get level configuration for a guild."""

        response = await make_api_request(url=f"/guilds/{guild_id}/levels", method="GET")
        if not response:
            return await LevelSetting.create(guild_id=guild_id)
        return LevelSetting(**response)

    @staticmethod
    async def create(guild_id: int, data: dict = {}) -> Union["LevelSetting", None]:
        """Create level configuration for a guild."""
        response = await make_api_request(
            url=f"/guilds/{guild_id}/levels", method="POST", json=data
        )
        if not response:
            return
        return LevelSetting(**response)

    @staticmethod
    async def update(guild_id: int, data: dict = {}) -> Union["LevelSetting", None]:
        """Update level configuration for a guild."""
        response = await make_api_request(url=f"/guilds/{guild_id}/levels", method="PUT", json=data)
        if not response:
            return
        return LevelSetting(**response)

    @staticmethod
    async def delete(guild_id: int) -> None:
        """Delete level configuration for a guild."""
        await make_api_request(url=f"/guilds/{guild_id}/levels", method="DELETE")

    async def save(self) -> Union["LevelSetting", None]:
        """Save the configuration to the API."""
        data = self.model_dump(mode="json", exclude_unset=True)
        return await LevelSetting.update(self.id, data)

    def calculate_xp_for_level(self, level: int) -> int:
        """Calculate total XP required to reach a specific level."""
        if level <= 0:
            return 0

        total_xp = 0
        for lvl in range(1, level + 1):
            level_xp = int(self.base_xp * (self.xp_multiplier ** (lvl - 1)))
            total_xp += level_xp
        return total_xp

    def calculate_level_from_xp(self, xp: int) -> int:
        """Calculate level from total XP."""
        if xp <= 0:
            return 0

        level = 0
        total_xp = 0

        while total_xp <= xp:
            level += 1
            level_xp = int(self.base_xp * (self.xp_multiplier ** (level - 1)))
            if total_xp + level_xp > xp:
                level -= 1
                break
            total_xp += level_xp

        return max(0, level)


class UserLevelData(UserDataField):
    """Model for user level data."""

    __property__ = "levels"

    user_id: Optional[int] = Field(
        default=None,
        description="ID of the user for which levels are set",
        exclude=True,
    )

    xp: int = Field(default=0, description="Total XP earned", ge=0)
    level: int = Field(default=0, description="Current level", ge=0)
    messages_sent: int = Field(default=0, description="Total messages sent", ge=0)

    def __lt__(self, other: Self) -> bool:
        """Compare two UserLevelData instances based on level and XP."""
        if self.xp == other.xp:
            return self.messages_sent < other.messages_sent
        return self.xp < other.xp

    def calculate_level_progress(self, config: LevelSetting) -> tuple[int, int, int]:
        """
        Calculate level progress.

        Returns:
            tuple: (current_level_xp, next_level_xp, xp_in_current_level)
        """
        current_level_total_xp = config.calculate_xp_for_level(self.level)
        next_level_total_xp = config.calculate_xp_for_level(self.level + 1)
        current_level_xp = next_level_total_xp - current_level_total_xp
        xp_in_current_level = self.xp - current_level_total_xp

        return current_level_xp, next_level_total_xp, xp_in_current_level
