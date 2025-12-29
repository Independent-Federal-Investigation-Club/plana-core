import hashlib
import io
import json
import os
import re
import time
import traceback
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, TypeVar

from discord import File, Message
from httpx import AsyncClient, HTTPStatusError
from loguru import logger

if TYPE_CHECKING:
    from pydantic import BaseModel


T = TypeVar("T")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def get_extension_from_url(url: str) -> str | None:
    ext = os.path.splitext(url.split("?")[0])[1].lower()
    return ext.lstrip(".")


def get_image_extension_from_content_type(content_type: str) -> str | None:
    match = re.match(r"image/([a-zA-Z0-9]+)", content_type)
    if match:
        ext = match.group(1).lower()
        if ext == "jpeg":
            ext = "jpg"
        return ext
    return None


def is_discord_cdn_url(url: str) -> bool:
    """
    Check if the URL is a Discord CDN URL.
    """
    return url.startswith("https://cdn.discordapp.com/") or url.startswith(
        "https://media.discordapp.net/"
    )


async def fetch_image(url: str, timeout: float) -> tuple[io.BytesIO | None, str]:
    """
    Fetch an image from a URL and return its content and file extension.
    """

    try:
        async with AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()
            if not content_type.startswith("image/"):
                logger.warning(f"URL {url} returned non-image content type: {content_type}")
                return None, "png"

            ext = get_extension_from_url(url)
            if not ext:
                ext = get_image_extension_from_content_type(content_type)
            if not ext:
                ext = "png"

            return io.BytesIO(response.content), ext
    except HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code} fetching image from {url}")
        return None, "png"
    except Exception as e:
        logger.error(f"Error fetching image from {url}: {format_traceback(e)}")
        return None, "png"


async def to_discord_file(url: str, timeout: float = 10.0) -> tuple[io.BytesIO | None, str]:
    """
    Convert a URL to a Discord file-like object.
    """
    image_data, ext = await fetch_image(url, timeout)
    if image_data:
        file_name = f"{hashlib.sha256(url.encode()).hexdigest()[:12]}.{ext}"
        return File(image_data, filename=file_name), file_name

    return None, "png"


def model_diff(old: "BaseModel", new: "BaseModel") -> Dict[str, Any]:
    def _diff(old_val: Any, new_val: Any) -> Any:
        # Handle nested Pydantic models
        if isinstance(old_val, "BaseModel") and isinstance(new_val, "BaseModel"):
            return _diff(
                old_val.model_dump(
                    mode="json",
                ),
                new_val.model_dump(
                    mode="json",
                ),
            )

        # Handle nested dictionaries
        if isinstance(old_val, dict) and isinstance(new_val, dict):
            changes = {
                k: _diff(old_val.get(k), v)
                for k, v in new_val.items()
                if old_val.get(k) != v or isinstance(v, (dict, "BaseModel"))
            }
            return {k: v for k, v in changes.items() if v is not None}

        # Handle primitive change
        return new_val if old_val != new_val else None

    return {
        k: v
        for k, v in _diff(
            old.model_dump(
                mode="json",
            ),
            new.model_dump(
                mode="json",
            ),
        ).items()
        if v is not None
    }


def is_image_url(url: str) -> bool:
    """
    Test if a URL is an image URL
    """
    return url.endswith(IMAGE_EXTENSIONS)


def is_valid_hex_color(color: str) -> bool:
    """
    Test if a string is a valid hex color
    """
    return bool(re.match("^#(?:[0-9a-fA-F]{3}){1,2}$", color))


def split_list_to_chunks(lst: list[T], chunk_size: int) -> list[list[T]]:
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def datetime_formatter(time: datetime):
    """Parse a datetime object into a human-readable format.

    Args:
        time: Datetime object to parse

    Returns:
        Human-readable string representation of the datetime object
    """
    # Abbreviated day of the week, e.g. "Mon"
    day_abbrev = time.strftime("%a")
    # Time in 12-hour format with no leading zero, e.g. "4:00PM"
    time_str = time.strftime("%I:%M%p").lstrip("0")
    # Month/Day/Year with no leading zeros, e.g. 1/20/2025
    month = time.month
    day = time.day
    year = time.year
    return f"{day_abbrev} {time_str} ({str(time.tzinfo)}), {month}/{day}/{year}"


def shorten(text: str, length: int) -> str:
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."


def cookie_str_to_dict(cookie_str: str) -> dict[str, str]:
    """
    Parse a cookie header string into a dictionary.

    Example:
        "foo=bar; baz=qux; zap=zazzle"
        -> {"foo": "bar", "baz": "qux", "zap": "zazzle"}
    """
    cookies: dict[str, str] = {}
    if not cookie_str:
        return cookies

    # Split on ';' to get individual "name=value" segments
    parts = cookie_str.split(";")
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Only split on the first '=' in case the value contains '=' itself
        if "=" in part:
            name, value = part.split("=", 1)
            cookies[name.strip()] = value.strip()
        else:
            # If there’s no '=', treat it as a flag (e.g. "Secure", "HttpOnly")
            cookies[part] = ""
    return cookies


def extract_discord_cdn_image_url(url: str) -> str:
    """
    Extract the image URL from a Discord CDN URL

    Example:
    https://cdn.discordapp.com/attachments/1214524316088274944/1221561014529818654/card.webp?ex=66130659&is=66009159&hm=2f25a5454950232bba62c195da137cd721641c954b358656fa1b133f71dfe186&

    Retruns:
    https://cdn.discordapp.com/attachments/1214524316088274944/1221561014529818654/card.webp
    """
    return url.split("?")[0]


