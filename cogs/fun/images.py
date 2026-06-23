
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

from utils import embeds


class FunImages(commands.Cog):
    """Random images and facts commands!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()

    async def _fetch(self, url, json=True):
        try:
            async with self.session.get(url) as resp:
                if json:
                    return await resp.json()
                return await resp.text()
        except Exception as e:
            print(f"API fetch error: {e}")
            return None

    @commands.hybrid_command(name="cat", description="Get a random cat picture!")
    async def cat(self, ctx: commands.Context):
        data = await self._fetch("https://api.thecatapi.com/v1/images/search")
        if data and len(data) > 0:
            embed = embeds.info("🐱 Random Cat!", "")
            embed.set_image(url=data[0]["url"])
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embeds.error("Oops!", "Couldn't get a cat picture!"))

    @commands.hybrid_command(name="dog", description="Get a random dog picture!")
    async def dog(self, ctx: commands.Context):
        data = await self._fetch("https://api.thedogapi.com/v1/images/search")
        if data and len(data) > 0:
            embed = embeds.info("🐶 Random Dog!", "")
            embed.set_image(url=data[0]["url"])
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embeds.error("Oops!", "Couldn't get a dog picture!"))

    @commands.hybrid_command(name="meme", description="Get a random meme!")
    async def meme(self, ctx: commands.Context):
        data = await self._fetch("https://meme-api.com/gimme")
        if data:
            embed = embeds.info(f"😂 Meme: {data['title']}", f"r/{data['subreddit']}")
            embed.set_image(url=data["url"])
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embeds.error("Oops!", "Couldn't get a meme!"))

    @commands.hybrid_command(name="fox", description="Get a random fox picture!")
    async def fox(self, ctx: commands.Context):
        data = await self._fetch("https://randomfox.ca/floof/")
        if data:
            embed = embeds.info("🦊 Random Fox!", "")
            embed.set_image(url=data["image"])
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embeds.error("Oops!", "Couldn't get a fox picture!"))

    @commands.hybrid_command(name="duck", description="Get a random duck picture!")
    async def duck(self, ctx: commands.Context):
        data = await self._fetch("https://random-d.uk/api/random")
        if data:
            embed = embeds.info("🦆 Random Duck!", "")
            embed.set_image(url=data["url"])
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embeds.error("Oops!", "Couldn't get a duck picture!"))

    @commands.hybrid_command(name="quote", description="Get a random quote!")
    async def quote(self, ctx: commands.Context):
        data = await self._fetch("https://api.quotable.io/random")
        if data:
            embed = embeds.info("💬 Quote!", f"\"{data['content']}\"\n\n- {data['author']}")
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embeds.error("Oops!", "Couldn't get a quote!"))

    @commands.hybrid_command(name="weather", description="Get weather info! (Note: Set OPENWEATHER_API_KEY in .env!)")
    @app_commands.describe(city="City to check weather for!")
    async def weather(self, ctx: commands.Context, *, city: str):
        from config import Config
        if not Config.OPENWEATHER_API_KEY:
            await ctx.send(embed=embeds.error("Oops!", "Set OPENWEATHER_API_KEY in your .env first!"))
            return
        
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&appid={Config.OPENWEATHER_API_KEY}"
        data = await self._fetch(url)
        if data and data.get("cod") == 200:
            embed = embeds.info(f"🌤️ Weather in {data['name']}, {data['sys']['country']}", "")
            embed.add_field(name="Temperature", value=f"{data['main']['temp']}°C")
            embed.add_field(name="Feels like", value=f"{data['main']['feels_like']}°C")
            embed.add_field(name="Description", value=data['weather'][0]['description'].capitalize())
            embed.add_field(name="Humidity", value=f"{data['main']['humidity']}%")
            embed.add_field(name="Wind speed", value=f"{data['wind']['speed']} m/s")
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embeds.error("Oops!", "Couldn't get weather info!"))


async def setup(bot: commands.Bot):
    await bot.add_cog(FunImages(bot))
