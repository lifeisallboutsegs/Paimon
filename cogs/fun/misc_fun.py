
import random

import discord
from discord import app_commands
from discord.ext import commands

from utils import embeds


class FunMisc(commands.Cog):
    """Miscellaneous fun commands!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="joke", description="Tell a random joke!")
    async def joke(self, ctx: commands.Context):
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "What do you call fake spaghetti? An impasta!",
            "Why did the scarecrow win an award? He was outstanding in his field!",
            "What do you call a bear with no teeth? A gummy bear!",
            "Why don't eggs tell jokes? They'd crack each other up!",
            "What's orange and sounds like a parrot? A carrot!",
            "Why did the bicycle fall over? Because it was two-tired!",
            "What do you call a fish without eyes? A fsh!",
        ]
        await ctx.send(embed=embeds.info("Joke", random.choice(jokes)))

    @commands.hybrid_command(name="random_num", description="Get a random number!")
    @app_commands.describe(min_num="Minimum number", max_num="Maximum number")
    async def random_number(self, ctx: commands.Context, min_num: int = 1, max_num: int = 100):
        if min_num > max_num:
            await ctx.send(embed=embeds.error("Error", "Minimum number can't be bigger than maximum!"))
            return
        await ctx.send(embed=embeds.info("Random Number", f"Your random number: {random.randint(min_num, max_num)}"))

    @commands.hybrid_command(name="choose", description="Let the bot choose for you!")
    @app_commands.describe(options="Options separated by spaces")
    async def choose(self, ctx: commands.Context, *, options: str):
        option_list = options.split()
        if len(option_list) < 2:
            await ctx.send(embed=embeds.error("Error", "Please give at least 2 options!"))
            return
        await ctx.send(embed=embeds.info("I choose...", f"**{random.choice(option_list)}**!"))


async def setup(bot: commands.Bot):
    await bot.add_cog(FunMisc(bot))
