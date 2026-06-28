from __future__ import annotations
import logging
import json
import time
import os
from pathlib import Path
import discord
from discord.ext import commands
from config import Config
from core.help import CustomHelpCommand
from core.watcher import CogWatcher
logger = logging.getLogger('bot.core')
async def get_prefix(bot: 'Bot', message: discord.Message):
    if message.guild is None:
        return [Config.PREFIX]
    guild_cfg = await bot.db.get_guild_config(message.guild.id)
    prefix = guild_cfg.get('prefix') or Config.PREFIX
    return [prefix]
class Bot(commands.Bot):

    def __init__(self, db):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix=get_prefix, intents=intents, case_insensitive=True, owner_ids=Config.OWNER_IDS or None, help_command=CustomHelpCommand())
        self.db = db
        self.start_time = discord.utils.utcnow()
        self.watcher = CogWatcher(self)

    async def setup_hook(self) -> None:
        await self._load_cogs()
        await self.watcher.start()

    async def close(self) -> None:
        await self.watcher.stop()
        await super().close()

    async def _load_cogs(self) -> None:
        cogs_dir = Path(__file__).resolve().parent.parent / 'cogs'
        for path in sorted(cogs_dir.rglob('*.py')):
            if path.stem.startswith('_'):
                continue
            rel_path = path.relative_to(cogs_dir)
            extension = 'cogs.' + '.'.join(rel_path.with_suffix('').parts)
            try:
                await self.load_extension(extension)
                logger.info('Loaded cog: %s', extension)
            except Exception:
                logger.exception('Failed to load cog: %s', extension)

    async def on_ready(self) -> None:
        logger.info('Logged in as %s (ID: %s)', self.user, self.user.id)
        logger.info('Connected to %d guild(s)', len(self.guilds))
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='over the server'))
        if os.path.exists('restart_info.json'):
            try:
                with open('restart_info.json', 'r') as f:
                    restart_info = json.load(f)
                channel_id = restart_info['channel_id']
                start_time = restart_info['start_time']
                time_taken = round(time.time() - start_time, 2)
                channel = self.get_channel(channel_id)
                if channel:
                    await channel.send(f'✅ Restarted! Took {time_taken} seconds.')
                os.remove('restart_info.json')
            except Exception as e:
                logger.exception('Failed to send restart message: %s', e)
                if os.path.exists('restart_info.json'):
                    os.remove('restart_info.json')
