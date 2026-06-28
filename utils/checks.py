from discord.ext import commands

from config import Config


def is_owner():

    async def predicate(ctx: commands.Context) -> bool:

        if await ctx.bot.is_owner(ctx.author):

            return True

        if ctx.author.id in Config.OWNER_IDS:

            return True

        raise commands.NotOwner()

    return commands.check(predicate)


def is_bot_admin():

    async def predicate(ctx: commands.Context) -> bool:

        if await ctx.bot.is_owner(ctx.author):

            return True

        if ctx.author.id in Config.OWNER_IDS:

            return True

        if ctx.author.id in Config.BOT_ADMIN_IDS:

            return True

        current = await ctx.bot.db.kv_get("bot_admins", "list")

        db_admins = set(map(int, current.split(","))) if current else set()

        if ctx.author.id in db_admins:

            return True

        raise commands.MissingPermissions(["bot_admin"])

    return commands.check(predicate)


def is_bot_moderator():

    async def predicate(ctx: commands.Context) -> bool:

        if await ctx.bot.is_owner(ctx.author):

            return True

        if ctx.author.id in Config.OWNER_IDS:

            return True

        if ctx.author.id in Config.BOT_ADMIN_IDS:

            return True

        if ctx.author.id in Config.BOT_MODERATOR_IDS:

            return True

        current = await ctx.bot.db.kv_get("bot_admins", "list")

        db_admins = set(map(int, current.split(","))) if current else set()

        if ctx.author.id in db_admins:

            return True

        current = await ctx.bot.db.kv_get("bot_mods", "list")

        db_mods = set(map(int, current.split(","))) if current else set()

        if ctx.author.id in db_mods:

            return True

        raise commands.MissingPermissions(["bot_moderator"])

    return commands.check(predicate)


def is_owner_or_admin():

    async def predicate(ctx: commands.Context) -> bool:

        if await ctx.bot.is_owner(ctx.author):

            return True

        if ctx.author.id in Config.OWNER_IDS:

            return True

        if ctx.author.id in Config.BOT_ADMIN_IDS:

            return True

        current = await ctx.bot.db.kv_get("bot_admins", "list")

        db_admins = set(map(int, current.split(","))) if current else set()

        if ctx.author.id in db_admins:

            return True

        if ctx.guild and ctx.author.guild_permissions.administrator:

            return True

        raise commands.MissingPermissions(["administrator"])

    return commands.check(predicate)


def mod_role_or_permission(permission: str):
    """Allow if the user has the given guild permission OR the server's configured mod role OR is a bot moderator/admin/owner."""

    async def predicate(ctx: commands.Context) -> bool:

        if await ctx.bot.is_owner(ctx.author):

            return True

        if ctx.author.id in Config.OWNER_IDS:

            return True

        if ctx.author.id in Config.BOT_ADMIN_IDS:

            return True

        if ctx.author.id in Config.BOT_MODERATOR_IDS:

            return True

        current = await ctx.bot.db.kv_get("bot_admins", "list")

        db_admins = set(map(int, current.split(","))) if current else set()

        if ctx.author.id in db_admins:

            return True

        current = await ctx.bot.db.kv_get("bot_mods", "list")

        db_mods = set(map(int, current.split(","))) if current else set()

        if ctx.author.id in db_mods:

            return True

        if ctx.guild is None:

            return False

        if getattr(ctx.author.guild_permissions, permission, False):

            return True

        cfg = await ctx.bot.db.get_guild_config(ctx.guild.id)

        mod_role_id = cfg.get("mod_role")

        if mod_role_id and any((r.id == mod_role_id for r in ctx.author.roles)):

            return True

        raise commands.MissingPermissions([permission])

    return commands.check(predicate)
