import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands

from plana.utils.context import PlanaContext
from plana.utils.translate import Tr, PlanaLocaleStr

from plana.services.manager import GuildManager

if TYPE_CHECKING:
    from plana.utils.core import PlanaCore


# Global cache for yt-dlp extracted info
_ytdl_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl: Dict[str, float] = {}
CACHE_DURATION = 3600  # 1 hour cache


@dataclass
class SongInfo:
    """Structured song information with type safety."""

    title: str
    url: str
    webpage_url: Optional[str] = None
    duration: Optional[int] = None
    uploader: Optional[str] = None
    thumbnail: Optional[str] = None
    view_count: Optional[int] = None
    upload_date: Optional[str] = None
    description: Optional[str] = None
    extractor: Optional[str] = None
    requester: Optional[Union[discord.User, discord.Member]] = None

    @classmethod
    def from_ytdl_data(
        cls, data: Dict[str, Any], requester: Optional[Union[discord.User, discord.Member]] = None
    ) -> "SongInfo":
        """Create SongInfo from yt-dlp extracted data."""
        return cls(
            title=data.get("title", "Unknown Title"),
            url=data.get("url", ""),
            webpage_url=data.get("webpage_url"),
            duration=data.get("duration"),
            uploader=data.get("uploader"),
            thumbnail=data.get("thumbnail"),
            view_count=data.get("view_count"),
            upload_date=data.get("upload_date"),
            description=data.get("description"),
            extractor=data.get("extractor"),
            requester=requester,
        )

    def format_duration(self) -> str:
        """Format duration in seconds to MM:SS or HH:MM:SS."""
        if self.duration is None:
            return "Unknown"

        hours = self.duration // 3600
        minutes = (self.duration % 3600) // 60
        seconds = self.duration % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def format_view_count(self) -> str:
        """Format view count with appropriate suffixes."""
        if self.view_count is None:
            return "Unknown"

        if self.view_count >= 1_000_000:
            return f"{self.view_count / 1_000_000:.1f}M"
        elif self.view_count >= 1_000:
            return f"{self.view_count / 1_000:.1f}K"
        return str(self.view_count)

    def format_upload_date(self) -> str:
        """Format upload date to readable format."""
        if not self.upload_date:
            return "Unknown"

        # yt-dlp returns dates in YYYYMMDD format
        try:
            year = self.upload_date[:4]
            month = self.upload_date[4:6]
            day = self.upload_date[6:8]
            return f"{year}-{month}-{day}"
        except (IndexError, ValueError):
            return self.upload_date


