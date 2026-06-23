
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import mod_role_or_permission


class ModerationWarnings(commands.Cog):
    """Warning commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="warn", description="Issue a warning to a member.")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @mod_role_or_permission("kick_members")
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        warn_id = await self.bot.db.add_warning(ctx.guild.id, member.id, ctx.author.id, reason)
        await ctx.send(f"⚠️ Member Warned: {member.mention} — {reason} (warning #{warn_id})")

    @commands.hybrid_command(name="warnings", description="List warnings for a member.")
    @app_commands.describe(member="Member to check")
    @mod_role_or_permission("kick_members")
    async def warnings(self, ctx: commands.Context, member: discord.Member):
        rows = await self.bot.db.get_warnings(ctx.guild.id, member.id)
        if not rows:
            await ctx.send(f"ℹ️ No Warnings: {member.mention} has a clean record.")
            return
        lines = []
        for r in rows:
            created = datetime.fromisoformat(r["created_at"])
            lines.append(f"`#{r['id']}` {r['reason']} — <t:{int(created.timestamp())}:R>")
        await ctx.send(f"⚠️ Warnings for {member}:\n" + "\n".join(lines))

    @commands.hybrid_command(name="clearwarnings", description="Clear all warnings for a member.")
    @app_commands.describe(member="Member to clear")
    @mod_role_or_permission("administrator")
    async def clearwarnings(self, ctx: commands.Context, member: discord.Member):
        await self.bot.db.clear_warnings(ctx.guild.id, member.id)
        await ctx.send(f"✅ Warnings Cleared: {member.mention}'s record is clean.")


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationWarnings(bot))
