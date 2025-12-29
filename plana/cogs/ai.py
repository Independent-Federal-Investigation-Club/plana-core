from plana.models.base import SnowflakeId
from typing import TYPE_CHECKING, Optional, List, AsyncGenerator, Union

import re
import random
import discord
from discord.ext import commands

from datetime import datetime, timezone

from loguru import logger
from plana.services.manager import GuildManager
from plana.services.agent import ChatRequest, PlanaAgent

from plana.models.ai import AISetting
from plana.utils.helper import datetime_formatter, format_template_message, format_traceback


if TYPE_CHECKING:
    from plana.utils.core import PlanaCore
    from plana.utils.context import PlanaContext


class PlanaAI(commands.Cog):
    """
    Cog for handling AI-related events and interactions.
    """

    def __init__(self, core: "PlanaCore") -> None:
        self.core: "PlanaCore" = core
        self.name = "ai"
        self.description = "Event handlers for handling AI-related events"
        self.agents: dict[int, PlanaAgent] = {}  # Store agents by guild ID

    async def get_agent(self, guild_id: int) -> PlanaAgent:
        """
        Get or create an agent for the specified guild.
        """
        ai_setting = await self.get_ai_setting(guild_id)
        if guild_id not in self.agents:
            self.agents[guild_id] = PlanaAgent(system_prompt=ai_setting.system_prompt)
        return self.agents[guild_id]

    async def save_memory(
        self, guild_id: int, context_id: int, user_message: str, assistant_message: str
    ) -> None:
        """
        Save the response messages to the agent's memory.

        Args:
            guild_id (int): The ID of the guild.
            context_id (int): The ID of the conversation (guild_id, thread_id, channel_id)
            user_message (str): The user's message.
            assistant_message (str): The assistant's response message.
        """
        if not guild_id or not context_id or not user_message or not assistant_message:
            logger.warning(
                "No guild_id, context_id, user_message, or assistant_message provided for saving memory."
            )
            return

        agent = await self.get_agent(guild_id=guild_id)

        # remove addtional discord context from user_message
        user_message = user_message.split("<UserRequestStart>")[-1].strip()

        agent.append_memory(
            context_id=context_id, user_message=user_message, assistant_message=assistant_message
        )

    async def get_ai_setting(self, guild_id: int) -> Optional[AISetting]:
        """
        Get AI settings for a specific guild. and debug the function in which it is called.
        """
        import inspect

        logger.debug(
            f"Getting AI settings for guild {guild_id}, called from {inspect.currentframe().f_back.f_code.co_name}"
        )
        manager = await GuildManager.get(guild_id=guild_id)
        if not manager or not manager.ai:
            return
        return manager.ai

    async def get_last_n_messages(
        self, message: discord.Message, n: int = 16
    ) -> List[discord.Message]:
        messages = [
            m async for m in message.channel.history(limit=n, before=message) if m.content.strip()
        ]

        # add the current message to the list
        messages.insert(0, message)

        # reverse the list to get the most recent message first
        messages.reverse()
        return messages

    async def format_guild_time(self, guild_id: int, time: Optional[datetime] = None) -> str:
        """Get the current date and time for a guild based on its preferences.

        Returns:
            Formatted string of the current date and time in the guild's timezone.
        """
        if time is None:
            time = datetime.now(timezone.utc)
        guild_now = await self.convert_to_guild_tz(time=time, guild_id=guild_id)
        return datetime_formatter(time=guild_now)

    async def convert_to_guild_tz(self, time: datetime, guild_id: int) -> datetime:
        """Convert a datetime object to the guild's timezone.

        Returns:
            Datetime object converted to the guild's timezone
        """
        tz = await GuildManager.get_timezone(guild_id=guild_id)
        return time.astimezone(tz)

    async def parse_last_n_messages(self, messages: List[discord.Message]) -> str:
        final_message = f"- The last {len(messages)} messages for reference:\n"
        for message in messages:
            formated_time = await self.format_guild_time(
                guild_id=message.guild.id, time=message.created_at
            )
            final_message += f"  - [{formated_time}] <@{message.author.id}>: {message.content.replace('\n', '')}\n"

        return final_message

    async def channel_context(self, message: discord.Message) -> str:
        category_name = (
            message.channel.parent.category.name
            if isinstance(message.channel, discord.Thread)
            else message.channel.category.name
        )
        return (
            f"- About This Server -> server_id:{message.guild.id}, server_name:{message.guild.name}, server_desc:{message.guild.description}\n"
            f"- About This Channel -> channel_id:{message.channel.id}, channel_name:{message.channel.name}, channel_desc:{message.channel.topic}, channel_category: {category_name}\n"
        )

    async def message_context(self, message: discord.Message) -> str:
        msg_ref = (
            message.reference
            if message.reference and isinstance(message.reference.resolved, discord.Message)
            else None
        )
        ref_msg = (
            f"- This message replies to this message -> {msg_ref.resolved.content}"
            if msg_ref
            else ""
        )
        return (
            f"- Current Time -> {await self.format_guild_time(guild_id=message.guild.id)}\n"
            f"- About This discord.Message -> message_id:{message.id}, member_id:{message.author.id}, author_name:{message.author.display_name}\n"
            f"{ref_msg}"
        )

    async def get_discord_context(self, message: discord.Message):
        if not message:
            return {"status": "error", "reason": "No additional message context found"}

        channel_context = await self.channel_context(message)
        message_context = await self.message_context(message)

        return (
            "\n<Context>\n"
            f"{channel_context}"
            f"{message_context}"
            f"- Discord Tricks -> mention a user: <@[MEMBER_ID]>, mention a channel: <#[CHANNEL_ID]>, mention a message: https://discord.com/channels/[SERVER_ID]/[CHANNEL_ID]/[MESSAGE_ID]\n"
            "</Context>\n"
        )

    async def message_history(self, message: discord.Message, n: int = 16):
        messages = await self.get_last_n_messages(message=message, n=n)
        context_msg = await self.parse_last_n_messages(messages=messages)

        return f"<History>\n{context_msg}</History>\n"

    async def input_prefill(self, message: discord.Message) -> str:
        """
        Prefill the prompt with the message context.
        """
        message_context = await self.get_discord_context(message)
        message_history = await self.message_history(message)

        return f"{message_context}\n{message_history}\n<UserRequestStart>{message.content}"

    def prompt_prep(self, prompt: str) -> str:
        """standardize the message to be sent to Plana AI service."""

        mention_ids = set(re.findall(r"<@!?(\d+)>", prompt))
        if not mention_ids:
            return prompt

        for mention_id in mention_ids:
            if mention_id == str(self.core.user.id):
                prompt = prompt.replace(f"<@{mention_id}>", f"@{self.core.user.display_name}")
                continue
            user = self.core.get_user(int(mention_id))
            if not user:
                continue
            prompt = prompt.replace(f"<@{mention_id}>", f"@{user.display_name}<id:{mention_id}>")

        return prompt

    async def is_bot_mentioned(self, message: discord.Message) -> bool:
        """Check if the bot is mentioned in the message."""
        return self.core.user in message.mentions

    async def should_respond_to_message(
        self, message: discord.Message, ai_setting: AISetting
    ) -> bool:
        """
        Determine if the bot should respond to a message based on AI settings.

        Args:
            message: Discord message to evaluate
            ai_setting: AI configuration settings

        Returns:
            True if bot should respond, False otherwise
        """
        # Always respond to mentions
        if await self.is_bot_mentioned(message):
            return True

        # Check engage mode
        if not ai_setting.engage_mode:
            return False

        # Check channel filtering
        if not await self.is_channel_allowed(message.channel.id, ai_setting):
            return False

        # Check role filtering
        if not await self.is_user_allowed(message.author, ai_setting):
            return False

        # Random engagement based on engage_rate
        return random.random() < ai_setting.engage_rate

    async def is_channel_allowed(self, channel_id: int, ai_setting: AISetting) -> bool:
        """
        Check if AI interactions are allowed in the specified channel.

        Args:
            channel_id: Channel ID to check
            ai_setting: AI configuration settings

        Returns:
            True if channel is allowed, False otherwise
        """
        if not ai_setting.target_channels:
            return True  # No restrictions

        channel_in_list = channel_id in ai_setting.target_channels

        if ai_setting.target_channels_mode:
            # Whitelist mode - only allowed channels
            return channel_in_list
        else:
            # Blacklist mode - all except blocked channels
            return not channel_in_list

    async def is_user_allowed(self, user: discord.Member, ai_setting: AISetting) -> bool:
        """
        Check if AI interactions are allowed for the specified user based on roles.

        Args:
            user: Discord member to check
            ai_setting: AI configuration settings

        Returns:
            True if user is allowed, False otherwise
        """
        if not ai_setting.target_roles:
            return True  # No restrictions

        user_role_ids = {role.id for role in user.roles}
        target_role_ids = set[SnowflakeId](ai_setting.target_roles)

        has_target_role = bool(user_role_ids & target_role_ids)

        if ai_setting.target_roles_mode:
            # Whitelist mode - only users with allowed roles
            return has_target_role
        else:
            # Blacklist mode - all except users with blocked roles
            return not has_target_role

    async def reply_stream(
        self,
        message: discord.Message,
        reply_generator: "AsyncGenerator" = None,
    ) -> str:
        response = ""
        placeholder = "..."
        ctx = await self.core.get_context(message)
        discord_message = (
            await ctx.send(placeholder) if ctx else await message.channel.send(placeholder)
        )
        try:
            buffer = ""
            async for text in reply_generator:
                # logger.debug("Buffer", buffer, "Text", text)
                if text is None:
                    response = "Something went wrong, please try again later."
                    break

                buffer += text
                if len(buffer) > 8:
                    response += buffer
                    buffer = ""
                    await discord_message.edit(content=response + "...")
            # # add the remaining buffer to the response
            response += buffer
            await discord_message.edit(
                content=response if response else "Plana don't understand that..."
            )

        except Exception as e:
            logger.error(f"Error, unable to reply: {format_traceback(e)}")
        return response

    async def handle_stream_message(self, message: discord.Message, request: ChatRequest) -> str:
        """
        Handle a streaming message by processing it through the AI service.

        Args:
            message: The Discord message to process.
            request: The chat request object containing the message and context ID.
        """
        response = await self.reply_stream(message=message, reply_generator=request.async_stream)
        request.response = response
        return response

    async def handle_normal_message(self, message: discord.Message, request: ChatRequest) -> str:
        """
        Handle a message by processing it through the AI service.

        Args:
            message: The Discord message to process.
            request: The chat request object containing the message and context ID.
        """
        response = ""
        async for text in request.async_stream:
            if text is None:
                response = "Something went wrong, please try again later."
                break
            response += text

        ctx = await self.core.get_context(message)
        await ctx.send(response) if ctx else await message.channel.send(response)

        request.response = response
        return response

    async def get_context_id(self, ctx: Union["PlanaContext", discord.Message]) -> int:
        """
        Determine the context ID based on the memory type.
        Args:
            ctx: The context or message to determine the context ID from.
        Returns:
            The context ID for the conversation.
        """
        config = await self.get_ai_setting(ctx.guild.id)

        if config.memory_type == 1:
            return ctx.guild.id
        elif config.memory_type == 2:
            if isinstance(ctx.channel, discord.TextChannel) and ctx.channel.category:
                return ctx.channel.category.id
            elif isinstance(ctx.channel, discord.Thread):
                return ctx.channel.parent.id
        return ctx.channel.id

    async def process_message(self, message: discord.Message) -> ChatRequest:
        """
        Process a message by preparing the prompt and querying the AI service.
        Args:
            message: The Discord message to process.
        Returns:
            ChatRequest: The request object containing the message and context ID.
        """
        config = await self.get_ai_setting(message.guild.id)

        # Process the message content
        await format_template_message(template=config.input_template, message=message)
        prompt = await self.input_prefill(message=message)
        prompt = self.prompt_prep(prompt=prompt)

        # determine the session ID based on the memory type [1. Per Guild Memory, 2. Per Category Memory, 3. Per Channel/Thread Memory]
        context_id = await self.get_context_id(ctx=message)

        request = ChatRequest(
            message=prompt,
            context_id=context_id,
        )

        agent = await self.get_agent(message.guild.id)
        await agent.query(request=request)

        return request

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Handle incoming messages for AI interactions.
        """
        # Skip if message is from a bot or not in a guild
        if message.author.bot or not message.guild:
            return

        # Skip if message has no content
        if not message.content.strip():
            return

        # Get AI settings for the guild
        ai_setting = await self.get_ai_setting(message.guild.id)
        if not ai_setting or not ai_setting.enabled:
            return

        # Check if bot should respond to this message
        if not await self.should_respond_to_message(message, ai_setting):
            return

        try:
            request = await self.process_message(message)
            async with message.channel.typing():
                if ai_setting.stream:
                    await self.handle_stream_message(message=message, request=request)
                else:
                    await self.handle_normal_message(message=message, request=request)

            await self.save_memory(
                guild_id=message.guild.id,
                context_id=request.context_id,
                user_message=request.message,
                assistant_message=request.response,
            )

        except Exception as e:
            self.core.handle_exception(
                f"Unable to process message for guild {message.guild.id}",
                e,
            )
            await message.add_reaction("❌")

    @commands.hybrid_group(
        name="ai",
        description="Manage AI features and settings",
    )
    @commands.guild_only()
    @commands.has_guild_permissions(administrator=True)
    async def ai_commands(self, ctx: "PlanaContext") -> None:
        """Entry point for AI management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(str(ctx.command))

    @ai_commands.command(
        name="toggle",
        description="Toggle AI features for this server",
    )
    async def toggle_ai(self, ctx: "PlanaContext") -> None:
        """Toggle AI features for the current server."""
        ai_setting = await self.get_ai_setting(ctx.guild.id)

        ai_setting.enabled = not ai_setting.enabled
        await ai_setting.save()

        status = "enabled" if ai_setting.enabled else "disabled"
        await ctx.send(f"AI features have been {status} for this server.", ephemeral=True)

    @ai_commands.command(
        name="clear",
        description="Clear AI memory for this server or channel",
    )
    async def clear_memory(self, ctx: "PlanaContext") -> None:
        """Clear AI conversation memory."""
        agent = await self.get_agent(ctx.guild.id)
        context_id = await self.get_context_id(ctx=ctx)
        agent.reset_memory(context_id=context_id)
        await ctx.send("AI memory has been cleared for this context.", ephemeral=True)


async def setup(core: "PlanaCore"):
    try:
        await core.add_cog(PlanaAI(core))
    except Exception as e:
        core.handle_exception(
            "An error occurred while adding PlanaAI cog",
            e,
        )
