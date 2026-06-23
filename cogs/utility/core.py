
import time
import platform

import discord
from discord import app_commands
from discord.ext import commands

from utils import embeds


class UtilityCore(commands.Cog):
    """Core utility commands (ping, info, uptime)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="ping", description="Check the bot's latency.")
    async def ping(self, ctx: commands.Context):
        start = time.perf_counter()
        message = await ctx.send("Pinging...")
        elapsed = (time.perf_counter() - start) * 1000
        await message.edit(content=None, embed=embeds.info(
            "Pong! 🏓", f"Gateway: `{self.bot.latency * 1000:.1f}ms`\nRoundtrip: `{elapsed:.1f}ms`"
        ))

    @commands.hybrid_command(name="info", description="Shows information about the bot.")
    async def info(self, ctx: commands.Context):
        embed = embeds.info("🤖 Bot Info", "")
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="Name", value=self.bot.user.name)
        embed.add_field(name="ID", value=self.bot.user.id)
        embed.add_field(name="Servers", value=len(self.bot.guilds))
        embed.add_field(name="Python", value=platform.python_version())
        embed.add_field(name="Discord.py", value=discord.__version__)
        embed.add_field(name="Created At", value=discord.utils.format_dt(self.bot.user.created_at, "R"))
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="uptime", description="Check how long the bot has been online.")
    async def uptime(self, ctx: commands.Context):
        delta = discord.utils.utcnow() - self.bot.start_time
        days = delta.days
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        embed = embeds.info("Bot Uptime", f"⏱️ {days}d {hours}h {minutes}m {seconds}s")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCore(bot))
