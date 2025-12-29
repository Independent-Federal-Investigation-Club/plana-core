from datetime import datetime
from typing import List, Optional, Union

from pydantic import Field

from plana.utils.helper import make_api_request

from .base import PlanaModel, SnowflakeId


class RssFeed(PlanaModel):
    """Model for RSS feed configuration."""

    id: Optional[SnowflakeId] = Field(default=None, description="ID of the RSS feed")
    guild_id: Optional[SnowflakeId] = Field(default=None, description="ID of the guild")
    channel_id: Optional[SnowflakeId] = Field(
        default=None, description="ID of the channel to post RSS updates"
    )
    url: Optional[str] = Field(default=None, description="URL of the RSS feed", max_length=500)
    name: Optional[str] = Field(default=None, description="Name of the RSS feed", max_length=100)
    enabled: bool = Field(default=True, description="Whether this RSS feed is enabled")
    message: Optional[str] = Field(
        default=None,
        description="Custom message to prepend to RSS updates. Supports template variables: "
        "{title}, {link}, {description}, {author}, {pubDate}, {pubDateShort}, "
        "{pubDateTime}, {pubDateISO}, {categories}, {feedName}, {feedUrl}",
        max_length=500,
    )
    last_updated: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the last update to the RSS feed",
    )

    @staticmethod
    async def get(guild_id: int, rss_id: int) -> Optional["RssFeed"]:
        """Fetch a specific RSS feed by guild ID and feed ID."""
        response = await make_api_request(url=f"/guilds/{guild_id}/rss/{rss_id}", method="GET")
        if not response:
            return None
        return RssFeed(**response)

    @staticmethod
    async def get_all(guild_id: int) -> List["RssFeed"]:
        response = await make_api_request(url=f"/guilds/{guild_id}/rss", method="GET")
        if not response:
            return []
        return [RssFeed(**item) for item in response.get("data", [])]

    @staticmethod
    async def create(guild_id: int, data: dict = {}) -> Union["RssFeed", None]:
        response = await make_api_request(f"/guilds/{guild_id}/rss", method="POST", json=data)
        if not response:
            return
        return RssFeed(**response)

    @staticmethod
    async def update(guild_id: int, rss_id: int, data: dict) -> Union["RssFeed", None]:
        response = await make_api_request(
            url=f"/guilds/{guild_id}/rss/{rss_id}",
            method="PUT",
            json=data,
        )
        if not response:
            return
        return RssFeed(**response)

    @staticmethod
    async def delete(guild_id: int, rss_id: int) -> None:
        await make_api_request(url=f"/guilds/{guild_id}/rss/{rss_id}", method="DELETE")

    async def save(self) -> Union["RssFeed", None]:
        """Save the current RSS setting to the API."""
        return await RssFeed.update(
            self.guild_id,
            self.id,
            self.model_dump(
                mode="json",
            ),
        )
