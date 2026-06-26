import discord
from discord import app_commands
from discord.ext import commands
from utils.checks import mod_role_or_permission

class ModerationMisc(commands.Cog):
    """Miscellaneous moderation commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='slowmode', description='Set slowmode for a channel')
    @app_commands.describe(seconds='Seconds for slowmode (0 to disable)')
    @mod_role_or_permission('manage_channels')
    @commands.bot_has_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, seconds: int):
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send('✅ Slowmode Disabled: Slowmode has been turned off!')
        else:
            await ctx.send(f'✅ Slowmode Set: Slowmode set to {seconds} seconds!')

    @commands.hybrid_command(name='nick', description="Change a member's nickname")
    @app_commands.describe(member='Member to change nickname for', nickname='New nickname (leave empty to remove)')
    @mod_role_or_permission('manage_nicknames')
    @commands.bot_has_permissions(manage_nicknames=True)
    async def nick(self, ctx: commands.Context, member: discord.Member, *, nickname: str=None):
        if member.top_role >= ctx.guild.me.top_role:
            await ctx.send(f"❌ Error: I can't change {member.mention}'s nickname because their role is higher than or equal to mine!")
            return
        if member.id == ctx.guild.owner_id and ctx.guild.me.id != ctx.guild.owner_id:
            await ctx.send(f"❌ Error: I can't change the server owner's nickname!")
            return
        try:
            await member.edit(nick=nickname)
            if nickname:
                await ctx.send(f"✅ Nickname Changed: Changed {member.mention}'s nickname to {nickname}!")
            else:
                await ctx.send(f"✅ Nickname Removed: Removed {member.mention}'s nickname!")
        except discord.Forbidden:
            await ctx.send(f"❌ Error: I don't have permission to change {member.mention}'s nickname!")
        except discord.HTTPException as e:
            await ctx.send(f'❌ Error: Failed to change nickname - {e}')

async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationMisc(bot))