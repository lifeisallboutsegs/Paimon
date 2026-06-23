
import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import is_owner_or_admin


class SettingsCore(commands.Cog):
    """Server settings commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(name="config", description="View or change server configuration.")
    async def config(self, ctx: commands.Context):
        cfg = await self.bot.db.get_guild_config(ctx.guild.id)
        await ctx.send(f"""**Server Configuration**
- Prefix: {cfg.get("prefix") or "(default)"}
- Welcome Channel: {f"<#{cfg['welcome_channel']}>" if cfg.get("welcome_channel") else "Not set"}
- Log Channel: {f"<#{cfg['log_channel']}>" if cfg.get("log_channel") else "Not set"}
- Mod Role: {f"<@&{cfg['mod_role']}>" if cfg.get("mod_role") else "Not set"}""")

    @config.command(name="prefix", description="Set a custom command prefix for this server.")
    @app_commands.describe(prefix="New prefix, e.g. !")
    @is_owner_or_admin()
    async def set_prefix(self, ctx: commands.Context, prefix: str):
        await self.bot.db.set_guild_config(ctx.guild.id, prefix=prefix)
        await ctx.send(f"✅ Prefix Updated\nNew prefix: `{prefix}`")

    @config.command(name="welcome_channel", description="Set the welcome message channel.")
    @app_commands.describe(channel="Channel for welcome messages")
    @is_owner_or_admin()
    async def set_welcome_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await self.bot.db.set_guild_config(ctx.guild.id, welcome_channel=channel.id)
        await ctx.send(f"✅ Welcome Channel Set\n{channel.mention}")

    @config.command(name="log_channel", description="Set the moderation log channel.")
    @app_commands.describe(channel="Channel for mod logs")
    @is_owner_or_admin()
    async def set_log_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await self.bot.db.set_guild_config(ctx.guild.id, log_channel=channel.id)
        await ctx.send(f"✅ Log Channel Set\n{channel.mention}")

    @config.command(name="mod_role", description="Set the role treated as moderator.")
    @app_commands.describe(role="Role granted moderation command access")
    @is_owner_or_admin()
    async def set_mod_role(self, ctx: commands.Context, role: discord.Role):
        await self.bot.db.set_guild_config(ctx.guild.id, mod_role=role.id)
        await ctx.send(f"✅ Mod Role Set\n{role.mention}")


async def setup(bot: commands.Bot):
    await bot.add_cog(SettingsCore(bot))
