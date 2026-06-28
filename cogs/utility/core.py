import time
import platform
import discord
from discord.ext import commands


class UtilityCore(commands.Cog):
    """Core utility commands (ping, info, uptime)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="ping", description="Check the bot's latency.")
    async def ping(self, ctx: commands.Context):
        start = time.perf_counter()
        message = await ctx.send("Pinging...")
        elapsed = (time.perf_counter() - start) * 1000
        await message.edit(
            content=f"Pong! 🏓\nGateway: `{self.bot.latency * 1000:.1f}ms`\nRoundtrip: `{elapsed:.1f}ms`"
        )

    @commands.hybrid_command(
        name="info", description="Shows information about the bot."
    )
    async def info(self, ctx: commands.Context):
        await ctx.send(
            f"🤖 Bot Info\n{self.bot.user.display_avatar.url}\n- Name: {self.bot.user.name}\n- ID: {self.bot.user.id}\n- Servers: {len(self.bot.guilds)}\n- Python: {platform.python_version()}\n- Discord.py: {discord.__version__}\n- Created At: {discord.utils.format_dt(self.bot.user.created_at, 'R')}"
        )

    @commands.hybrid_command(
        name="uptime", description="Check how long the bot has been online."
    )
    async def uptime(self, ctx: commands.Context):
        delta = discord.utils.utcnow() - self.bot.start_time
        days = delta.days
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        await ctx.send(f"⏱️ {days}d {hours}h {minutes}m {seconds}s")


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCore(bot))
