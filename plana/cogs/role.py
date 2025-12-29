from typing import TYPE_CHECKING, Union, Optional, List

import discord
from discord.ext import commands

from loguru import logger
from plana.services.manager import GuildManager

if TYPE_CHECKING:
    from plana.utils.core import PlanaCore
    from plana.models.react_role import ReactRoleSetting, RoleAssignment


class PlanaRole(commands.Cog):
    """
    Cog containing event handlers for the Plana bot.
    """

    def __init__(self, core: "PlanaCore") -> None:
        self.core: "PlanaCore" = core
        self.name = "react_role"
        self.description = "Event handlers for handling reaction roles events"

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """
        Event handler for when a reaction is added to a message.
        """
        logger.debug(f"Reaction added by {payload}")

        try:
            await self.handle_react_role_for_emoji(payload)
        except Exception as e:
            self.core.handle_exception(
                "An error occurred while handling reaction add",
                e,
            )

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        """
        Event handler for when a reaction is removed from a message.
        """

        logger.debug(f"Reaction removed by {payload}")

        try:
            await self.handle_react_role_for_emoji(payload)
        except Exception as e:
            self.core.handle_exception(
                "An error occurred while handling reaction remove",
                e,
            )

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        # Ensure the interaction is of type component [e.g., button or select menu]
        if not interaction.type == discord.InteractionType.component:
            return

        # Check if interaction.data exists and has the expected attributes
        if not hasattr(interaction, "data") or not interaction.data:
            return

        if not hasattr(interaction.data, "component_type") and hasattr(
            interaction.data, "custom_id"
        ):
            return

        if interaction.data.get("component_type") == 2:  # Button
            custom_id = f"{interaction.data.get('custom_id')}"
            logger.debug(f"Button interaction received: {custom_id}")

        elif interaction.data.get("component_type") == 3 and interaction.data.get(
            "values"
        ):  # Select menu
            value = interaction.data.get("values")[0]
            custom_id = f"{interaction.data.get('custom_id')}-{value}"
            logger.debug(f"Select menu interaction received: {custom_id}")

        logger.debug(f"Interaction received: {interaction}")

        try:
            assignment = await self.fetch_react_role_assignment(
                interaction.guild_id,
                interaction.message.id,
                custom_id,
            )

            if not assignment:
                return

            await self.handle_role_assignment(interaction.user, assignment, interaction=interaction)
        except Exception as e:
            self.core.handle_exception(
                "An error occurred while handling interaction",
                e,
            )

    async def fetch_react_role_assignment(
        self,
        guild_id: int,
        message_id: int,
        custom_id: str,
    ) -> Union["RoleAssignment", None]:
        """
        Handle the reaction role logic when a reaction is added or removed.
        """
        manager = await GuildManager.get(guild_id)

        if not manager:
            logger.debug(f"No guild manager found for guild {guild_id}")
            return

        react_role_setting: "ReactRoleSetting" = next(
            (setting for setting in manager.react_roles if setting.message_id == message_id),
            None,
        )

        if not react_role_setting:
            logger.debug(
                f"No react role setting found for message {message_id} in guild {guild_id}"
            )
            return

        if not react_role_setting.enabled:
            logger.debug(
                f"React role setting is disabled for message {message_id} in guild {guild_id}"
            )
            return

        trigger_assignment = next(
            (
                assignment
                for assignment in react_role_setting.role_assignments
                if assignment.trigger_id == custom_id
            ),
            None,
        )
        if not trigger_assignment:
            logger.debug(
                f"No trigger assignment found for custom_id {custom_id} in guild {guild_id}"
            )
            return

        return trigger_assignment

    async def handle_role_assignment(
        self,
        user: discord.Member,
        assignment: "RoleAssignment",
        interaction: Optional[discord.Interaction] = None,
    ) -> None:
        """
        Assign or remove roles based on the reaction role assignment.
        """

        logger.debug(
            f"Handling role assignment for user {user.id} in guild {user.guild.id} with assignment {assignment}"
        )

        modified_roles: List[discord.Role] = []

        for role_id in assignment.role_ids:
            role = user.guild.get_role(role_id)
            if not role:
                logger.debug(f"Role {role_id} not found in guild {user.guild.id}")
                return

            modified_roles.append(role)

            # If the user already has the role, remove it
            if user.get_role(role_id):
                logger.debug(
                    f"Removing role {role.name} from user {user.name} in guild {user.guild.name}"
                )
                await user.remove_roles(role)
                continue

            await user.add_roles(role)
            logger.debug(f"Added role {role.name} to user {user.name} in guild {user.guild.name}")

        messages = (
            f"✅ {", ".join([role.name for role in modified_roles if role.name])} has been updated."
        )

        if interaction:
            await interaction.response.send_message(
                messages,
                ephemeral=True,
            )
        else:
            dm_channel = await user.create_dm()
            await dm_channel.send(
                messages,
            )

    async def handle_react_role_for_emoji(
        self,
        payload: discord.RawReactionActionEvent,
    ) -> None:
        """
        Handle the reaction role logic for a specific emoji.
        """
        guild = self.core.get_guild(payload.guild_id)

        user = guild.get_member(payload.user_id) if guild else None

        if user.bot:
            return

        custom_id = f"{payload.emoji.id if payload.emoji.is_custom_emoji() else payload.emoji.name}"
        logger.debug(
            f"Reaction added by {user.id} in {payload.guild_id} on message {payload.message_id}, custom_id: {custom_id}"
        )
        assignment = await self.fetch_react_role_assignment(
            payload.guild_id, payload.message_id, custom_id
        )

        if not assignment:
            return

        await self.handle_role_assignment(user, assignment)


async def setup(core: "PlanaCore"):
    try:
        await core.add_cog(PlanaRole(core))
    except Exception as e:
        core.handle_exception(
            "An error occurred while adding PlanaEvents cog",
            e,
        )
