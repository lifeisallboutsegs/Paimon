
import random

from discord import app_commands
from discord.ext import commands

from utils import embeds

EIGHT_BALL_RESPONSES = [
    "Yes.", "No.", "Maybe.", "Definitely.", "Ask again later.",
    "Absolutely not.", "Without a doubt.", "I wouldn't count on it.",
]


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="coinflip", description="Flip a coin.")
    async def coinflip(self, ctx: commands.Context):
        await ctx.send(embed=embeds.info("🪙 Coin Flip", random.choice(["Heads!", "Tails!"])))

    @commands.hybrid_command(name="8ball", description="Ask the magic 8-ball a question.")
    @app_commands.describe(question="What do you want to ask?")
    async def eight_ball(self, ctx: commands.Context, *, question: str):
        await ctx.send(embed=embeds.info(f"🎱 {question}", random.choice(EIGHT_BALL_RESPONSES)))

    @commands.hybrid_command(name="roll", description="Roll dice, e.g. 2d6.")
    @app_commands.describe(dice="Format: NdM, e.g. 2d6")
    async def roll(self, ctx: commands.Context, dice: str = "1d6"):
        try:
            count, sides = map(int, dice.lower().split("d"))
            count, sides = max(1, min(count, 100)), max(2, min(sides, 1000))
        except ValueError:
            await ctx.send(embed=embeds.error("Invalid Format", "Use `NdM`, e.g. `2d6`."))
            return
        rolls = [random.randint(1, sides) for _ in range(count)]
        await ctx.send(embed=embeds.info(f"🎲 Rolling {dice}", f"{rolls} = **{sum(rolls)}**"))


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
