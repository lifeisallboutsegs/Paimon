import discord
COLOR_SUCCESS = discord.Color.green()
COLOR_ERROR = discord.Color.red()
COLOR_WARNING = discord.Color.orange()
COLOR_INFO = discord.Color.blurple()

def success(title: str, description: str='') -> discord.Embed:
    return discord.Embed(title=f'✅ {title}', description=description, color=COLOR_SUCCESS)

def error(title: str, description: str='') -> discord.Embed:
    return discord.Embed(title=f'❌ {title}', description=description, color=COLOR_ERROR)

def warning(title: str, description: str='') -> discord.Embed:
    return discord.Embed(title=f'⚠️ {title}', description=description, color=COLOR_WARNING)

def info(title: str, description: str='') -> discord.Embed:
    return discord.Embed(title=f'ℹ️ {title}', description=description, color=COLOR_INFO)
