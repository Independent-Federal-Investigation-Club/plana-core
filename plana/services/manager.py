# Preference management for guilds
import traceback
from typing import TYPE_CHECKING, List, Optional, Tuple
from zoneinfo import ZoneInfo, available_timezones

from discord import Locale
from loguru import logger
from pydantic import BaseModel, Field

from plana.models.achievements import AchievementSetting
from plana.models.ai import AISetting
from plana.models.guild import Guild, GuildPreference
from plana.models.levels import LevelSetting
from plana.models.react_role import ReactRoleSetting
from plana.models.rss import RssFeed
from plana.models.user import FieldType, User, UserDataField
from plana.models.welcome import WelcomeSetting

if TYPE_CHECKING:
    from plana.utils.context import PlanaContext


class GuildSettings(BaseModel):
    """Guild model for storing and retrieving guild information."""

    id: Optional[int] = Field(
        default=None, description="ID of the guild for which preferences are set"
    )

    preferences: Optional["GuildPreference"] = Field(
        default=None, description="Preferences for the guild"
    )

    react_roles: Optional[list["ReactRoleSetting"]] = Field(
        default=None, description="React roles for the guild"
    )

    levels: Optional["LevelSetting"] = Field(
        default=None, description="Level settings for the guild"
    )

    welcome: Optional["WelcomeSetting"] = Field(
        default=None, description="Welcome settings for the guild"
    )

    rss_feeds: List["RssFeed"] = Field(
        default_factory=list, description="RSS settings for the guild"
    )

    achievements: Optional["AchievementSetting"] = Field(
        default=None, description="Achievement settings for the guild"
    )

    ai: Optional["AISetting"] = Field(default=None, description="AI settings for the guild")

    @staticmethod
    async def get(guild_id: int) -> "GuildSettings":
        preferences = await GuildPreference.get(guild_id)
        levels = await LevelSetting.get(guild_id)
        welcome = await WelcomeSetting.get(guild_id)
        achievements = await AchievementSetting.get(guild_id)
        ai = await AISetting.get(guild_id)

        react_roles = await ReactRoleSetting.get_all(guild_id)
        rss_feeds = await RssFeed.get_all(guild_id)

        return GuildSettings(
            id=guild_id,
            preferences=preferences,
            react_roles=react_roles,
            welcome=welcome,
            levels=levels,
            ai=ai,
            rss_feeds=rss_feeds,
            achievements=achievements,
        )

    @staticmethod
    async def delete(guild_id: int) -> None:
        await GuildPreference.delete(guild_id)
        await LevelSetting.delete(guild_id)
        await WelcomeSetting.delete(guild_id)
        await AchievementSetting.delete(guild_id)
        await AISetting.delete(guild_id)

        for react_role in await ReactRoleSetting.get_all(guild_id):
            await react_role.delete(guild_id, react_role.id)

        for rss_feed in await RssFeed.get_all(guild_id):
            await rss_feed.delete(guild_id, rss_feed.id)

    @staticmethod
    async def reset(guild_id: int) -> "GuildSettings":
        await GuildSettings.delete(guild_id)
        return await GuildSettings.get(guild_id)


class GuildManager:
    """A static class to manage and cache guild preferences for the Plana bot."""

    settings: dict[int, GuildSettings] = {}

    @staticmethod
    async def get(guild_id: int) -> GuildSettings:
        """
        Retrieve the preferences for a specific guild.
        """
        stack = traceback.extract_stack()
        caller = stack[-2]  # -1 is current line

        if guild_id in GuildManager.settings:
            return GuildManager.settings[guild_id]

        GuildManager.settings[guild_id] = await GuildSettings.get(guild_id)
        return GuildManager.settings[guild_id]

    @staticmethod
    async def refresh(guild_id: int, setting_name: Optional[str] = None) -> GuildSettings:
        """
        Refresh the cached preferences for a specific guild.
        """

        if not setting_name or guild_id not in GuildManager.settings:
            GuildManager.settings[guild_id] = await GuildSettings.get(guild_id)
            return GuildManager.settings[guild_id]

        guild = GuildManager.settings[guild_id]
        if setting_name == "preferences":
            guild.preferences = await GuildPreference.get(guild_id)
        elif setting_name == "levels":
            guild.levels = await LevelSetting.get(guild_id)
        elif setting_name == "welcome":
            guild.welcome = await WelcomeSetting.get(guild_id)
        elif setting_name == "achievements":
            guild.achievements = await AchievementSetting.get(guild_id)
        elif setting_name == "react_roles":
            guild.react_roles = await ReactRoleSetting.get_all(guild_id)
        elif setting_name == "rss":
            guild.rss_feeds = await RssFeed.get_all(guild_id)
        elif setting_name == "ai":
            guild.ai = await AISetting.get(guild_id)

        return guild

    @staticmethod
    async def reset(guild_id: int) -> GuildSettings:
        """
        Reset the guild preferences to default values.
        """
        GuildManager.settings[guild_id] = await GuildSettings.reset(guild_id)
        return GuildManager.settings[guild_id]

    @staticmethod
    async def get_locale(ctx: "PlanaContext") -> Locale:
        """
        Get the locale for a specific guild.
        """

        if ctx.interaction and ctx.interaction.locale:
            return ctx.interaction.locale

        settings = await GuildManager.get(ctx.guild.id)
        if settings.preferences and settings.preferences.language:
            return Locale(settings.preferences.language)

        return Locale.american_english

    @staticmethod
    async def get_timezone(guild_id: int) -> ZoneInfo:
        """
        Get the timezone for a specific guild.
        """
        settings = await GuildManager.get(guild_id=guild_id)

        # check if the guild has a valid timezone set
        if (
            settings.preferences
            and settings.preferences.timezone
            and settings.preferences.timezone in available_timezones()
        ):
            return ZoneInfo(settings.preferences.timezone)

        return ZoneInfo("America/Chicago")


