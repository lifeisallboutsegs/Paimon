
import discord
from discord import app_commands
from discord.ext import commands

from utils import embeds


class UtilityServer(commands.Cog):
    """Server and user info commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="userinfo", description="Show information about a member.")
    @app_commands.describe(member="Member to inspect (defaults to you)")
    async def userinfo(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        embed = embeds.info(f"{member}", "")
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=member.id)
        embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, "R"))
        embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, "R"))
        roles = ", ".join(r.mention for r in member.roles if r.name != "@everyone") or "None"
        embed.add_field(name="Roles", value=roles, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="serverinfo", description="Show information about this server.")
    async def serverinfo(self, ctx: commands.Context):
        guild = ctx.guild
        embed = embeds.info(guild.name, "")
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown")
        embed.add_field(name="Members", value=guild.member_count)
        embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "R"))
        embed.add_field(name="Channels", value=len(guild.channels))
        embed.add_field(name="Roles", value=len(guild.roles))
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="avatar", description="Get a member's avatar.")
    @app_commands.describe(member="Member to inspect (defaults to you)")
    async def avatar(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        embed = embeds.info(f"{member}'s Avatar", "")
        embed.set_image(url=member.display_avatar.url)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityServer(bot))
