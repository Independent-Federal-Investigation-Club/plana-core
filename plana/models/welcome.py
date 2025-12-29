from datetime import datetime
from typing import List, Optional, Self, Union

from pydantic import Field, field_validator

from plana.utils.helper import make_api_request

from .base import PlanaModel, SnowflakeId
from .message import Message


class WelcomeAction(PlanaModel):
    """Model for welcome actions configuration."""

    type: str = Field(description="Type of action (add_role, remove_role, send_dm)")
    target_ids: List[SnowflakeId] = Field(
        description="List of role IDs or user IDs depending on action type"
    )
    delay_seconds: Optional[int] = Field(
        default=0, description="Delay in seconds before executing the action", ge=0
    )
    conditions: Optional[dict] = Field(
        default_factory=dict, description="Conditions for action execution"
    )


class WelcomeSetting(PlanaModel):
    """Model for guild welcome system configuration."""

    id: Optional[SnowflakeId] = Field(default=None, description="ID of the guild")
    enabled: Optional[bool] = Field(default=False, description="Whether welcome system is enabled")

    # Channel settings
    welcome_channel_id: Optional[SnowflakeId] = Field(
        default=None, description="Channel ID for welcome messages"
    )
    goodbye_channel_id: Optional[SnowflakeId] = Field(
        default=None, description="Channel ID for goodbye messages"
    )
    dm_new_users: Optional[bool] = Field(
        default=False, description="Whether to send DM to new users"
    )

    # Message content
    welcome_message: Optional[Message] = Field(default=None, description="Welcome message template")
    goodbye_message: Optional[Message] = Field(default=None, description="Goodbye message template")
    dm_message: Optional[Message] = Field(
        default=None, description="DM message template for new users"
    )

    # Auto roles and actions
    auto_roles: Optional[List[int]] = Field(
        default_factory=list, description="List of role IDs to assign to new members"
    )

    updated_at: Optional[datetime] = Field(default=None, description="Timestamp of last update")

    @field_validator("auto_roles")
    @classmethod
    def validate_auto_roles(cls, v: List[int]) -> List[int]:
        if len(v) > 20:  # Discord limit
            raise ValueError("Cannot assign more than 20 auto roles")
        return v

    @staticmethod
    async def get(guild_id: int) -> Union[Self | None]:
        response = await make_api_request(url=f"/guilds/{guild_id}/welcome", method="GET")
        if not response:
            return await WelcomeSetting.create(guild_id=guild_id)
        return WelcomeSetting(**response)

    @staticmethod
    async def create(guild_id: int, data: dict = {}) -> Union[Self | None]:
        response = await make_api_request(f"/guilds/{guild_id}/welcome", method="POST", json=data)
        if not response:
            return
        return WelcomeSetting(**response)

    @staticmethod
    async def update(guild_id: int, data: dict = {}) -> Union[Self | None]:
        response = await make_api_request(f"/guilds/{guild_id}/welcome", method="PATCH", json=data)
        if not response:
            return
        return WelcomeSetting(**response)

    @staticmethod
    async def delete(guild_id: int) -> None:
        await make_api_request(f"/guilds/{guild_id}/welcome", method="DELETE")

    async def save(self) -> Union[Self | None]:
        return await WelcomeSetting.update(
            self.id, data=self.model_dump(mode="json", exclude_unset=True)
        )
