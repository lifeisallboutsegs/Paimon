
import logging
from pathlib import Path

import aiohttp
from discord.ext import commands

from utils import embeds
from utils.checks import is_owner

logger = logging.getLogger("bot.admin.cogs")


class AdminCogs(commands.Cog):
    """Commands to manage cogs"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if await ctx.bot.is_owner(ctx.author):
            return True
        from config import Config
        if ctx.author.id in Config.OWNER_IDS:
            return True
        raise commands.NotOwner()

    @commands.command(name="load")
    async def load_cog(self, ctx: commands.Context, category_or_name: str, name: str = None):
        """Load a cog. Use: !load [category] <name> or !load <name>"""
        try:
            if name:
                extension = f"cogs.{category_or_name}.{name}"
            else:
                extension = f"cogs.{category_or_name}"
            
            await self.bot.load_extension(extension)
            await ctx.send(embed=embeds.success("Cog Loaded", extension))
        except Exception as exc:
            await ctx.send(embed=embeds.error("Load Failed", str(exc)))

    @commands.command(name="unload")
    async def unload_cog(self, ctx: commands.Context, category_or_name: str, name: str = None):
        """Unload a cog. Use: !unload [category] <name> or !unload <name>"""
        try:
            if name:
                extension = f"cogs.{category_or_name}.{name}"
            else:
                extension = f"cogs.{category_or_name}"
            
            await self.bot.unload_extension(extension)
            await ctx.send(embed=embeds.success("Cog Unloaded", extension))
        except Exception as exc:
            await ctx.send(embed=embeds.error("Unload Failed", str(exc)))

    @commands.command(name="reload")
    async def reload_cog(self, ctx: commands.Context, category_or_name: str, name: str = None):
        """Reload a cog. Use: !reload [category] <name> or !reload <name>"""
        try:
            if name:
                extension = f"cogs.{category_or_name}.{name}"
            else:
                extension = f"cogs.{category_or_name}"
            
            await self.bot.reload_extension(extension)
            await ctx.send(embed=embeds.success("Cog Reloaded", extension))
        except Exception as exc:
            await ctx.send(embed=embeds.error("Reload Failed", str(exc)))

    @commands.command(name="install")
    async def install_cog(self, ctx: commands.Context, category: str, name: str, url: str):
        """Install a cog from a raw URL (like GitHub/Pastebin). Categories: admin, moderation, fun, economy, utility, settings, leveling"""
        try:
            # Valid categories
            valid_categories = ["admin", "moderation", "fun", "economy", "utility", "settings", "leveling"]
            category = category.lower()
            if category not in valid_categories:
                await ctx.send(embed=embeds.error("Invalid Category", f"Valid categories: {', '.join(valid_categories)}"))
                return

            cogs_dir = Path(__file__).resolve().parent.parent
            category_dir = cogs_dir / category
            
            # Create category directory if not exists
            category_dir.mkdir(exist_ok=True)
            cog_path = category_dir / f"{name}.py"
            
            # Download the cog
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await ctx.send(embed=embeds.error("Download Failed", f"Status: {resp.status}"))
                        return
                    content = await resp.text()

            # Write to disk
            cog_path.write_text(content, encoding="utf-8")
            
            # Load the cog
            extension_path = f"cogs.{category}.{name}"
            await self.bot.load_extension(extension_path)
            await ctx.send(embed=embeds.success("Cog Installed", f"Installed and loaded {extension_path}!"))
        except Exception as exc:
            await ctx.send(embed=embeds.error("Install Failed", str(exc)))


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCogs(bot))
