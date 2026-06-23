
import random

import discord
from discord import app_commands
from discord.ext import commands

from utils import embeds


class FunGames(commands.Cog):
    """Fun games commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="coinflip", description="Flip a coin.")
    async def coinflip(self, ctx: commands.Context):
        await ctx.send(embed=embeds.info("Coin Flip", random.choice(["Heads!", "Tails!"])))

    @commands.hybrid_command(name="8ball", description="Ask the magic 8-ball a question.")
    @app_commands.describe(question="What do you want to ask?")
    async def eight_ball(self, ctx: commands.Context, *, question: str):
        responses = [
            "Yes.", "No.", "Maybe.", "Definitely.", "Ask again later.",
            "Absolutely not.", "Without a doubt.", "I wouldn't count on it.",
        ]
        await ctx.send(embed=embeds.info(question, random.choice(responses)))

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
        await ctx.send(embed=embeds.info(f"Rolling {dice}", f"{rolls} = **{sum(rolls)}**"))

    @commands.hybrid_command(name="rps", description="Play rock-paper-scissors!")
    @app_commands.describe(choice="Your choice (rock, paper, scissors)")
    async def rps(self, ctx: commands.Context, choice: str):
        choice = choice.lower()
        if choice not in ["rock", "paper", "scissors"]:
            await ctx.send(embed=embeds.error("Invalid Choice", "Choose rock, paper, or scissors!"))
            return
        bot_choice = random.choice(["rock", "paper", "scissors"])
        if choice == bot_choice:
            result = "It's a tie!"
        elif (choice == "rock" and bot_choice == "scissors") or \
             (choice == "paper" and bot_choice == "rock") or \
             (choice == "scissors" and bot_choice == "paper"):
            result = "You win!"
        else:
            result = "You lose!"
        await ctx.send(embed=embeds.info(
            "Rock-Paper-Scissors",
            f"You chose: **{choice}**\nBot chose: **{bot_choice}**\n\n{result}"
        ))


async def setup(bot: commands.Bot):
    await bot.add_cog(FunGames(bot))