class GuildDataTracker:
    """A static class to manage and cache guild data for the Plana bot."""

    dirty_guilds: set[int] = set[int]()

    @staticmethod
    def mark_dirty(guild_id: int) -> None:
        """Mark a guild as dirty for update."""
        GuildDataTracker.dirty_guilds.add(guild_id)

    @staticmethod
    def clean_all() -> None:
        """Clean all dirty guilds."""
        GuildDataTracker.dirty_guilds.clear()

    @staticmethod
    def get_dirty() -> List[int]:
        """Get list of dirty guilds."""
        return list(GuildDataTracker.dirty_guilds)

    @staticmethod
    async def update_dirty() -> None:
        """Update all dirty guilds."""
        for guild_id in GuildDataTracker.dirty_guilds:
            await Guild.refresh(guild_id)

        GuildDataTracker.clean_all()


class UserManager:
    """A static class to manage and cache user preferences for the Plana bot."""

    users: dict[Tuple[int, int], "User"] = {}
    dirty_users: set[Tuple[int, int]] = set[Tuple[int, int]]()

    @staticmethod
    async def init(guild_id: int) -> None:
        """
        Initialize the UserManager by loading all users from the API.
        This is typically called at startup.
        """
        users = await User.get_all(guild_id)
        for user in users:
            UserManager.users[(user.guild_id, user.user_id)] = user
            UserManager.mark_clean(user.guild_id, user.user_id)

    @staticmethod
    async def get(guild_id: int, user_id: int) -> "User":
        """
        Retrieve the preferences for a specific user.
        """

        if (guild_id, user_id) in UserManager.users:
            return UserManager.users[(guild_id, user_id)]

        return await UserManager.refresh(guild_id, user_id)

    @staticmethod
    async def get_all(guild_id: int) -> List["User"]:
        """
        Retrieve all users for a specific guild.
        """
        return [UserManager.users[(gid, uid)] for gid, uid in UserManager.users if gid == guild_id]

    @staticmethod
    async def refresh(guild_id: int, user_id: int) -> "User":
        """
        Refresh the cached preferences for a specific user.
        """

        UserManager.users[(guild_id, user_id)] = await User.get(guild_id, user_id)
        UserManager.mark_clean(guild_id, user_id)
        return UserManager.users[(guild_id, user_id)]

    @staticmethod
    async def bulk_update(users: List[User]) -> None | dict:
        """
        Bulk update user preferences.
        """
        response = await User.bulk_update(users)
        for user in users:
            UserManager.mark_clean(user.guild_id, user.user_id)

        return response

    @staticmethod
    async def update(guild_id: int, user_id: int, user_data: dict) -> None:
        """
        Mark a user as dirty for update.
        """
        user = await UserManager.get(guild_id, user_id)

        user.user_data = user_data
        UserManager.mark_dirty(guild_id, user_id)

    @staticmethod
    async def get_property(guild_id: int, user_id: int, model: FieldType) -> Optional[FieldType]:
        """
        Get a specific property of the user_data for a specific user.
        """
        user = await UserManager.get(guild_id, user_id)

        if not user.user_data or model.__property__ not in user.user_data:
            user.user_data[model.__property__] = {}

        value = user.user_data[model.__property__] or {}
        return model.model_validate(value)

    @staticmethod
    async def update_property(guild_id: int, user_id: int, data: UserDataField) -> None:
        """
        Update a specific property of the user_data for a specific user.
        """
        user = await UserManager.get(guild_id, user_id)
        if not user.user_data:
            user.user_data = {}

        user.user_data[data.__class__.__property__] = data.model_dump(
            mode="json",
        )
        UserManager.mark_dirty(guild_id, user_id)

    @staticmethod
    def get_dirty() -> List[User]:
        """Get list of dirty users."""
        return [
            UserManager.users[(gid, uid)]
            for gid, uid in UserManager.dirty_users
            if (gid, uid) in UserManager.users
        ]

    @staticmethod
    def mark_dirty(guild_id: int, user_id: int) -> None:
        """Mark a user as dirty."""
        UserManager.dirty_users.add((guild_id, user_id))

    @staticmethod
    def mark_clean(guild_id: int, user_id: int) -> None:
        """Mark a user as clean."""
        UserManager.dirty_users.discard((guild_id, user_id))

    @staticmethod
    async def update_dirty() -> None:
        """Mark a user as dirty."""
        await UserManager.bulk_update(UserManager.get_dirty())
