
import discord
from discord import app_commands
from discord.ext import commands
from utils import embeds


class UtilityHelp(commands.Cog):
    """Custom help command!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="help", description="Shows all available commands!")
    @app_commands.describe(category="Optional: Show commands for a specific category")
    async def help_command(self, ctx: commands.Context, category: str = None):
        # List of valid categories
        categories = {
            "admin": "🛠️ Admin Commands (Bot Owner Only)",
            "moderation": "🔨 Moderation Commands",
            "economy": "💰 Economy Commands",
            "leveling": "📈 Leveling Commands",
            "fun": "🎉 Fun Commands",
            "utility": "🔧 Utility Commands",
            "settings": "⚙️ Settings Commands"
        }
        
        if category and category.lower() not in categories:
            await ctx.send(embed=embeds.error("Oops!", f"Invalid category! Use one of: {', '.join(categories.keys())}"))
            return
        
        embed = embeds.info("🤖 Bot Help", "")
        
        if category:
            cat = category.lower()
            embed.title = f"{categories[cat]} Help"
            commands_list = []
            for cmd in self.bot.walk_commands():
                if cmd.cog_name:
                    # Check if cog name matches category
                    if cat in cmd.cog_name.lower():
                        if cmd.name not in ["jishaku"]:  # Skip debug commands
                            desc = cmd.description or "No description"
                            commands_list.append(f"**{cmd.name}**: {desc}")
            if commands_list:
                embed.description = "\n".join(commands_list)
            else:
                embed.description = "No commands found for this category."
        else:
            # Show all categories
            for cat, desc in categories.items():
                commands_list = []
                for cmd in self.bot.walk_commands():
                    if cmd.cog_name:
                        if cat in cmd.cog_name.lower() and cmd.name not in ["jishaku"]:
                            commands_list.append(cmd.name)
                if commands_list:
                    embed.add_field(name=desc, value=f"`{', '.join(commands_list)}`", inline=False)
        
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityHelp(bot))
