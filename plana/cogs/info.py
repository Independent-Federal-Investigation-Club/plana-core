import os
import platform
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import discord
import psutil

from discord.ext import commands

from plana.ui.embeds import embed_template
from plana.utils.context import PlanaContext
from plana.utils.core import PlanaCore
from plana.utils.helper import format_date_value
from plana.utils.translate import Tr, PlanaLocaleStr

from plana.services.manager import GuildManager


class InfoView(discord.ui.View):
    """Interactive view for info commands with buttons for different information categories."""

    def __init__(self, cog: "PlanaInfo", ctx: PlanaContext):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx

    @discord.ui.button(label="Bot Info", style=discord.ButtonStyle.primary, emoji="🤖")
    async def bot_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.cog.create_bot_info_embed(self.ctx)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="System Stats", style=discord.ButtonStyle.secondary, emoji="💻")
    async def system_stats_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = await self.cog.create_system_stats_embed(self.ctx)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Guild Analytics", style=discord.ButtonStyle.success, emoji="📊")
    async def guild_analytics_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = await self.cog.create_guild_analytics_embed(self.ctx)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Performance", style=discord.ButtonStyle.danger, emoji="⚡")
    async def performance_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.cog.create_performance_embed(self.ctx)
        await interaction.response.edit_message(embed=embed, view=self)


