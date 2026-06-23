
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from utils import embeds, helpers
from utils.checks import mod_role_or_permission


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(member="Member to kick", reason="Reason for the kick")
    @mod_role_or_permission("kick_members")
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        await member.kick(reason=f"{ctx.author}: {reason}")
        await ctx.send(embed=embeds.success("Member Kicked", f"{member.mention} — {reason}"))

    @commands.hybrid_command(name="ban", description="Ban a member from the server.")
    @app_commands.describe(member="Member to ban", reason="Reason for the ban")
    @mod_role_or_permission("ban_members")
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        await member.ban(reason=f"{ctx.author}: {reason}", delete_message_seconds=0)
        await ctx.send(embed=embeds.success("Member Banned", f"{member.mention} — {reason}"))

    @commands.hybrid_command(name="timeout", description="Timeout a member.")
    @app_commands.describe(member="Member to timeout", duration="e.g. 10m, 1h, 1d", reason="Reason")
    @mod_role_or_permission("moderate_members")
    @commands.bot_has_permissions(moderate_members=True)
    async def timeout(
        self, ctx: commands.Context, member: discord.Member, duration: str,
        *, reason: str = "No reason provided",
    ):
        seconds = helpers.parse_duration(duration)
        if seconds is None:
            await ctx.send(embed=embeds.error("Invalid Duration", "Use a format like `10m`, `1h`, `2d`."))
            return
        await member.timeout(timedelta(seconds=seconds), reason=f"{ctx.author}: {reason}")
        await ctx.send(embed=embeds.success(
            "Member Timed Out", f"{member.mention} for {helpers.human_timedelta_seconds(seconds)} — {reason}"
        ))

    @commands.hybrid_command(name="warn", description="Issue a warning to a member.")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @mod_role_or_permission("kick_members")
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        warn_id = await self.bot.db.add_warning(ctx.guild.id, member.id, ctx.author.id, reason)
        await ctx.send(embed=embeds.warning("Member Warned", f"{member.mention} — {reason} (warning #{warn_id})"))

    @commands.hybrid_command(name="warnings", description="List warnings for a member.")
    @app_commands.describe(member="Member to check")
    @mod_role_or_permission("kick_members")
    async def warnings(self, ctx: commands.Context, member: discord.Member):
        rows = await self.bot.db.get_warnings(ctx.guild.id, member.id)
        if not rows:
            await ctx.send(embed=embeds.info("No Warnings", f"{member.mention} has a clean record."))
            return
        lines = []
        for r in rows:
            created = datetime.fromisoformat(r["created_at"])
            lines.append(f"`#{r['id']}` {r['reason']} — <t:{int(created.timestamp())}:R>")
        await ctx.send(embed=embeds.info(f"Warnings for {member}", "\n".join(lines)))

    @commands.hybrid_command(name="clearwarnings", description="Clear all warnings for a member.")
    @app_commands.describe(member="Member to clear")
    @mod_role_or_permission("administrator")
    async def clearwarnings(self, ctx: commands.Context, member: discord.Member):
        await self.bot.db.clear_warnings(ctx.guild.id, member.id)
        await ctx.send(embed=embeds.success("Warnings Cleared", f"{member.mention}'s record is clean."))

    @commands.hybrid_command(name="purge", description="Delete a number of recent messages.")
    @app_commands.describe(amount="How many messages to delete (max 100)")
    @mod_role_or_permission("manage_messages")
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int):
        amount = max(1, min(amount, 100))
        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(
            embed=embeds.success("Messages Purged", f"Deleted {len(deleted) - 1} message(s)."),
            delete_after=5,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
