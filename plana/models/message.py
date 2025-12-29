from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Self, Tuple, Union

import discord
from loguru import logger
from pydantic import Field, field_validator, model_validator

from plana.models.base import PlanaModel, SnowflakeId
from plana.models.discord import GuildEmoji
from plana.utils.helper import make_api_request

if TYPE_CHECKING:
    from plana.utils.core import PlanaCore


class Button(PlanaModel):
    """Model for Discord button component."""

    custom_id: Optional[str] = Field(
        default=None, description="Custom ID for the button", max_length=100
    )
    label: str = Field(description="Button label text", max_length=80)
    style: int = Field(description="Button style (1-6)", ge=1, le=6)
    emoji: Optional[GuildEmoji] = Field(default=None, description="Optional emoji for the button")
    url: Optional[str] = Field(default=None, description="URL for link-style buttons")
    disabled: Optional[bool] = Field(default=False, description="Whether the button is disabled")

    @model_validator(mode="after")
    def validate_custom_id_or_url(self) -> "Button":
        if self.custom_id and self.url:
            raise ValueError("Button cannot have both custom_id and url")
        if not self.custom_id and not self.url:
            raise ValueError("Button must have either custom_id or url")
        return self

    def to_discord(self) -> discord.ui.Button:
        """Convert to discord.py Button."""
        button = discord.ui.Button(
            label=self.label,
            style=discord.ButtonStyle(self.style),
            disabled=self.disabled or False,
        )
        if self.emoji and isinstance(self.emoji, GuildEmoji):
            button.emoji = self.emoji.to_discord_emoji()
        else:
            button.emoji = self.emoji if isinstance(self.emoji, str) else None

        if self.custom_id:
            button.url = None
            button.custom_id = self.custom_id
        elif self.url:
            button.url = self.url
            button.custom_id = None
            button.style = discord.ButtonStyle.link

        return button


class SelectOption(PlanaModel):
    """Model for dropdown select option."""

    label: str = Field(description="Option label", max_length=100)
    value: str = Field(description="Option value", max_length=100)
    description: Optional[str] = Field(
        default=None, description="Option description", max_length=100
    )
    emoji: Optional[GuildEmoji] = Field(default=None, description="Optional emoji for the option")
    default: Optional[bool] = Field(
        default=False, description="Whether this option is selected by default"
    )

    def to_discord(self) -> discord.SelectOption:
        """Convert to discord.py SelectOption."""
        option = discord.SelectOption(
            label=self.label,
            value=self.value,
            description=self.description,
            default=self.default or False,
        )
        if self.emoji and isinstance(self.emoji, GuildEmoji):
            option.emoji = self.emoji.to_discord_emoji()
        else:
            option.emoji = self.emoji if isinstance(self.emoji, str) else None
        return option


class SelectMenu(PlanaModel):
    """Model for Discord select menu component."""

    custom_id: str = Field(description="Custom ID for the select menu", max_length=100)
    placeholder: Optional[str] = Field(default=None, description="Placeholder text", max_length=150)
    min_values: Optional[int] = Field(
        default=1, description="Minimum number of selections", ge=0, le=25
    )
    max_values: Optional[int] = Field(
        default=1, description="Maximum number of selections", ge=1, le=25
    )
    options: List[SelectOption] = Field(description="List of select options")
    disabled: Optional[bool] = Field(
        default=False, description="Whether the select menu is disabled"
    )

    def to_discord(self) -> discord.ui.Select:
        """Convert to discord.py Select."""
        select = discord.ui.Select(
            custom_id=self.custom_id,
            placeholder=self.placeholder,
            min_values=self.min_values or 1,
            max_values=self.max_values or 1,
            disabled=self.disabled or False,
        )
        select.options = [option.to_discord() for option in self.options]
        return select


class EmbedFooter(PlanaModel):
    text: str = Field(description="Footer text content", max_length=2048)
    icon_url: Optional[str] = Field(default=None, description="URL of footer icon image")


class EmbedField(PlanaModel):
    name: str = Field(description="Name of the field")
    value: str = Field(description="Value of the field")
    inline: Optional[bool] = Field(
        default=True, description="Whether the field should be displayed inline"
    )


class EmbedAuthor(PlanaModel):
    name: str = Field(description="Name of the author")
    url: Optional[str] = Field(default=None, description="URL that the author name should link to")
    icon_url: Optional[str] = Field(default=None, description="URL of author icon image")


class Embed(PlanaModel):

    title: Optional[str] = Field(default=None, max_length=256, description="Title of the embed")
    description: Optional[str] = Field(
        default=None, max_length=2048, description="Description of the embed"
    )
    url: Optional[str] = Field(default=None, description="URL that the title should link to")
    timestamp: Optional[datetime] = Field(
        default=None, description="Timestamp to display in the embed"
    )
    color: Optional[int] = Field(
        default=None, description="Color code of the embed (integer representation)"
    )
    footer: Optional[EmbedFooter] = Field(default=None, description="Footer information")
    image: Optional[str] = Field(default=None, description="URL of the main image")
    thumbnail: Optional[str] = Field(default=None, description="URL of the thumbnail image")
    author: Optional[EmbedAuthor] = Field(default=None, description="Author information")
    fields: Optional[List[EmbedField]] = Field(
        default_factory=list, description="List of embed fields"
    )

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (0 <= v <= 16777215):  # 0xFFFFFF
            raise ValueError("Color must be between 0 and 16777215")
        return v

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v: Optional[List[EmbedField]]) -> Optional[List[EmbedField]]:
        if v is not None and len(v) > 25:
            raise ValueError("Embed cannot have more than 25 fields")
        return v

    async def to_discord(self) -> Tuple[discord.Embed, List[discord.File]]:
        embed = discord.Embed(
            title=self.title,
            description=self.description,
            url=self.url,
            color=self.color,
            timestamp=self.timestamp,
        )

        files = []
        if self.image:
            embed.set_image(url=self.image)

        if self.thumbnail:
            embed.set_thumbnail(url=self.thumbnail)

        if self.author:
            embed.set_author(
                name=self.author.name, url=self.author.url, icon_url=self.author.icon_url
            )

        if self.footer:
            embed.set_footer(text=self.footer.text, icon_url=self.footer.icon_url)

        if self.fields:
            for field in self.fields:
                embed.add_field(name=field.name, value=field.value, inline=field.inline or True)

        return embed, files