class MusicPlayer:
    """Represents a music player for a specific guild."""

    def __init__(self, ctx: PlanaContext):
        self.ctx = ctx
        self.voice_client: Optional[discord.VoiceClient] = None
        self.current_song: Optional[SongInfo] = None
        self.queue: List[SongInfo] = []
        self.loop_mode: str = "off"  # off, song, queue
        self.volume: float = 0.5
        self.skip_votes: set = set()
        self.required_skips: int = 0

    async def connect(self, channel: Union[discord.VoiceChannel, discord.StageChannel]) -> bool:
        """Connect to a voice channel."""
        if isinstance(channel, discord.StageChannel):
            return False  # Don't support stage channels for now

        self.voice_client = await channel.connect()
        return True

    async def disconnect(self):
        """Disconnect from voice channel."""
        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None
        self.current_song = None
        self.queue.clear()
        self.skip_votes.clear()

    def add_to_queue(self, song: SongInfo):
        """Add a song to the queue."""
        self.queue.append(song)

    def get_next_song(self) -> Optional[SongInfo]:
        """Get the next song from queue based on loop mode."""
        if self.loop_mode == "song" and self.current_song:
            return self.current_song
        elif self.queue:
            if self.loop_mode == "queue" and self.current_song:
                self.queue.append(self.current_song)
            return self.queue.pop(0)
        return

    def clear_queue(self):
        """Clear the music queue."""
        self.queue.clear()

    def shuffle_queue(self):
        """Shuffle the music queue."""
        import random

        random.shuffle(self.queue)

    def set_volume(self, volume: float):
        """Set the player volume (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, volume))
        if self.voice_client and self.voice_client.source:
            self.voice_client.source.volume = self.volume

    def vote_skip(self, user_id: int) -> tuple[int, int]:
        """Add a skip vote and return current votes and required votes."""
        self.skip_votes.add(user_id)
        # Calculate required skips (majority of users in voice channel, minimum 2)
        if self.voice_client and self.voice_client.channel:
            members = [m for m in self.voice_client.channel.members if not m.bot]
            self.required_skips = max(2, len(members) // 2 + 1)
        return len(self.skip_votes), self.required_skips

    def should_skip(self) -> bool:
        """Check if enough votes to skip."""
        return len(self.skip_votes) >= self.required_skips

    def reset_skip_votes(self):
        """Reset skip votes for new song."""
        self.skip_votes.clear()


class YTDLError(Exception):
    """Custom exception for YTDL errors."""

    pass


class YTDLSource(discord.PCMVolumeTransformer):
    """Audio source for YouTube-DL with global caching and optimized settings."""

    # Optimized YTDL settings for high-scale deployment
    YTDL_OPTIONS = {
        "format": "bestaudio[ext=webm]/bestaudio/best",
        "extractaudio": False,  # Stream directly for better performance
        "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
        "restrictfilenames": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "logtostderr": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "auto",
        "source_address": "0.0.0.0",
        "cachedir": False,  # Disable file caching for memory efficiency
        "writesubtitles": False,
        "writeautomaticsub": False,
        "geo_bypass": True,
        "youtube_include_dash_manifest": False,  # Avoid DASH for compatibility
        "extract_flat": False,
        "socket_timeout": 30,
        "retries": 3,
    }

    # Fixed FFmpeg options to avoid duplicate parameters
    FFMPEG_OPTIONS = {
        "before_options": (
            "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
            "-probesize 50M -analyzeduration 50M -fflags +nobuffer "
            "-thread_queue_size 1024"
        ),
        "options": "-vn -filter:a volume=0.8",
    }

    ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title")
        self.url = data.get("url")
        self.duration = data.get("duration")
        self.uploader = data.get("uploader")
        self.thumbnail = data.get("thumbnail")

    @classmethod
    def _clean_cache(cls):
        """Clean expired entries from cache."""
        current_time = time.time()
        expired_keys = [key for key, exp_time in _cache_ttl.items() if current_time > exp_time]
        for key in expired_keys:
            _ytdl_cache.pop(key, None)
            _cache_ttl.pop(key, None)

    @classmethod
    async def _extract_info_cached(
        cls, url: str, *, executor=None, download: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Extract info with global caching for better performance."""
        # Clean expired cache entries periodically
        cls._clean_cache()

        # Check cache first (significant performance boost)
        cache_key = f"{url}:{download}"
        if cache_key in _ytdl_cache:
            return _ytdl_cache[cache_key]

        # Extract info using thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            executor, lambda: cls.ytdl.extract_info(url, download=download)
        )

        # Cache the result for future requests
        if data:
            _ytdl_cache[cache_key] = data
            _cache_ttl[cache_key] = time.time() + CACHE_DURATION

        return data

    @classmethod
    async def from_url(cls, url, *, executor=None, stream=True):
        """Create audio source from URL with caching and optimization."""
        # Always use streaming for better performance and reduced server load
        data = await cls._extract_info_cached(url, executor=executor, download=False)

        if data and "entries" in data:
            # Take first item from a playlist
            data = data["entries"][0]

        if not data:
            raise YTDLError("Failed to extract data from URL")

        # Get the direct audio URL for streaming
        audio_url = data["url"]

        # Create optimized PCM audio source with fixed options
        source = discord.FFmpegPCMAudio(
            audio_url,
            before_options=cls.FFMPEG_OPTIONS["before_options"],
            options=cls.FFMPEG_OPTIONS["options"],
        )

        return cls(source, data=data)

    @classmethod
    async def search_youtube(cls, query: str, *, executor=None) -> Optional[Dict[str, Any]]:
        """Search YouTube with caching for repeated searches."""
        search_url = f"ytsearch:{query}"
        data = await cls._extract_info_cached(search_url, executor=executor, download=False)

        if data and "entries" in data and data["entries"]:
            return data["entries"][0]
        return


