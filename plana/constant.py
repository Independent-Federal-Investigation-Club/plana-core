import logging
import os
from random import choice

from discord import Color, Locale

INFO = logging.INFO
DEBUG = logging.DEBUG
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

# Server Setting
MESSAGE_LOGGING_ENABLED = False
MODERATION_ENABLED = False
PLANATALK_ENABLED = True
PLANAECHO_ENABLED = False
NOVELAI_ENABLED = False
CHECKIN_ENABLED = False


# PlanaTalk Setting
# openai  = "https://api.openai.com/v1/"
# deepseek = "https://api.deepseek.com/"
# nvidia = "https://integrate.api.nvidia.com/v1"
# gemini = "https://generativelanguage.googleapis.com/v1beta/openai/"


# User Setting
USER_DEFAULT_LOCALE = Locale.american_english
USER_DEFAULT_DARK_MODE = True

# Logging Setting
LOGGING_DEFAULT_LEVEL = DEBUG if os.getenv("DEBUG") else INFO
LOGGING_DEFAULT_PATH = "plana/logs/"

# Hoyolab API Setting
HOYOLAB_CHECKIN_API = "http://localhost:8080/checkin"
HOYOLAB_ACCOUNT_API = "http://localhost:8080/list"
HOYOLAB_COOKIE_INSTRUCTIONS = "https://media.discordapp.net/attachments/471701478382370818/1320951067420262521/dev_tools_tutorial.gif"
HOYO_SERVICE_API_KEY = ""

# Plana Settings
DEFAULT_LOCALE = Locale.american_english
DEFAULT_LOCALE_DIR = "plana/locales"

# Embed Images
DEFAULT_FOOTER_TEXT = "Powered by Plana AI, all rights reserved"
DEFAULT_EMBED_COLOR = Color.green()
DEFAULT_ERROR_COLOR = Color.red()

DEFAULT_EMBED_IMAGES = [
    "https://media.discordapp.net/attachments/471701478382370818/1322771307493982269/image.png",
    "https://media.discordapp.net/attachments/471701478382370818/1322771341513986068/image.png",
    "https://media.discordapp.net/attachments/471701478382370818/1322771375563214889/image.png",
    "https://media.discordapp.net/attachments/471701478382370818/1322771428675686451/image.png",
]

DEFAULT_ERROR_EMBED_IMAGE = (
    "https://media.discordapp.net/attachments/471701478382370818/1322771265647415378/image.png"
)

# Plana Automate Settings
DEFAULT_TIMEZONE = "America/Chicago"


PERPLEXITY_COOKIES = ""


def get_embed_image():
    return choice(DEFAULT_EMBED_IMAGES)
