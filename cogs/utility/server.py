
import discord
from discord import app_commands
from discord.ext import commands


class UtilityServer(commands.Cog):
    """Server and user info commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="userinfo", description="Show information about a member.")
    @app_commands.describe(member="Member to inspect (defaults to you)")
    async def userinfo(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        roles = ", ".join(r.mention for r in member.roles if r.name != "@everyone") or "None"
        await ctx.send(f"""**User Info for {member}**
- ID: {member.id}
- Joined Server: {discord.utils.format_dt(member.joined_at, "R")}
- Account Created: {discord.utils.format_dt(member.created_at, "R")}
- Roles: {roles}
{member.display_avatar.url}""")

    @commands.hybrid_command(name="serverinfo", description="Show information about this server.")
    async def serverinfo(self, ctx: commands.Context):
        guild = ctx.guild
        await ctx.send(f"""**Server Info for {guild.name}**
- Owner: {guild.owner.mention if guild.owner else "Unknown"}
- Members: {guild.member_count}
- Created: {discord.utils.format_dt(guild.created_at, "R")}
- Channels: {len(guild.channels)}
- Roles: {len(guild.roles)}
{f"{guild.icon.url}" if guild.icon else ""}""")

    @commands.hybrid_command(name="avatar", description="Get a member's avatar.")
    @app_commands.describe(member="Member to inspect (defaults to you)")
    async def avatar(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(member.display_avatar.url)


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityServer(bot))
