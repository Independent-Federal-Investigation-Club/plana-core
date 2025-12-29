from datetime import datetime
from typing import List, Optional, Union
from pydantic import Field
from .base import PlanaModel, SnowflakeId

from plana.utils.helper import make_api_request


class RoleAssignment(PlanaModel):
    """Model for role assignment configuration."""

    role_ids: List[SnowflakeId] = Field(description="List of Discord role IDs to assign")
    trigger_id: str = Field(
        description="ID of the trigger (emoji.id or emoji.name), button custom_id, or menu.custom_id-option.value)"
    )


class ReactRoleSetting(PlanaModel):
    """Model for react role configuration."""

    id: Optional[SnowflakeId] = Field(default=None, description="ID of the react role config")
    guild_id: Optional[SnowflakeId] = Field(default=None, description="ID of the guild")
    message_id: Optional[SnowflakeId] = Field(
        default=None, description="ID of the message to attach react roles to"
    )
    name: Optional[str] = Field(
        default=None,
        description="Name/description of this react role setup",
        max_length=100,
    )
    role_assignments: List[RoleAssignment] = Field(
        default_factory=list, description="List of role assignments"
    )
    enabled: Optional[bool] = Field(
        default=True, description="Whether this react role configuration is enabled"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the last update to the message",
    )

    @staticmethod
    async def get(guild_id: int, config_id: int) -> Union["ReactRoleSetting", None]:
        response = await make_api_request(
            url=f"/guilds/{guild_id}/react-roles/{config_id}", method="GET"
        )
        if not response:
            return
        return ReactRoleSetting(**response)

    @staticmethod
    async def get_all(guild_id: int) -> List["ReactRoleSetting"]:
        response = await make_api_request(url=f"/guilds/{guild_id}/react-roles", method="GET")
        if not response:
            return []
        return [ReactRoleSetting(**config) for config in response.get("data", [])]

    @staticmethod
    async def create(guild_id: int, data: dict = {}) -> Union["ReactRoleSetting", None]:
        response = await make_api_request(
            f"/guilds/{guild_id}/react-roles", method="POST", json=data
        )
        if not response:
            return
        return ReactRoleSetting(**response)

    @staticmethod
    async def update(
        guild_id: int, config_id: int, data: dict = {}
    ) -> Union["ReactRoleSetting", None]:
        response = await make_api_request(
            f"/guilds/{guild_id}/react-roles/{config_id}", method="PATCH", json=data
        )
        if not response:
            return
        return ReactRoleSetting(**response)

    @staticmethod
    async def delete(guild_id: int, config_id: int) -> None:
        await make_api_request(f"/guilds/{guild_id}/react-roles/{config_id}", method="DELETE")

    async def save(self) -> Union["ReactRoleSetting", None]:
        if self.id:
            return await ReactRoleSetting.update(
                self.guild_id, self.id, data=self.model_dump(mode="json", exclude_unset=True)
            )
        return await ReactRoleSetting.create(
            self.guild_id, data=self.model_dump(mode="json", exclude_unset=True)
        )
