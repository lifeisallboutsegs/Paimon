from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord.ext import commands

from config import Config

logger = logging.getLogger("bot.core")


async def get_prefix(bot: "Bot", message: discord.Message):
    if message.guild is None:
        return commands.when_mentioned_or(Config.PREFIX)(bot, message)
    guild_cfg = await bot.db.get_guild_config(message.guild.id)
    prefix = guild_cfg.get("prefix") or Config.PREFIX
    return commands.when_mentioned_or(prefix)(bot, message)


class Bot(commands.Bot):
    def __init__(self, db):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            case_insensitive=True,
            owner_ids=Config.OWNER_IDS or None,
            help_command=commands.DefaultHelpCommand(no_category="Commands"),
        )
        self.db = db
        self.start_time = discord.utils.utcnow()

    async def setup_hook(self) -> None:
        await self._load_cogs()
        # Slash commands are synced manually via the "!sync" admin command
        # instead of on every startup -- global syncs can take up to an
        # hour to propagate, so doing it on every restart is wasteful.

    async def _load_cogs(self) -> None:
        cogs_dir = Path(__file__).resolve().parent.parent / "cogs"
        for path in sorted(cogs_dir.rglob("*.py")):
            if path.stem.startswith("_"):
                continue
            # Calculate the relative path from cogs_dir
            rel_path = path.relative_to(cogs_dir)
            # Convert path to extension name (e.g., moderation/punishments.py -> moderation.punishments)
            extension = "cogs." + ".".join(rel_path.with_suffix("").parts)
            try:
                await self.load_extension(extension)
                logger.info("Loaded cog: %s", extension)
            except Exception:
                logger.exception("Failed to load cog: %s", extension)

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        logger.info("Connected to %d guild(s)", len(self.guilds))
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="over the server")
        )