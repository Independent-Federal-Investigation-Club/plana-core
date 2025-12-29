import asyncio
import os
import traceback

import discord
from dotenv import load_dotenv
from loguru import logger
from pretty_help import AppMenu, PrettyHelp

from plana.constant import DEFAULT_EMBED_IMAGES, DEFAULT_FOOTER_TEXT
from plana.utils.core import PlanaCore


async def main():
    """
    Main function for logging in to Discord. Args : None Returns : None Raises : Exception : Error when logging in
    """

    intents = discord.Intents(
        bans=True,
        guilds=True,
        members=True,
        invites=True,
        messages=True,
        reactions=True,
        presences=True,
        voice_states=True,
        message_content=True,
        emojis_and_stickers=True,
    )

    load_dotenv()

    menu = AppMenu(ephemeral=True)

    logger.info("Starting PlanaCore...")

    try:
        core = PlanaCore(
            command_prefix=["!"],
            command_attrs={"hidden": True},
            help_command=PrettyHelp(
                menu=menu,
                color=discord.Color.green(),
                ending_note=DEFAULT_FOOTER_TEXT,
                image_url=DEFAULT_EMBED_IMAGES[0],
            ),
            intents=intents,
            case_insensitive=True,
        )

        logger.info("PlanaCore initialized successfully")
        logger.info("Attempting to start bot...")

        await core.start(os.getenv("DISCORD_TOKEN"))

    except discord.LoginFailure as error:
        logger.error(f"Invalid Discord token: {error}")
    except discord.HTTPException as error:
        logger.error(f"HTTP error during login: {error}")
    except Exception as error:
        logger.error(f"Unexpected error when starting bot: {error}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        if "core" in locals():
            await core.close()


# main function for the main module
if __name__ == "__main__":
    asyncio.run(main())
