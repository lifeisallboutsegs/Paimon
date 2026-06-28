import discord
from discord import app_commands
from discord.ext import commands
class EconomyCore(commands.Cog):
    """Core economy commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='balance', description="Check your (or someone else's) balance.", aliases=['bal'])
    @app_commands.describe(member='Member to check (defaults to you)')
    async def balance(self, ctx: commands.Context, member: discord.Member=None):
        member = member or ctx.author
        bal = await self.bot.db.get_balance(ctx.guild.id, member.id)
        await ctx.send(f"{member.display_name}'s Balance: 💰 {bal} coins")

    @commands.hybrid_command(name='give', description='Give some of your coins to another member.')
    @app_commands.describe(member='Who to give coins to', amount='How many coins')
    async def give(self, ctx: commands.Context, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send(f'❌ Invalid Amount: Amount must be positive.')
        sender_balance = await self.bot.db.get_balance(ctx.guild.id, ctx.author.id)
        if sender_balance < amount:
            return await ctx.send(f'❌ Insufficient Funds: You only have {sender_balance} coins.')
        await self.bot.db.add_balance(ctx.guild.id, ctx.author.id, -amount)
        await self.bot.db.add_balance(ctx.guild.id, member.id, amount)
        await ctx.send(f'✅ Coins Sent: You gave {amount} coins to {member.mention}.')

    @commands.hybrid_command(name='balancetop', description="Show the server's coin leaderboard.", aliases=['baltop'])
    async def balancetop(self, ctx: commands.Context):
        data = await self.bot.db.get_balance_leaderboard(ctx.guild.id)
        if not data:
            await ctx.send('💰 Coin Leaderboard: No one has any coins yet!')
        else:
            lines = []
            for i, entry in enumerate(data, 1):
                member = ctx.guild.get_member(entry['user_id'])
                name = member.display_name if member else f"Unknown User ({entry['user_id']})"
                lines.append(f"**
            await ctx.send(f'💰 Coin Leaderboard:\n' + '\n'.join(lines))
async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCore(bot))
