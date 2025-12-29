# Models copied from the Plana API

from typing import Optional, TypeVar, Union

from pydantic import BaseModel, Field

from plana.utils.helper import make_api_request

from .base import PlanaModel, SnowflakeId


class UserDataField(PlanaModel):
    __property__ = "user_data"


FieldType = TypeVar("T", bound=UserDataField)


class User(PlanaModel):
    """User model for storing and retrieving user data."""

    id: Optional[SnowflakeId] = Field(
        default=None, description="Custom Global Unique ID of the user"
    )

    user_id: SnowflakeId = Field(
        description="ID of the user for which users are set",
    )

    guild_id: Optional[SnowflakeId] = Field(
        default=None,
        description="ID of the guild for which users are set",
    )

    user_data: Optional[dict] = Field(default_factory=dict, description="User data dictionary")

    @staticmethod
    async def get(guild_id: int, user_id: int) -> Union["User", None]:
        response = await make_api_request(url=f"/guilds/{guild_id}/users/{user_id}", method="GET")
        if not response:
            return await User.create(guild_id, {"user_id": user_id})
        return User(**response)

    @staticmethod
    async def get_all(guild_id: int) -> list["User"]:
        response = await make_api_request(url=f"/guilds/{guild_id}/users", method="GET")
        if not response:
            return []
        return [User(**user) for user in response.get("data", [])]

    @staticmethod
    async def create(guild_id: int, data: dict = {}) -> Union["User", None]:
        response = await make_api_request(f"/guilds/{guild_id}/users", method="POST", json=data)
        if not response:
            return
        return User(**response)

    @staticmethod
    async def set(guild_id: int, user_id: int, data: dict = {}) -> Union["User", None]:
        response = await make_api_request(
            f"/guilds/{guild_id}/users/{user_id}", method="POST", json=data
        )
        if not response:
            return
        return User(**response)

    @staticmethod
    async def bulk_update(users: list["User"]) -> None | dict:
        """
        Bulk update user preferences without guild_id.
        """
        return await make_api_request(
            f"/users/bulk",
            method="PUT",
            json=[user.model_dump(mode="json", exclude_unset=True) for user in users],
        )

    @staticmethod
    async def delete(guild_id: int, user_id: int) -> None:
        await make_api_request(f"/guilds/{guild_id}/users/{user_id}", method="DELETE")

    async def save(self) -> Union["User", None]:
        return await User.set(
            self.guild_id, self.user_id, data=self.model_dump(mode="json", exclude_unset=True)
        )
