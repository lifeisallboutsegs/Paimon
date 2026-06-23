
import random
import json

import discord
from discord import app_commands
from discord.ext import commands

from utils import embeds
from utils.helpers import xp_for_level


class LevelingCore(commands.Cog):
    """Leveling system commands and listener"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_rewards(self, guild_id: int) -> dict:
        data = await self.bot.db.kv_get(f"level_rewards:{guild_id}", "data")
        if data:
            return json.loads(data)
        return {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        # Give random XP between 15 and 25 per message
        xp_amount = random.randint(15, 25)
        result = await self.bot.db.add_xp(message.guild.id, message.author.id, xp_amount)
        if result is not None:
            leveled_up, new_level = result
            if leveled_up:
                rewards = await self._get_rewards(message.guild.id)
                reward_str = []
                if str(new_level) in rewards:
                    reward = rewards[str(new_level)]
                    if reward.get('role'):
                        role = message.guild.get_role(reward['role'])
                        if role and role not in message.author.roles:
                            try:
                                await message.author.add_roles(role, reason=f"Level {new_level} reward!")
                                reward_str.append(role.mention)
                            except:
                                pass
                    if reward.get('coins') and reward['coins'] > 0:
                        await self.bot.db.add_balance(message.guild.id, message.author.id, reward['coins'])
                        reward_str.append(f"{reward['coins']} coins")
                
                embed_desc = f"{message.author.mention} is now **Level {new_level}**!"
                if reward_str:
                    embed_desc += f"\n🎁 Rewards: {' and '.join(reward_str)}!"
                
                embed = embeds.success("Level Up! 🎉", embed_desc)
                await message.channel.send(embed=embed)

    @commands.hybrid_command(name="level", description="Check your or someone else's level and XP.")
    @app_commands.describe(member="Member to check (defaults to you)")
    async def level(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        data = await self.bot.db.get_level(ctx.guild.id, member.id)
        level = data["level"]
        current_xp = data["xp"]
        needed_xp = xp_for_level(level)
        embed = embeds.info(f"{member.display_name}'s Level", "")
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Level", value=f"🎉 {level}")
        embed.add_field(name="XP", value=f"{current_xp}/{needed_xp}")
        # Progress bar
        bar_length = 15
        progress = int((current_xp / needed_xp) * bar_length)
        bar = "█" * progress + "░" * (bar_length - progress)
        embed.add_field(name="Progress", value=f"[{bar}] {int((current_xp/needed_xp)*100)}%", inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="leaderboard", description="Show the server's level leaderboard.")
    async def leaderboard(self, ctx: commands.Context):
        data = await self.bot.db.get_level_leaderboard(ctx.guild.id)
        embed = embeds.info("🏆 Level Leaderboard", "")
        if not data:
            embed.description = "No one has any XP yet!"
        else:
            lines = []
            for i, entry in enumerate(data, 1):
                member = ctx.guild.get_member(entry["user_id"])
                name = member.display_name if member else f"Unknown User ({entry['user_id']})"
                lines.append(f"**#{i}** {name} - Level {entry['level']} ({entry['xp']} XP)")
            embed.description = "\n".join(lines)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingCore(bot))