def load_json(filename: str = "config.json") -> dict:
    """
    Fetch default config file
    """
    try:
        with open(filename, encoding="utf8") as data:
            return json.load(data)
    except FileNotFoundError:
        raise FileNotFoundError("JSON file wasn't found")


def dump_json(data: dict, filename: str) -> None:
    """
    Save data to a JSON file
    """
    try:
        with open(filename, "w", encoding="utf8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving JSON file {filename}: {format_traceback(e)}")
        raise e


def format_traceback(err: Exception | None, advance: bool = False) -> str:
    """Format traceback details for debugging.

    Args:
        err (Exception): The caught exception.
        advance (bool): True for extended details, False for concise.

    Returns:
        str: A formatted traceback string.
    """

    if err is None:
        return "No traceback available"

    if os.getenv("DEBUG") == "TRUE":
        advance = True

    if advance:
        # Get full traceback including exception info
        _traceback = "".join(traceback.format_exception(type(err), err, err.__traceback__))
        error = f"```\n{_traceback}\n```"
        return error
    else:
        return f"{type(err).__name__}: {err}"


def format_date_value(target, clock: bool = True, ago: bool = False, only_ago: bool = False) -> str:
    """
    Converts a timestamp to a Discord timestamp format
    """
    if isinstance(target, int) or isinstance(target, float):
        target = datetime.utcfromtimestamp(target)
    unix = int(time.mktime(target.timetuple()))
    timestamp = f"<t:{unix}:{('f' if clock else 'D')}>"
    if ago:
        timestamp += f" (<t:{unix}:R>)"
    if only_ago:
        timestamp = f"<t:{unix}:R>"
    return timestamp


async def make_api_request(
    url: str, method: str = "GET", params: dict = {}, json: dict = {}
) -> dict:
    """
    Make an asynchronous HTTP request to the Plana API.

    Args:
        url (str): The URL to request.
        method (str): The HTTP method (default is GET).
        params (dict): Optional query parameters for the request.
        json (dict): Optional JSON body for the request.

    Returns:
        dict: The JSON response from the request.
    """
    headers = {
        "Content-Type": "application/json",
        "Plana-API-Key": os.getenv("PLANA_API_KEY"),
    }

    if not url.startswith("http"):
        url = f"{os.getenv('PLANA_API_URL')}{url}"

    return await make_request(url, method, headers, params, json)


async def make_request(
    url: str,
    method: str = "GET",
    headers: dict = {},
    params: dict = {},
    json: dict = {},
) -> dict:
    """
    Make an asynchronous HTTP request and return the JSON response.

    Args:
        url (str): The URL to request.
        method (str): The HTTP method (default is GET).
        headers (dict): Optional headers for the request.
        params (dict): Optional query parameters for the request.

    Returns:
        dict: The JSON response from the request.
    """

    logger.info(f"Making {method} request to {url}")

    try:
        async with AsyncClient() as client:
            response = await client.request(method, url, headers=headers, params=params, json=json)
            response.raise_for_status()
            return response.json()
    except HTTPStatusError as e:
        logger.error(
            f"HTTP error {e.response.status_code} while making request to {url}: {e.response.text}"
        )
        return {}
    except Exception as e:
        logger.error(f"Error while making request to {url}: {e}, {traceback.format_exc()}")
        return {}


def _get_variable_context(message: Message) -> dict:
    """
    Build a comprehensive context dictionary with all available variables.
    """
    context = {}

    context.update(
        {
            "message": message.content,
            "message.content": message.content,
            "message.id": str(message.id),
        }
    )
    # User variables
    user = message.author
    context.update(
        {
            "user": user.display_name,
            "user.mention": user.mention,
            "user.id": str(user.id),
            "user.name": user.name,
            "user.idname": user.name,
            "user.avatar_url": user.display_avatar.url,
            "user.avatar": user.avatar.key if user.avatar else None,
            "user.bot": str(user.bot),
        }
    )

    # Server variables
    guild = message.guild
    if guild:
        context.update(
            {
                "server": guild.name,
                "server.name": guild.name,
                "server.id": str(guild.id),
                "server.icon_url": guild.icon.url if guild.icon else None,
                "server.icon": guild.icon.key if guild.icon else None,
                "server.owner": guild.owner.display_name if guild.owner else "Unknown",
                "server.owner_id": str(guild.owner_id) if guild.owner_id else "Unknown",
                "server.member_count": str(guild.member_count),
                "server.verification_level": str(guild.verification_level.value),
                "server.joined_at": (
                    guild.me.joined_at.isoformat() if guild.me.joined_at else None
                ),
            }
        )

    # Channel variables
    channel = message.channel
    context.update(
        {
            "channel": f"#{channel.name}" if hasattr(channel, "name") else str(channel),
            "channel.name": getattr(channel, "name", "Unknown"),
            "channel.id": str(channel.id),
            "channel.type": str(channel.type.value),
        }
    )

    return context


def _replace_variables(text: str, context: dict) -> str:
    """
    Replace variables in text using the provided context dictionary.
    Uses regex for more robust replacement.
    """
    import re

    def replace_var(match):
        var_name = match.group(1)
        return str(context.get(var_name, match.group(0)))  # Return original if not found

    # Replace {variable} patterns
    return re.sub(r"\{([^}]+)\}", replace_var, text)


async def format_template_message(template: str, message: Message) -> str:
    """
    Format the user's input based on the input template and message context.
    """
    if not template:
        return message.content

    # Get all available variables
    context = _get_variable_context(message)

    try:
        # Replace variables in the input template
        message.content = _replace_variables(template, context)
        return message.content
    except Exception as e:
        logger.error(
            f"Error while formatting message context: {e}, input_template: {template}, message: {message.content}"
        )
        return message.content
