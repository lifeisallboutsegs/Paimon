
import logging

import discord
from discord.ext import commands

from utils import embeds

logger = logging.getLogger("bot.errors")


class Errors(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingPermissions):
            perms = ", ".join(error.missing_permissions)
            await ctx.send(embed=embeds.error("Missing Permissions", f"You need: `{perms}`"))
            return

        if isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions)
            await ctx.send(embed=embeds.error("I'm Missing Permissions", f"I need: `{perms}`"))
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=embeds.error("Missing Argument", f"`{error.param.name}` is required."))
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send(embed=embeds.error("Invalid Argument", str(error)))
            return

        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=embeds.warning("Cooldown", f"Try again in {error.retry_after:.1f}s."))
            return

        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send(embed=embeds.error("Server Only", "This command can't be used in DMs."))
            return

        logger.exception("Unhandled command error in %s", ctx.command, exc_info=error)
        await ctx.send(embed=embeds.error("Unexpected Error", "Something went wrong and has been logged."))

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error):
        logger.exception("Unhandled app command error", exc_info=error)
        if interaction.response.is_done():
            await interaction.followup.send("Something went wrong.", ephemeral=True)
        else:
            await interaction.response.send_message("Something went wrong.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Errors(bot))
