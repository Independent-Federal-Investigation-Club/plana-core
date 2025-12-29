from pathlib import Path
from typing import Optional

import i18n
from discord import Locale, app_commands
from loguru import logger

from plana.constant import DEFAULT_LOCALE, DEFAULT_LOCALE_DIR

__all__ = ["Tr", "PlanaTranslator", "PlanaLocaleStr"]


class PlanaLocaleStr(app_commands.locale_str):
    """Custom locale_str for Plana bot with additional attributes."""

    def __init__(self, key: str, **extras):
        """
        Initialize a PlanaLocaleStr.

        Args:
            key: The translation key
            **extras: Additional attributes for translation context and template variables
        """
        message = Tr.t(key, locale=Locale.american_english)

        super().__init__(message, **extras)
        self.key = key
        self.extras = extras


class PlanaTranslator(app_commands.Translator):
    """Discord.py Translator implementation for Plana bot."""

    async def translate(
        self,
        string: PlanaLocaleStr,
        locale: Locale,
        context: app_commands.TranslationContext,
    ) -> Optional[str]:
        """
        Translate a locale_str for the given locale.

        Args:
            string: The locale_str to translate
            locale: The target locale
            context: Translation context

        Returns:
            Translated string or None if no translation available
        """
        # Get the translation key from the locale_str
        key = string.key if hasattr(string, "key") else string.message
        try:
            translation = Tr.t(key, locale=locale, **string.extras)
            return translation if translation else key

        except Exception as e:
            logger.warning(f"Translation failed for key '{key}' in locale '{locale}': {e}")
            return


class Tr:
    """localization manager using python-i18n with Discord integration.

    Naming convention:

    | Type                    | Key Pattern                                                                             | Example                            |
    | ----------------------- | --------------------------------------------------------------------------------------- | ---------------------------------- |
    | **Command Name**        | `cogname.command.name`                                                                  | `music.playlist.name`                   |
    | **Command Description** | `cogname.command.description`                                                           | `music.playlist.description`            |
    | **Subcommand Name**        | `cogname.command.name`                                                               | `music.playlist.add.name`                   |
    | **SubCommand Description** | `cogname.command.description`                                                        | `music.playlist.add.description`            |
    | **Command Parameter**   | `cogname.command.param.paramname.description`                                           | `music.playlist.add.param.song_name.description` |
    | **Response Messages**   | `cogname.command.response.text`                                                         | `admin.ban.response.success`       |
    | **Error Messages**      | `cogname.error.text`                                                                    | `admin.error.permission_denied`    |
    | **Embeds**              | `cogname.command.embedname.fieldname`                                                  | `music.queue.embed.title`          |
    | **UI Components**       | `cogname.command.ui.componenttype.name`                                                | `music.skip.ui.button.label`          |


    NOTES: Template variables are supported with %{variable_name} syntax.

    """

    _initialized = False

    @classmethod
    def _setup_i18n(cls, locale_dir: str = DEFAULT_LOCALE_DIR):
        """Initialize i18n configuration."""
        if cls._initialized:
            return

        locale_path = Path(locale_dir)
        i18n.set("filename_format", "{locale}.{format}")
        i18n.set("file_format", "yml")
        i18n.set("available_locales", ["en-US", "zh-CN", "ja"])
        i18n.set("fallback", DEFAULT_LOCALE.value)
        i18n.set("skip_locale_root_data", True)

        i18n.load_path.append(str(locale_path))
        cls._initialized = True

    @staticmethod
    def t(key: str, locale: Optional[Locale] = DEFAULT_LOCALE, **kwargs) -> str:
        """
        Translate a key with optional parameters.

        Args:
            key: Translation key (dot notation supported)
            locale: Discord locale (defaults to fallback)
            **kwargs: Template variables

        Returns:
            Translated string
        """
        Tr._setup_i18n()
        return i18n.t(key, locale=locale.value, **kwargs)  #
