
from discord.ext import commands


def is_owner_or_admin():
    async def predicate(ctx: commands.Context) -> bool:
        if await ctx.bot.is_owner(ctx.author):
            return True
        if ctx.guild and ctx.author.guild_permissions.administrator:
            return True
        raise commands.MissingPermissions(["administrator"])
    return commands.check(predicate)


def mod_role_or_permission(permission: str):
    """Allow if the user has the given guild permission OR the server's configured mod role."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            return False
        if getattr(ctx.author.guild_permissions, permission, False):
            return True
        cfg = await ctx.bot.db.get_guild_config(ctx.guild.id)
        mod_role_id = cfg.get("mod_role")
        if mod_role_id and any(r.id == mod_role_id for r in ctx.author.roles):
            return True
        raise commands.MissingPermissions([permission])
    return commands.check(predicate)
