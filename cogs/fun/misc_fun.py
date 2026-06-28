import random
import aiohttp
from discord import app_commands
from discord.ext import commands


class FunMisc(commands.Cog):
    """Miscellaneous fun commands!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="joke", description="Tell a random joke!")
    async def joke(self, ctx: commands.Context):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.some-random-api.com/joke") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        joke = data.get("joke")
                        if joke:
                            await ctx.send(f"ℹ️ Joke\n{joke}")
                            return
        except Exception:
            pass

        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "What do you call fake spaghetti? An impasta!",
            "Why did the scarecrow win an award? He was outstanding in his field!",
            "What do you call a bear with no teeth? A gummy bear!",
            "Why don't eggs tell jokes? They'd crack each other up!",
            "What's orange and sounds like a parrot? A carrot!",
            "Why did the bicycle fall over? Because it was two-tired!",
            "What do you call a fish without eyes? A fsh!",
        ]
        await ctx.send(f"ℹ️ Joke\n{random.choice(jokes)}")

    @commands.hybrid_command(
        name="quote", description="Get a random anime quote!"
    )
    async def quote(self, ctx: commands.Context):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.some-random-api.com/animu/quote") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        quote = data.get("quote")
                        name = data.get("name")
                        anime = data.get("anime")
                        if quote:
                            if name or anime:
                                await ctx.send(f"ℹ️ Quote\n\"{quote}\"\n— {name or 'Unknown'} ({anime or 'Unknown'})")
                            else:
                                await ctx.send(f"ℹ️ Quote\n{quote}")
                            return
        except Exception:
            pass

        await ctx.send("❌ Oops! Could not fetch a quote right now.")

    @commands.hybrid_command(
        name="weather",
        description="Get weather info! (Note: Set OPENWEATHER_API_KEY in .env!)",
    )
    @app_commands.describe(city="City to check weather for!")
    async def weather(self, ctx: commands.Context, *, city: str):
        from config import Config

        if not Config.OPENWEATHER_API_KEY:
            await ctx.send("❌ Oops!\nSet OPENWEATHER_API_KEY in your .env first!")
            return
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&appid={Config.OPENWEATHER_API_KEY}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()
        except Exception:
            data = None

        if data and data.get("cod") == 200:
            await ctx.send(
                f"ℹ️ Weather in {data['name']}, {data['sys']['country']}\nTemperature: {data['main']['temp']}°C\nFeels like: {data['main']['feels_like']}°C\nDescription: {data['weather'][0]['description'].capitalize()}\nHumidity: {data['main']['humidity']}%\nWind speed: {data['wind']['speed']} m/s"
            )
        else:
            await ctx.send("❌ Oops!\nCouldn't get weather info!")

    @commands.hybrid_command(name="random_num", description="Get a random number!")
    @app_commands.describe(min_num="Minimum number", max_num="Maximum number")
    async def random_number(
        self, ctx: commands.Context, min_num: int = 1, max_num: int = 100
    ):
        if min_num > max_num:
            await ctx.send("❌ Error\nMinimum number can't be bigger than maximum!")
            return
        await ctx.send(
            f"ℹ️ Random Number\nYour random number: {random.randint(min_num, max_num)}"
        )

    @commands.hybrid_command(name="choose", description="Let the bot choose for you!")
    @app_commands.describe(options="Options separated by spaces")
    async def choose(self, ctx: commands.Context, *, options: str):
        option_list = options.split()
        if len(option_list) < 2:
            await ctx.send("❌ Error\nPlease give at least 2 options!")
            return
        await ctx.send(f"ℹ️ I choose...\n**{random.choice(option_list)}**!")


async def setup(bot: commands.Bot):
    await bot.add_cog(FunMisc(bot))
