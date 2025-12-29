from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from plana.utils.core import PlanaCore


class PlanaContext(commands.Context):
    """Extended Context for custom Discord bot interactions.

    Args:
        kwargs: Arbitrary keyword arguments passed to the parent Context.
    """

    def __init__(self, **kwargs) -> None:
        self.bot: "PlanaCore"
        super().__init__(**kwargs)


def responsible(target: discord.Member, reason: str) -> str:
    """
    Default responsible maker targeted to find user in AuditLogs
    """
    responsible = f"[ {target} ]"
    if not reason:
        return f"{responsible} no reason given..."
    return f"{responsible} {reason}"


def format_action_message(case: str, mass: bool = False) -> str:
    """
    Default way to present action confirmation in chat
    """
    output = f"**{case}** the user"

    if mass:
        output = f"**{case}** the IDs/Users"

    return f"✅ Successfully {output}"
