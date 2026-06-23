
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils import embeds

DAILY_AMOUNT = 100
DAILY_COOLDOWN = timedelta(hours=24)


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="balance", description="Check your (or someone else's) balance.")
    @app_commands.describe(member="Member to check (defaults to you)")
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        bal = await self.bot.db.get_balance(ctx.guild.id, member.id)
        await ctx.send(embed=embeds.info(f"{member.display_name}'s Balance", f"💰 {bal} coins"))

    @commands.hybrid_command(name="daily", description="Claim your daily coins.")
    async def daily(self, ctx: commands.Context):
        last = await self.bot.db.get_last_daily(ctx.guild.id, ctx.author.id)
        now = datetime.now(timezone.utc)
        if last:
            remaining = DAILY_COOLDOWN - (now - datetime.fromisoformat(last))
            if remaining.total_seconds() > 0:
                hours, rem = divmod(int(remaining.total_seconds()), 3600)
                minutes = rem // 60
                await ctx.send(embed=embeds.warning("Already Claimed", f"Come back in {hours}h {minutes}m."))
                return
        await self.bot.db.add_balance(ctx.guild.id, ctx.author.id, DAILY_AMOUNT)
        await self.bot.db.set_last_daily(ctx.guild.id, ctx.author.id, now.isoformat())
        await ctx.send(embed=embeds.success("Daily Claimed", f"You received {DAILY_AMOUNT} coins! 💰"))

    @commands.hybrid_command(name="give", description="Give some of your coins to another member.")
    @app_commands.describe(member="Who to give coins to", amount="How many coins")
    async def give(self, ctx: commands.Context, member: discord.Member, amount: int):
        if amount <= 0:
            await ctx.send(embed=embeds.error("Invalid Amount", "Amount must be positive."))
            return
        sender_balance = await self.bot.db.get_balance(ctx.guild.id, ctx.author.id)
        if sender_balance < amount:
            await ctx.send(embed=embeds.error("Insufficient Funds", f"You only have {sender_balance} coins."))
            return
        await self.bot.db.add_balance(ctx.guild.id, ctx.author.id, -amount)
        await self.bot.db.add_balance(ctx.guild.id, member.id, amount)
        await ctx.send(embed=embeds.success("Coins Sent", f"You gave {amount} coins to {member.mention}."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
