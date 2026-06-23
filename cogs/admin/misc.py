
import discord
from discord import app_commands
from discord.ext import commands

from utils import embeds
from utils.checks import is_owner


class AdminMisc(commands.Cog):
    """Miscellaneous admin commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if await ctx.bot.is_owner(ctx.author):
            return True
        from config import Config
        if ctx.author.id in Config.OWNER_IDS:
            return True
        raise commands.NotOwner()

    @commands.command(name="sync")
    async def sync_commands(self, ctx: commands.Context, scope: str = "guild"):
        """Sync slash commands. scope: 'guild' (instant, this server only) or 'global' (~1hr to propagate)."""
        if scope == "guild" and ctx.guild:
            synced = await self.bot.tree.sync(guild=ctx.guild)
        else:
            synced = await self.bot.tree.sync()
        await ctx.send(embed=embeds.success("Synced", f"{len(synced)} command(s) ({scope})."))

    @commands.command(name="shutdown")
    async def shutdown(self, ctx: commands.Context):
        await ctx.send(embed=embeds.warning("Shutting Down", "Goodbye 👋"))
        await self.bot.close()

    @commands.command(name="restart")
    async def restart(self, ctx: commands.Context):
        await ctx.send(embed=embeds.warning("Restarting", "Be right back! 🔄"))
        await self.bot.close()

    @commands.command(name="status")
    @app_commands.describe(text="Text for the status")
    async def status(self, ctx: commands.Context, *, text: str):
        await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=text))
        await ctx.send(embed=embeds.success("Status Updated", f"New status: watching **{text}**"))


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminMisc(bot))
