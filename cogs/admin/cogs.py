
import logging
from pathlib import Path
import aiohttp
import random

from discord.ext import commands

from utils import embeds
from utils.checks import is_owner
from config import Config
from groq import AsyncGroq

logger = logging.getLogger("bot.admin.cogs")


class AdminCogs(commands.Cog):
    """Commands to manage cogs"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.key_index = 0
        self.clients = []
        if Config.GROQ_API_KEYS:
            for key in Config.GROQ_API_KEYS:
                self.clients.append(AsyncGroq(api_key=key))

    def _get_client(self):
        if not self.clients:
            return None
        client = self.clients[self.key_index]
        self.key_index = (self.key_index + 1) % len(self.clients)
        return client

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
    async def install_cog(self, ctx: commands.Context, url: str, name: str = None, category: str = None):
        """Install a cog from a raw URL. Optional: name, category"""
        try:
            valid_categories = ["admin", "moderation", "fun", "economy", "utility", "settings", "leveling"]
            
            # Download the cog first
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await ctx.send(embed=embeds.error("Download Failed", f"Status: {resp.status}"))
                        return
                    content = await resp.text()
            
            # If category or name not provided, use AI to suggest
            if not category or not name:
                category, name = await self._suggest_cog_info(content, valid_categories, name, category)
            
            category = category.lower()
            if category not in valid_categories:
                await ctx.send(embed=embeds.error("Invalid Category", f"Valid categories: {', '.join(valid_categories)}"))
                return
            
            # Ensure name is valid
            name = name.lower().replace(" ", "_").replace("-", "_")
            if not name or not name.isprintable():
                await ctx.send(embed=embeds.error("Invalid Name", "Please provide a valid cog name!"))
                return

            cogs_dir = Path(__file__).resolve().parent.parent
            category_dir = cogs_dir / category
            category_dir.mkdir(exist_ok=True)
            cog_path = category_dir / f"{name}.py"
            
            # Write to disk
            cog_path.write_text(content, encoding="utf-8")
            
            # Load the cog
            extension_path = f"cogs.{category}.{name}"
            await self.bot.load_extension(extension_path)
            await ctx.send(embed=embeds.success("Cog Installed", f"Installed and loaded {extension_path}!"))
        except Exception as exc:
            await ctx.send(embed=embeds.error("Install Failed", str(exc)))
    
    async def _suggest_cog_info(self, content: str, valid_categories: list, name: str = None, category: str = None):
        """Use AI to suggest cog name/category (only a small sample of content)"""
        client = self._get_client()
        if not client:
            # Fallback
            if not category:
                category = "fun"
            if not name:
                name = f"cog_{random.randint(1000, 9999)}"
            return category, name
        
        # Take only first ~500 characters to save tokens
        content_sample = content[:500]
        
        system_prompt = """You are a helper for a Discord bot. Given a sample of a Python cog file, suggest:
1. A short, snake_case filename without .py (e.g., "my_cog" or "moderation_commands")
2. A category from this list: admin, moderation, fun, economy, utility, settings, leveling

Respond ONLY with JSON in the format: {"name": "suggested_name", "category": "suggested_category"}"""
        
        try:
            completion = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Content sample:\n{content_sample}"}
                ],
                temperature=0.3,
                max_completion_tokens=200
            )
            
            import json
            ai_response = completion.choices[0].message.content
            data = json.loads(ai_response)
            suggested_name = data.get("name", name or f"cog_{random.randint(1000,9999)}")
            suggested_category = data.get("category", category or "fun")
            return suggested_category, suggested_name
        except:
            # Fallback
            if not category:
                category = "fun"
            if not name:
                name = f"cog_{random.randint(1000, 9999)}"
            return category, name


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCogs(bot))
