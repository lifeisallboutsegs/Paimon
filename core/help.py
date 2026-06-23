
import discord
from discord.ext import commands


class CustomHelpCommand(commands.DefaultHelpCommand):
    """Custom help command that groups commands by proper categories!"""
    
    # Map cog names to user-friendly categories
    CATEGORY_MAP = {
        "admin": "Admin",
        "bot_staff": "Admin",
        "cogs": "Admin",
        "misc": "Admin",
        "moderation": "Moderation",
        "punishments": "Moderation",
        "warnings": "Moderation",
        "economy": "Economy",
        "leveling": "Leveling",
        "fun": "Fun",
        "funai": "Fun",
        "fungames": "Fun",
        "funmisc": "Fun",
        "funsocial": "Fun",
        "utility": "Utility",
        "settings": "Settings"
    }

    def __init__(self):
        super().__init__(no_category="Commands")

    def get_category(self, cog: commands.Cog | None) -> str:
        """Get the user-friendly category for a cog!"""
        if cog is None:
            return "Commands"
        cog_name = cog.qualified_name.lower()
        for key, category in self.CATEGORY_MAP.items():
            if key in cog_name:
                return category
        return "Commands"

    async def send_bot_help(self, mapping):
        """Send help for the whole bot!"""
        # Group commands by category
        category_commands = {}
        for cog, cmds in mapping.items():
            category = self.get_category(cog)
            # Filter out hidden commands
            filtered = await self.filter_commands(cmds, sort=True)
            if filtered:
                if category not in category_commands:
                    category_commands[category] = []
                category_commands[category].extend(filtered)
        
        # Build the message
        destination = self.get_destination()
        help_text = []
        
        # Add bot description (if any)
        if self.context.bot.description:
            help_text.append(self.context.bot.description)
            help_text.append("")
        
        # Add each category
        for category in sorted(category_commands.keys()):
            help_text.append(f"**{category}:**")
            cmd_names = [cmd.name for cmd in category_commands[category]]
            help_text.append(f"  `{'`, `'.join(cmd_names)}`")
            help_text.append("")
        
        # Send the message
        await destination.send("\n".join(help_text))

    async def send_cog_help(self, cog):
        """Send help for a specific cog!"""
        category = self.get_category(cog)
        destination = self.get_destination()
        help_text = []
        help_text.append(f"**{category} - {cog.qualified_name}**")
        if cog.description:
            help_text.append(cog.description)
        help_text.append("")
        
        # Filter commands
        filtered = await self.filter_commands(cog.get_commands(), sort=True)
        if filtered:
            for cmd in filtered:
                help_text.append(f"**{cmd.name}**: {cmd.description or 'No description'}")
                if cmd.aliases:
                    help_text.append(f"  Aliases: `{'`, `'.join(cmd.aliases)}`")
        else:
            help_text.append("No commands available for this cog.")
        
        await destination.send("\n".join(help_text))

    async def send_command_help(self, command):
        """Send help for a specific command!"""
        destination = self.get_destination()
        help_text = []
        help_text.append(f"**{command.name}**")
        if command.description:
            help_text.append(command.description)
        if command.aliases:
            help_text.append(f"Aliases: `{'`, `'.join(command.aliases)}`")
        if command.usage:
            help_text.append(f"Usage: `{self.context.clean_prefix}{command.name} {command.usage}`")
        elif command.signature:
            help_text.append(f"Usage: `{self.context.clean_prefix}{command.name} {command.signature}`")
        if command.help:
            help_text.append("")
            help_text.append(command.help)
        await destination.send("\n".join(help_text))
