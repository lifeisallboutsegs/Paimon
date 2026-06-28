import discord

from discord import app_commands

from discord.ext import commands

from utils.checks import is_owner


class AdminStaff(commands.Cog):
    """Commands to manage bot admins and moderators"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if await ctx.bot.is_owner(ctx.author):
            return True

        from config import Config

        if ctx.author.id in Config.OWNER_IDS:
            return True

        raise commands.NotOwner()

    @commands.hybrid_group(name="botadmin", description="Manage bot admins")
    async def botadmin(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @botadmin.command(name="add", description="Add a bot admin")
    @app_commands.describe(member="Member to add as bot admin")
    async def add_bot_admin(self, ctx: commands.Context, member: discord.User):
        current = await self.bot.db.kv_get("bot_admins", "list")
        admins = set(map(int, current.split(","))) if current else set()
        if member.id in admins:
            await ctx.send("This user is already a bot admin!")
            return

        admins.add(member.id)
        await self.bot.db.kv_set("bot_admins", "list", ",".join(map(str, admins)))
        await ctx.send(f"Added {member.mention} as bot admin!")

    @botadmin.command(name="remove", description="Remove a bot admin")
    @app_commands.describe(member="Member to remove as bot admin")
    async def remove_bot_admin(self, ctx: commands.Context, member: discord.User):
        current = await self.bot.db.kv_get("bot_admins", "list")
        admins = set(map(int, current.split(","))) if current else set()
        if member.id not in admins:
            await ctx.send("This user is not a bot admin!")
            return

        admins.remove(member.id)
        await self.bot.db.kv_set("bot_admins", "list", ",".join(map(str, admins)))
        await ctx.send(f"Removed {member.mention} as bot admin!")

    @botadmin.command(name="list", description="List all bot admins")
    async def list_bot_admins(self, ctx: commands.Context):
        current = await self.bot.db.kv_get("bot_admins", "list")
        admins = list(map(int, current.split(","))) if current else []
        if not admins:
            await ctx.send("No bot admins configured!")
            return

        mentions = []
        for uid in admins:
            user = self.bot.get_user(uid)
            if user:
                mentions.append(user.mention)

            else:
                mentions.append(f"Unknown User ({uid})")

        await ctx.send("\n".join(mentions))

    @commands.hybrid_group(name="botmod", description="Manage bot moderators")
    async def botmod(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @botmod.command(name="add", description="Add a bot moderator")
    @app_commands.describe(member="Member to add as bot moderator")
    async def add_bot_mod(self, ctx: commands.Context, member: discord.User):
        current = await self.bot.db.kv_get("bot_mods", "list")
        mods = set(map(int, current.split(","))) if current else set()
        if member.id in mods:
            await ctx.send("This user is already a bot moderator!")
            return

        mods.add(member.id)
        await self.bot.db.kv_set("bot_mods", "list", ",".join(map(str, mods)))
        await ctx.send(f"Added {member.mention} as bot moderator!")

    @botmod.command(name="remove", description="Remove a bot moderator")
    @app_commands.describe(member="Member to remove as bot moderator")
    async def remove_bot_mod(self, ctx: commands.Context, member: discord.User):
        current = await self.bot.db.kv_get("bot_mods", "list")
        mods = set(map(int, current.split(","))) if current else set()
        if member.id not in mods:
            await ctx.send("This user is not a bot moderator!")
            return

        mods.remove(member.id)
        await self.bot.db.kv_set("bot_mods", "list", ",".join(map(str, mods)))
        await ctx.send(f"Removed {member.mention} as bot moderator!")

    @botmod.command(name="list", description="List all bot moderators")
    async def list_bot_mods(self, ctx: commands.Context):
        current = await self.bot.db.kv_get("bot_mods", "list")
        mods = list(map(int, current.split(","))) if current else []
        if not mods:
            await ctx.send("No bot moderators configured!")
            return

        mentions = []
        for uid in mods:
            user = self.bot.get_user(uid)
            if user:
                mentions.append(user.mention)

            else:
                mentions.append(f"Unknown User ({uid})")

        await ctx.send("\n".join(mentions))


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminStaff(bot))
