import discord

from discord import app_commands

from discord.ext import commands

import json

from utils.checks import is_owner_or_admin


class LevelingRewards(commands.Cog):
    """Level-up reward management commands!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_rewards(self, guild_id: int) -> dict:
        data = await self.bot.db.kv_get(f"level_rewards:{guild_id}", "data")
        if data:
            return json.loads(data)
        return {}

    async def _save_rewards(self, guild_id: int, rewards: dict):
        await self.bot.db.kv_set(
            f"level_rewards:{guild_id}", "data", json.dumps(rewards)
        )

    @commands.hybrid_group(name="rewards", description="Manage level-up rewards!")
    async def rewards(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            rewards = await self._get_rewards(ctx.guild.id)
            if not rewards:
                await ctx.send("Level-Up Rewards: No rewards set up yet!")
                return
            msg = ["🎁 Level-Up Rewards"]
            sorted_rewards = sorted(rewards.items(), key=lambda x: int(x[0]))
            for level, reward in sorted_rewards:
                parts = []
                if reward.get("role"):
                    parts.append(f"<@&{reward['role']}>")
                if reward.get("coins", 0) > 0:
                    parts.append(f"{reward['coins']} coins")
                msg.append(f"Level {level}: {' and '.join(parts)}")
            await ctx.send("\n".join(msg))

    @rewards.command(
        name="add",
        description="Add a level-up reward!",
        help="Add a level-up reward! You must specify at least a role OR coins (or both).\nExamples:\n  !rewards add 10 @VIP\n  !rewards add 20 1000\n  !rewards add 30 @Legend 5000",
        usage="<level> [role_or_coins] [coins]",
        with_app_command=False,
    )
    @is_owner_or_admin()
    async def add_reward(self, ctx: commands.Context, level: int, *args):
        role = None
        coins = 0
        for arg in args:
            try:
                coins = int(arg)
                continue
            except ValueError:
                pass
            try:
                role = await commands.RoleConverter().convert(ctx, arg)
            except commands.RoleNotFound:
                await ctx.send(f"Error: '{arg}' is not a valid role!")
                return
        if role is None and coins <= 0:
            await ctx.send("Error: You need to specify at least a role or coins!")
            return
        rewards = await self._get_rewards(ctx.guild.id)
        reward_data = {}
        if role:
            reward_data["role"] = role.id
        if coins > 0:
            reward_data["coins"] = coins
        rewards[str(level)] = reward_data
        await self._save_rewards(ctx.guild.id, rewards)
        parts = []
        if role:
            parts.append(role.mention)
        if coins > 0:
            parts.append(f"{coins} coins")
        await ctx.send(f"✅ Reward Added! Level {level}: {' and '.join(parts)}!")

    @rewards.app_command.command(name="add", description="Add a level-up reward!")
    @app_commands.describe(
        level="The level to reward!", role="The role to give!", coins="Coins to give!"
    )
    @app_commands.guild_only()
    @is_owner_or_admin()
    async def add_reward_slash(
        self,
        interaction: discord.Interaction,
        level: int,
        role: discord.Role = None,
        coins: int = 0,
    ):
        ctx = await commands.Context.from_interaction(interaction)
        await self._save_reward(ctx, level, role, coins)

    async def _save_reward(self, ctx, level, role, coins):
        if role is None and coins <= 0:
            await ctx.send("Error: You need to specify at least a role or coins!")
            return
        rewards = await self._get_rewards(ctx.guild.id)
        reward_data = {}
        if role:
            reward_data["role"] = role.id
        if coins > 0:
            reward_data["coins"] = coins
        rewards[str(level)] = reward_data
        await self._save_rewards(ctx.guild.id, rewards)
        parts = []
        if role:
            parts.append(role.mention)
        if coins > 0:
            parts.append(f"{coins} coins")
        await ctx.send(f"✅ Reward Added! Level {level}: {' and '.join(parts)}!")

    @rewards.command(
        name="remove",
        description="Remove a level-up reward!",
        help="Remove a level-up reward for the specified level.\nExample: !rewards remove 10",
        usage="<level>",
    )
    @app_commands.describe(level="The level to remove the reward from!")
    @is_owner_or_admin()
    async def remove_reward(self, ctx: commands.Context, level: int):
        rewards = await self._get_rewards(ctx.guild.id)
        if str(level) in rewards:
            del rewards[str(level)]
            await self._save_rewards(ctx.guild.id, rewards)
            await ctx.send(f"✅ Reward Removed! Removed reward from level {level}!")
        else:
            await ctx.send("Error: No reward set for that level!")


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingRewards(bot))
