import random

import discord

from discord import app_commands

from discord.ext import commands


class FunGames(commands.Cog):
    """Fun games commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="rps", description="Play rock-paper-scissors!")
    @app_commands.describe(choice="Your choice (rock, paper, scissors)")
    async def rps(self, ctx: commands.Context, choice: str):
        choice = choice.lower()
        if choice not in ["rock", "paper", "scissors"]:
            await ctx.send("❌ Invalid Choice\nChoose rock, paper, or scissors!")
            return

        bot_choice = random.choice(["rock", "paper", "scissors"])
        if choice == bot_choice:
            result = "It's a tie!"

        elif (
            choice == "rock"
            and bot_choice == "scissors"
            or (choice == "paper" and bot_choice == "rock")
            or (choice == "scissors" and bot_choice == "paper")
        ):
            result = "You win!"

        else:
            result = "You lose!"

        await ctx.send(
            f"ℹ️ Rock-Paper-Scissors\nYou chose: **{choice}**\nBot chose: **{bot_choice}**\n\n{result}"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(FunGames(bot))
