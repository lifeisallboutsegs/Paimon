
import discord
from discord import app_commands
from discord.ext import commands
import json

from utils import embeds
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
        await self.bot.db.kv_set(f"level_rewards:{guild_id}", "data", json.dumps(rewards))

    @commands.hybrid_group(name="rewards", description="Manage level-up rewards!")
    async def rewards(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            rewards = await self._get_rewards(ctx.guild.id)
            if not rewards:
                await ctx.send(embed=embeds.info("Level-Up Rewards", "No rewards set up yet!"))
                return
            
            embed = embeds.info("🎁 Level-Up Rewards", "")
            sorted_rewards = sorted(rewards.items(), key=lambda x: int(x[0]))
            desc = []
            for level, reward in sorted_rewards:
                role_mention = f"<@&{reward['role']}>" if reward.get('role') else "No role"
                coin_amount = reward.get('coins', 0)
                desc.append(f"**Level {level}**: {role_mention}, {coin_amount} coins")
            embed.description = "\n".join(desc)
            await ctx.send(embed=embed)

    @rewards.command(name="add", description="Add a level-up reward!")
    @app_commands.describe(level="The level to reward!", role="The role to give!", coins="Coins to give!")
    @is_owner_or_admin()
    async def add_reward(self, ctx: commands.Context, level: int, role: discord.Role = None, coins: int = 0):
        rewards = await self._get_rewards(ctx.guild.id)
        rewards[str(level)] = {"role": role.id if role else None, "coins": coins}
        await self._save_rewards(ctx.guild.id, rewards)
        
        parts = []
        if role:
            parts.append(role.mention)
        if coins > 0:
            parts.append(f"{coins} coins")
        
        await ctx.send(embed=embeds.success("Reward Added!", f"Level {level}: {' and '.join(parts)}!"))

    @rewards.command(name="remove", description="Remove a level-up reward!")
    @app_commands.describe(level="The level to remove the reward from!")
    @is_owner_or_admin()
    async def remove_reward(self, ctx: commands.Context, level: int):
        rewards = await self._get_rewards(ctx.guild.id)
        if str(level) in rewards:
            del rewards[str(level)]
            await self._save_rewards(ctx.guild.id, rewards)
            await ctx.send(embed=embeds.success("Reward Removed!", f"Removed reward from level {level}!"))
        else:
            await ctx.send(embed=embeds.error("Error!", "No reward set for that level!"))


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingRewards(bot))
