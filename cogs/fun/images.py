import io
import urllib.parse
from typing import Literal, Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

EMBED_COLOR = discord.Color.blurple()


class FunImages(commands.Cog):
    """Random images, memes, and fun image-generation commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    async def _fetch_json(self, url: str):
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except Exception as e:
            print(f"[FunImages] JSON fetch error for {url}: {e}")
            return None

    def _resolve_user(self, ctx: commands.Context, member: Optional[discord.User]) -> discord.abc.User:
        return member or ctx.author

    def _avatar_url(self, user: discord.abc.User) -> str:
        return str(user.display_avatar.with_format("png").with_size(1024))

    def _display_name(self, user: discord.abc.User) -> str:
        """Best available display name: server nickname if we have a Member, else username."""
        return getattr(user, "display_name", None) or user.name

    def _enc(self, value: str) -> str:
        return urllib.parse.quote_plus(value, safe="")

    async def _send_embed_image(self, ctx: commands.Context, title: str, image_url: str, footer: Optional[str] = None, url: Optional[str] = None):
        embed = discord.Embed(title=title, color=EMBED_COLOR, url=url)
        embed.set_image(url=image_url)
        if footer:
            embed.set_footer(text=footer)
        await ctx.send(embed=embed)

    async def _send_generated_image(self, ctx: commands.Context, url: str, filename: str, friendly_name: str):
        """Downloads a dynamically generated image (canvas APIs) and uploads it,
        since these endpoints return raw image bytes rather than a stable URL."""
        try:
            async with self.session.get(url) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if resp.status != 200 or "image" not in content_type:
                    detail = ""
                    try:
                        body = await resp.json()
                        detail = body.get("error") or body.get("message") or ""
                    except Exception:
                        pass
                    msg = f"❌ Couldn't generate **{friendly_name}**."
                    if resp.status in (401, 403):
                        msg += " This feature may require a premium API key that hasn't been configured."
                    if detail:
                        msg += f"\n> {detail}"
                    await ctx.send(msg)
                    return

                data = await resp.read()
                if not data:
                    raise ValueError("Empty response")

                ext = "png"
                if "gif" in content_type:
                    ext = "gif"
                elif "webp" in content_type:
                    ext = "webp"
                elif "jpeg" in content_type or "jpg" in content_type:
                    ext = "jpg"
                if not filename.lower().endswith((".png", ".gif", ".jpg", ".jpeg", ".webp")):
                    filename = f"{filename}.{ext}"

                await ctx.send(file=discord.File(io.BytesIO(data), filename=filename))
        except Exception as e:
            print(f"[FunImages] Image generation error for {url}: {e}")
            await ctx.send(f"❌ Couldn't generate **{friendly_name}**. Please try again later.")

    @commands.hybrid_command(name="cat", description="Sends a random cat picture 🐱")
    async def cat(self, ctx: commands.Context):
        await ctx.defer()
        data = await self._fetch_json("https://api.thecatapi.com/v1/images/search")
        if data and len(data) > 0 and data[0].get("url"):
            await self._send_embed_image(ctx, "🐱 Random Cat", data[0]["url"])
        else:
            await ctx.send("❌ Couldn't fetch a cat picture right now. Try again in a bit!")

    @commands.hybrid_command(name="dog", description="Sends a random dog picture 🐶")
    async def dog(self, ctx: commands.Context):
        await ctx.defer()
        data = await self._fetch_json("https://api.thedogapi.com/v1/images/search")
        if data and len(data) > 0 and data[0].get("url"):
            await self._send_embed_image(ctx, "🐶 Random Dog", data[0]["url"])
        else:
            await ctx.send("❌ Couldn't fetch a dog picture right now. Try again in a bit!")

    @commands.hybrid_command(name="fox", description="Sends a random fox picture 🦊")
    async def fox(self, ctx: commands.Context):
        await ctx.defer()
        data = await self._fetch_json("https://randomfox.ca/floof/")
        if data and data.get("image"):
            await self._send_embed_image(ctx, "🦊 Random Fox", data["image"])
        else:
            await ctx.send("❌ Couldn't fetch a fox picture right now. Try again in a bit!")

    @commands.hybrid_command(name="duck", description="Sends a random duck picture 🦆")
    async def duck(self, ctx: commands.Context):
        await ctx.defer()
        data = await self._fetch_json("https://random-d.uk/api/random")
        if data and data.get("url"):
            await self._send_embed_image(ctx, "🦆 Random Duck", data["url"])
        else:
            await ctx.send("❌ Couldn't fetch a duck picture right now. Try again in a bit!")

    @commands.hybrid_command(name="meme", description="Sends a random meme from Reddit 😂")
    @app_commands.describe(subreddit="Optional: pull a meme from a specific subreddit (e.g. 'wholesomememes')")
    async def meme(self, ctx: commands.Context, subreddit: Optional[str] = None):
        await ctx.defer()
        base = "https://meme-api.com/gimme"
        url = f"{base}/{self._enc(subreddit)}" if subreddit else base

        is_nsfw_channel = bool(getattr(ctx.channel, "is_nsfw", lambda: False)())
        data = None
        for _ in range(3):
            candidate = await self._fetch_json(url)
            if not candidate or "url" not in candidate:
                continue
            if candidate.get("nsfw") and not is_nsfw_channel:
                continue
            data = candidate
            break

        if not data:
            if subreddit:
                await ctx.send(
                    f"❌ Couldn't find a clean meme from **r/{subreddit}** for this channel. "
                    "Try a different subreddit, or use this in an NSFW channel."
                )
            else:
                await ctx.send("❌ Couldn't fetch a meme right now. Try again in a bit!")
            return

        await self._send_embed_image(
            ctx,
            data.get("title", "Random Meme"),
            data["url"],
            footer=f"r/{data.get('subreddit', 'unknown')}",
            url=data.get("postLink"),
        )

    @commands.hybrid_command(name="thirsty", description="Stamps a cheeky 'horny' tag onto someone's avatar 😅")
    @app_commands.describe(member="Whose avatar to use (defaults to you)")
    async def thirsty(self, ctx: commands.Context, member: Optional[discord.User] = None):
        await ctx.defer()
        user = self._resolve_user(ctx, member)
        a_q = self._enc(self._avatar_url(user))
        url = f"https://api.some-random-api.com/canvas/misc/horny?avatar={a_q}"
        await self._send_generated_image(ctx, url, "thirsty.png", "thirsty stamp")

    @commands.hybrid_command(name="stupid", description="Generates the 'It's so stupid, it might just work' meme")
    @app_commands.describe(text="The caption text", member="Whose avatar to use (defaults to you)")
    async def stupid_plan(self, ctx: commands.Context, text: str, member: Optional[discord.User] = None):
        await ctx.defer()
        user = self._resolve_user(ctx, member)
        a_q = self._enc(self._avatar_url(user))
        t_q = self._enc(text)
        url = f"https://api.some-random-api.com/canvas/misc/its-so-stupid?dog={t_q}&avatar={a_q}"
        await self._send_generated_image(ctx, url, "stupid_plan.png", "stupid plan meme")

    @commands.hybrid_command(name="lolice", description="Sends someone to anime police custody 🚓")
    @app_commands.describe(member="Whose avatar to use (defaults to you)")
    async def lolice(self, ctx: commands.Context, member: Optional[discord.User] = None):
        await ctx.defer()
        user = self._resolve_user(ctx, member)
        a_q = self._enc(self._avatar_url(user))
        url = f"https://api.some-random-api.com/canvas/misc/lolice?avatar={a_q}"
        await self._send_generated_image(ctx, url, "lolice.png", "lolice card")

    @commands.hybrid_command(name="namecard", description="Generates an anime-style namecard with your avatar")
    @app_commands.describe(
        birthday="Birthday text (e.g. '5 June')",
        member="Whose avatar/name to use (defaults to you)",
    )
    async def namecard(
        self,
        ctx: commands.Context,
        birthday: str,
        member: Optional[discord.User] = None,
    ):
        await ctx.defer()
        user = self._resolve_user(ctx, member)
        a_q = self._enc(self._avatar_url(user))
        u_q = self._enc(self._display_name(user))
        b_q = self._enc(birthday)
        url = (
            f"https://api.some-random-api.com/canvas/misc/namecard?username={u_q}&birthday={b_q}&avatar={a_q}"
        )
        await self._send_generated_image(ctx, url, "namecard.png", "namecard")

    @commands.hybrid_command(name="tweet", description="Generates a fake tweet image")
    @app_commands.describe(
        text="The tweet's text",
        member="Whose avatar/name to use (defaults to you)",
        theme="Light or dark mode",
    )
    async def fake_tweet(
        self,
        ctx: commands.Context,
        text: str,
        member: Optional[discord.User] = None,
        theme: Literal["light", "dark"] = "light",
    ):
        await ctx.defer()
        user = self._resolve_user(ctx, member)
        a_q = self._enc(self._avatar_url(user))
        dn_q = self._enc(self._display_name(user))
        un_q = self._enc(user.name)
        c_q = self._enc(text)
        url = (
            f"https://api.some-random-api.com/canvas/misc/tweet?displayname={dn_q}&username={un_q}&comment={c_q}&theme={theme}&avatar={a_q}"
        )
        await self._send_generated_image(ctx, url, "fake_tweet.png", "fake tweet")

    @commands.hybrid_command(name="youtubecomment", description="Generates a fake YouTube comment image")
    @app_commands.describe(
        text="The comment's text",
        member="Whose avatar/name to use (defaults to you)",
    )
    async def yt_comment(
        self,
        ctx: commands.Context,
        text: str,
        member: Optional[discord.User] = None,
    ):
        await ctx.defer()
        user = self._resolve_user(ctx, member)
        a_q = self._enc(self._avatar_url(user))
        un_q = self._enc(self._display_name(user))
        c_q = self._enc(text)
        url = (
            f"https://api.some-random-api.com/canvas/misc/youtube-comment?username={un_q}&comment={c_q}&avatar={a_q}"
        )
        await self._send_generated_image(ctx, url, "yt_comment.png", "YouTube comment")

    @commands.hybrid_command(name="anime", description="Sends a random anime reaction gif or quote")
    @app_commands.describe(category="The kind of anime gif/quote to fetch")
    async def anime(
        self,
        ctx: commands.Context,
        category: Literal["face", "hug", "kiss", "pat", "slap", "wink", "nom", "poke", "cry", "quote"] = "quote",
    ):
        await ctx.defer()
        data = await self._fetch_json(f"https://api.some-random-api.com/animu/{category}")
        if not data:
            await ctx.send(f"❌ Couldn't fetch an anime **{category}** right now. Try again in a bit!")
            return

        if category == "quote" and data.get("quote"):
            embed = discord.Embed(description=f"*\u201c{data['quote']}\u201d*", color=EMBED_COLOR)
            embed.set_footer(text=f"— {data.get('name', 'Unknown')} ({data.get('anime', 'Unknown anime')})")
            await ctx.send(embed=embed)
        else:
            link = data.get("link") or data.get("url")
            if link:
                await self._send_embed_image(ctx, f"Anime {category.title()}", link)
            else:
                await ctx.send("❌ Unexpected response from the anime API.")

    @commands.hybrid_command(name="amongus", description="Generates an Among Us GIF animation")
    @app_commands.describe(
        member="Whose avatar/name to use (defaults to you)",
        impostor="Was this person the impostor? (default: False)",
    )
    async def among_us(
        self,
        ctx: commands.Context,
        member: Optional[discord.User] = None,
        impostor: bool = False,
    ):
        await ctx.defer()
        user = self._resolve_user(ctx, member)
        a_q = self._enc(self._avatar_url(user))
        u_q = self._enc(self._display_name(user))

        url = (
            f"https://api.some-random-api.com/premium/amongus"
            f"?avatar={a_q}&username={u_q}&impostor={str(impostor).lower()}"
        )
        await self._send_generated_image(ctx, url, "amongus.gif", "Among Us animation")

    @commands.hybrid_command(name="petpet", description="Generates a petpet gif of someone's avatar (premium)")
    @app_commands.describe(member="Whose avatar to use (defaults to you)")
    async def petpet(self, ctx: commands.Context, member: Optional[discord.User] = None):
        await ctx.defer()
        user = self._resolve_user(ctx, member)
        a_q = self._enc(self._avatar_url(user))
        url = f"https://api.some-random-api.com/premium/petpet?avatar={a_q}"
        await self._send_generated_image(ctx, url, "petpet.gif", "petpet gif")


async def setup(bot: commands.Bot):
    await bot.add_cog(FunImages(bot))