class Message(PlanaModel):
    """Model for Discord message with react role functionality."""

    id: Optional[SnowflakeId] = Field(default=None, description="Custom ID of the message")

    name: Optional[str] = Field(
        default=None,
        description="Name of the message (for identification purposes)",
        max_length=100,
    )

    message_id: Optional[SnowflakeId] = Field(
        default=None, description="ID of the message (if already sent)"
    )
    guild_id: Optional[SnowflakeId] = Field(default=None, description="ID of the guild")
    channel_id: Optional[SnowflakeId] = Field(default=None, description="ID of the channel")

    content: Optional[str] = Field(default=None, description="Message content", max_length=2000)
    embeds: Optional[List[Embed]] = Field(default_factory=list, description="List of embeds")
    components: Optional[List[Button | SelectMenu]] = Field(
        default_factory=list, description="List of buttons and select menus"
    )
    reactions: Optional[List[GuildEmoji]] = Field(
        default_factory=list, description="List of emojis attached to the message"
    )
    published: Optional[bool] = Field(
        default=False, description="Whether the message has been published to Discord"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the last update to the message",
    )

    @staticmethod
    async def get(guild_id: int, id: int) -> Union[Self | None]:
        response = await make_api_request(url=f"/guilds/{guild_id}/messages/{id}", method="GET")
        if not response:
            return
        return Message(**response)

    @staticmethod
    async def create(guild_id: int, data: dict = {}) -> Union[Self | None]:
        response = await make_api_request(f"/guilds/{guild_id}/messages", method="POST", json=data)
        if not response:
            return
        return Message(**response)

    @staticmethod
    async def update(guild_id: int, id: int, data: dict = {}) -> Union[Self | None]:
        response = await make_api_request(
            f"/guilds/{guild_id}/messages/{id}", method="PUT", json=data
        )
        if not response:
            return
        return Message(**response)

    @staticmethod
    async def delete(guild_id: int, id: int) -> None:
        await make_api_request(f"/guilds/{guild_id}/messages/{id}", method="DELETE")

    async def save(self) -> Union[Self | None]:
        if not self.id:
            raise ValueError("Message ID is required to save the message")

        response = await make_api_request(
            f"/messages/{self.id}",
            method="PUT",
            json=self.model_dump(mode="json", exclude_unset=True),
        )
        if not response:
            return
        return Message(**response)

    # Discord integration methods
    async def send(self, core: "PlanaCore") -> Optional[discord.Message]:
        """Send the message to Discord with context validation."""
        if not self._exists(core):
            return

        content, embeds, view, files = await self._parse()
        channel = core.get_channel(self.channel_id)

        message: discord.Message = await channel.send(
            content=content, embeds=embeds, view=view, files=files
        )

        if self.reactions:
            for reaction in self.reactions:
                await message.add_reaction(reaction.to_discord_emoji())

        return message

    async def edit(self, core: "PlanaCore") -> Optional[discord.Message]:
        """Edit the message in Discord."""
        if not self._exists(core):
            return

        if not self.message_id:
            logger.warning(f"Message {self.id} has no message_id to edit")
            return

        content, embeds, view, _ = await self._parse(use_discord_cdn=False)
        channel = core.get_channel(self.channel_id)

        discord_message = await channel.fetch_message(self.message_id)
        if not discord_message:
            logger.warning(f"Message {self.message_id} not found in channel {channel.name}")
            return

        # clear attachments since it has been c
        updated_message: discord.Message = await discord_message.edit(
            content=content, embeds=embeds, view=view
        )

        if self.reactions:
            await updated_message.clear_reactions()

            for reaction in self.reactions:
                await updated_message.add_reaction(reaction.to_discord_emoji())

        return updated_message

    def to_discord_view(self) -> Optional[discord.ui.View]:
        """Create a Discord View with buttons and select menus."""
        if not self.components:
            return

        view = discord.ui.View(timeout=None)  # Persistent view

        for item in self.components:
            view.add_item(item.to_discord())

        return view

    def _exists(self, core: "PlanaCore") -> bool:
        """Check if the message's context exists in discord."""
        if not self.channel_id or not self.guild_id:
            logger.warning(f"No channel_id or guild_id specified for message {self.id}")
            return False

        guild = core.get_guild(self.guild_id)
        if not guild:
            logger.warning(f"Guild {self.guild_id} not found")
            return False

        channel = guild.get_channel(self.channel_id)
        if not channel:
            logger.warning(f"Channel {self.channel_id} not found in guild {self.guild_id}")
            return False

        return True

    async def _parse(
        self,
    ) -> Tuple[str, List[discord.Embed], Optional[discord.ui.View], List[discord.File]]:
        """Parse the message into a format suitable for Discord."""

        embeds = []
        files = []
        content = self.content
        view = self.to_discord_view()

        for embed in self.embeds:
            discord_embed, embed_files = await embed.to_discord()
            embeds.append(discord_embed)
            files.extend(embed_files)

        return content, embeds, view, files
