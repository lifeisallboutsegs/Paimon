
import discord
import os
import sys
import subprocess
from discord import app_commands
from discord.ext import commands

from utils import embeds
from utils.checks import is_owner


class AdminMisc(commands.Cog):
    """Miscellaneous admin commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if await ctx.bot.is_owner(ctx.author):
            return True
        from config import Config
        if ctx.author.id in Config.OWNER_IDS:
            return True
        raise commands.NotOwner()

    @commands.command(name="sync")
    async def sync_commands(self, ctx: commands.Context, scope: str = "guild"):
        """Sync slash commands. scope: 'guild' (instant, this server only) or 'global' (~1hr to propagate)."""
        if scope == "guild" and ctx.guild:
            synced = await self.bot.tree.sync(guild=ctx.guild)
        else:
            synced = await self.bot.tree.sync()
        await ctx.send(embed=embeds.success("Synced", f"{len(synced)} command(s) ({scope})."))

    @commands.command(name="shutdown")
    async def shutdown(self, ctx: commands.Context):
        await ctx.send(embed=embeds.warning("Shutting Down", "Goodbye 👋"))
        await self.bot.close()

    @commands.command(name="restart")
    async def restart(self, ctx: commands.Context):
        await ctx.send(embed=embeds.warning("Restarting", "Be right back! 🔄"))
        await self.bot.close()
        # Respawn the bot
        os.execv(sys.executable, [sys.executable] + sys.argv)

    @commands.hybrid_command(name="status", description="Set the bot's status!")
    @app_commands.describe(activity_type="Type of activity", text="Text for the status", status="Bot status (online/idle/dnd)")
    @app_commands.choices(
        activity_type=[
            app_commands.Choice(name="Playing", value="playing"),
            app_commands.Choice(name="Listening to", value="listening"),
            app_commands.Choice(name="Watching", value="watching"),
            app_commands.Choice(name="Competing in", value="competing"),
            app_commands.Choice(name="Streaming", value="streaming")
        ],
        status=[
            app_commands.Choice(name="Online", value="online"),
            app_commands.Choice(name="Idle", value="idle"),
            app_commands.Choice(name="Do Not Disturb", value="dnd")
        ]
    )
    async def status(self, ctx: commands.Context, activity_type: str = "watching", *, text: str, status: str = "online"):
        # Map activity type string to discord.ActivityType
        activity_map = {
            "playing": discord.ActivityType.playing,
            "listening": discord.ActivityType.listening,
            "watching": discord.ActivityType.watching,
            "competing": discord.ActivityType.competing,
            "streaming": discord.ActivityType.streaming
        }
        
        # Map status string to discord.Status
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd
        }
        
        # Create activity
        if activity_type == "streaming":
            activity = discord.Streaming(name=text, url="https://twitch.tv/discord")  # Default twitch URL
        else:
            activity = discord.Activity(type=activity_map.get(activity_type, discord.ActivityType.watching), name=text)
        
        # Change presence
        await self.bot.change_presence(status=status_map.get(status, discord.Status.online), activity=activity)
        
        # Send confirmation
        activity_text = {
            "playing": "Playing",
            "listening": "Listening to",
            "watching": "Watching",
            "competing": "Competing in",
            "streaming": "Streaming"
        }.get(activity_type, "Watching")
        
        status_text = {
            "online": "Online",
            "idle": "Idle",
            "dnd": "Do Not Disturb"
        }.get(status, "Online")
        
        await ctx.send(embed=embeds.success("Status Updated", f"New status: {status_text} - {activity_text} **{text}**"))


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminMisc(bot))
