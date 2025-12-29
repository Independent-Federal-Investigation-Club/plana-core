# Models copied from the Plana API

from typing import Optional, Union, List, TYPE_CHECKING

from pydantic import Field
from plana.utils.helper import make_api_request
from .discord import (
    GuildUser,
    GuildRole,
    GuildEmoji,
    GuildSticker,
    TextChannel,
    GuildCategory,
)
from .base import PlanaModel, SnowflakeId

if TYPE_CHECKING:
    from discord import Guild as DiscordGuild


class Guild(PlanaModel):
    """
    Pydantic Model for Discord Guild Data for Input Validation
    """

    id: SnowflakeId = Field(..., description="Discord Server ID")
    name: str = Field(..., max_length=100, description="Name of the server")
    icon: Optional[str] = Field(None, max_length=34, description="Server icon hash")
    banner: Optional[str] = Field(None, max_length=34, description="Server banner hash")
    owner_id: SnowflakeId = Field(..., description="ID of the server owner")

    premium_tier: Optional[int] = Field(
        0, description="Server premium tier (0 = None, 1 = Tier 1, etc.)"
    )
    premium_subscription_count: Optional[int] = Field(
        0, description="Number of premium subscriptions"
    )

    users: List[GuildUser] = Field(default_factory=list, description="List of users in the guild")
    roles: List[GuildRole] = Field(default_factory=list, description="List of roles in the guild")
    emojis: List[GuildEmoji] = Field(
        default_factory=list, description="List of emojis in the guild"
    )
    stickers: List[GuildSticker] = Field(
        default_factory=list, description="List of stickers in the guild"
    )
    channels: List[TextChannel] = Field(
        default_factory=list, description="List of channels in the guild"
    )
    categories: List[GuildCategory] = Field(
        default_factory=list, description="List of categories in the guild"
    )

    @staticmethod
    def from_discord_guild(guild: "DiscordGuild") -> "Guild":
        """
        Create a Guild instance from a Discord guild object.
        """
        return Guild(
            id=guild.id,
            name=guild.name,
            icon=guild.icon.key if guild.icon else None,
            banner=guild.banner.key if guild.banner else None,
            owner_id=guild.owner_id,
            premium_tier=guild.premium_tier,
            premium_subscription_count=guild.premium_subscription_count,
            users=[GuildUser.from_discord_user(user) for user in guild.members],
            roles=[GuildRole.from_discord_role(role) for role in guild.roles],
            emojis=[GuildEmoji.from_discord_emoji(emoji) for emoji in guild.emojis],
            stickers=[GuildSticker.from_discord_sticker(sticker) for sticker in guild.stickers],
            channels=[TextChannel.from_discord_channel(channel) for channel in guild.text_channels],
            categories=[
                GuildCategory.from_discord_category(category) for category in guild.categories
            ],
        )

    @staticmethod
    async def get(guild_id: int) -> Union["Guild", None]:
        response = await make_api_request(url=f"/guilds/{guild_id}/data", method="GET")
        if not response:
            return
        return Guild(**response)

    @staticmethod
    async def create(guild_id: int, data: dict) -> Union["Guild", None]:
        response = await make_api_request(url=f"/guilds/{guild_id}/data", method="POST", json=data)
        if not response:
            return
        return Guild(**response)

    @staticmethod
    async def delete(guild_id: int) -> None:
        await make_api_request(url=f"/guilds/{guild_id}/data", method="DELETE")

    @staticmethod
    async def update(guild_id: int, data: dict) -> Union["Guild", None]:
        response = await make_api_request(url=f"/guilds/{guild_id}/data", method="PUT", json=data)
        if not response:
            return
        return Guild(**response)

    @staticmethod
    async def refresh(guild: "DiscordGuild") -> None:
        """
        Reset guild data to default settings.
        """

        guild_data = Guild.from_discord_guild(guild=guild)
        payload = guild_data.model_dump(mode="json")

        response = await Guild.update(guild_id=guild.id, data=payload)
        if not response:
            await Guild.create(guild_id=guild.id, data=payload)


class GuildPreference(PlanaModel):
    """Guild preferences model for storing and retrieving guild settings."""

    id: Optional[SnowflakeId] = Field(
        default=None, description="ID of the guild for which preferences are set"
    )
    enabled: Optional[bool] = Field(default=None, description="Whether bot is enabled in guild")
    command_prefix: Optional[str] = Field(default=None, max_length=10, description="Command prefix")
    language: Optional[str] = Field(default=None, max_length=10, description="Bot language")
    timezone: Optional[str] = Field(default=None, max_length=50, description="Server timezone")
    embed_color: Optional[str] = Field(
        default=None, max_length=7, description="Default embed color"
    )
    embed_footer: Optional[str] = Field(
        default=None, max_length=100, description="Default embed footer"
    )
    embed_footer_images: Optional[list[str]] = Field(
        default=None, description="Default embed footer images"
    )

    @staticmethod
    async def get(guild_id: int) -> Union["GuildPreference", None]:
        response = await make_api_request(url=f"/guilds/{guild_id}/preferences", method="GET")
        if not response:
            return await GuildPreference.create(guild_id=guild_id)
        return GuildPreference(**response)

    @staticmethod
    async def create(guild_id: int, data: dict = {}) -> Union["GuildPreference", None]:
        response = await make_api_request(
            f"/guilds/{guild_id}/preferences", method="POST", json=data
        )
        if not response:
            return
        return GuildPreference(**response)

    @staticmethod
    async def update(guild_id: int, data: dict = {}) -> Union["GuildPreference", None]:
        response = await make_api_request(
            f"/guilds/{guild_id}/preferences", method="PATCH", json=data
        )
        if not response:
            return
        return GuildPreference(**response)

    @staticmethod
    async def delete(guild_id: int) -> None:
        await make_api_request(f"/guilds/{guild_id}/preferences", method="DELETE")

    async def save(self) -> Union["GuildPreference", None]:
        return await GuildPreference.update(
            self.id, data=self.model_dump(mode="json", exclude_unset=True)
        )
