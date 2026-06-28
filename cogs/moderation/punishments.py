from datetime import timedelta
import discord
from discord import app_commands
from discord.ext import commands
from utils import helpers
from utils.checks import mod_role_or_permission

class ModerationPunishments(commands.Cog):
    """Punishment commands (kick, ban, mute, etc.)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='kick', description='Kick a member from the server.')
    @app_commands.describe(member='Member to kick', reason='Reason for the kick')
    @mod_role_or_permission('kick_members')
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str='No reason provided'):
        await member.kick(reason=f'{ctx.author}: {reason}')
        await ctx.send(f'✅ Member Kicked: {member.mention} — {reason}')

    @commands.hybrid_command(name='ban', description='Ban a member from the server.')
    @app_commands.describe(member='Member to ban', reason='Reason for the ban')
    @mod_role_or_permission('ban_members')
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str='No reason provided'):
        await member.ban(reason=f'{ctx.author}: {reason}', delete_message_seconds=0)
        await ctx.send(f'✅ Member Banned: {member.mention} — {reason}')

    @commands.hybrid_command(name='unban', description='Unban a user from the server.')
    @app_commands.describe(user='User to unban (username#discriminator or ID)')
    @mod_role_or_permission('ban_members')
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, *, user: str):
        bans = [entry async for entry in ctx.guild.bans()]
        for ban_entry in bans:
            if str(ban_entry.user) == user or str(ban_entry.user.id) == user:
                await ctx.guild.unban(ban_entry.user)
                return await ctx.send(f'✅ User Unbanned: {ban_entry.user.mention}')
        await ctx.send(f'❌ Error: User not found in ban list.')

    @commands.hybrid_command(name='timeout', description='Timeout a member.')
    @app_commands.describe(member='Member to timeout', duration='e.g. 10m, 1h, 1d', reason='Reason')
    @mod_role_or_permission('moderate_members')
    @commands.bot_has_permissions(moderate_members=True)
    async def timeout(self, ctx: commands.Context, member: discord.Member, duration: str, *, reason: str='No reason provided'):
        seconds = helpers.parse_duration(duration)
        if seconds is None:
            await ctx.send(f'❌ Invalid Duration: Use a format like `10m`, `1h`, `2d`.')
            return
        await member.timeout(timedelta(seconds=seconds), reason=f'{ctx.author}: {reason}')
        await ctx.send(f'✅ Member Timed Out: {member.mention} for {helpers.human_timedelta_seconds(seconds)} — {reason}')

    @commands.hybrid_command(name='mute', description='Mute a member using the Muted role.')
    @app_commands.describe(member='Member to mute', reason='Reason for the mute')
    @mod_role_or_permission('manage_roles')
    @commands.bot_has_permissions(manage_roles=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, *, reason: str='No reason provided'):
        mute_role = discord.utils.get(ctx.guild.roles, name='Muted')
        if not mute_role:
            mute_role = await ctx.guild.create_role(name='Muted')
            for channel in ctx.guild.channels:
                await channel.set_permissions(mute_role, send_messages=False, speak=False)
        await member.add_roles(mute_role, reason=f'{ctx.author}: {reason}')
        await ctx.send(f'✅ Member Muted: {member.mention} — {reason}')

    @commands.hybrid_command(name='unmute', description='Unmute a member.')
    @app_commands.describe(member='Member to unmute')
    @mod_role_or_permission('manage_roles')
    @commands.bot_has_permissions(manage_roles=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        mute_role = discord.utils.get(ctx.guild.roles, name='Muted')
        if mute_role in member.roles:
            await member.remove_roles(mute_role)
            await ctx.send(f'✅ Member Unmuted: {member.mention}')
        else:
            await ctx.send(f'❌ Error: This user is not muted.')

async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationPunishments(bot))
