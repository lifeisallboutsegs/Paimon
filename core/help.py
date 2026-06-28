import discord

from discord.ext import commands


class CustomHelpCommand(commands.DefaultHelpCommand):
    """Custom help command that groups commands by proper categories!"""

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
        "settings": "Settings",
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

        category_commands = {}

        for cog, cmds in mapping.items():

            category = self.get_category(cog)

            filtered = await self.filter_commands(cmds, sort=True)

            if filtered:

                if category not in category_commands:

                    category_commands[category] = []

                category_commands[category].extend(filtered)

        destination = self.get_destination()

        help_text = []

        if self.context.bot.description:

            help_text.append(self.context.bot.description)

            help_text.append("")

        for category in sorted(category_commands.keys()):

            help_text.append(f"**{category}:**")

            cmd_names = [cmd.name for cmd in category_commands[category]]

            help_text.append(f"  `{'`, `'.join(cmd_names)}`")

            help_text.append("")

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

        filtered = await self.filter_commands(cog.get_commands(), sort=True)

        if filtered:

            for cmd in filtered:

                cmd_path = " ".join(self.get_command_path(cmd))

                help_text.append(
                    f"**{cmd_path}**: {cmd.description or 'No description'}"
                )

                if cmd.aliases:

                    help_text.append(f"  Aliases: `{'`, `'.join(cmd.aliases)}`")

        else:

            help_text.append("No commands available for this cog.")

        await destination.send("\n".join(help_text))

    def get_command_path(self, command):
        """Get the full command path as a list of command names."""

        path = []

        current = command

        while current:

            path.insert(0, current.name)

            current = current.parent

        return path

    async def send_group_help(self, group):
        """Send help for a command group!"""

        destination = self.get_destination()

        cmd_path = " ".join(self.get_command_path(group))

        help_text = []

        help_text.append(f"**{cmd_path}**")

        if group.description:

            help_text.append(group.description)

        if group.help:

            help_text.append("")

            help_text.append(group.help)

        help_text.append("")

        filtered = await self.filter_commands(group.commands, sort=True)

        if filtered:

            help_text.append("**Subcommands:**")

            help_text.append("")

            for cmd in filtered:

                subcmd_path = " ".join(self.get_command_path(cmd))

                help_text.append(f"**{subcmd_path}**")

                if cmd.description:

                    help_text.append(cmd.description)

                if cmd.aliases:

                    help_text.append(f"Aliases: `{'`, `'.join(cmd.aliases)}`")

                if cmd.usage:

                    help_text.append(
                        f"Usage: `{self.context.clean_prefix}{subcmd_path} {cmd.usage}`"
                    )

                elif cmd.signature:

                    help_text.append(
                        f"Usage: `{self.context.clean_prefix}{subcmd_path} {cmd.signature}`"
                    )

                    param_descs = {}

                    if (
                        hasattr(cmd, "app_command")
                        and cmd.app_command
                        and hasattr(cmd.app_command, "parameters")
                    ):

                        for param in cmd.app_command.parameters:

                            param_descs[param.name] = {
                                "desc": param.description or "No description",
                                "required": (
                                    param.required
                                    if hasattr(param, "required")
                                    else False
                                ),
                            }

                    if cmd.params:

                        help_text.append("")

                        help_text.append("**Parameters:**")

                        for name, param in cmd.params.items():

                            if name == "self" or name == "ctx":

                                continue

                            desc_info = param_descs.get(
                                name,
                                {"desc": "No description", "required": param.required},
                            )

                            is_required = param.default is param.empty

                            param_str = f"  `{name}`: {desc_info['desc']}"

                            if is_required:

                                param_str += " (required)"

                            else:

                                param_str += " (optional)"

                            help_text.append(param_str)

                if cmd.help:

                    help_text.append("")

                    help_text.append(cmd.help)

                help_text.append("")

                help_text.append("---")

                help_text.append("")

        else:

            help_text.append("No subcommands available for this group.")

        await destination.send("\n".join(help_text))

    async def send_command_help(self, command):
        """Send help for a specific command! If it's a subcommand, send group help instead!"""

        if command.parent:

            await self.send_group_help(command.parent)

        else:

            destination = self.get_destination()

            help_text = []

            cmd_path = " ".join(self.get_command_path(command))

            help_text.append(f"**{cmd_path}**")

            if command.description:

                help_text.append(command.description)

            if command.aliases:

                help_text.append(f"Aliases: `{'`, `'.join(command.aliases)}`")

            if command.usage:

                help_text.append(
                    f"Usage: `{self.context.clean_prefix}{cmd_path} {command.usage}`"
                )

            elif command.signature:

                help_text.append(
                    f"Usage: `{self.context.clean_prefix}{cmd_path} {command.signature}`"
                )

                param_descs = {}

                if (
                    hasattr(command, "app_command")
                    and command.app_command
                    and hasattr(command.app_command, "parameters")
                ):

                    for param in command.app_command.parameters:

                        param_descs[param.name] = {
                            "desc": param.description or "No description",
                            "required": (
                                param.required if hasattr(param, "required") else False
                            ),
                        }

                if command.params:

                    help_text.append("")

                    help_text.append("**Parameters:**")

                    for name, param in command.params.items():

                        if name == "self" or name == "ctx":

                            continue

                        desc_info = param_descs.get(
                            name, {"desc": "No description", "required": param.required}
                        )

                        is_required = param.default is param.empty

                        param_str = f"  `{name}`: {desc_info['desc']}"

                        if is_required:

                            param_str += " (required)"

                        else:

                            param_str += " (optional)"

                        help_text.append(param_str)

            if command.help:

                help_text.append("")

                help_text.append(command.help)

            await destination.send("\n".join(help_text))
