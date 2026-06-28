import random
import discord
from discord import app_commands
from discord.ext import commands

class UtilityMisc(commands.Cog):
    """Miscellaneous utility commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='say', description='Make the bot say something.')
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(message='The message to say')
    async def say(self, ctx: commands.Context, *, message: str):
        await ctx.send(message)

    @commands.hybrid_command(name='message', description='Send a message to a specific channel.')
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(channel='The channel to send to', message='The message to send')
    async def message_command(self, ctx: commands.Context, channel: discord.TextChannel, *, message: str):
        await channel.send(message)
        await ctx.send(f'✅ Message Sent\nSent message to {channel.mention}')

    @commands.hybrid_command(name='embed', description='Make the bot send an embed.')
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(title='Embed title', description='Embed description')
    async def embed_command(self, ctx: commands.Context, title: str, *, description: str):
        await ctx.send(f'**{title}**\n{description}')

    @commands.hybrid_command(name='poll', description='Create a simple poll.')
    @app_commands.describe(question='Poll question')
    async def poll(self, ctx: commands.Context, *, question: str):
        message = await ctx.send(f'📊 Poll\n{question}')
        await message.add_reaction('👍')
        await message.add_reaction('👎')

    @commands.hybrid_command(name='question', description='Ask the bot a yes/no question.')
    @app_commands.describe(question='Your question')
    async def question(self, ctx: commands.Context, *, question: str):
        responses = ['Yes', 'No', 'Maybe', 'Definitely', "I don't think so", 'Absolutely!']
        await ctx.send(f'❓ {question}\n{random.choice(responses)}')

async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityMisc(bot))
