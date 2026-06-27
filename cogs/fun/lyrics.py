import re
import logging
import discord
from discord import app_commands
from discord.ext import commands
from bs4 import BeautifulSoup
import aiohttp
from config import Config

logger = logging.getLogger(__name__)


class Lyrics(commands.Cog):
    """Lyrics commands using Genius API!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.http_session = None

    async def cog_load(self):
        self.http_session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()

    def _get_http_session(self):
        if self.http_session is None or self.http_session.closed:
            self.http_session = aiohttp.ClientSession()
        return self.http_session

    async def search_songs(self, query: str):
        session = self._get_http_session()
        url = "https://api.genius.com/search"
        params = {"q": query}
        headers = {"Authorization": f"Bearer {Config.GENIUS_ACCESS_TOKEN}"}
        async with session.get(url, params=params, headers=headers) as resp:
            data = await resp.json()
            return data.get("response", {}).get("hits", [])

    async def scrape_lyrics(self, song_url: str):
        session = self._get_http_session()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        }

        try:
            async with session.get(song_url, headers=headers) as resp:
                logger.info("Scraping %s — HTTP %s", song_url, resp.status)
                if resp.status != 200:
                    logger.error("Non-200 response (%s) for %s", resp.status, song_url)
                    return None
                html = await resp.text()
        except Exception:
            logger.exception("Network error while fetching %s", song_url)
            return None

        soup = BeautifulSoup(html, "html.parser")
        containers = soup.find_all("div", attrs={"data-lyrics-container": "true"})

        if not containers:
            logger.warning("No [data-lyrics-container] found at %s", song_url)
            containers = soup.find_all("div", class_=re.compile(r"Lyrics__Container"))

        if not containers:
            logger.warning("No lyrics containers at all for %s", song_url)
            return None

        parts = []
        for container in containers:
            for br in container.find_all("br"):
                br.replace_with("\n")
            text = container.get_text(separator="\n").strip()
            if text:
                parts.append(text)

        lyrics = re.sub(r"\n{3,}", "\n\n", "\n\n".join(parts)).strip()
        logger.info("Scraped %d chars from %s", len(lyrics), song_url)
        return lyrics or None

    @commands.hybrid_command(name="lyrics", description="Get lyrics for a song!")
    @app_commands.describe(query="Song name to search for!")
    async def lyrics_command(self, ctx: commands.Context, *, query: str):
        await ctx.defer()

        try:
            hits = await self.search_songs(query)
        except Exception:
            logger.exception("search_songs failed for query %r", query)
            await ctx.send("❌ An error occurred while searching. Check logs.")
            return

        if not hits:
            await ctx.send("❌ Couldn't find any songs for that query!")
            return

        options = []
        for i, hit in enumerate(hits[:10]):
            result = hit["result"]
            label = f"{result['title']} by {result['primary_artist']['name']}"
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=str(i),
                    description=result["url"][:100],
                )
            )

        cog_ref = self

        class SongSelect(discord.ui.View):
            def __init__(self, hits, ctx):
                super().__init__(timeout=60)
                self.hits = hits
                self.ctx = ctx
                self.message = None

            @discord.ui.select(
                placeholder="Choose a song!", options=options, min_values=1, max_values=1
            )
            async def select_callback(
                self, interaction: discord.Interaction, select: discord.ui.Select
            ):
                if interaction.user != self.ctx.author:
                    await interaction.response.send_message(
                        "❌ This is not your menu!", ephemeral=True
                    )
                    return

                await interaction.response.defer()

                index = int(select.values[0])
                result = self.hits[index]["result"]

                try:
                    lyrics = await cog_ref.scrape_lyrics(result["url"])
                except Exception:
                    logger.exception("scrape_lyrics raised for %s", result["url"])
                    await interaction.followup.send(
                        "❌ Unexpected error while scraping lyrics.", ephemeral=True
                    )
                    self.stop()
                    return

                if not lyrics:
                    await interaction.followup.send(
                        f"❌ Couldn't scrape lyrics for **{result['title']}**.\n"
                        f"Try the page directly: {result['url']}",
                        ephemeral=True,
                    )
                    self.stop()
                    return

                embed = discord.Embed(
                    title=f"🎵 {result['title']}",
                    description=f"by {result['primary_artist']['name']}",
                    color=discord.Color.blue(),
                )
                embed.set_thumbnail(url=result["song_art_image_url"])
                embed.add_field(name="URL", value=result["url"], inline=False)

                preview = lyrics[:1021] + "..." if len(lyrics) > 1024 else lyrics
                embed.add_field(name="Lyrics", value=f"```\n{preview}\n```", inline=False)

                await self.message.edit(content="", embed=embed, view=None)
                self.stop()

            async def on_timeout(self):
                if self.message:
                    try:
                        await self.message.edit(content="⏰ Selection timed out.", view=None)
                    except discord.NotFound:
                        pass

        view = SongSelect(hits, ctx)
        sent_msg = await ctx.send(
            "🔍 Found these songs! Choose one from the dropdown to get lyrics.",
            view=view,
        )
        view.message = sent_msg


async def setup(bot: commands.Bot):
    await bot.add_cog(Lyrics(bot))
