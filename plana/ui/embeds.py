import traceback
from datetime import datetime
from random import choice

import discord
from pytz import timezone

from plana.constant import (
    DEFAULT_EMBED_COLOR,
    DEFAULT_EMBED_IMAGES,
    DEFAULT_ERROR_COLOR,
    DEFAULT_FOOTER_TEXT,
    DEFAULT_TIMEZONE,
)
from plana.services.manager import GuildManager
from plana.types.exceptions import PlanaError

__all__ = (
    "embed_template",
    "error_embed_template",
)


async def embed_template(guild_id: int) -> discord.Embed:
    """
    Fetches the embed template for a specific guild.

    Args:
        guild_id (int): The ID of the guild to fetch the embed template for.

    Returns:
        discord.Embed: The embed template for the specified guild.
    """

    color = DEFAULT_EMBED_COLOR
    footer = DEFAULT_FOOTER_TEXT
    timestamp = datetime.now(timezone(DEFAULT_TIMEZONE))
    image = choice(DEFAULT_EMBED_IMAGES)

    settings = await GuildManager.get(guild_id=guild_id)

    if settings and settings.preferences:
        if settings.preferences.embed_color:
            color = discord.Colour.from_str(settings.preferences.embed_color)
        if settings.preferences.embed_footer:
            footer = settings.preferences.embed_footer
        if settings.preferences.embed_footer_images:
            image = choice(settings.preferences.embed_footer_images)
        if settings.preferences.timezone:
            timestamp = datetime.now(timezone(settings.preferences.timezone))

    embed = discord.Embed(
        color=color,
        timestamp=timestamp,
    )

    embed.set_image(url=image)
    embed.set_footer(text=footer)

    return embed


async def error_embed_template(
    guild_id: int,
    error: Exception | PlanaError,
    verbose: bool = False,
) -> discord.Embed:
    """
    Generates an error embed template for a specific guild.

    Args:
        guild_id (int): The ID of the guild to fetch the embed template for.
        error (Exception): The error to include in the embed.
        verbose (bool): Whether to include detailed error information.

    Returns:
        discord.Embed: The error embed template for the specified guild.
    """
    embed = await embed_template(guild_id)
    embed.title = "An Error Occurred"
    embed.color = DEFAULT_ERROR_COLOR

    if isinstance(error, PlanaError):
        embed.title = error.title
        embed.description = error.message
        return embed

    if verbose:
        embed.description = (
            f"```python\n{traceback.format_exc()}\n{type(error).__name__}: {error}\n```"
        )
    else:
        embed.description = f"{type(error).__name__}: {error}"

    return embed
