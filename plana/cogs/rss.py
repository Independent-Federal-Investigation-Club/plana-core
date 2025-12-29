import random
from typing import TYPE_CHECKING, Optional, List
from datetime import datetime, timezone
import asyncio
import aiohttp
import feedparser

import discord
from discord.ext import commands, tasks

from loguru import logger
from plana.services.manager import GuildManager
from plana.ui.embeds import embed_template
from plana.utils.translate import PlanaLocaleStr
from plana.utils.context import PlanaContext
from plana.models.rss import RssFeed, RssFeed

if TYPE_CHECKING:
    from plana.utils.core import PlanaCore


class PlanaRSS(commands.Cog):
    """
    Cog containing event handlers for the Plana bot.
    """

    def __init__(self, core: "PlanaCore") -> None:
        self.core: "PlanaCore" = core
        self.name = "rss"
        self.description = "Cog for managing RSS feeds and updates"
        self.rss_checker.start()

    def cog_unload(self) -> None:
        """Clean up when the cog is unloaded."""
        self.rss_checker.cancel()

    @tasks.loop(minutes=30)
    async def rss_checker(self) -> None:
        """Check all RSS feeds for updates every 30 minutes."""
        # random delay for avoiding burst traffic
        await asyncio.sleep(random.uniform(20, 120.0))

        try:
            guilds = self.core.guilds
            for guild in guilds:
                await self._check_guild_feeds(guild.id)
        except Exception as e:
            logger.error(f"Error in RSS checker: {e}")

    @rss_checker.before_loop
    async def before_rss_checker(self) -> None:
        """Wait until the bot is ready before starting the RSS checker."""
        await self.core.wait_until_ready()

    async def _check_guild_feeds(self, guild_id: int) -> None:
        """Check all RSS feeds for a specific guild."""
        rss_feeds = await self.get_rss_feeds(guild_id)
        if not rss_feeds:
            return

        has_updates = False

        for feed in rss_feeds:
            if feed.enabled:
                has_updates |= await self._process_feed(guild_id, feed)

    async def _process_feed(self, guild_id: int, feed: "RssFeed") -> bool:
        """Process a single RSS feed and post new entries."""
        try:
            # random delay for avoiding burst traffic
            await asyncio.sleep(random.uniform(0.5, 120.0))

            # Fetch RSS feed
            parsed_feed = await self._fetch_rss_feed(feed.url)

            if not parsed_feed or not parsed_feed.entries:
                return False

            # Get the channel to post updates
            channel = self.core.get_channel(feed.channel_id)
            if not channel:
                logger.warning(f"Channel {feed.channel_id} not found for RSS feed {feed.name}")
                return False

            # Find new entries
            new_entries = await self._get_new_entries(feed, parsed_feed.entries)

            # Post new entries
            for entry in new_entries:
                embed = await self._create_rss_embed(guild_id, feed, entry)
                message_content = (
                    self._format_template_message(feed.message, entry, feed)
                    if feed.message
                    else None
                )

                try:
                    await channel.send(content=message_content, embed=embed)
                    logger.info(f"Posted RSS update for {feed.name} in guild {guild_id}")
                except Exception as e:
                    logger.error(f"Failed to send RSS update: {e}")

            # Update last_updated timestamp if we had new entries
            if new_entries:
                feed.last_updated = datetime.now(timezone.utc)
                await feed.save()
                return True

            return False

        except Exception as e:
            logger.error(f"Error processing RSS feed {feed.name}: {e}")
            self.core.handle_exception(
                f"Error processing RSS feed {feed.name} in guild {guild_id}",
                e,
            )
            return False

    async def _fetch_rss_feed(self, url: str) -> Optional[feedparser.FeedParserDict]:
        """Fetch and parse an RSS feed."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        content = await response.text()
                        return feedparser.parse(content)
                    else:
                        logger.warning(f"Failed to fetch RSS feed {url}: HTTP {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error fetching RSS feed {url}: {e}")
            return None

    async def _get_new_entries(self, feed: "RssFeed", entries: List) -> List:
        """Get new entries since the last update."""
        if not feed.last_updated:
            # If no last_updated, return only the latest entry to avoid spam
            return entries[:1] if entries else []

        new_entries = []
        for entry in entries:
            entry_date = self._get_entry_date(entry)
            if entry_date and entry_date > feed.last_updated:
                new_entries.append(entry)

        # Sort by date, oldest first
        new_entries.sort(
            key=lambda x: self._get_entry_date(x) or datetime.min.replace(tzinfo=timezone.utc)
        )
        return new_entries

    def _get_entry_date(self, entry) -> Optional[datetime]:
        """Extract publication date from RSS entry with multiple fallbacks."""
        # Try different date fields in order of preference
        date_fields = ["published_parsed", "updated_parsed", "created_parsed"]

        for field in date_fields:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    time_struct = getattr(entry, field)
                    return datetime(*time_struct[:6], tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue

        # Try string date fields as fallback
        string_date_fields = ["published", "updated", "created"]
        for field in string_date_fields:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    from email.utils import parsedate_to_datetime

                    dt = parsedate_to_datetime(getattr(entry, field))
                    return dt.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue

        return None

    def _clean_html_text(self, text: str) -> str:
        """Clean HTML tags and entities from text."""
        import re
        from html import unescape

        if not text:
            return ""
        return unescape(re.sub(r"<[^>]+>", "", text)).strip()

    def _format_template_message(self, template: str, entry, feed: "RssFeed") -> str:
        """Process template variables in message content."""
        if not template:
            return ""

        # Build template variables
        pub_date = self._get_entry_date(entry)
        categories = self._get_entry_categories(entry)

        variables = {
            "title": self._clean_html_text(getattr(entry, "title", "")),
            "link": getattr(entry, "link", ""),
            "description": self._clean_html_text(
                getattr(entry, "summary", getattr(entry, "description", ""))
            ),
            "author": getattr(entry, "author", ""),
            "feedName": feed.name,
            "feedUrl": feed.url,
            "categories": ", ".join(categories[:3]) if categories else "",
            "pubDate": pub_date.strftime("%Y-%m-%d %H:%M UTC") if pub_date else "",
            "pubDateShort": pub_date.strftime("%Y-%m-%d") if pub_date else "",
            "pubDateTime": pub_date.strftime("%H:%M UTC") if pub_date else "",
            "pubDateISO": pub_date.isoformat() if pub_date else "",
        }

        try:
            return template.format(**variables)
        except (KeyError, ValueError) as e:
            logger.warning(f"Template formatting error: {e}")
            return template

    async def _create_rss_embed(self, guild_id: int, feed: "RssFeed", entry) -> discord.Embed:
        """Create a Discord embed from an RSS entry with comprehensive RSS 2.0 support."""
        embed = await embed_template(guild_id)

        # Basic content
        title = self._clean_html_text(getattr(entry, "title", "New RSS Feed"))[:256]
        embed.title = title

        description = self._clean_html_text(
            getattr(entry, "summary", getattr(entry, "description", ""))
        )
        if description:
            if len(description) > 2048:
                description = description[:2045] + "..."
            embed.description = description

        # URL and timestamp
        if hasattr(entry, "link") and entry.link:
            embed.url = entry.link

        pub_date = self._get_entry_date(entry)
        if pub_date:
            embed.timestamp = pub_date

        # Author info
        author_name = self._get_author_name(entry)
        if author_name:
            embed.set_author(name=author_name[:256])

        # Media content
        self._add_embed_media(embed, entry)

        # Additional fields
        self._add_embed_fields(embed, entry)

        # Footer
        embed.set_footer(text=f"📡 {feed.name}")

        return embed

    def _get_author_name(self, entry) -> Optional[str]:
        """Extract author name from RSS entry."""
        if hasattr(entry, "author_detail") and entry.author_detail:
            return entry.author_detail.get("name")

        if hasattr(entry, "author") and entry.author:
            import re

            # Try to extract name from "Name <email>" or "email (Name)" formats
            name_match = re.search(r"([^<(]+?)(?:\s*<|$)", entry.author)
            if name_match and "@" not in name_match.group(1):
                return name_match.group(1).strip()

            paren_match = re.search(r"\(([^)]+)\)", entry.author)
            if paren_match:
                return paren_match.group(1).strip()

            return entry.author.strip()

        return None

    def _add_embed_media(self, embed: discord.Embed, entry) -> None:
        """Add media elements (images, thumbnails) to the embed."""
        # Check for enclosures (RSS 2.0 media)
        if hasattr(entry, "enclosures") and entry.enclosures:
            for enclosure in entry.enclosures:
                if enclosure.get("type", "").startswith("image/") and enclosure.get("href"):
                    embed.set_image(url=enclosure["href"])
                    return

        # Check for media thumbnail
        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            thumbnail_url = (
                entry.media_thumbnail[0].get("url")
                if isinstance(entry.media_thumbnail, list)
                else entry.media_thumbnail.get("url")
            )
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

        # Check for media content
        if hasattr(entry, "media_content") and entry.media_content:
            for media in entry.media_content:
                if media.get("type", "").startswith("image/") and media.get("url"):
                    embed.set_image(url=media["url"])
                    return

    def _add_embed_fields(self, embed: discord.Embed, entry) -> None:
        """Add RSS fields to the embed."""
        fields_added = 0
        max_fields = 3

        # Categories
        categories = self._get_entry_categories(entry)
        if categories and fields_added < max_fields:
            categories_text = ", ".join(categories[:5])
            if len(categories_text) <= 1024:
                embed.add_field(name="🏷️ Categories", value=categories_text, inline=True)
                fields_added += 1

        # Comments
        if hasattr(entry, "comments") and entry.comments and fields_added < max_fields:
            embed.add_field(
                name="💬 Comments", value=f"[Discussion]({entry.comments})", inline=True
            )
            fields_added += 1

        # Non-image attachments
        if hasattr(entry, "enclosures") and entry.enclosures and fields_added < max_fields:
            for enclosure in entry.enclosures:
                if not enclosure.get("type", "").startswith("image/") and enclosure.get("href"):
                    media_type = enclosure.get("type", "file").split("/")[-1].upper()
                    length = enclosure.get("length")
                    size_str = (
                        f" ({self._format_file_size(int(length))})"
                        if length and length.isdigit()
                        else ""
                    )
                    embed.add_field(
                        name="📎 Attachment",
                        value=f"[{media_type}]({enclosure['href']}){size_str}",
                        inline=True,
                    )
                    fields_added += 1
                    break

    def _get_entry_categories(self, entry) -> list[str]:
        """Extract categories from RSS entry."""
        categories = []

        # RSS 2.0 tags/categories
        if hasattr(entry, "tags") and entry.tags:
            categories.extend([tag.get("term", "") for tag in entry.tags if tag.get("term")])

        # Alternative category fields
        if hasattr(entry, "category") and entry.category:
            if isinstance(entry.category, str):
                categories.append(entry.category)
            elif isinstance(entry.category, list):
                categories.extend([cat for cat in entry.category if isinstance(cat, str)])

        # Clean and deduplicate categories
        return list(dict.fromkeys([cat.strip() for cat in categories if cat and cat.strip()]))

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}TB"

    async def get_rss_feeds(self, guild_id: int) -> List[RssFeed]:
        """
        Fetch the RSS setting for a specific guild.
        """
        manager = await GuildManager.get(guild_id)
        if not manager or not manager.rss_feeds:
            return None
        return manager.rss_feeds

    @commands.guild_only()
    @commands.hybrid_group(
        name=PlanaLocaleStr("rss.name"),
        description=PlanaLocaleStr("rss.description"),
    )
    async def rss(self, ctx: PlanaContext) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send_help(str(ctx.command))

    @rss.command(
        name=PlanaLocaleStr("rss.fetch.name"),
        description=PlanaLocaleStr("rss.fetch.description"),
    )
    @commands.guild_only()
    async def rss_fetch(self, ctx: PlanaContext) -> None:
        """
        Fetch the latest RSS feed entries for the guild.
        """
        await ctx.send("RSS feeds have been checked for updates.", ephemeral=True)
        await self._check_guild_feeds(ctx.guild.id)

    @rss.command(
        name=PlanaLocaleStr("rss.latest.name"),
        description=PlanaLocaleStr("rss.latest.description"),
    )
    @commands.guild_only()
    async def rss_latest(self, ctx: PlanaContext, feed_name: str) -> None:
        """
        Get the latest entry from a specific RSS feed.
        """
        rss_feeds = await self.get_rss_feeds(ctx.guild.id)
        if not rss_feeds:
            await ctx.send("No RSS feeds configured for this guild.", ephemeral=True)
            return

        # Find the selected feed
        selected_feed = next((feed for feed in rss_feeds if feed.name == feed_name), None)
        if not selected_feed:
            await ctx.send("Feed not found. Please select a valid feed.", ephemeral=True)
            return

        # Fetch the RSS feed
        parsed_feed = await self._fetch_rss_feed(selected_feed.url)
        if not parsed_feed or not parsed_feed.entries:
            await ctx.send("Unable to fetch feed or no entries found.", ephemeral=True)
            return

        # Get the latest entry
        latest_entry = parsed_feed.entries[0]
        embed = await self._create_rss_embed(ctx.guild.id, selected_feed, latest_entry)

        await ctx.send(embed=embed)

    @rss_latest.autocomplete("feed_name")
    async def rss_latest_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[discord.app_commands.Choice[str]]:
        """
        Autocomplete for RSS feed names.
        """
        rss_feeds = await self.get_rss_feeds(interaction.guild_id)
        if not rss_feeds:
            return []

        # Filter feeds based on current input
        matching_feeds = [feed for feed in rss_feeds if current.lower() in feed.name.lower()]

        # Return up to 25 choices (Discord limit)
        return [
            discord.app_commands.Choice(name=feed.name, value=feed.name)
            for feed in matching_feeds[:25]
        ]


async def setup(core: "PlanaCore"):
    try:
        await core.add_cog(PlanaRSS(core))
    except Exception as e:
        core.handle_exception(
            "An error occurred while adding PlanaRSS cog",
            e,
        )
