from datetime import datetime, timedelta, timezone

import random

import discord

from discord import app_commands

from discord.ext import commands

DAILY_AMOUNT = 100

DAILY_COOLDOWN = timedelta(hours=24)

WORK_COOLDOWN = timedelta(hours=1)

WORK_MESSAGES = [
    "You fixed a bug and earned",
    "You delivered a package and got",
    "You wrote a great article and received",
    "You helped a neighbor and were given",
    "You won a small contest and got",
]


class EconomyRewards(commands.Cog):
    """Economy reward commands (daily, work)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="daily", description="Claim your daily coins.")
    async def daily(self, ctx: commands.Context):
        last = await self.bot.db.get_last_daily(ctx.guild.id, ctx.author.id)
        now = datetime.now(timezone.utc)
        if last:
            remaining = DAILY_COOLDOWN - (now - datetime.fromisoformat(last))
            if remaining.total_seconds() > 0:
                hours, rem = divmod(int(remaining.total_seconds()), 3600)
                minutes = rem // 60
                await ctx.send(f"Already Claimed: Come back in {hours}h {minutes}m.")
                return
        await self.bot.db.add_balance(ctx.guild.id, ctx.author.id, DAILY_AMOUNT)
        await self.bot.db.set_last_daily(ctx.guild.id, ctx.author.id, now.isoformat())
        await ctx.send(f"✅ Daily Claimed! You received {DAILY_AMOUNT} coins! 💰")

    @commands.hybrid_command(name="work", description="Work to earn some coins!")
    async def work(self, ctx: commands.Context):
        last = await self.bot.db.get_last_work(ctx.guild.id, ctx.author.id)
        now = datetime.now(timezone.utc)
        if last:
            remaining = WORK_COOLDOWN - (now - datetime.fromisoformat(last))
            if remaining.total_seconds() > 0:
                minutes, seconds = divmod(int(remaining.total_seconds()), 60)
                await ctx.send(f"Not Yet: Come back in {minutes}m {seconds}s.")
                return
        amount = random.randint(50, 150)
        await self.bot.db.add_balance(ctx.guild.id, ctx.author.id, amount)
        await self.bot.db.set_last_work(ctx.guild.id, ctx.author.id, now.isoformat())
        message = random.choice(WORK_MESSAGES)
        await ctx.send(f"✅ Work Complete! {message} {amount} coins! 💰")


async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyRewards(bot))
