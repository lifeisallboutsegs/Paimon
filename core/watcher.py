
import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from discord.ext import commands
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

logger = logging.getLogger("bot.watcher")


class CogFileHandler(FileSystemEventHandler):
    """Handler to watch for file changes in the cogs directory!"""
    
    def __init__(self, bot: commands.Bot, loop: asyncio.AbstractEventLoop):
        self.bot = bot
        self.loop = loop
        self.last_reload = {}  # path -> (last_time, last_mtime)

    def on_modified(self, event):
        """Handle file modified events!"""
        if not isinstance(event, FileModifiedEvent) or event.is_directory:
            return
        
        path = Path(event.src_path)
        if path.suffix != ".py" or path.stem.startswith("_"):
            return
        
        # Debounce: don't reload too often (use time.time() since we're in a thread)
        now = time.time()
        try:
            current_mtime = path.stat().st_mtime
        except:
            current_mtime = now
            
        if path in self.last_reload:
            last_time, last_mtime = self.last_reload[path]
            if (now - last_time) < 5.0 or abs(current_mtime - last_mtime) < 0.1:
                return
        
        self.last_reload[path] = (now, current_mtime)
        
        # Get the extension name
        cogs_dir = Path(__file__).parent.parent / "cogs"
        if not path.is_relative_to(cogs_dir):
            return
        
        try:
            rel_path = path.relative_to(cogs_dir)
            extension = "cogs." + ".".join(rel_path.with_suffix("").parts)
            
            # Schedule reload on the bot's loop
            asyncio.run_coroutine_threadsafe(self._reload_extension(extension), self.loop)
        except Exception as e:
            logger.exception("Failed to schedule reload for %s", path)

    async def _reload_extension(self, extension: str):
        """Reload the extension!"""
        try:
            await self.bot.reload_extension(extension)
            logger.info("Auto-reloaded cog: %s", extension)
        except Exception as e:
            logger.exception("Failed to auto-reload %s", extension)


class CogWatcher:
    """Watcher that monitors cogs directory for file changes!"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.observer: Optional[Observer] = None
        self.cogs_dir = Path(__file__).parent.parent / "cogs"
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self):
        """Start the watcher!"""
        if self.observer is not None:
            return
        
        self.loop = asyncio.get_event_loop()
        handler = CogFileHandler(self.bot, self.loop)
        
        self.observer = Observer()
        self.observer.schedule(handler, str(self.cogs_dir), recursive=True)
        self.observer.start()
        
        logger.info("Started watching %s for changes!", self.cogs_dir)

    async def stop(self):
        """Stop the watcher!"""
        if self.observer is None:
            return
        
        self.observer.stop()
        self.observer.join()
        self.observer = None
        logger.info("Stopped cog watcher!")
