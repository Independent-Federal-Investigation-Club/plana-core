from discord import Locale
from discord.app_commands.errors import AppCommandError

from plana.constant import DEFAULT_LOCALE


class PlanaError(Exception):
    def __init__(self, *, locale: Locale, title: str, message: str) -> None:
        self.title = title
        self.message = message


class InvalidInputError(PlanaError):
    def __init__(self, reason: str, locale: Locale = DEFAULT_LOCALE) -> None:
        super().__init__(
            locale=locale,
            title="Invalid input",
            message=reason,
        )


class InvalidQueryError(PlanaError):
    def __init__(self, locale: Locale = DEFAULT_LOCALE) -> None:
        super().__init__(
            locale=locale,
            title="Invalid query",
            message="Unable to find anything with the provided query, please select choices from the autocomplete instead of typing your own query.",
        )


class AccountNotFoundError(PlanaError, AppCommandError):
    def __init__(self, locale: Locale = DEFAULT_LOCALE) -> None:
        super().__init__(
            locale=locale,
            title="Account not found",
            message="Unable to find an account with the provided query, please select choices from the autocomplete instead of typing your own query.",
        )


class NoAccountFoundError(PlanaError):
    def __init__(self, locale: Locale = DEFAULT_LOCALE) -> None:
        super().__init__(
            locale=locale,
            title="No account found",
            message="You don't have any accounts yet. Add one with </accounts>",
        )


class InvalidImageURLError(PlanaError):
    def __init__(self, locale: Locale = DEFAULT_LOCALE) -> None:
        super().__init__(
            locale=locale,
            title="Invalid image URL",
            message="A valid image URL needs to be a direct URL to an image file that contains an image extension, and is publicly accessible.",
        )


class IncompleteParamError(PlanaError):
    def __init__(self, reason: str, locale: Locale = DEFAULT_LOCALE) -> None:
        super().__init__(
            locale=locale,
            title="The given command parameters are incomplete",
            message=reason,
        )


class NSFWPromptError(PlanaError):
    def __init__(self, locale: Locale = DEFAULT_LOCALE) -> None:
        super().__init__(
            locale=locale,
            title="NSFW Prompt",
            message="The prompt contains NSFW content, please try again with a different prompt.",
        )


class GuildOnlyFeatureError(PlanaError):
    def __init__(self, locale: Locale = DEFAULT_LOCALE) -> None:
        super().__init__(
            locale=locale,
            title="Guild Only Feature",
            message="This feature is only available in guilds, please try again in a guild.",
        )
