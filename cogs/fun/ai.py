import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import escape_markdown
from groq import AsyncGroq
import random
import asyncio
import re
import html
import threading
import urllib.parse
from collections import deque, defaultdict
import aiohttp
import json
import time
from config import Config
from .ai_tools import TOOLS
from .ai_utils import (
    find_best_match,
    sanitize_custom_emoji,
    extract_urls_from_tool_response,
    serialize_assistant_message,
    resolve_mentions_in_message,
    parse_reply_tags,
    parse_old_function_syntax,
    strip_url_from_text,
)

MEM_SUMMARY_NS = "ai_memory_summary"
MEM_RECENT_NS = "ai_memory_recent"


class FunAI(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.key_index = 0
        self._key_index_lock = threading.Lock()
        self.clients = []
        if Config.GROQ_API_KEYS:
            for key in Config.GROQ_API_KEYS:
                self.clients.append(AsyncGroq(api_key=key))
        else:
            print("Warning: GROQ_API_KEYS not set - AI commands won't work!")
        self.context_store = defaultdict(lambda: deque(maxlen=60))
        self.user_memory_recent = defaultdict(lambda: deque(maxlen=10))
        self.user_memory_summary = defaultdict(str)
        self._memory_loaded = set()
        self.message_since_last_reply = defaultdict(int)
        self.user_interaction_count = defaultdict(lambda: defaultdict(int))
        self.http_session = None
        self.mention_cooldowns = {}
        self.report_cooldowns = {}
        self._pending_replies = set()
        self._pending_summarize = set()
        self._summarize_locks = {}
        self.trivia_session_token = None
        self.owner_ids = Config.OWNER_IDS
        self.admin_ids = Config.BOT_ADMIN_IDS
        self.mod_ids = Config.BOT_MODERATOR_IDS
        self.include_other_bots_in_context = getattr(
            Config, "AI_INCLUDE_OTHER_BOTS", False
        )
        self.tools = TOOLS

    async def cog_load(self):
        self.http_session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.http_session and (not self.http_session.closed):
            await self.http_session.close()

    def _get_http_session(self):
        if self.http_session is None or self.http_session.closed:
            self.http_session = aiohttp.ClientSession()
        return self.http_session

    def _get_db(self):
        return getattr(self.bot, "db", None)

    async def _hydrate_user_memory(self, user_id: int):
        if user_id in self._memory_loaded:
            return
        self._memory_loaded.add(user_id)
        db = self._get_db()
        if not db:
            return
        try:
            summary = await db.kv_get(MEM_SUMMARY_NS, str(user_id))
            if summary:
                self.user_memory_summary[user_id] = summary
            recent_raw = await db.kv_get(MEM_RECENT_NS, str(user_id))
            if recent_raw:
                recent = json.loads(recent_raw)
                self.user_memory_recent[user_id] = deque(recent, maxlen=10)
        except Exception as e:
            print(f"Memory hydrate failed for {user_id}: {e}")

    async def _persist_user_summary(self, user_id: int):
        db = self._get_db()
        if not db:
            return
        try:
            await db.kv_set(
                MEM_SUMMARY_NS, str(user_id), self.user_memory_summary[user_id]
            )
        except Exception as e:
            print(f"Memory summary persist failed for {user_id}: {e}")

    async def _persist_user_recent(self, user_id: int):
        db = self._get_db()
        if not db:
            return
        try:
            await db.kv_set(
                MEM_RECENT_NS,
                str(user_id),
                json.dumps(list(self.user_memory_recent[user_id])),
            )
        except Exception as e:
            print(f"Memory recent persist failed for {user_id}: {e}")

    async def _clear_user_memory_storage(self, user_id: int):
        db = self._get_db()
        if not db:
            return
        try:
            await db.kv_delete(MEM_SUMMARY_NS, str(user_id))
            await db.kv_delete(MEM_RECENT_NS, str(user_id))
        except Exception as e:
            print(f"Memory clear failed for {user_id}: {e}")

    async def _get_json_with_retry(
        self, session, url, params=None, retries=2, base_delay=0.6
    ):
        last_exc = None
        for attempt in range(retries + 1):
            try:
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 429 or resp.status >= 500:
                        last_exc = Exception(f"HTTP {resp.status}")
                    else:
                        return await resp.json()
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                last_exc = e
            if attempt < retries:
                await asyncio.sleep(base_delay * 2**attempt)
        if last_exc:
            raise last_exc
        return None

    async def _call_tool(
        self, tool_name: str, tool_args: dict, message: discord.Message = None
    ):
        session = self._get_http_session()
        try:
            if tool_name == "get_random_cat":
                async with session.get(
                    "https://api.thecatapi.com/v1/images/search",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    return (
                        json.dumps({"url": data[0]["url"]})
                        if data
                        else json.dumps({"error": "No cat found"})
                    )
            elif tool_name == "get_random_dog":
                async with session.get(
                    "https://api.thedogapi.com/v1/images/search",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    return (
                        json.dumps({"url": data[0]["url"]})
                        if data
                        else json.dumps({"error": "No dog found"})
                    )
            elif tool_name == "get_random_fox":
                async with session.get(
                    "https://randomfox.ca/floof/",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    return (
                        json.dumps({"url": data["image"]})
                        if data
                        else json.dumps({"error": "No fox found"})
                    )
            elif tool_name == "get_random_duck":
                async with session.get(
                    "https://random-d.uk/api/v2/random",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    return (
                        json.dumps({"url": data["url"]})
                        if data
                        else json.dumps({"error": "No duck found"})
                    )
            elif tool_name == "get_random_panda":
                async with session.get(
                    "https://some-random-api.com/animal/panda",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    return json.dumps(
                        {"url": data.get("image", ""), "fact": data.get("fact", "")}
                    )
            elif tool_name == "get_joke":
                async with session.get(
                    "https://v2.jokeapi.dev/joke/Any?safe-mode",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    return json.dumps(data)
            elif tool_name == "get_weather":
                city = tool_args.get("city", "").strip()
                if not city:
                    return json.dumps({"error": "No city provided"})
                if not getattr(Config, "OPENWEATHER_API_KEY", None):
                    return json.dumps({"error": "OpenWeather API key not configured"})
                url = "https://api.openweathermap.org/data/2.5/weather"
                params = {
                    "q": city,
                    "units": "metric",
                    "appid": Config.OPENWEATHER_API_KEY,
                }
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    data = await resp.json()
                    return json.dumps(data)
            elif tool_name == "get_meme":
                async with session.get(
                    "https://meme-api.com/gimme",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    return json.dumps(data)
            elif tool_name == "set_status":
                if not message:
                    return json.dumps({"error": "No message context"})
                is_authorized = (
                    message.author.id in self.owner_ids
                    or message.author.id in self.admin_ids
                    or message.author.id in self.mod_ids
                )
                if not is_authorized:
                    return json.dumps(
                        {"error": "Only bot owners/admins/mods can change status"}
                    )
                status_type = tool_args.get("status_type")
                activity_type = tool_args.get("activity_type")
                activity_text = tool_args.get("activity_text")
                if status_type:
                    sl = status_type.lower().strip()
                    if sl in ("do not disturb", "don't disturb", "busy"):
                        status_type = "dnd"
                    elif sl in ("offline", "away"):
                        status_type = "invisible"
                    else:
                        status_type = sl
                if activity_type:
                    al = activity_type.lower().strip()
                    aliases = {
                        "play": "playing",
                        "plays": "playing",
                        "listen": "listening",
                        "listens": "listening",
                        "watch": "watching",
                        "watches": "watching",
                        "compete": "competing",
                        "competes": "competing",
                        "stream": "streaming",
                        "streams": "streaming",
                    }
                    activity_type = aliases.get(al, al)
                status_map = {
                    "online": discord.Status.online,
                    "idle": discord.Status.idle,
                    "dnd": discord.Status.dnd,
                    "invisible": discord.Status.invisible,
                }
                activity_map = {
                    "playing": discord.ActivityType.playing,
                    "listening": discord.ActivityType.listening,
                    "watching": discord.ActivityType.watching,
                    "competing": discord.ActivityType.competing,
                    "streaming": discord.ActivityType.streaming,
                }
                new_status = status_map.get(status_type, self.bot.status)
                new_activity = self.bot.activity
                if activity_text:
                    if activity_type == "streaming":
                        new_activity = discord.Streaming(
                            name=activity_text, url="https://twitch.tv/discord"
                        )
                    else:
                        final_type = activity_map.get(
                            activity_type, discord.ActivityType.playing
                        )
                        new_activity = discord.Activity(
                            type=final_type, name=activity_text
                        )
                await self.bot.change_presence(status=new_status, activity=new_activity)
                return json.dumps(
                    {
                        "success": True,
                        "status": status_type,
                        "activity_type": activity_type,
                        "activity_text": activity_text,
                    }
                )
            elif tool_name == "mention_user_in_channel":
                if not message:
                    return json.dumps({"error": "No message context"})
                is_authorized = (
                    message.author.id in self.owner_ids
                    or message.author.id in self.admin_ids
                    or message.author.id in self.mod_ids
                )
                if not is_authorized:
                    return json.dumps(
                        {
                            "error": "Only bot owners/admins/mods can mention users via the bot in other channels"
                        }
                    )
                user_id = tool_args.get("user_id", "").strip()
                channel_name = tool_args.get("channel_name", "").strip().lstrip("#")
                msg_text = tool_args.get("message", "")
                delay = max(0, min(300, float(tool_args.get("delay", 0))))
                if not user_id or not channel_name:
                    return json.dumps(
                        {"error": "user_id and channel_name are required"}
                    )
                guild = message.guild
                text_channel_names = [c.name for c in guild.text_channels]
                best_channel_name = find_best_match(channel_name, text_channel_names)
                target_channel = None
                if best_channel_name:
                    target_channel = discord.utils.find(
                        lambda c: isinstance(c, discord.TextChannel)
                        and c.name == best_channel_name,
                        guild.channels,
                    )
                if not target_channel:
                    available = [c.name for c in guild.text_channels]
                    return json.dumps(
                        {
                            "error": f"Channel '{channel_name}' not found",
                            "available_channels": available,
                        }
                    )
                cooldown_key = (
                    message.author.id,
                    int(user_id) if user_id.isdigit() else user_id,
                    target_channel.id,
                )
                current_time = time.time()
                if (
                    cooldown_key in self.mention_cooldowns
                    and current_time - self.mention_cooldowns[cooldown_key] < 30
                ):
                    remaining = int(
                        30 - (current_time - self.mention_cooldowns[cooldown_key])
                    )
                    return json.dumps(
                        {
                            "error": f"Please wait {remaining} seconds before mentioning that user again in that channel"
                        }
                    )
                bot_perms = target_channel.permissions_for(guild.me)
                if not bot_perms.send_messages:
                    return json.dumps(
                        {"error": f"No permission to send in #{target_channel.name}"}
                    )
                mention_str = f"<@{user_id}>"
                content = (
                    f"{mention_str} {msg_text}".strip() if msg_text else mention_str
                )
                if delay > 0:
                    await asyncio.sleep(delay)
                await target_channel.send(content)
                self.mention_cooldowns[cooldown_key] = time.time()
                return json.dumps(
                    {
                        "success": True,
                        "channel": target_channel.name,
                        "user_id": user_id,
                        "delay": delay,
                    }
                )
            elif tool_name == "send_dm":
                if not message:
                    return json.dumps({"error": "No message context"})
                is_authorized = (
                    message.author.id in self.owner_ids
                    or message.author.id in self.admin_ids
                    or message.author.id in self.mod_ids
                )
                if not is_authorized:
                    return json.dumps(
                        {
                            "error": "Only bot owners/admins/mods can send DMs via the bot"
                        }
                    )
                user_id = tool_args.get("user_id", "").strip()
                dm_message = tool_args.get("message", "").strip()
                delay = max(0, min(300, float(tool_args.get("delay", 0))))
                if not user_id or not dm_message:
                    return json.dumps({"error": "user_id and message are required"})
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    if delay > 0:
                        await asyncio.sleep(delay)
                    await user.send(dm_message)
                    return json.dumps(
                        {"success": True, "user": str(user), "delay": delay}
                    )
                except discord.Forbidden:
                    return json.dumps({"error": "User has DMs disabled"})
                except discord.NotFound:
                    return json.dumps({"error": "User not found"})
            elif tool_name == "send_to_channel":
                if not message:
                    return json.dumps({"error": "No message context"})
                is_authorized = (
                    message.author.id in self.owner_ids
                    or message.author.id in self.admin_ids
                    or message.author.id in self.mod_ids
                )
                if not is_authorized:
                    return json.dumps(
                        {
                            "error": "Only bot owners/admins/mods can send messages to other channels"
                        }
                    )
                channel_name = tool_args.get("channel_name", "").strip().lstrip("#")
                msg_text = tool_args.get("message", "").strip()
                delay = max(0, min(300, float(tool_args.get("delay", 0))))
                if not channel_name or not msg_text:
                    return json.dumps(
                        {"error": "channel_name and message are required"}
                    )
                guild = message.guild
                text_channel_names = [c.name for c in guild.text_channels]
                best_channel_name = find_best_match(channel_name, text_channel_names)
                target = None
                if best_channel_name:
                    target = discord.utils.find(
                        lambda c: isinstance(c, discord.TextChannel)
                        and c.name == best_channel_name,
                        guild.channels,
                    )
                if not target:
                    available = [c.name for c in guild.text_channels]
                    return json.dumps(
                        {
                            "error": f"Channel '{channel_name}' not found",
                            "available": available,
                        }
                    )
                if not target.permissions_for(guild.me).send_messages:
                    return json.dumps(
                        {"error": f"No permission to send in #{target.name}"}
                    )
                if delay > 0:
                    await asyncio.sleep(delay)
                await target.send(msg_text)
                return json.dumps(
                    {"success": True, "channel": target.name, "delay": delay}
                )
            elif tool_name == "react_to_message":
                if not message:
                    return json.dumps({"error": "No message context"})
                emoji_input = tool_args.get("emoji", "👍").strip()
                try:
                    await message.add_reaction(emoji_input)
                    return json.dumps({"success": True, "emoji": emoji_input})
                except discord.HTTPException as e:
                    return json.dumps({"error": str(e)})
            elif tool_name == "get_server_info":
                if not message:
                    return json.dumps({"error": "No message context"})
                guild = message.guild
                info = {
                    "name": guild.name,
                    "id": str(guild.id),
                    "owner_id": str(guild.owner_id),
                    "member_count": guild.member_count,
                    "text_channels": len(guild.text_channels),
                    "voice_channels": len(guild.voice_channels),
                    "roles": len(guild.roles),
                    "created_at": str(guild.created_at.strftime("%B %d, %Y")),
                    "boost_level": guild.premium_tier,
                    "boosts": guild.premium_subscription_count,
                }
                return json.dumps(info)
            elif tool_name == "get_user_info":
                if not message:
                    return json.dumps({"error": "No message context"})
                user_id = tool_args.get("user_id", "").strip()
                if not user_id:
                    return json.dumps({"error": "user_id required"})
                try:
                    member = message.guild.get_member(int(user_id))
                    if not member:
                        member = await message.guild.fetch_member(int(user_id))
                    info = {
                        "name": member.display_name,
                        "tag": str(member),
                        "id": str(member.id),
                        "joined_at": (
                            str(member.joined_at.strftime("%B %d, %Y"))
                            if member.joined_at
                            else "Unknown"
                        ),
                        "created_at": str(member.created_at.strftime("%B %d, %Y")),
                        "roles": [
                            r.name for r in member.roles if r.name != "@everyone"
                        ],
                        "bot": member.bot,
                        "status": str(member.status),
                    }
                    return json.dumps(info)
                except (discord.NotFound, discord.HTTPException):
                    return json.dumps({"error": "User not found in this server"})
            elif tool_name == "list_channels":
                if not message:
                    return json.dumps({"error": "No message context"})
                guild = message.guild
                channels = [
                    {
                        "name": c.name,
                        "id": str(c.id),
                        "category": c.category.name if c.category else None,
                    }
                    for c in guild.text_channels
                ]
                return json.dumps({"channels": channels})
            elif tool_name == "get_trivia":

                async def get_trivia_session_token():
                    async with session.get(
                        "https://opentdb.com/api_token.php?command=request",
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        token_data = await resp.json()
                        if token_data.get("response_code") == 0:
                            return token_data["token"]
                    return None

                async def reset_trivia_session_token():
                    if not self.trivia_session_token:
                        return await get_trivia_session_token()
                    async with session.get(
                        f"https://opentdb.com/api_token.php?command=reset&token={self.trivia_session_token}",
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        token_data = await resp.json()
                        if token_data.get("response_code") == 0:
                            return token_data["token"]
                    return await get_trivia_session_token()

                if not self.trivia_session_token:
                    self.trivia_session_token = await get_trivia_session_token()
                category_map = {
                    "general": 9,
                    "books": 10,
                    "film": 11,
                    "music": 12,
                    "science": 17,
                    "computers": 18,
                    "math": 19,
                    "sports": 21,
                    "history": 23,
                    "politics": 24,
                    "art": 25,
                    "animals": 27,
                    "vehicles": 28,
                    "comics": 29,
                    "anime": 31,
                    "games": 15,
                }
                cat = tool_args.get("category", "").lower()
                cat_id = category_map.get(cat, "")
                token_param = (
                    f"&token={self.trivia_session_token}"
                    if self.trivia_session_token
                    else ""
                )
                url = f"https://opentdb.com/api.php?amount=1&type=multiple{('&category=' + str(cat_id) if cat_id else '')}{token_param}"
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    data = await resp.json()
                    response_code = data.get("response_code")
                    if response_code in (3, 4):
                        self.trivia_session_token = await reset_trivia_session_token()
                        if self.trivia_session_token:
                            token_param = f"&token={self.trivia_session_token}"
                            url = f"https://opentdb.com/api.php?amount=1&type=multiple{('&category=' + str(cat_id) if cat_id else '')}{token_param}"
                            async with session.get(
                                url, timeout=aiohttp.ClientTimeout(total=10)
                            ) as resp2:
                                data = await resp2.json()
                                response_code = data.get("response_code")
                    if response_code == 0 and data.get("results"):
                        q = data["results"][0]
                        return json.dumps(
                            {
                                "question": html.unescape(q["question"]),
                                "correct_answer": html.unescape(q["correct_answer"]),
                                "incorrect_answers": [
                                    html.unescape(a) for a in q["incorrect_answers"]
                                ],
                                "category": html.unescape(q["category"]),
                                "difficulty": q["difficulty"],
                            }
                        )
                    return json.dumps({"error": "No trivia found"})
            elif tool_name == "urban_dictionary":
                term = tool_args.get("term", "").strip()
                if not term:
                    return json.dumps({"error": "No term provided"})
                async with session.get(
                    "https://api.urbandictionary.com/v0/define",
                    params={"term": term},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    if data.get("list"):
                        entry = data["list"][0]
                        definition = re.sub("\\[|\\]", "", entry.get("definition", ""))[
                            :400
                        ]
                        example = re.sub("\\[|\\]", "", entry.get("example", ""))[:200]
                        return json.dumps(
                            {
                                "word": escape_markdown(entry.get("word")),
                                "definition": escape_markdown(definition),
                                "example": escape_markdown(example),
                                "thumbs_up": entry.get("thumbs_up"),
                                "thumbs_down": entry.get("thumbs_down"),
                            }
                        )
                    return json.dumps(
                        {"error": f"No definition found for '{escape_markdown(term)}'"}
                    )
            elif tool_name == "translate_text":
                text = tool_args.get("text", "").strip()
                target_lang = tool_args.get("target_lang", "en").strip()
                if not text:
                    return json.dumps({"error": "No text provided"})
                langpair = f"auto|{target_lang}"
                async with session.get(
                    "https://api.mymemory.translated.net/get",
                    params={"q": text, "langpair": langpair},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    translated = data.get("responseData", {}).get("translatedText", "")
                    if (
                        isinstance(translated, str)
                        and "MYMEMORY WARNING" in translated.upper()
                    ):
                        return json.dumps(
                            {
                                "error": "Translation quota exceeded for this language pair, try again later"
                            }
                        )
                    return json.dumps(
                        {
                            "original": text,
                            "translated": translated,
                            "target_lang": target_lang,
                        }
                    )
            elif tool_name == "get_crypto_price":
                coin = tool_args.get("coin", "bitcoin").strip().lower()
                coin_ids = {
                    "btc": "bitcoin",
                    "eth": "ethereum",
                    "bnb": "binancecoin",
                    "sol": "solana",
                    "ada": "cardano",
                    "xrp": "ripple",
                    "doge": "dogecoin",
                    "ltc": "litecoin",
                    "dot": "polkadot",
                }
                coin_id = coin_ids.get(coin, coin)
                url = "https://api.coingecko.com/api/v3/simple/price"
                params = {
                    "ids": coin_id,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                }
                try:
                    data = await self._get_json_with_retry(session, url, params=params)
                except Exception:
                    return json.dumps(
                        {
                            "error": "Crypto price service is rate-limited right now, try again in a bit"
                        }
                    )
                if data and coin_id in data:
                    price_data = data[coin_id]
                    return json.dumps(
                        {
                            "coin": coin_id,
                            "price_usd": price_data.get("usd"),
                            "change_24h": price_data.get("usd_24h_change"),
                        }
                    )
                return json.dumps({"error": f"Could not find price for {coin}"})
            elif tool_name == "get_anime_quote":
                try:
                    async with session.get(
                        "https://api.animechan.io/v1/quotes/random",
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status == 429:
                            return json.dumps(
                                {
                                    "error": "Anime quote service is rate-limited (free tier caps at 5/hour), try later"
                                }
                            )
                        data = await resp.json()
                except Exception:
                    return json.dumps(
                        {"error": "Anime quote service unavailable right now"}
                    )
                quote_data = data.get("data", {})
                return json.dumps(
                    {
                        "quote": quote_data.get("content", ""),
                        "character": quote_data.get("character", {}).get(
                            "name", "Unknown"
                        ),
                        "anime": quote_data.get("anime", {}).get("name", "Unknown"),
                    }
                )
            elif tool_name == "get_waifu_image":
                async with session.get(
                    "https://api.waifu.pics/sfw/waifu",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    return json.dumps({"url": data.get("url", "")})
            elif tool_name == "roll_dice":
                sides = max(2, min(int(tool_args.get("sides", 6)), 1000))
                count = max(1, min(int(tool_args.get("count", 1)), 20))
                rolls = [random.randint(1, sides) for _ in range(count)]
                return json.dumps(
                    {
                        "rolls": rolls,
                        "total": sum(rolls),
                        "sides": sides,
                        "count": count,
                    }
                )
            elif tool_name == "flip_coin":
                result = random.choice(["Heads", "Tails"])
                return json.dumps({"result": result})
            elif tool_name == "get_quote":
                async with session.get(
                    "https://zenquotes.io/api/random",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    if data:
                        return json.dumps(
                            {
                                "quote": data[0].get("q", ""),
                                "author": data[0].get("a", "Unknown"),
                            }
                        )
                    return json.dumps({"error": "No quote found"})
            elif tool_name == "get_fact":
                async with session.get(
                    "https://uselessfacts.jsph.pl/api/v2/facts/random",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    return json.dumps({"fact": data.get("text", "")})
            elif tool_name == "pin_message":
                if not message:
                    return json.dumps({"error": "No message context"})
                is_authorized = (
                    message.author.id in self.owner_ids
                    or message.author.id in self.admin_ids
                    or message.author.id in self.mod_ids
                )
                if not is_authorized:
                    return json.dumps(
                        {"error": "Only bot owners/admins/mods can pin messages"}
                    )
                try:
                    await message.pin()
                    return json.dumps({"success": True})
                except discord.Forbidden:
                    return json.dumps({"error": "No permission to pin messages"})
                except discord.HTTPException as e:
                    return json.dumps({"error": str(e)})
            elif tool_name == "get_github_user":
                username = tool_args.get("username", "").strip()
                if not username:
                    return json.dumps({"error": "No username provided"})
                safe_username = urllib.parse.quote(username, safe="")
                async with session.get(
                    f"https://api.github.com/users/{safe_username}",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 404:
                        return json.dumps(
                            {"error": f"GitHub user '{username}' not found"}
                        )
                    data = await resp.json()
                    return json.dumps(
                        {
                            "login": data.get("login"),
                            "name": data.get("name"),
                            "bio": data.get("bio"),
                            "public_repos": data.get("public_repos"),
                            "followers": data.get("followers"),
                            "following": data.get("following"),
                            "location": data.get("location"),
                            "blog": data.get("blog"),
                            "created_at": data.get("created_at", "")[:10],
                        }
                    )
            elif tool_name == "get_owner_info":
                return json.dumps(
                    {
                        "owner_count": len(self.owner_ids),
                        "admin_count": len(self.admin_ids),
                        "mod_count": len(self.mod_ids),
                        "has_owners": len(self.owner_ids) > 0,
                        "has_admins": len(self.admin_ids) > 0,
                        "has_mods": len(self.mod_ids) > 0,
                    }
                )
            elif tool_name == "report_issue_or_abuse":
                if not message:
                    return json.dumps({"error": "No message context"})
                report_type = tool_args.get("report_type", "").strip().lower()
                reason = tool_args.get("reason", "").strip()
                if not report_type or not reason:
                    return json.dumps({"error": "report_type and reason are required"})
                current_time = time.time()
                user_id = message.author.id
                if (
                    user_id in self.report_cooldowns
                    and current_time - self.report_cooldowns[user_id] < 30
                ):
                    remaining = int(
                        30 - (current_time - self.report_cooldowns[user_id])
                    )
                    return json.dumps(
                        {
                            "error": f"Please wait {remaining} seconds before submitting another report"
                        }
                    )
                report_target_ids = (
                    list(self.owner_ids) + list(self.admin_ids) + list(self.mod_ids)
                )
                if not report_target_ids:
                    return json.dumps({"error": "No owners/admins/mods configured"})
                report_message = f"⚠️ **{report_type.upper()} REPORT** ⚠️\n"
                report_message += f"**Reported by:** {escape_markdown(str(message.author))} (ID: {message.author.id})\n"
                report_message += f"**Server:** {escape_markdown(message.guild.name)} (ID: {message.guild.id})\n"
                report_message += f"**Channel:** #{escape_markdown(message.channel.name)} (ID: {message.channel.id})\n"
                if report_type == "abuse" and tool_args.get("user_id"):
                    report_message += f"**Reported user ID:** {tool_args['user_id']}\n"
                report_message += f"**Reason:**\n{escape_markdown(reason)}"
                dm_errors = []
                for target_user_id in report_target_ids:
                    try:
                        user = self.bot.get_user(target_user_id)
                        if not user:
                            user = await self.bot.fetch_user(target_user_id)
                        if user:
                            await user.send(report_message)
                    except Exception as e:
                        dm_errors.append(
                            f"Failed to DM user {target_user_id}: {str(e)}"
                        )
                self.report_cooldowns[user_id] = current_time
                if dm_errors:
                    return json.dumps({"success": True, "dm_errors": dm_errors})
                return json.dumps({"success": True})
            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})
        except asyncio.TimeoutError:
            return json.dumps({"error": f"Tool {tool_name} timed out"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _get_client(self):
        if not self.clients:
            return None
        with self._key_index_lock:
            client = self.clients[self.key_index]
            self.key_index = (self.key_index + 1) % len(self.clients)
        return client

    async def _follow_up_completion(
        self, client, model, messages, temperature, max_tokens
    ):
        completion = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                top_p=1,
            ),
            timeout=30,
        )
        return completion.choices[0].message.content

    async def _generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "llama-3.3-70b-versatile",
        max_tokens: int = 1024,
        use_tools: bool = True,
        fail_silent: bool = False,
        message: discord.Message = None,
        temperature: float = None,
    ):
        client = self._get_client()
        if not client:
            if fail_silent:
                return (None, [])
            return (
                "Oops! My AI brain is offline right now! Ask the owner to set GROQ_API_KEYS!",
                [],
            )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        urls_to_send = []
        seen_urls = set()
        if temperature is None:
            temperature = random.uniform(1.2, 1.8)
        try:
            if use_tools:
                try:
                    completion = await asyncio.wait_for(
                        client.chat.completions.create(
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            max_completion_tokens=max_tokens,
                            top_p=1,
                            tools=self.tools,
                            tool_choice="auto",
                        ),
                        timeout=30,
                    )
                    msg = completion.choices[0].message
                    has_tool_calls = hasattr(msg, "tool_calls") and msg.tool_calls
                    has_old_function_syntax = False
                    old_function_calls = []
                    if msg.content:
                        old_function_calls = parse_old_function_syntax(msg.content)
                        has_old_function_syntax = len(old_function_calls) > 0
                    if has_tool_calls:
                        tool_responses = []
                        for tool_call in msg.tool_calls:
                            tool_name = tool_call.function.name
                            try:
                                tool_args = (
                                    json.loads(tool_call.function.arguments)
                                    if tool_call.function.arguments
                                    else {}
                                )
                            except json.JSONDecodeError:
                                tool_args = {}
                            tool_response = await self._call_tool(
                                tool_name, tool_args, message
                            )
                            tool_responses.append(
                                (tool_call.id, tool_name, tool_response)
                            )
                            extract_urls_from_tool_response(
                                tool_response, urls_to_send, seen_urls
                            )
                        if msg.content:
                            return (msg.content, urls_to_send)
                        else:
                            messages.append(serialize_assistant_message(msg))
                            for (
                                tool_call_id,
                                tool_name,
                                tool_response,
                            ) in tool_responses:
                                messages.append(
                                    {
                                        "tool_call_id": tool_call_id,
                                        "role": "tool",
                                        "name": tool_name,
                                        "content": tool_response,
                                    }
                                )
                            final_response = await self._follow_up_completion(
                                client, model, messages, temperature - 0.3, max_tokens
                            )
                            return (final_response, urls_to_send)
                    elif has_old_function_syntax:
                        tool_responses = []
                        for tool_name, tool_args in old_function_calls:
                            tool_response = await self._call_tool(
                                tool_name, tool_args, message
                            )
                            tool_responses.append((tool_name, tool_response))
                            extract_urls_from_tool_response(
                                tool_response, urls_to_send, seen_urls
                            )
                        if msg.content:
                            cleaned_text = re.sub(
                                "<function=[^>]+>(?:</function>)?", "", msg.content
                            ).strip()
                            if cleaned_text:
                                return (cleaned_text, urls_to_send)
                        for tool_name, tool_response in tool_responses:
                            messages.append(
                                {
                                    "role": "user",
                                    "content": f"Function {tool_name} returned: {tool_response}",
                                }
                            )
                        final_response = await self._follow_up_completion(
                            client, model, messages, temperature - 0.3, max_tokens
                        )
                        return (final_response, urls_to_send)
                    return (msg.content, urls_to_send)
                except asyncio.TimeoutError as tool_error:
                    print(f"Groq call timed out, falling back: {tool_error}")
                    use_tools = False
                except Exception as tool_error:
                    print(f"Tool calling failed, falling back: {tool_error}")
                    use_tools = False
            completion = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_completion_tokens=max_tokens,
                    top_p=1,
                ),
                timeout=30,
            )
            response_text = completion.choices[0].message.content
            if use_tools:
                old_function_calls = (
                    parse_old_function_syntax(response_text) if response_text else []
                )
                if old_function_calls:
                    tool_responses = []
                    for tool_name, tool_args in old_function_calls:
                        tool_response = await self._call_tool(
                            tool_name, tool_args, message
                        )
                        tool_responses.append((tool_name, tool_response))
                        extract_urls_from_tool_response(
                            tool_response, urls_to_send, seen_urls
                        )
                    if response_text:
                        cleaned_text = re.sub(
                            "<function=[^>]+>(?:</function>)?", "", response_text
                        ).strip()
                        if cleaned_text:
                            return (cleaned_text, urls_to_send)
                    for tool_name, tool_response in tool_responses:
                        messages.append(
                            {
                                "role": "user",
                                "content": f"Function {tool_name} returned: {tool_response}",
                            }
                        )
                    final_response = await self._follow_up_completion(
                        client, model, messages, temperature - 0.3, max_tokens
                    )
                    return (final_response, urls_to_send)
            return (response_text, urls_to_send)
        except Exception as e:
            print(f"AI error: {e}")
            if fail_silent:
                return (None, [])
            return ("something broke on my end, try again", [])

    async def _is_command(self, message: discord.Message) -> bool:
        prefixes = []
        try:
            prefix = self.bot.command_prefix
            if callable(prefix):
                result = prefix(self.bot, message)
                if hasattr(result, "__await__"):
                    result = await result
                if isinstance(result, (list, tuple)):
                    prefixes = list(result)
                else:
                    prefixes = [result]
            elif isinstance(prefix, (list, tuple)):
                prefixes = list(prefix)
            else:
                prefixes = [prefix]
        except Exception as e:
            print(f"Error in _is_command for message {message.id}: {e}")
            return False
        for p in prefixes:
            if isinstance(p, str):
                if p.startswith("<@"):
                    continue
                if message.content.startswith(p):
                    rest = message.content[len(p) :].strip()
                    if rest:
                        return True
        return False

    async def _summarize_memory(self, user_id: int, messages_to_summarize: list):
        if not messages_to_summarize:
            return
        existing_summary = self.user_memory_summary[user_id]
        system_prompt = "You are a memory compressor. Given an existing summary and new messages, produce a single updated summary under 500 characters. Focus on facts, preferences, topics discussed. Plain text only, no bullets."
        parts = []
        if existing_summary:
            parts.append(f"Existing summary: {existing_summary}")
        parts.append("New messages:")
        for msg in messages_to_summarize:
            role = "Bot" if msg["role"] == "assistant" else "User"
            parts.append(f"{role}: {msg['content']}")
        summary, _ = await self._generate_response(
            system_prompt,
            "\n".join(parts),
            use_tools=False,
            fail_silent=True,
            max_tokens=200,
        )
        if summary:
            self.user_memory_summary[user_id] = summary
            await self._persist_user_summary(user_id)

    async def _summarize_memory_safe(self, user_id: int, messages_to_summarize: list):
        if user_id not in self._summarize_locks:
            self._summarize_locks[user_id] = asyncio.Lock()
        async with self._summarize_locks[user_id]:
            await self._summarize_memory(user_id, messages_to_summarize)

    def _should_reply(self, message: discord.Message, bot_mentioned: bool) -> bool:
        guild_id = message.guild.id
        channel_id = message.channel.id
        key = (guild_id, channel_id)
        msg_count = self.message_since_last_reply[key]
        if bot_mentioned:
            return True
        if msg_count >= 20:
            return True
        return False

    def _build_context_string(self, guild_id: int, user_id: int = None) -> str:
        lines = []
        if user_id:
            if self.user_memory_summary[user_id]:
                lines.append("--- PAST CONVERSATIONS WITH THIS USER ---")
                lines.append(self.user_memory_summary[user_id])
                lines.append("---\n")
            if self.user_memory_recent[user_id]:
                lines.append(
                    "--- RECENT MESSAGES BETWEEN YOU TWO ACROSS THE SERVER ---"
                )
                for msg in self.user_memory_recent[user_id]:
                    prefix = "you" if msg["role"] == "assistant" else "them"
                    lines.append(f"{prefix}: {msg['content']}")
                lines.append("---\n")
        guild_context = list(self.context_store[guild_id])
        if guild_context:
            lines.append("--- RECENT SERVER CHAT ---")
            msg_map = {m["message_id"]: m for m in guild_context if m["message_id"]}
            for msg in guild_context:
                if msg["is_bot"]:
                    prefix = (
                        f"you ({self.bot.user.display_name}) said"
                        if msg.get("is_self")
                        else f"{msg['author_name']} (bot) said"
                    )
                else:
                    prefix = f"{msg['author_name']} (ID:{msg['author_id']}) said"
                if msg.get("reply_to_id") and msg["reply_to_id"] in msg_map:
                    replied_to = msg_map[msg["reply_to_id"]]
                    replied_author = (
                        replied_to["author_name"]
                        if not replied_to["is_bot"]
                        else f"you ({self.bot.user.display_name})"
                    )
                    lines.append(
                        f"{prefix} [in reply to {replied_author}]: {msg['content']}"
                    )
                else:
                    lines.append(f"{prefix}: {msg['content']}")
            lines.append("--- END OF SERVER CHAT ---")
        return "\n".join(lines)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        if message.author.bot:
            if (
                message.author.id == self.bot.user.id
                or not self.include_other_bots_in_context
            ):
                return
        if len(message.content.strip()) < 2:
            return
        guild_id = message.guild.id
        bot_name_lower = self.bot.user.display_name.lower()
        content_lower = message.content.lower()
        is_mentioned_by_ping = self.bot.user in message.mentions
        is_mentioned_by_name = (
            re.search("\\b" + re.escape(bot_name_lower) + "\\b", content_lower)
            is not None
        )
        bot_mentioned = is_mentioned_by_ping or is_mentioned_by_name
        if message.author.bot:
            readable_content = resolve_mentions_in_message(
                message.content,
                message.mentions,
                message.role_mentions,
                message.channel_mentions,
            )
            self.context_store[guild_id].append(
                {
                    "message_id": message.id,
                    "author_id": message.author.id,
                    "author_name": message.author.display_name,
                    "content": readable_content,
                    "is_bot": True,
                    "is_self": False,
                    "reply_to_id": (
                        message.reference.message_id
                        if message.reference and message.reference.message_id
                        else None
                    ),
                }
            )
            return
        is_command = await self._is_command(message)
        if is_command:
            return
        readable_content = resolve_mentions_in_message(
            message.content,
            message.mentions,
            message.role_mentions,
            message.channel_mentions,
        )
        non_bot_mentions = [u for u in message.mentions if not u.bot]
        self.context_store[guild_id].append(
            {
                "message_id": message.id,
                "author_id": message.author.id,
                "author_name": message.author.display_name,
                "content": readable_content,
                "is_bot": False,
                "is_self": False,
                "reply_to_id": (
                    message.reference.message_id
                    if message.reference and message.reference.message_id
                    else None
                ),
            }
        )
        self.message_since_last_reply[guild_id, message.channel.id] += 1
        if not self.clients:
            return
        should_reply = self._should_reply(message, bot_mentioned)
        if not should_reply:
            return
        dedup_key = message.id
        if dedup_key in self._pending_replies:
            return
        self._pending_replies.add(dedup_key)
        await self._hydrate_user_memory(message.author.id)
        self.user_memory_recent[message.author.id].append(
            {"role": "user", "content": readable_content}
        )
        self.user_interaction_count[guild_id][message.author.id] += 1
        if len(self.user_memory_recent[message.author.id]) >= 8:
            self._pending_summarize.add(message.author.id)

        async def handle_reply():
            try:
                context_str = self._build_context_string(guild_id, message.author.id)
                familiarity = self.user_interaction_count[guild_id][message.author.id]
                if familiarity > 15:
                    familiarity_note = (
                        "you know this person well, be relaxed and casual with them"
                    )
                elif familiarity > 5:
                    familiarity_note = (
                        "you've chatted with this person a few times before"
                    )
                else:
                    familiarity_note = "you barely know this person yet"
                guild = message.guild
                channel_list = ", ".join(
                    [f"#{c.name}" for c in guild.text_channels[:20]]
                )
                emoji_list = []
                emoji_map = {}
                for emoji in guild.emojis:
                    if emoji.animated:
                        emoji_str = f"<a:{emoji.name}:{emoji.id}>"
                    else:
                        emoji_str = f"<:{emoji.name}:{emoji.id}>"
                    emoji_list.append(emoji_str)
                    emoji_map[emoji.name.lower()] = emoji_str
                if len(emoji_list) > 50:
                    emoji_str = (
                        ", ".join(emoji_list[:50])
                        + f" (and {len(emoji_list) - 50} more)"
                    )
                else:
                    emoji_str = ", ".join(emoji_list) if emoji_list else "None"
                current_message_context = f"[CURRENT MESSAGE] {message.author.display_name} (ID:{message.author.id}) is talking TO YOU"
                if non_bot_mentions:
                    mentioned_names = ", ".join(
                        [f"{u.display_name} (ID:{u.id})" for u in non_bot_mentions]
                    )
                    current_message_context += f" — they mentioned {mentioned_names} in their message (those are other people being talked about, not you)"
                current_message_context += f':\n"{readable_content}"'
                system_prompt = self._build_system_prompt(
                    guild,
                    channel_list,
                    emoji_str,
                    message,
                    familiarity_note,
                    context_str,
                )
                temperature = random.uniform(1.2, 1.8)
                reply, urls = await self._generate_response(
                    system_prompt,
                    current_message_context,
                    max_tokens=400,
                    fail_silent=True,
                    message=message,
                    temperature=temperature,
                )
                key = (guild_id, message.channel.id)
                if not reply:
                    self.message_since_last_reply[key] = 0
                    self.user_memory_recent[message.author.id].pop()
                    return
                reply = reply.strip()
                if re.fullmatch("\\[NO_?REPLY\\]", reply, re.IGNORECASE) or re.search(
                    "\\[NO_?REPLY\\]", reply, re.IGNORECASE
                ):
                    self.message_since_last_reply[key] = 0
                    self.user_memory_recent[message.author.id].pop()
                    return
                delay_seconds, send_type, reply_to, reply_text, reaction_emoji = (
                    parse_reply_tags(reply)
                )
                reply_text = sanitize_custom_emoji(reply_text)
                if urls:
                    reply_text = strip_url_from_text(reply_text, urls)
                send_delay = delay_seconds
                send_reply_to = reply_to
                send_text = reply_text
                send_reaction = reaction_emoji
                send_type_val = send_type
                send_urls = urls
                send_guild_id = guild_id
                send_channel = message.channel
                send_message = message
                send_dedup_key = dedup_key
                send_author_id = message.author.id

                async def send_it():
                    try:
                        if send_delay > 0:
                            await asyncio.sleep(send_delay)
                        if not send_channel:
                            return
                        target_msg = send_message
                        if send_reply_to:
                            guild_context = list(self.context_store[send_guild_id])
                            for stored_msg in reversed(guild_context):
                                if (
                                    send_reply_to.lower()
                                    in stored_msg["content"].lower()
                                    or send_reply_to.lower()
                                    == stored_msg["author_name"].lower()
                                    or str(stored_msg["author_id"]) == send_reply_to
                                ):
                                    try:
                                        if stored_msg.get("message_id"):
                                            fetched_msg = (
                                                await send_channel.fetch_message(
                                                    stored_msg["message_id"]
                                                )
                                            )
                                            if (
                                                fetched_msg
                                                and fetched_msg.channel.id
                                                == send_channel.id
                                            ):
                                                target_msg = fetched_msg
                                            else:
                                                target_msg = send_message
                                        else:
                                            target_msg = send_message
                                    except Exception:
                                        target_msg = send_message
                                    break
                        if send_reaction:
                            try:
                                await (
                                    target_msg.add_reaction(send_reaction)
                                    if target_msg
                                    else send_message.add_reaction(send_reaction)
                                )
                            except Exception as e:
                                print(f"Error adding reaction: {e}")
                        sent_msg = None
                        if send_text and len(send_text) <= 1900:
                            chars = len(send_text)
                            wpm = random.uniform(190, 300)
                            typing_time = min(max(chars / 5 / (wpm / 60), 0.5), 8.0)
                            typing_time += random.uniform(-0.1, 0.4)
                            typing_channel = (
                                target_msg.channel
                                if target_msg and hasattr(target_msg, "channel")
                                else send_channel
                            )
                            async with typing_channel.typing():
                                await asyncio.sleep(typing_time)
                            if send_type_val == "reply_mention":
                                sent_msg = await (target_msg or send_message).reply(
                                    send_text, mention_author=True
                                )
                            elif send_type_val == "reply":
                                sent_msg = await (target_msg or send_message).reply(
                                    send_text, mention_author=False
                                )
                            elif send_type_val in ("send", "send_reply"):
                                sent_msg = await send_channel.send(send_text)
                        for url in send_urls:
                            await asyncio.sleep(random.uniform(0.3, 0.7))
                            await send_channel.send(url)
                        key = (send_guild_id, send_channel.id)
                        self.message_since_last_reply[key] = 0
                        if send_text and len(send_text) <= 1900 and sent_msg:
                            self.context_store[send_guild_id].append(
                                {
                                    "message_id": sent_msg.id,
                                    "author_id": self.bot.user.id,
                                    "author_name": self.bot.user.display_name,
                                    "content": send_text,
                                    "is_bot": True,
                                    "is_self": True,
                                    "reply_to_id": (
                                        target_msg.id if target_msg else send_message.id
                                    ),
                                }
                            )
                            self.user_memory_recent[send_author_id].append(
                                {"role": "assistant", "content": send_text}
                            )
                            await self._persist_user_recent(send_author_id)
                    except discord.Forbidden:
                        pass
                    except discord.HTTPException as e:
                        print(f"HTTP error sending reply: {e}")
                    except Exception as e:
                        print(f"Send error: {e}")
                    finally:
                        self._pending_replies.discard(send_dedup_key)
                        if send_author_id in self._pending_summarize:
                            self._pending_summarize.discard(send_author_id)
                            recent = list(self.user_memory_recent[send_author_id])
                            if len(recent) >= 8:
                                to_summarize = recent[:6]
                                remaining = recent[6:]
                                task = asyncio.create_task(
                                    self._summarize_memory_safe(
                                        send_author_id, to_summarize
                                    )
                                )
                                task.add_done_callback(
                                    lambda t: t.exception()
                                    and print(f"Summarize task error: {t.exception()}")
                                )
                                self.user_memory_recent[send_author_id] = deque(
                                    remaining, maxlen=10
                                )

                task = asyncio.create_task(send_it())
                task.add_done_callback(
                    lambda t: t.exception()
                    and print(f"Send it task error: {t.exception()}")
                )
            except Exception as e:
                print(f"on_message handler error: {e}")
                self._pending_replies.discard(dedup_key)
                if message.author.id in self._pending_summarize:
                    self._pending_summarize.discard(message.author.id)
                    recent = list(self.user_memory_recent[message.author.id])
                    if len(recent) >= 8:
                        to_summarize = recent[:6]
                        remaining = recent[6:]
                        task = asyncio.create_task(
                            self._summarize_memory_safe(message.author.id, to_summarize)
                        )
                        task.add_done_callback(
                            lambda t: t.exception()
                            and print(f"Summarize task error: {t.exception()}")
                        )
                        self.user_memory_recent[message.author.id] = deque(
                            remaining, maxlen=10
                        )

        task = asyncio.create_task(handle_reply())
        task.add_done_callback(
            lambda t: t.exception()
            and print(f"Handle reply task error: {t.exception()}")
        )

    def _build_system_prompt(
        self, guild, channel_list, emoji_str, message, familiarity_note, context_str
    ) -> str:
        return f"""\nYou are {self.bot.user.display_name}.\n\nYou are NOT an AI assistant. You're just another girl hanging out in this Discord server. People know you as chaotic, witty, sarcastic, funny, occasionally sweet, occasionally feral. You talk because you WANT to, not because you're programmed to answer everything.\n\n{context_str}\n\nABOUT YOU\n- Name: {self.bot.user.display_name}\n- User ID: {self.bot.user.id}\n- Server: {guild.name}\n- Channels: {channel_list}\n- Custom Server Emojis: {emoji_str}\n\nWHO IS TALKING TO YOU RIGHT NOW\n- {message.author.display_name} (ID: {message.author.id}) is the one talking\n- Familiarity with them: {familiarity_note}\n\nCRITICAL — UNDERSTANDING WHO IS WHO IN CHAT\nWhen you see the server chat history, each line is labeled as:\n "DisplayName (ID:userid) said: [their message]"\n "DisplayName (ID:userid) said [in reply to AnotherName]: [their message]"\n "you (YourName) said: [your reply]"\n\nThis tells you exactly who said what and who they're replying to.\n\nIMPORTANT: WHEN TO REPLY\n- You MUST reply if you are mentioned by ping or name\n- Otherwise, ONLY reply if you can make a genuinely funny, savage, or troll comment based on the full conversation context\n- If you don't have a good joke/savage/troll comment, reply with [NO_REPLY]\n- If the conversation is serious, or you don't have anything to add, reply with [NO_REPLY]\n\nIMPORTANT: CUSTOM EMOJI RULES (READ THIS CAREFULLY):\n- When using custom emojis from the list, copy them exactly as they appear!\n- Do NOT modify them in any way!\n- Do NOT use just <EMOJI_ID>!\n- Do NOT add random letters after emojis!\n- Do NOT try to create your own custom emoji formats!\n\nExample:\n- GOOD: <:TAKI_peperain:843347114414047232>\n- BAD: <843347114414047232>, :TAKI_peperain:IIIK, <:TAKI_peperain:>, <$>:TAKI_peperain:843347114414047232>\n\nNote: Mention people with <@USER_ID> directly in response when needed, but do not spam mentions.\n\nIMPORTANT: Do not use <function=...> syntax; the tools are automatically handled by the system, so you don't need to call them manually.\n\nIf you want to reply to a specific message in the chat history (not just the latest one), use [REPLY_TO:query] at the start of your response, where "query" is a snippet of the message content, the author's name, or their user ID. For example:\n[REPLY_TO:Hey guys] Yeah, that was a great idea!\n[REPLY_TO:123456789012345678] Nice point!\n[REPLY_TO:JohnDoe] I agree with you!\n\nIf you want to react to the message instead of (or in addition to) replying, use [REACT:emoji] at the start of your response. You can combine both [REPLY_TO:...] and [REACT:...].\n\nYou can also choose how to send the message:\n- [REPLY_MENTION] to reply and mention the user (default)\n- [REPLY] to reply without mentioning\n- [SEND] to just send a message to the channel without replying\n- [SEND_REPLY] to send a message that looks like a reply but doesn't actually ping\n\nYou can also delay your response with [DELAY:Xs] or [DELAY:Xm] where X is a number (seconds or minutes, max 5 minutes).\n\nThese tags can be combined in any order, but they should all come before your actual response text.\n\nExample combinations:\n[DELAY:30s][REPLY][REACT:👍] That's cool!\n[REPLY_TO:That was wild][REACT:😂] Lol yeah that was crazy\n[DELAY:1m][SEND] Just wanted to drop this here\n\nOkay, go!"""

    def _send_safe(self, ctx, text):
        if len(text) > 1900:
            text = text[:1900] + "..."
        return ctx.send(text)

    @commands.hybrid_command(name="ask", description="Ask the AI anything!")
    @app_commands.describe(question="Your question!")
    async def ask(self, ctx: commands.Context, *, question: str):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a sharp, no-nonsense Discord bot. Answer clearly and concisely. No fluff, no cheerfulness. Under 1800 chars.",
            question,
            message=ctx.message,
        )
        message_text = f"**Q:** {question}\n**A:** {response}"
        if len(message_text) > 1900:
            message_text = f"**Q:** {question}\n**A:** {response[:1900 - len(f'**Q:** {question}\n**A:** ...')]}..."
        await self._send_safe(ctx, message_text)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="story", description="Generate a short story!")
    @app_commands.describe(prompt="A prompt for the story!")
    async def story(self, ctx: commands.Context, *, prompt: str = "make it weird"):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a creative writer. Write a SHORT (max 900 chars) story. Make it actually interesting, not generic. No markdown.",
            f"Write a short story about: {prompt}",
            message=ctx.message,
        )
        message_text = f"📖 **Story Time:**\n{response}"
        if len(message_text) > 1900:
            message_text = f"📖 **Story Time:**\n{response[:1900 - len('📖 **Story Time:**\n...')]}..."
        await self._send_safe(ctx, message_text)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="roast", description="Roast someone!")
    @app_commands.describe(member="Who to roast!")
    async def roast(self, ctx: commands.Context, member: discord.Member):
        if member.id == self.bot.user.id:
            await ctx.send("roast myself? i don't have enough self-loathing for that")
            return
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a savage roast machine. Write a sharp, witty, cutting but not genuinely cruel roast. Clever > mean. Max 400 chars. No markdown.",
            f"Roast a Discord user named {member.display_name}. Make it clever.",
            message=ctx.message,
        )
        message_text = f"{member.mention} {response}"
        if len(message_text) > 1900:
            message_text = (
                f"{member.mention} {response[:1900 - len(f'{member.mention} ...')]}..."
            )
        await self._send_safe(ctx, message_text)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="compliment", description="Compliment someone!")
    @app_commands.describe(member="Who to compliment!")
    async def compliment(self, ctx: commands.Context, member: discord.Member):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a genuine, slightly awkward compliment giver. Write something real and specific, not generic garbage. Max 400 chars. No markdown.",
            f"Write a genuine compliment for a Discord user named {member.display_name}.",
            message=ctx.message,
        )
        message_text = f"{member.mention} {response}"
        if len(message_text) > 1900:
            message_text = (
                f"{member.mention} {response[:1900 - len(f'{member.mention} ...')]}..."
            )
        await self._send_safe(ctx, message_text)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="pickupline", description="Get a pickup line!")
    async def pickupline(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response(
            "Generate a single pickup line. Make it either genuinely clever or so bad it's funny. Not both. Max 200 chars. No markdown.",
            "Give me a pickup line.",
            message=ctx.message,
        )
        await self._send_safe(ctx, response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="fortune", description="Get your fortune!")
    async def fortune(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a fortune teller but make it feel real, not generic horoscope garbage. Short, a little cryptic, slightly unsettling. Max 300 chars. No markdown.",
            "Tell me my fortune.",
            message=ctx.message,
        )
        await self._send_safe(ctx, response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(
        name="insult", description="Fake insult someone (harmless)"
    )
    @app_commands.describe(member="Who to insult!")
    async def insult(self, ctx: commands.Context, member: discord.Member):
        if member.id == self.bot.user.id:
            await ctx.send("i refuse to participate in self-criticism")
            return
        await ctx.defer()
        response, urls = await self._generate_response(
            "Write a savage, clearly jokey, exaggerated fake insult. Make it absurd enough that no one could take it. Max 300 chars. No markdown.",
            f"Write a damn insult for {member.display_name}.",
            message=ctx.message,
        )
        message_text = f"{member.mention} {response}"
        if len(message_text) > 1900:
            message_text = (
                f"{member.mention} {response[:1900 - len(f'{member.mention} ...')]}..."
            )
        await self._send_safe(ctx, message_text)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="advice", description="Get questionable life advice!")
    @app_commands.describe(topic="What do you need advice about?")
    async def advice(self, ctx: commands.Context, *, topic: str = "life in general"):
        await ctx.defer()
        response, urls = await self._generate_response(
            "Give advice that sounds almost wise but is slightly unhinged. Not fully serious but not pure comedy. Max 500 chars. No markdown.",
            f"Give me advice about: {topic}",
            message=ctx.message,
        )
        await self._send_safe(ctx, response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="poem", description="Generate a poem!")
    @app_commands.describe(topic="What's the poem about?")
    async def poem(
        self, ctx: commands.Context, *, topic: str = "something i won't regret"
    ):
        await ctx.defer()
        response, urls = await self._generate_response(
            "Write a short poem. Can be funny, dark, weird, or beautiful. Max 8 lines. No markdown.",
            f"Write a poem about: {topic}",
            message=ctx.message,
        )
        await self._send_safe(ctx, response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="ship", description="Ship two users!")
    @app_commands.describe(user1="First user!", user2="Second user!")
    async def ship(
        self, ctx: commands.Context, user1: discord.Member, user2: discord.Member
    ):
        if user1.id == user2.id:
            await ctx.send(
                "you can't ship someone with themselves, that's just a mirror"
            )
            return
        await ctx.defer()
        response, urls = await self._generate_response(
            "Write a short ship description. Make it feel real and specific, not generic. Give it a compatibility score and a vibe. Max 400 chars. No markdown.",
            f"Write a ship for {user1.display_name} and {user2.display_name}.",
            message=ctx.message,
        )
        message_text = f"🚢 **{user1.display_name} x {user2.display_name}**\n{response}"
        if len(message_text) > 1900:
            message_text = f"🚢 **{user1.display_name} x {user2.display_name}**\n{response[:1900 - len(f'🚢 **{user1.display_name} x {user2.display_name}**\n...')]}..."
        await self._send_safe(ctx, message_text)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="dadjoke", description="Get a dad joke!")
    async def dadjoke(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response(
            "Tell a single dad joke. The worse the pun the better. Max 300 chars. No markdown.",
            "Tell me a dad joke.",
            message=ctx.message,
        )
        await self._send_safe(ctx, response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(
        name="wouldyourather", description="Get a Would You Rather question!"
    )
    async def wouldyourather(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response(
            "Give a Would You Rather question that's actually interesting — not too easy, not too gross. Max 300 chars. No markdown.",
            "Give me a Would You Rather question.",
            message=ctx.message,
        )
        await self._send_safe(ctx, response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="rate", description="Rate anything!")
    @app_commands.describe(thing="What to rate!")
    async def rate(self, ctx: commands.Context, *, thing: str):
        await ctx.defer()
        score = random.randint(0, 10)
        response, urls = await self._generate_response(
            f"You are a harsh but honest critic. Rate the given thing {score}/10 and give a one-sentence reason. Be direct. Max 200 chars. No markdown.",
            f"Rate this: {thing}. The score is {score}/10.",
            message=ctx.message,
        )
        message_text = f"**{thing}:** {response}"
        if len(message_text) > 1900:
            message_text = (
                f"**{thing}:** {response[:1900 - len(f'**{thing}:** ...')]}..."
            )
        await self._send_safe(ctx, message_text)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="8ball", description="Ask the magic 8-ball!")
    @app_commands.describe(question="Your yes/no question!")
    async def eightball(self, ctx: commands.Context, *, question: str):
        await ctx.defer()
        responses = [
            "yeah obviously",
            "no chance",
            "maybe, but probably not",
            "absolutely not",
            "signs point to yes",
            "ask again when you're smarter",
            "the universe says no",
            "sure why not",
            "lol no",
            "deep down you already know the answer",
            "it is certain",
            "don't count on it",
            "without a doubt",
            "my sources say no",
            "reply hazy, try again",
            "outlook not so good",
        ]
        answer = random.choice(responses)
        await ctx.send(f"🎱 **{question}**\n{answer}")

    @commands.hybrid_command(
        name="translate", description="Translate text to another language!"
    )
    @app_commands.describe(
        text="Text to translate",
        language="Target language (e.g. Spanish, French, Japanese)",
    )
    async def translate(self, ctx: commands.Context, language: str, *, text: str):
        await ctx.defer()
        lang_codes = {
            "spanish": "es",
            "french": "fr",
            "german": "de",
            "japanese": "ja",
            "korean": "ko",
            "chinese": "zh",
            "arabic": "ar",
            "portuguese": "pt",
            "italian": "it",
            "russian": "ru",
            "hindi": "hi",
            "turkish": "tr",
            "dutch": "nl",
            "polish": "pl",
            "swedish": "sv",
        }
        lang_code = lang_codes.get(language.lower(), language.lower()[:2])
        result = await self._call_tool(
            "translate_text", {"text": text, "target_lang": lang_code}
        )
        try:
            data = json.loads(result)
            if "translated" in data:
                await ctx.send(f"**{language}:** {data['translated']}")
            else:
                await ctx.send(
                    f"couldn't translate that: {data.get('error', 'unknown error')}"
                )
        except Exception:
            await ctx.send("translation failed, sorry")

    @commands.hybrid_command(name="trivia", description="Get a trivia question!")
    @app_commands.describe(
        category="Optional category (general, science, history, sports, anime, etc)"
    )
    async def trivia(self, ctx: commands.Context, category: str = ""):
        await ctx.defer()
        result = await self._call_tool("get_trivia", {"category": category})
        try:
            data = json.loads(result)
            if "question" in data:
                question = re.sub(
                    "&quot;|&#039;|&amp;|&lt;|&gt;",
                    lambda m: {
                        "&quot;": '"',
                        "&#039;": "'",
                        "&amp;": "&",
                        "&lt;": "<",
                        "&gt;": ">",
                    }.get(m.group(), m.group()),
                    data["question"],
                )
                correct = data["correct_answer"]
                all_answers = data["incorrect_answers"] + [correct]
                random.shuffle(all_answers)
                answer_list = "\n".join(
                    [f"{('✅' if a == correct else '❌')} {a}" for a in all_answers]
                )
                await ctx.send(
                    f"**{data['category']} | {data['difficulty'].title()}**\n{question}\n||{answer_list}||"
                )
            else:
                await ctx.send(
                    f"couldn't get trivia: {data.get('error', 'unknown error')}"
                )
        except Exception:
            await ctx.send("trivia failed, the database is being weird")

    @commands.hybrid_command(name="crypto", description="Check a cryptocurrency price!")
    @app_commands.describe(coin="Coin name or symbol (e.g. bitcoin, ETH)")
    async def crypto(self, ctx: commands.Context, coin: str = "bitcoin"):
        await ctx.defer()
        result = await self._call_tool("get_crypto_price", {"coin": coin})
        try:
            data = json.loads(result)
            if "price_usd" in data:
                change = data.get("change_24h", 0) or 0
                arrow = "📈" if change >= 0 else "📉"
                await ctx.send(
                    f"{arrow} **{data['coin'].title()}:** ${data['price_usd']:,.2f} ({change:+.2f}% 24h)"
                )
            else:
                await ctx.send(
                    f"can't find price for {coin}: {data.get('error', 'unknown error')}"
                )
        except Exception:
            await ctx.send("crypto lookup failed")

    @commands.hybrid_command(
        name="urban", description="Look up a word on Urban Dictionary!"
    )
    @app_commands.describe(term="Word or phrase to look up")
    async def urban(self, ctx: commands.Context, *, term: str):
        await ctx.defer()
        result = await self._call_tool("urban_dictionary", {"term": term})
        try:
            data = json.loads(result)
            if "definition" in data:
                await ctx.send(
                    f"**{data['word']}**\n{data['definition']}\n*Example: {data['example']}*"
                    if data.get("example")
                    else f"**{data['word']}**\n{data['definition']}"
                )
            else:
                await ctx.send(f"no urban dictionary definition found for '{term}'")
        except Exception:
            await ctx.send("urban dictionary lookup failed")


    @commands.hybrid_command(name="view_memory", description="View your conversation memory!")
    async def view_memory(self, ctx: commands.Context):
        await ctx.defer()
        await self._hydrate_user_memory(ctx.author.id)
        
        lines = ["## Your Memory"]
        
        if self.user_memory_summary[ctx.author.id]:
            lines.append(f"### Summary\n{self.user_memory_summary[ctx.author.id]}")
        else:
            lines.append("### Summary\nNo summary yet")
        
        recent_messages = self.user_memory_recent[ctx.author.id]
        if recent_messages:
            lines.append("\n### Recent Messages")
            for i, msg in enumerate(recent_messages):
                role = "🤖 Bot" if msg["role"] == "assistant" else "👤 You"
                lines.append(f"\n{role} #{i+1}: {msg['content']}")
        else:
            lines.append("\n### Recent Messages\nNo recent messages")
        
        await self._send_safe(ctx, "\n".join(lines))

    @commands.hybrid_command(name="clear_memory", description="Clear your conversation memory!")
    async def clear_memory(self, ctx: commands.Context):
        await ctx.defer()
        self.user_memory_summary[ctx.author.id] = ""
        self.user_memory_recent[ctx.author.id] = deque(maxlen=10)
        await self._clear_user_memory_storage(ctx.author.id)
        await ctx.send("✅ Your memory has been cleared!")


async def setup(bot: commands.Bot):
    await bot.add_cog(FunAI(bot))
