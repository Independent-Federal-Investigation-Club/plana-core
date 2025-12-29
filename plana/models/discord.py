# Copy from the Plana-API Database models

from typing import Optional, TYPE_CHECKING
from pydantic import Field
import discord
from .base import PlanaModel, SnowflakeId

if TYPE_CHECKING:
    from discord import (
        User as DiscordUser,
        Role as DiscordRole,
        GuildSticker as DiscordSticker,
        Emoji as DiscordEmoji,
        CategoryChannel as DiscordCategory,
    )
    from discord import TextChannel as DiscordTextChannel


class GuildUser(PlanaModel):
    """
    Pydantic Model for Discord Guild User Data
    """

    user_id: SnowflakeId = Field(..., description="Discord User ID")
    username: str = Field(..., max_length=100, description="Username of the user")
    avatar: Optional[str] = Field(None, max_length=32, description="User's avatar hash")

    @staticmethod
    def from_discord_user(user: "DiscordUser") -> "GuildUser":
        """
        Create a GuildUser instance from a Discord user object.
        """
        return GuildUser(
            user_id=user.id,
            username=user.name,
            avatar=user.avatar.key if user.avatar else None,
        )


class GuildRole(PlanaModel):
    """
    Pydantic Model for Discord Guild Role Data
    """

    role_id: SnowflakeId = Field(..., description="Discord Role ID")
    name: str = Field(..., max_length=100, description="Name of the role")
    color: Optional[int] = Field(None, description="Role color in decimal format")
    permissions: Optional[int] = Field(None, description="Role permissions bitfield")
    position: int = Field(0, description="Position of the role in the hierarchy")

    @staticmethod
    def from_discord_role(role: "DiscordRole") -> "GuildRole":
        """
        Create a GuildRole instance from a Discord role object.
        """
        return GuildRole(
            role_id=role.id,
            name=role.name,
            color=role.color.value if role.color else None,
            permissions=role.permissions.value if role.permissions else None,
            position=role.position,
        )


class GuildEmoji(PlanaModel):
    """
    Pydantic Model for Discord Guild Emoji Data
    """

    emoji_id: Optional[SnowflakeId] = Field(default=None, description="Discord Emoji ID")
    name: str = Field(..., max_length=100, description="Name of the emoji")
    url: Optional[str] = Field(
        None, max_length=256, description="URL of the emoji [for emoji uploads]"
    )
    animated: bool = Field(False, description="Whether the emoji is animated")

    @property
    def custom_id(self) -> str:
        """
        Returns the custom ID of the emoji, which is its name or ID.
        """
        return self.name if self.emoji_id == 0 else str(self.emoji_id)

    def to_discord_emoji(self) -> str:
        """Convert to Discord emoji format."""
        if self.emoji_id:
            return discord.PartialEmoji(
                name=self.name,
                id=self.emoji_id,
                animated=self.animated or False,
            )

        return self.name

    @staticmethod
    def from_discord_emoji(emoji: "DiscordEmoji") -> "GuildEmoji":
        """
        Create a GuildEmoji instance from a Discord emoji object.
        """
        return GuildEmoji(
            emoji_id=emoji.id,
            name=emoji.name,
            url=emoji.url,
            animated=emoji.animated,
        )


class GuildSticker(PlanaModel):
    """
    Pydantic Model for Discord Guild Sticker Data
    """

    sticker_id: SnowflakeId = Field(..., description="Discord Sticker ID")
    name: str = Field(..., max_length=100, description="Name of the sticker")
    url: Optional[str] = Field(..., max_length=256, description="URL of the sticker")
    description: Optional[str] = Field(
        None, max_length=512, description="Description of the sticker"
    )
    emoji: str = Field(..., max_length=100, description="Emoji representation of the sticker")

    format: int = Field(
        ..., description="Format type of the sticker (1 = PNG, 2 = APNG, 3 = LOTTIE, 4 = GIF)"
    )
    available: bool = Field(True, description="Whether the sticker is available")

    @staticmethod
    def from_discord_sticker(sticker: "DiscordSticker") -> "GuildSticker":
        """
        Create a GuildSticker instance from a Discord sticker object.
        """
        return GuildSticker(
            sticker_id=sticker.id,
            name=sticker.name,
            url=sticker.url,
            description=sticker.description,
            emoji=sticker.emoji,
            format=sticker.format,
            available=sticker.available,
        )


class TextChannel(PlanaModel):
    """
    Pydantic Model for Discord Guild Channel Data
    """

    channel_id: SnowflakeId = Field(..., description="Discord Channel ID")
    category_id: SnowflakeId = Field(..., description="ID of the category this channel belongs to")
    name: str = Field(..., max_length=100, description="Name of the channel")
    position: int = Field(0, description="Position of the channel in the list")
    topic: Optional[str] = Field(None, max_length=1024, description="Channel topic")
    nsfw: bool = Field(
        False, description="Whether the channel is marked as NSFW (Not Safe For Work)"
    )

    @staticmethod
    def from_discord_channel(channel: "DiscordTextChannel") -> "TextChannel":
        """
        Create a TextChannel instance from a Discord channel object.
        """
        return TextChannel(
            channel_id=channel.id,
            category_id=channel.category_id,
            name=channel.name,
            position=channel.position,
            topic=channel.topic,
            nsfw=channel.nsfw,
        )


class GuildCategory(PlanaModel):
    """
    Pydantic Model for Discord Guild Category Data
    """

    category_id: SnowflakeId = Field(..., description="Discord Category ID")
    name: str = Field(..., max_length=100, description="Name of the category")
    position: int = Field(0, description="Position of the category in the list")

    @staticmethod
    def from_discord_category(category: "DiscordCategory") -> "GuildCategory":
        """
        Create a GuildCategory instance from a Discord category object.
        """
        return GuildCategory(
            category_id=category.id,
            name=category.name,
            position=category.position,
        )