class PlanaInfo(commands.Cog):
    """
    information and utility commands cog with premium features.
    Provides comprehensive bot analytics, system monitoring, and interactive displays.
    """

    def __init__(self, core: PlanaCore) -> None:
        self.core: PlanaCore = core
        self.name = "info"
        self.description = "Advanced information and utility commands for monitoring and analytics"

        self.process: psutil.Process = psutil.Process(os.getpid())
        self._stats_cache: Dict = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=2)  # Cache for 2 minutes

    def _get_cached_stats(self) -> Optional[Dict]:
        """Get cached system stats if still valid."""
        if (
            self._cache_timestamp
            and datetime.now(timezone.utc) - self._cache_timestamp < self._cache_duration
        ):
            return self._stats_cache
        return

    def _update_stats_cache(self) -> Dict:
        """Update and return fresh system stats."""
        stats = {
            "cpu_percent": self.process.cpu_percent(interval=0.1),
            "memory_info": self.process.memory_full_info(),
            "memory_percent": self.process.memory_percent(),
            "network_io": psutil.net_io_counters() if hasattr(psutil, "net_io_counters") else None,
            "disk_io": psutil.disk_io_counters() if hasattr(psutil, "disk_io_counters") else None,
            "threads": self.process.num_threads(),
            "connections": (
                len(self.process.connections()) if hasattr(self.process, "connections") else 0
            ),
        }

        self._stats_cache = stats
        self._cache_timestamp = datetime.now(timezone.utc)
        return stats

    @commands.guild_only()
    @commands.hybrid_group(
        name=PlanaLocaleStr("info.name"),
        description=PlanaLocaleStr("info.description"),
    )
    async def info(self, ctx: PlanaContext) -> None:
        if ctx.invoked_subcommand is None:
            # Create interactive info panel
            embed = await self.create_bot_info_embed(ctx)
            view = InfoView(self, ctx)
            await ctx.send(embed=embed, view=view)

    def calculate_average_members(self) -> float:
        """
        Calculates the average member count across all guilds where the bot is present.

        Returns:
            float: The average number of members per guild.
        """
        all_guilds = self.core.guilds
        if not all_guilds:
            return 0.0
        total_members = sum(guild.member_count or 0 for guild in all_guilds)
        return total_members / len(all_guilds)

    async def create_bot_info_embed(self, ctx: PlanaContext) -> discord.Embed:
        """
        Creates an embed containing comprehensive bot information.

        Args:
            ctx (PlanaContext): The context of the command invocation.

        Returns:
            discord.Embed: An embed with various informational fields about the bot.
        """
        commands = [cmd.name for cmd in self.core.commands]
        locale = await GuildManager.get_locale(ctx)

        embed = await embed_template(ctx.guild.id)
        embed.title = Tr.t("info.about.embed.title", locale=locale)

        embed.set_thumbnail(url=ctx.bot.user.avatar)

        # Basic bot information
        embed.add_field(
            name=Tr.t("info.about.embed.last_started", locale=locale),
            value=format_date_value(self.core.uptime, ago=True),
            inline=True,
        )

        embed.add_field(
            name=Tr.t("info.about.embed.version", locale=locale),
            value=f"Python {platform.python_version()}\ndiscord.py {discord.__version__}",
            inline=True,
        )

        embed.add_field(
            name=Tr.t("info.about.embed.platform", locale=locale),
            value=f"{platform.system()} {platform.release()}",
            inline=True,
        )

        embed.add_field(
            name=Tr.t("info.about.embed.creator", locale=locale),
            value="[S.C.H.A.L.E](https://github.com/Independent-Federal-Investigation-Club)",
            inline=False,
        )

        # Statistics
        total_users = sum(g.member_count or 0 for g in self.core.guilds)
        embed.add_field(
            name=Tr.t("info.about.embed.server_count", locale=locale),
            value=Tr.t(
                "info.about.embed.server_stats",
                locale=locale,
                guild_count=len(ctx.bot.guilds),
                user_count=total_users,
                average=self.calculate_average_members(),
            ),
            inline=True,
        )

        embed.add_field(
            name=Tr.t("info.about.embed.shard_info", locale=locale),
            value=Tr.t(
                "info.about.embed.shard_stats",
                locale=locale,
                shard_id=ctx.guild.shard_id if ctx.guild else 0,
                shard_count=self.core.shard_count or 1,
                latency=round(self.core.latency * 1000),
            ),
            inline=True,
        )

        embed.add_field(
            name=f"{Tr.t('info.about.embed.loaded_commands', locale=locale)} ({len(commands)})",
            value=", ".join(commands),
            inline=False,
        )

        # Memory usage
        memory_info = self.process.memory_full_info()
        embed.add_field(
            name=Tr.t("info.about.embed.memory_usage", locale=locale),
            value=f"{memory_info.rss / (1024**2):.2f} MB ({self.process.memory_percent():.1f}%)",
            inline=True,
        )

        return embed

    async def create_system_stats_embed(self, ctx: PlanaContext) -> discord.Embed:
        """Create detailed system statistics embed."""
        locale = await GuildManager.get_locale(ctx)
        stats = self._get_cached_stats() or self._update_stats_cache()

        embed = await embed_template(ctx.guild.id)
        embed.title = Tr.t("info.system.embed.title", locale=locale)

        # CPU Information
        embed.add_field(
            name=Tr.t("info.system.embed.cpu_usage", locale=locale),
            value=f"{stats['cpu_percent']:.1f}%",
            inline=True,
        )

        embed.add_field(
            name=Tr.t("info.system.embed.cpu_count", locale=locale),
            value=f"{psutil.cpu_count(logical=False)} physical / {psutil.cpu_count()} logical",
            inline=True,
        )

        # Memory Information
        memory_info = stats["memory_info"]
        embed.add_field(
            name=Tr.t("info.system.embed.memory_detailed", locale=locale),
            value=Tr.t(
                "info.system.embed.memory_stats",
                locale=locale,
                rss=memory_info.rss / (1024**2),
                vms=memory_info.vms / (1024**2),
                percent=stats["memory_percent"],
            ),
            inline=True,
        )

        # Process Information
        embed.add_field(
            name=Tr.t("info.system.embed.process_info", locale=locale),
            value=Tr.t(
                "info.system.embed.process_stats",
                locale=locale,
                pid=self.process.pid,
                threads=stats["threads"],
                connections=stats["connections"],
            ),
            inline=True,
        )

        # Network I/O if available
        if stats["network_io"]:
            net_io = stats["network_io"]
            embed.add_field(
                name=Tr.t("info.system.embed.network_io", locale=locale),
                value=Tr.t(
                    "info.system.embed.network_stats",
                    locale=locale,
                    sent=net_io.bytes_sent / (1024**2),
                    recv=net_io.bytes_recv / (1024**2),
                ),
                inline=True,
            )

        return embed

    async def create_guild_analytics_embed(self, ctx: PlanaContext) -> discord.Embed:
        """Create guild analytics embed with member distribution and activity."""
        locale = await GuildManager.get_locale(ctx)
        guild = ctx.guild

        embed = await embed_template(ctx.guild.id)
        embed.title = Tr.t("info.analytics.embed.title", locale=locale, guild_name=guild.name)

        # Member statistics
        members = guild.members
        bots = [m for m in members if m.bot]
        humans = [m for m in members if not m.bot]

        # Status distribution
        online = len([m for m in humans if m.status == discord.Status.online])
        idle = len([m for m in humans if m.status == discord.Status.idle])
        dnd = len([m for m in humans if m.status == discord.Status.dnd])
        offline = len(humans) - online - idle - dnd

        embed.add_field(
            name=Tr.t("info.analytics.embed.member_breakdown", locale=locale),
            value=Tr.t(
                "info.analytics.embed.member_stats",
                locale=locale,
                total=len(members),
                humans=len(humans),
                bots=len(bots),
            ),
            inline=True,
        )

        embed.add_field(
            name=Tr.t("info.analytics.embed.status_distribution", locale=locale),
            value=Tr.t(
                "info.analytics.embed.status_stats",
                locale=locale,
                online=online,
                idle=idle,
                dnd=dnd,
                offline=offline,
            ),
            inline=True,
        )

        # Channel information
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)

        embed.add_field(
            name=Tr.t("info.analytics.embed.channel_breakdown", locale=locale),
            value=Tr.t(
                "info.analytics.embed.channel_stats",
                locale=locale,
                text=text_channels,
                voice=voice_channels,
                categories=categories,
            ),
            inline=True,
        )

        # Role information
        embed.add_field(
            name=Tr.t("info.analytics.embed.roles", locale=locale),
            value=f"{len(guild.roles)} roles",
            inline=True,
        )

        # Boost information
        embed.add_field(
            name=Tr.t("info.analytics.embed.boost_info", locale=locale),
            value=Tr.t(
                "info.analytics.embed.boost_stats",
                locale=locale,
                level=guild.premium_tier,
                boosts=guild.premium_subscription_count,
            ),
            inline=True,
        )

        # Guild features
        if guild.features:
            features_text = ", ".join([f.replace("_", " ").title() for f in guild.features[:5]])
            if len(guild.features) > 5:
                features_text += f" +{len(guild.features) - 5} more"

            embed.add_field(
                name=Tr.t("info.analytics.embed.features", locale=locale),
                value=features_text,
                inline=False,
            )

        return embed

    async def create_performance_embed(self, ctx: PlanaContext) -> discord.Embed:
        """Create performance monitoring embed."""
        locale = await GuildManager.get_locale(ctx)

        embed = await embed_template(ctx.guild.id)
        embed.title = Tr.t("info.performance.embed.title", locale=locale)

        # Latency information
        embed.add_field(
            name=Tr.t("info.performance.embed.latency", locale=locale),
            value=f"{round(self.core.latency * 1000)}ms",
            inline=True,
        )

        # Uptime
        uptime_delta = datetime.now(timezone.utc) - self.core.uptime
        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        embed.add_field(
            name=Tr.t("info.performance.embed.uptime", locale=locale),
            value=Tr.t(
                "info.performance.embed.uptime_format",
                locale=locale,
                days=days,
                hours=hours,
                minutes=minutes,
            ),
            inline=True,
        )

        return embed

    @info.command(
        name=PlanaLocaleStr("info.about.name"),
        description=PlanaLocaleStr("info.about.description"),
    )
    @commands.guild_only()
    async def display_bot_info(self, ctx: PlanaContext) -> None:
        """
        Displays comprehensive information about the bot.
        """
        try:
            embed = await self.create_bot_info_embed(ctx)
            await ctx.send(embed=embed)
        except Exception as e:
            self.core.handle_exception("An error occurred while creating the bot info embed", e)

    @info.command(
        name=PlanaLocaleStr("info.system.name"),
        description=PlanaLocaleStr("info.system.description"),
    )
    @commands.guild_only()
    async def display_system_info(self, ctx: PlanaContext) -> None:
        """
        Displays detailed system information and performance metrics with live monitoring.
        """
        try:
            embed = await self.create_system_stats_embed(ctx)
            await ctx.send(embed=embed, ephemeral=True)
        except Exception as e:
            self.core.handle_exception("An error occurred while creating the system info embed", e)

    @info.command(
        name=PlanaLocaleStr("info.analytics.name"),
        description=PlanaLocaleStr("info.analytics.description"),
    )
    @commands.guild_only()
    async def display_analytics(self, ctx: PlanaContext) -> None:
        """
        Displays interactive guild analytics and member statistics.
        """
        try:
            embed = await self.create_guild_analytics_embed(ctx)
            await ctx.send(embed=embed)
        except Exception as e:
            self.core.handle_exception("An error occurred while creating the analytics embed", e)

    @info.command(
        name=PlanaLocaleStr("info.bot-stats.name"),
        description=PlanaLocaleStr("info.bot-stats.description"),
    )
    @commands.guild_only()
    async def display_bot_stats(self, ctx: PlanaContext) -> None:
        """
        Displays CPU and memory usage statistics for the running bot process.
        """
        stats = self._get_cached_stats() or self._update_stats_cache()
        locale = await GuildManager.get_locale(ctx)

        embed = await embed_template(ctx.guild.id)
        embed.title = Tr.t("info.bot-stats.embed.title", locale=locale)

        embed.add_field(
            name=Tr.t("info.bot-stats.embed.cpu_usage", locale=locale),
            value=f"{stats['cpu_percent']:.2f}%",
            inline=True,
        )

        memory_info = stats["memory_info"]
        embed.add_field(
            name=Tr.t("info.bot-stats.embed.memory_usage", locale=locale),
            value=f"{memory_info.rss / (1024**2):.2f} MB ({stats['memory_percent']:.2f}%)",
            inline=True,
        )

        embed.add_field(
            name=Tr.t("info.bot-stats.embed.threads", locale=locale),
            value=f"{stats['threads']}",
            inline=True,
        )

        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(
        name=PlanaLocaleStr("ping.name"),
        description=PlanaLocaleStr("ping.description"),
    )
    @commands.guild_only()
    async def check_bot_latency(self, ctx: PlanaContext) -> None:
        """
        Checks and displays the bot's latency with detailed timing information.
        """
        locale = await GuildManager.get_locale(ctx)

        # Measure API latency
        start_time = datetime.now(timezone.utc)

        if ctx.interaction is not None:
            await ctx.interaction.response.defer(ephemeral=True)
            api_latency = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            embed = await embed_template(ctx.guild.id)
            embed.title = Tr.t("ping.embed.title", locale=locale)

            embed.add_field(
                name=Tr.t("ping.embed.websocket", locale=locale),
                value=f"{round(self.core.latency * 1000)}ms",
                inline=True,
            )

            embed.add_field(
                name=Tr.t("ping.embed.api_response", locale=locale),
                value=f"{api_latency:.0f}ms",
                inline=True,
            )

            # Determine connection quality
            ws_latency = self.core.latency * 1000
            if ws_latency < 100:
                quality = Tr.t("ping.quality.excellent", locale=locale)
                color = discord.Color.green()
            elif ws_latency < 200:
                quality = Tr.t("ping.quality.good", locale=locale)
                color = discord.Color.yellow()
            else:
                quality = Tr.t("ping.quality.poor", locale=locale)
                color = discord.Color.red()

            embed.color = color
            embed.add_field(
                name=Tr.t("ping.embed.quality", locale=locale),
                value=quality,
                inline=False,
            )

            await ctx.send(embed=embed, ephemeral=True)
        else:
            message = Tr.t(
                "ping.simple_response", locale=locale, latency=round(self.core.latency * 1000)
            )
            await ctx.send(message)

    @commands.hybrid_command(
        name=PlanaLocaleStr("invite.name"),
        description=PlanaLocaleStr("invite.description"),
    )
    @commands.guild_only()
    async def provide_invite_link(self, ctx: PlanaContext) -> None:
        """
        Provides an invite link with proper permissions.

        Args:
            ctx (PlanaContext): The context of the command invocation.
        """
        locale = await GuildManager.get_locale(ctx)

        # Calculate required permissions
        permissions = discord.Permissions(
            manage_messages=True,
            manage_roles=True,
            kick_members=True,
            ban_members=True,
            moderate_members=True,
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            use_external_emojis=True,
            connect=True,
            speak=True,
        )

        invite_link = discord.utils.oauth_url(self.core.user.id, permissions=permissions)

        embed = await embed_template(ctx.guild.id)
        embed.title = Tr.t("invite.embed.title", locale=locale)
        embed.description = Tr.t("invite.embed.description", locale=locale, user=ctx.author.mention)

        embed.add_field(
            name=Tr.t("invite.embed.link", locale=locale),
            value=f"[{Tr.t('invite.embed.click_here', locale=locale)}]({invite_link})",
            inline=False,
        )

        embed.add_field(
            name=Tr.t("invite.embed.permissions", locale=locale),
            value=Tr.t("invite.embed.permissions_note", locale=locale),
            inline=False,
        )

        # Add view with buttons
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label=Tr.t("invite.button.add_bot", locale=locale),
                url=invite_link,
                style=discord.ButtonStyle.link,
                emoji="🤖",
            )
        )

        # Support server link (if you have one)
        support_invite = "https://discord.gg/your-support-server"  # Replace with actual invite
        view.add_item(
            discord.ui.Button(
                label=Tr.t("invite.button.support", locale=locale),
                url=support_invite,
                style=discord.ButtonStyle.link,
                emoji="❓",
            )
        )

        await ctx.send(embed=embed, view=view)


async def setup(core: PlanaCore) -> None:
    """
    The setup function used by discord.py to load cogs.

    Args:
        core (PlanaCore): The core instance of the Plana bot.
    """
    try:
        await core.add_cog(PlanaInfo(core))
    except Exception as exc:
        core.handle_exception("An error occurred while adding PlanaInfoCog", exc)