class PlanaMusic(commands.Cog):
    """Cog responsible for music playback optimized for high-scale deployment."""

    def __init__(self, core: "PlanaCore") -> None:
        self.core: "PlanaCore" = core
        self.name = "music"
        self.description = "High-performance music system with caching and optimization"
        self.players: Dict[int, MusicPlayer] = {}
        self.executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="ytdl-worker")

    def get_player(self, ctx: PlanaContext) -> MusicPlayer:
        """Get or create a music player for the guild."""
        if ctx.guild.id not in self.players:
            self.players[ctx.guild.id] = MusicPlayer(ctx)
        return self.players[ctx.guild.id]

    async def cleanup_player(self, guild_id: int):
        """Clean up a player when it's no longer needed."""
        if guild_id in self.players:
            await self.players[guild_id].disconnect()
            del self.players[guild_id]

    async def _start_playing(self, player: MusicPlayer, song_info: SongInfo):
        """Start playing a specific song with optimized audio streaming."""
        if not player.voice_client:
            return

        # Create optimized audio source with caching
        source = await YTDLSource.from_url(song_info.url, executor=self.executor)
        source.volume = player.volume

        # Play with error handling callback
        player.voice_client.play(
            source,
            after=lambda e: asyncio.run_coroutine_threadsafe(
                self._on_song_finished(player, e), self.core.loop
            ),
        )

        player.current_song = song_info
        player.reset_skip_votes()

    async def _play_next(self, player: MusicPlayer):
        """Play the next song in the queue."""
        if not player.voice_client:
            return

        next_song = player.get_next_song()
        if not next_song:
            player.current_song = None
            return

        await self._start_playing(player, next_song)

    async def _on_song_finished(self, player: MusicPlayer, error):
        """Handle when a song finishes playing."""
        if error:
            print(f"Player error: {error}")

        await self._play_next(player)

    def _create_song_embed(
        self,
        song: SongInfo,
        locale: Optional[discord.Locale] = None,
        embed_type: str = "nowplaying",
    ) -> discord.Embed:
        """Create an embed for song information."""
        # Choose embed color and title based on type
        if embed_type == "added":
            color = discord.Color.blue()
            title = Tr.t("music.play.embed.added_title", locale=locale)
        elif embed_type == "playing":
            color = discord.Color.green()
            title = Tr.t("music.play.embed.playing_title", locale=locale)
        else:  # nowplaying
            color = discord.Color.orange()
            title = Tr.t("music.nowplaying.embed.title", locale=locale)

        # Create embed with song title as description for better visibility
        embed = discord.Embed(
            title=title,
            description=f"**[{song.title}]({song.webpage_url or 'https://youtube.com'})**",
            color=color,
        )

        # Set thumbnail if available
        if song.thumbnail:
            embed.set_image(url=song.thumbnail)

        # Add main information
        embed.add_field(
            name=Tr.t("music.embed.duration", locale=locale),
            value=song.format_duration(),
            inline=True,
        )

        embed.add_field(
            name=Tr.t("music.embed.uploader", locale=locale),
            value=song.uploader or "Unknown",
            inline=True,
        )

        if song.view_count is not None:
            embed.add_field(
                name=Tr.t("music.embed.views", locale=locale),
                value=song.format_view_count(),
                inline=True,
            )

        # Add upload date if available
        if song.upload_date:
            embed.add_field(
                name=Tr.t("music.embed.uploaded", locale=locale),
                value=song.format_upload_date(),
                inline=True,
            )

        # Add platform/extractor info
        if song.extractor:
            embed.add_field(
                name=Tr.t("music.embed.source", locale=locale),
                value=song.extractor.title() if song.extractor else "Unknown",
                inline=True,
            )

        # Add requester
        if song.requester:
            embed.add_field(
                name=Tr.t("music.embed.requested_by", locale=locale),
                value=song.requester.mention,
                inline=True,
            )

        return embed

    async def _send_now_playing(self, player: MusicPlayer):
        """Send an now playing embed."""
        if not player.current_song:
            return

        locale = player.ctx.interaction.locale if player.ctx.interaction else None
        embed = self._create_song_embed(player.current_song, locale, "nowplaying")

        # Add queue info to footer
        embed.set_footer(
            text=Tr.t(
                "music.nowplaying.embed.footer",
                locale=locale,
                queue_length=len(player.queue),
                loop_mode=player.loop_mode,
            )
        )

        await player.ctx.reply(embed=embed)

    @commands.hybrid_group(
        name=PlanaLocaleStr("music.music.name"),
        description=PlanaLocaleStr("music.music.description"),
    )
    @commands.guild_only()
    async def music(self, ctx: PlanaContext) -> None:
        """Entry point for music subcommands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(str(ctx.command))

    @music.command(
        name=PlanaLocaleStr("music.play.name"),
        description=PlanaLocaleStr("music.play.description"),
    )
    @app_commands.describe(query=PlanaLocaleStr("music.play.param.query.description"))
    @app_commands.rename(query=PlanaLocaleStr("music.play.param.query.name"))
    @commands.guild_only()
    async def play(self, ctx: PlanaContext, *, query: str) -> None:
        """Play a song with optimized streaming and caching."""
        locale = await GuildManager.get_locale(ctx)
        # Validate user is in voice channel
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(Tr.t("music.error.user_not_in_voice", locale=locale), ephemeral=True)
            return

        await ctx.defer()
        player = self.get_player(ctx)

        # Connect with error handling
        if not player.voice_client:
            if not await player.connect(ctx.author.voice.channel):
                await ctx.send(Tr.t("music.error.cannot_connect", locale=locale), ephemeral=True)
                return

        # Search with caching for better performance
        if query.startswith(("http://", "https://")):
            # Direct URL - extract with caching
            data = await YTDLSource._extract_info_cached(
                query, executor=self.executor, download=False
            )
            if data and "entries" in data:
                data = data["entries"][0]
            if not data:
                await ctx.send(
                    Tr.t("music.play.response.not_found", locale=locale, query=query),
                    ephemeral=True,
                )
                return
        else:
            # Search query with caching
            data = await YTDLSource.search_youtube(query, executor=self.executor)
            if not data:
                await ctx.send(
                    Tr.t("music.play.response.not_found", locale=locale, query=query),
                    ephemeral=True,
                )
                return

        song_info = SongInfo.from_ytdl_data(data, ctx.author)

        # Queue or play logic
        if player.current_song:
            player.add_to_queue(song_info)
            await ctx.send(
                Tr.t(
                    "music.play.response.added_to_queue",
                    locale=locale,
                    title=song_info.title,
                    position=len(player.queue),
                )
            )
        else:
            # Start playing immediately with optimization
            await self._start_playing(player, song_info)
            await ctx.send(
                Tr.t("music.play.response.started_playing", locale=locale, title=song_info.title)
            )

    @music.command(
        name=PlanaLocaleStr("music.skip.name"),
        description=PlanaLocaleStr("music.skip.description"),
    )
    @commands.guild_only()
    async def skip(self, ctx: PlanaContext) -> None:
        """Skip the current song (voting system)."""
        locale = await GuildManager.get_locale(ctx)
        await ctx.defer()
        player = self.get_player(ctx)

        if not player.current_song:
            await ctx.send(Tr.t("music.error.nothing_playing", locale=locale), ephemeral=True)
            return

        # Validate user is in same voice channel
        if not ctx.author.voice or ctx.author.voice.channel != player.voice_client.channel:
            await ctx.send(Tr.t("music.error.not_in_same_channel", locale=locale), ephemeral=True)
            return

        current_votes, required_votes = player.vote_skip(ctx.author.id)

        if player.should_skip():
            player.voice_client.stop()
            await ctx.send(
                Tr.t("music.skip.response.skipped", locale=locale, title=player.current_song.title)
            )
        else:
            await ctx.send(
                Tr.t(
                    "music.skip.response.vote_added",
                    locale=locale,
                    current=current_votes,
                    required=required_votes,
                )
            )

    @music.command(
        name=PlanaLocaleStr("music.forceskip.name"),
        description=PlanaLocaleStr("music.forceskip.description"),
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.guild_only()
    async def forceskip(self, ctx: PlanaContext) -> None:
        """Force skip the current song (requires manage channels permission)."""
        locale = await GuildManager.get_locale(ctx)
        player = self.get_player(ctx)

        if not player.current_song:
            await ctx.send(Tr.t("music.error.nothing_playing", locale=locale), ephemeral=True)
            return

        title = player.current_song.title
        player.voice_client.stop()
        await ctx.send(Tr.t("music.forceskip.response.skipped", locale=locale, title=title))

    @music.command(
        name=PlanaLocaleStr("music.queue.name"),
        description=PlanaLocaleStr("music.queue.description"),
    )
    @commands.guild_only()
    async def queue(self, ctx: PlanaContext) -> None:
        """Display the current music queue."""
        locale = await GuildManager.get_locale(ctx)
        await ctx.defer()
        player = self.get_player(ctx)

        if not player.current_song and not player.queue:
            await ctx.send(Tr.t("music.queue.response.empty", locale=locale), ephemeral=True)
            return

        embed = discord.Embed(
            title=Tr.t("music.queue.embed.title", locale=locale), color=discord.Color.blue()
        )

        # Current song
        if player.current_song:
            current = player.current_song
            embed.add_field(
                name=Tr.t("music.queue.embed.now_playing", locale=locale),
                value=f"**[{current.title}]({current.webpage_url or 'https://youtube.com'})**\n"
                f"{Tr.t('music.queue.embed.duration', locale=locale)}: {current.format_duration()}\n"
                f"{Tr.t('music.queue.embed.requested_by', locale=locale)}: {current.requester.mention}",
                inline=False,
            )

        # Queue
        if player.queue:
            queue_text = ""
            for i, song in enumerate(player.queue[:10], 1):  # Show first 10 songs
                queue_text += (
                    f"{i}. **[{song.title}]({song.webpage_url or 'https://youtube.com'})**\n"
                )
                queue_text += f"   {song.format_duration()} - {song.requester.mention}\n"

            if len(player.queue) > 10:
                queue_text += f"\n{Tr.t('music.queue.embed.and_more', locale=locale, count=len(player.queue) - 10)}"

            embed.add_field(
                name=Tr.t("music.queue.embed.upcoming", locale=locale),
                value=queue_text,
                inline=False,
            )

        # Footer with stats
        total_duration = sum(song.duration or 0 for song in player.queue)
        embed.set_footer(
            text=Tr.t(
                "music.queue.embed.footer",
                locale=locale,
                count=len(player.queue),
                duration=self._format_duration(total_duration),
                loop=player.loop_mode,
            )
        )

        await ctx.send(embed=embed)

    @music.command(
        name=PlanaLocaleStr("music.volume.name"),
        description=PlanaLocaleStr("music.volume.description"),
    )
    @app_commands.describe(level=PlanaLocaleStr("music.volume.param.level.description"))
    @app_commands.rename(level=PlanaLocaleStr("music.volume.param.level.name"))
    @commands.guild_only()
    async def volume(self, ctx: PlanaContext, level: Optional[int] = None) -> None:
        """Set or display the player volume."""
        locale = await GuildManager.get_locale(ctx)
        await ctx.defer()
        player = self.get_player(ctx)

        if level is None:
            await ctx.send(
                Tr.t(
                    "music.volume.response.current", locale=locale, volume=int(player.volume * 100)
                )
            )
            return

        if not 0 <= level <= 100:
            await ctx.send(
                Tr.t("music.volume.response.invalid_range", locale=locale), ephemeral=True
            )
            return

        old_volume = int(player.volume * 100)
        player.set_volume(level / 100)

        await ctx.send(
            Tr.t(
                "music.volume.response.changed",
                locale=locale,
                old_volume=old_volume,
                new_volume=level,
            )
        )

    @music.command(
        name=PlanaLocaleStr("music.loop.name"),
        description=PlanaLocaleStr("music.loop.description"),
    )
    @app_commands.describe(mode=PlanaLocaleStr("music.loop.param.mode.description"))
    @app_commands.rename(mode=PlanaLocaleStr("music.loop.param.mode.name"))
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Off", value="off"),
            app_commands.Choice(name="Song", value="song"),
            app_commands.Choice(name="Queue", value="queue"),
        ]
    )
    @commands.guild_only()
    async def loop(self, ctx: PlanaContext, mode: Optional[str] = None) -> None:
        """Set the loop mode for the player."""
        locale = await GuildManager.get_locale(ctx)
        await ctx.defer()
        player = self.get_player(ctx)

        if mode is None:
            await ctx.send(Tr.t(f"music.loop.response.current_{player.loop_mode}", locale=locale))
            return

        player.loop_mode = mode
        await ctx.send(Tr.t(f"music.loop.response.set_{mode}", locale=locale))

    @music.command(
        name=PlanaLocaleStr("music.pause.name"),
        description=PlanaLocaleStr("music.pause.description"),
    )
    @commands.guild_only()
    async def pause(self, ctx: PlanaContext) -> None:
        """Pause the current song."""
        locale = await GuildManager.get_locale(ctx)
        await ctx.defer()
        player = self.get_player(ctx)

        if not player.voice_client or not player.voice_client.is_playing():
            await ctx.send(Tr.t("music.error.nothing_playing", locale=locale), ephemeral=True)
            return

        player.voice_client.pause()
        await ctx.send(Tr.t("music.pause.response.paused", locale=locale))

    @music.command(
        name=PlanaLocaleStr("music.resume.name"),
        description=PlanaLocaleStr("music.resume.description"),
    )
    @commands.guild_only()
    async def resume(self, ctx: PlanaContext) -> None:
        """Resume the paused song."""
        locale = await GuildManager.get_locale(ctx)
        await ctx.defer()
        player = self.get_player(ctx)

        if not player.voice_client or not player.voice_client.is_paused():
            await ctx.send(Tr.t("music.error.not_paused", locale=locale), ephemeral=True)
            return

        player.voice_client.resume()
        await ctx.send(Tr.t("music.resume.response.resumed", locale=locale))

    @music.command(
        name=PlanaLocaleStr("music.stop.name"),
        description=PlanaLocaleStr("music.stop.description"),
    )
    @commands.guild_only()
    async def stop(self, ctx: PlanaContext) -> None:
        """Stop music and clear the queue."""
        locale = await GuildManager.get_locale(ctx)
        await ctx.defer()
        player = self.get_player(ctx)

        if not player.voice_client:
            await ctx.send(Tr.t("music.error.not_connected", locale=locale), ephemeral=True)
            return

        player.clear_queue()
        player.voice_client.stop()
        await ctx.send(Tr.t("music.stop.response.stopped", locale=locale))

    @music.command(
        name=PlanaLocaleStr("music.disconnect.name"),
        description=PlanaLocaleStr("music.disconnect.description"),
    )
    @commands.guild_only()
    async def disconnect(self, ctx: PlanaContext) -> None:
        """Disconnect from voice channel and clear all data."""
        locale = await GuildManager.get_locale(ctx)
        await ctx.defer()
        player = self.get_player(ctx)

        if not player.voice_client:
            await ctx.send(Tr.t("music.error.not_connected", locale=locale), ephemeral=True)
            return

        await self.cleanup_player(ctx.guild.id)
        await ctx.send(Tr.t("music.disconnect.response.disconnected", locale=locale))

    @music.command(
        name=PlanaLocaleStr("music.shuffle.name"),
        description=PlanaLocaleStr("music.shuffle.description"),
    )
    @commands.guild_only()
    async def shuffle(self, ctx: PlanaContext) -> None:
        """Shuffle the current queue."""
        locale = await GuildManager.get_locale(ctx)
        await ctx.defer()
        player = self.get_player(ctx)

        if not player.queue:
            await ctx.send(
                Tr.t("music.shuffle.response.empty_queue", locale=locale), ephemeral=True
            )
            return

        player.shuffle_queue()
        await ctx.send(
            Tr.t("music.shuffle.response.shuffled", locale=locale, count=len(player.queue))
        )

    @music.command(
        name=PlanaLocaleStr("music.nowplaying.name"),
        description=PlanaLocaleStr("music.nowplaying.description"),
    )
    @commands.guild_only()
    async def nowplaying(self, ctx: PlanaContext) -> None:
        """Display information about the currently playing song."""
        locale = await GuildManager.get_locale(ctx)
        await ctx.defer()

        player = self.get_player(ctx)

        if not player.current_song:
            await ctx.send(Tr.t("music.error.nothing_playing", locale=locale), ephemeral=True)
            return

        await self._send_now_playing(player)

    @music.command(
        name=PlanaLocaleStr("music.clear.name"),
        description=PlanaLocaleStr("music.clear.description"),
    )
    @commands.guild_only()
    async def clear(self, ctx: PlanaContext) -> None:
        """Clear the music queue."""
        locale = await GuildManager.get_locale(ctx)
        await ctx.defer()

        player = self.get_player(ctx)

        if not player.queue:
            await ctx.send(
                Tr.t("music.clear.response.already_empty", locale=locale), ephemeral=True
            )
            return

        cleared_count = len(player.queue)
        player.clear_queue()
        await ctx.send(Tr.t("music.clear.response.cleared", locale=locale, count=cleared_count))

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        """Handle voice state updates for auto-disconnect optimization."""
        if member == self.core.user:
            return

        # Optimized auto-disconnect for resource management
        for guild_id, player in list(self.players.items()):
            if (
                player.voice_client
                and player.voice_client.channel
                and len([m for m in player.voice_client.channel.members if not m.bot]) == 0
            ):

                # Shorter wait time for better resource management
                await asyncio.sleep(30)

                # Check again if still alone
                if (
                    player.voice_client
                    and player.voice_client.channel
                    and len([m for m in player.voice_client.channel.members if not m.bot]) == 0
                ):

                    await self.cleanup_player(guild_id)

    async def cog_unload(self) -> None:
        """Clean up resources when cog is unloaded."""
        for guild_id in list(self.players.keys()):
            await self.cleanup_player(guild_id)
        self.executor.shutdown(wait=False)


async def setup(core: "PlanaCore") -> None:
    """Add the MusicManager cog to the provided core."""
    try:
        await core.add_cog(PlanaMusic(core))
    except Exception as e:
        core.handle_exception("Failed to load MusicManager cog", e)
