from typing import List, Optional, Union

from pydantic import Field

from plana.utils.helper import make_api_request

from .base import PlanaModel, SnowflakeId


class AISetting(PlanaModel):
    """Guild AI feature preferences and configuration."""

    id: Optional[SnowflakeId] = Field(
        default=None, description="ID of the guild for which AI preferences are set"
    )
    # Core Settings
    enabled: Optional[bool] = Field(default=True, description="Whether AI features are enabled")

    stream: Optional[bool] = Field(
        default=False, description="Enable streaming responses from the AI"
    )

    engage_mode: Optional[bool] = Field(
        default=False,
        description="Engage mode for AI interactions: False=passive (only at mentioned), True=active (responds to messages)",
    )

    engage_rate: Optional[float] = Field(
        default=0.01,
        description="Probability of AI engaging in conversations when engage mode is active",
    )

    # Memory Configuration
    memory_type: Optional[int] = Field(
        default=1, description="Memory scope: 1=guild-wide, 2=per-category, 3=per-channel"
    )
    memory_limit: Optional[int] = Field(
        default=50, description="Maximum number of messages to include in the context"
    )
    # AI Behavior
    system_prompt: Optional[str] = Field(
        default=None, max_length=2000, description="Custom system prompt for AI personality"
    )
    input_template: Optional[str] = Field(
        default='{user.mention} asks: "{message.content}"',
        max_length=500,
        description="Template for formatting user input to AI",
    )

    target_roles: Optional[List[SnowflakeId]] = Field(
        default_factory=list, description="Role IDs to target for AI interactions"
    )
    target_roles_mode: Optional[bool] = Field(
        default=False,
        description="Mode for targeting roles: False=blacklist (ignore), True=whitelist (allow)",
    )

    # Channel Configuration
    target_channels: Optional[List[SnowflakeId]] = Field(
        default_factory=list, description="Channel IDs to target for AI interactions"
    )
    target_channels_mode: Optional[bool] = Field(
        default=False,
        description="Mode for targeting channels: False=blacklist (ignore), True=whitelist (allow)",
    )
    # Advanced Features
    ai_moderation: Optional[bool] = Field(
        default=False,
        description="Enable AI-assisted moderation (future feature, don't implement)",
    )
    reaction_responses: Optional[bool] = Field(
        default=True, description="Allow AI to respond with reactions"
    )

    @staticmethod
    async def get(guild_id: int) -> Union["AISetting", None]:
        """Get AI configuration for a guild."""
        response = await make_api_request(url=f"/guilds/{guild_id}/ai", method="GET")
        if not response:
            return await AISetting.create(guild_id=guild_id)
        return AISetting(**response)

    @staticmethod
    async def create(guild_id: int, data: dict = {}) -> Union["AISetting", None]:
        """Create AI configuration for a guild."""
        response = await make_api_request(url=f"/guilds/{guild_id}/ai", method="POST", json=data)
        if not response:
            return
        return AISetting(**response)

    @staticmethod
    async def update(guild_id: int, data: dict = {}) -> Union["AISetting", None]:
        """Update AI configuration for a guild."""
        response = await make_api_request(url=f"/guilds/{guild_id}/ai", method="PATCH", json=data)
        if not response:
            return
        return AISetting(**response)

    @staticmethod
    async def delete(guild_id: int) -> None:
        """Delete AI configuration for a guild."""
        await make_api_request(url=f"/guilds/{guild_id}/ai", method="DELETE")

    async def save(self) -> Union["AISetting", None]:
        """Save the configuration to the API."""
        data = self.model_dump(mode="json", exclude_unset=True)
        return await AISetting.update(self.id, data)
