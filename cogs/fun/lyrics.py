import re
import discord
from discord import app_commands
from discord.ext import commands
from bs4 import BeautifulSoup
import aiohttp
from config import Config

class Lyrics(commands.Cog):
    """Lyrics commands using Genius API!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.http_session = None

    async def cog_load(self):
        self.http_session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.http_session and (not self.http_session.closed):
            await self.http_session.close()

    def _get_http_session(self):
        if self.http_session is None or self.http_session.closed:
            self.http_session = aiohttp.ClientSession()
        return self.http_session

    async def search_songs(self, query: str):
        """Search Genius for songs"""
        session = self._get_http_session()
        url = 'https://api.genius.com/search'
        params = {'q': query}
        headers = {'Authorization': f'Bearer {Config.GENIUS_ACCESS_TOKEN}'}
        async with session.get(url, params=params, headers=headers) as resp:
            data = await resp.json()
            return data.get('response', {}).get('hits', [])

    async def scrape_lyrics(self, song_url: str):
        """Scrape lyrics from Genius song page"""
        session = self._get_http_session()
        headers = {'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7', 'accept-language': 'en-US,en;q=0.9', 'cache-control': 'max-age=0', 'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"', 'sec-fetch-dest': 'document', 'sec-fetch-mode': 'navigate', 'sec-fetch-site': 'none', 'sec-fetch-user': '?1', 'upgrade-insecure-requests': '1', 'cookie': '_genius_ab_test_cohort=13'}
        async with session.get(song_url, headers=headers) as resp:
            html = await resp.text()
        soup = BeautifulSoup(html, 'html.parser')
        lyrics_containers = []
        lyrics_containers.extend(soup.find_all('div', attrs={'data-lyrics-container': 'true'}))
        if not lyrics_containers:
            lyrics_containers.extend(soup.find_all('div', class_='lyrics'))
        if not lyrics_containers:
            lyrics_containers.extend(soup.find_all('div', class_=re.compile('Lyrics__Container')))
        lyrics_text = ''
        for container in lyrics_containers:
            for unwanted in container.find_all(attrs={'data-exclude-from-selection': 'true'}):
                unwanted.decompose()
            for unwanted in container.find_all('div', class_=re.compile('LyricsHeader__Container')):
                unwanted.decompose()
            for br in container.find_all('br'):
                br.replace_with('\n')
            container_text = container.get_text(separator='\n').strip()
            if container_text:
                lyrics_text += container_text + '\n\n'
        lyrics_text = re.sub('\\n{3,}', '\n\n', lyrics_text).strip()
        return lyrics_text

    @commands.hybrid_command(name='lyrics', description='Get lyrics for a song!')
    @app_commands.describe(query='Song name to search for!')
    async def lyrics_command(self, ctx: commands.Context, *, query: str):
        await ctx.defer()
        hits = await self.search_songs(query)
        if not hits:
            await ctx.send("❌ Couldn't find any songs for that query!")
            return
        options = []
        for i, hit in enumerate(hits[:10]):
            result = hit['result']
            options.append(discord.SelectOption(label=f"{result['title']} by {result['primary_artist']['name']}", value=str(i), description=result['url'][:100] if len(result['url']) > 100 else result['url']))

        class SongSelect(discord.ui.View):

            def __init__(self, hits, cog, ctx):
                super().__init__(timeout=60)
                self.hits = hits
                self.cog = cog
                self.ctx = ctx
                self.message = None

            @discord.ui.select(placeholder='Choose a song!', options=options, min_values=1, max_values=1)
            async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
                if interaction.user != ctx.author:
                    await interaction.response.send_message('❌ This is not your menu!', ephemeral=True)
                    return
                index = int(select.values[0])
                result = self.hits[index]['result']
                lyrics = await self.cog.scrape_lyrics(result['url'])
                if not lyrics:
                    await interaction.response.send_message(f"❌ Couldn't scrape lyrics for {result['title']}!\n{result['url']}", ephemeral=True)
                    self.stop()
                    return
                embed = discord.Embed(title=f"🎵 {result['title']}", description=f"by {result['primary_artist']['name']}", color=discord.Color.blue())
                embed.set_thumbnail(url=result['song_art_image_url'])
                embed.set_image(url=result['header_image_thumbnail_url'])
                embed.add_field(name='URL', value=result['url'], inline=False)
                if len(lyrics) > 1024:
                    lyrics = lyrics[:1021] + '...'
                embed.add_field(name='Lyrics', value=f'```\n{lyrics}\n```', inline=False)
                await self.message.edit(content='', embed=embed, view=None)
                await interaction.response.defer()
                self.stop()
        view = SongSelect(hits, self, ctx)
        sent_msg = await ctx.send('🔍 Found these songs! Choose one from the dropdown below to get lyrics!', view=view)
        view.message = sent_msg

async def setup(bot: commands.Bot):
    await bot.add_cog(Lyrics(bot))