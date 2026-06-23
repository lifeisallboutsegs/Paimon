import logging

from discord.ext import commands

from utils import embeds

logger = logging.getLogger("bot.admin")


class Admin(commands.Cog):
    """Bot-owner utilities. Not visible/usable to anyone but the configured OWNER_IDS."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    @commands.command(name="load")
    async def load_cog(self, ctx: commands.Context, name: str):
        try:
            await self.bot.load_extension(f"cogs.{name}")
        except Exception as exc:
            await ctx.send(embed=embeds.error("Load Failed", str(exc)))
            return
        await ctx.send(embed=embeds.success("Cog Loaded", name))

    @commands.command(name="unload")
    async def unload_cog(self, ctx: commands.Context, name: str):
        try:
            await self.bot.unload_extension(f"cogs.{name}")
        except Exception as exc:
            await ctx.send(embed=embeds.error("Unload Failed", str(exc)))
            return
        await ctx.send(embed=embeds.success("Cog Unloaded", name))

    @commands.command(name="reload")
    async def reload_cog(self, ctx: commands.Context, name: str):
        try:
            await self.bot.reload_extension(f"cogs.{name}")
        except Exception as exc:
            await ctx.send(embed=embeds.error("Reload Failed", str(exc)))
            return
        await ctx.send(embed=embeds.success("Cog Reloaded", name))

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


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
