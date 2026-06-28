import discord
from discord import app_commands
from discord.ext import commands

class FunSocial(commands.Cog):
    """Social fun commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='hug', description='Hug someone!')
    @app_commands.describe(member='Member to hug')
    async def hug(self, ctx: commands.Context, member: discord.Member):
        await ctx.send(f'{ctx.author.mention} hugs {member.mention}! 🤗')

    @commands.hybrid_command(name='slap', description='Slap someone!')
    @app_commands.describe(member='Member to slap')
    async def slap(self, ctx: commands.Context, member: discord.Member):
        await ctx.send(f'{ctx.author.mention} slaps {member.mention}! 👋')

async def setup(bot: commands.Bot):
    await bot.add_cog(FunSocial(bot))
