from discord import app_commands

from discord.ext import commands

from utils.checks import mod_role_or_permission


class ModerationMessages(commands.Cog):
    """Message moderation commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="clear",
        description="Delete a number of recent messages.",
        aliases=["purge"],
    )
    @app_commands.describe(amount="How many messages to delete (max 100)")
    @mod_role_or_permission("manage_messages")
    @commands.bot_has_permissions(manage_messages=True)
    async def clear(self, ctx: commands.Context, amount: int = 10):
        if amount < 1 or amount > 100:
            return await ctx.send(
                "❌ Invalid Amount\nAmount must be between 1 and 100."
            )
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(
            f"✅ Messages Cleared\nDeleted {len(deleted) - 1} messages."
        )
        await msg.delete(delay=3)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationMessages(bot))
