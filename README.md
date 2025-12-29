# Plana

A feature-rich Discord bot built with Python and discord.py, designed for community engagement and server management.

## Features

### 🤖 AI Conversations
Chat naturally with Plana by mentioning the bot. Powered by OpenAI, with configurable memory scopes and engage modes for dynamic server interactions.

- **Mention to chat** — Simply @Plana to start a conversation
- **Conversation memory** — Remembers context within guilds, categories, or channels
- **Engage mode** — Optionally participates in conversations proactively
- **Tool integration** — Dice rolls, calculations, and more

### 📈 Leveling System
Reward active members with XP and levels. Configurable multipliers, role rewards, and leaderboards.

### 🏆 Achievements
Track user milestones and award achievements for participation, reactions, messages, and more.

### 🎭 Reaction Roles
Self-assignable roles through reactions or button interactions. Easy setup with flexible trigger options.

### 📰 RSS Feeds
Automatically post updates from RSS feeds to designated channels. Stay connected with external content.

### 👋 Welcome & Goodbye
Customizable welcome and goodbye messages with template support for personalized greetings.

### 🎵 Music
Voice channel music playback with YouTube support.

### 🛡️ Moderation
Message management tools including bulk delete with filters for files, mentions, images, and more.

## Requirements

- Python 3.12+
- Redis (for event pub/sub)
- OpenAI API key (for AI features)

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/plana-core.git
   cd plana-core
   ```

2. **Install dependencies**
   ```bash
   pip install -e .
   # or with uv
   uv sync
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Discord token and API keys
   ```

4. **Run the bot**
   ```bash
   python main.py
   ```

## Configuration

| Variable | Description |
|----------|-------------|
| `DISCORD_TOKEN` | Your Discord bot token |
| `OPENAI_API_KEY` | OpenAI API key for AI features |
| `REDIS_URL` | Redis connection string |
| `API_BASE_URL` | Backend API URL for data persistence |

## Project Structure

```
plana-core/
├── main.py              # Entry point
├── plana/
│   ├── cogs/            # Feature modules (AI, levels, music, etc.)
│   ├── models/          # Data models and API interfaces
│   ├── services/        # Business logic and external integrations
│   ├── ui/              # Discord UI components (embeds, views)
│   └── utils/           # Helpers and utilities
└── pyproject.toml       # Project configuration
```

## License

See [LICENSE](LICENSE) for details.

---

Built with ❤️ using [discord.py](https://github.com/Rapptz/discord.py)
