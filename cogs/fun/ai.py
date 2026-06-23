import discord
from discord import app_commands
from discord.ext import commands
from groq import AsyncGroq
import random
import asyncio
import re
from collections import deque, defaultdict
import aiohttp
import json
import time

from config import Config


class FunAI(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.key_index = 0
        self.clients = []
        if Config.GROQ_API_KEYS:
            for key in Config.GROQ_API_KEYS:
                self.clients.append(AsyncGroq(api_key=key))
        else:
            print("Warning: GROQ_API_KEYS not set - AI commands won't work!")
        self.context_store = defaultdict(lambda: deque(maxlen=60))
        self.last_reply = defaultdict(float)
        self.message_since_last_reply = defaultdict(int)
        self.active_channels = defaultdict(set)
        self.user_interaction_count = defaultdict(lambda: defaultdict(int))
        self.http_session = None
        self._pending_replies = set()

        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_random_cat",
                    "description": "Get a random picture of a cat",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_random_dog",
                    "description": "Get a random picture of a dog",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_random_fox",
                    "description": "Get a random picture of a fox",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_random_duck",
                    "description": "Get a random picture of a duck",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_joke",
                    "description": "Get a random joke",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "The city name to get weather for"}
                        },
                        "required": ["city"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_meme",
                    "description": "Get a random meme",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "set_status",
                    "description": "Change the bot's presence, status, and/or activity",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status_type": {
                                "type": "string",
                                "description": "Bot presence status: online, idle, dnd, invisible",
                                "enum": ["online", "idle", "dnd", "invisible"]
                            },
                            "activity_type": {
                                "type": "string",
                                "description": "Type of activity: playing, listening, watching, competing, streaming",
                                "enum": ["playing", "listening", "watching", "competing", "streaming"]
                            },
                            "activity_text": {
                                "type": "string",
                                "description": "Text content for the activity"
                            }
                        },
                        "required": []
                    }
                }
            }
        ]

    async def cog_load(self):
        self.http_session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()

    def _get_http_session(self):
        if self.http_session is None or self.http_session.closed:
            self.http_session = aiohttp.ClientSession()
        return self.http_session

    async def _call_tool(self, tool_name: str, tool_args: dict):
        session = self._get_http_session()
        try:
            if tool_name == "get_random_cat":
                async with session.get("https://api.thecatapi.com/v1/images/search", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps({"url": data[0]["url"]}) if data else json.dumps({"error": "No cat found"})

            elif tool_name == "get_random_dog":
                async with session.get("https://api.thedogapi.com/v1/images/search", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps({"url": data[0]["url"]}) if data else json.dumps({"error": "No dog found"})

            elif tool_name == "get_random_fox":
                async with session.get("https://randomfox.ca/floof/", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps({"url": data["image"]}) if data else json.dumps({"error": "No fox found"})

            elif tool_name == "get_random_duck":
                async with session.get("https://random-d.uk/api/v2/random", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps({"url": data["url"]}) if data else json.dumps({"error": "No duck found"})

            elif tool_name == "get_joke":
                async with session.get("https://v2.jokeapi.dev/joke/Any?safe-mode", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps(data)

            elif tool_name == "get_weather":
                city = tool_args.get("city", "").strip()
                if not city:
                    return json.dumps({"error": "No city provided"})
                if not getattr(Config, "OPENWEATHER_API_KEY", None):
                    return json.dumps({"error": "OpenWeather API key not configured"})
                url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&appid={Config.OPENWEATHER_API_KEY}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps(data)

            elif tool_name == "get_meme":
                async with session.get("https://meme-api.com/gimme", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps(data)

            elif tool_name == "set_status":
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
                        "play": "playing", "plays": "playing",
                        "listen": "listening", "listens": "listening",
                        "watch": "watching", "watches": "watching",
                        "compete": "competing", "competes": "competing",
                        "stream": "streaming", "streams": "streaming"
                    }
                    activity_type = aliases.get(al, al)

                status_map = {
                    "online": discord.Status.online,
                    "idle": discord.Status.idle,
                    "dnd": discord.Status.dnd,
                    "invisible": discord.Status.invisible
                }
                activity_map = {
                    "playing": discord.ActivityType.playing,
                    "listening": discord.ActivityType.listening,
                    "watching": discord.ActivityType.watching,
                    "competing": discord.ActivityType.competing,
                    "streaming": discord.ActivityType.streaming
                }

                new_status = status_map.get(status_type, self.bot.status)
                new_activity = self.bot.activity

                if activity_text:
                    if activity_type == "streaming":
                        new_activity = discord.Streaming(name=activity_text, url="https://twitch.tv/discord")
                    else:
                        final_type = activity_map.get(activity_type, discord.ActivityType.playing)
                        new_activity = discord.Activity(type=final_type, name=activity_text)

                await self.bot.change_presence(status=new_status, activity=new_activity)
                return json.dumps({"success": True, "status": status_type, "activity_type": activity_type, "activity_text": activity_text})

            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except asyncio.TimeoutError:
            return json.dumps({"error": f"Tool {tool_name} timed out"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _get_client(self):
        if not self.clients:
            return None
        client = self.clients[self.key_index]
        self.key_index = (self.key_index + 1) % len(self.clients)
        return client

    async def _generate_response(self, system_prompt: str, user_prompt: str, model: str = "llama-3.3-70b-versatile", max_tokens: int = 1024, use_tools: bool = True, fail_silent: bool = False):
        client = self._get_client()
        if not client:
            if fail_silent:
                return None, []
            return "Oops! My AI brain is offline right now! Ask the owner to set GROQ_API_KEYS!", []

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        urls_to_send = []
        seen_urls = set()

        try:
            if use_tools:
                try:
                    completion = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=1.2,
                        max_completion_tokens=max_tokens,
                        top_p=1,
                        tools=self.tools,
                        tool_choice="auto"
                    )

                    message = completion.choices[0].message
                    has_tool_calls = hasattr(message, "tool_calls") and message.tool_calls

                    if has_tool_calls:
                        messages.append(message)

                        for tool_call in message.tool_calls:
                            tool_name = tool_call.function.name
                            try:
                                tool_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                            except json.JSONDecodeError:
                                tool_args = {}

                            tool_response = await self._call_tool(tool_name, tool_args)

                            try:
                                tool_data = json.loads(tool_response)
                                for key in ("url", "image", "postLink"):
                                    if key in tool_data:
                                        url = tool_data[key]
                                        if url and url not in seen_urls:
                                            urls_to_send.append(url)
                                            seen_urls.add(url)
                                        break
                            except Exception:
                                pass

                            messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": tool_name,
                                "content": tool_response
                            })

                        completion = await client.chat.completions.create(
                            model=model,
                            messages=messages,
                            temperature=1.0,
                            max_completion_tokens=max_tokens,
                            top_p=1
                        )
                        return completion.choices[0].message.content, urls_to_send

                    return message.content, urls_to_send

                except Exception as tool_error:
                    print(f"Tool calling failed, falling back: {tool_error}")

            completion = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=1.2,
                max_completion_tokens=max_tokens,
                top_p=1
            )
            return completion.choices[0].message.content, urls_to_send

        except Exception as e:
            print(f"AI error: {e}")
            if fail_silent:
                return None, []
            return "Oops! Something went wrong on my end. Try again later!", []

    def _is_command(self, message: discord.Message) -> bool:
        if not hasattr(self.bot, "_prefix_cache"):
            pass
        prefixes = []
        try:
            prefix = self.bot.command_prefix
            if callable(prefix):
                return False
            if isinstance(prefix, (list, tuple)):
                prefixes = list(prefix)
            else:
                prefixes = [prefix]
        except Exception:
            return False

        for p in prefixes:
            if message.content.startswith(p):
                rest = message.content[len(p):].strip()
                if rest:
                    return True
        return False

    def _should_reply(self, message: discord.Message, bot_mentioned: bool) -> bool:
        guild_id = message.guild.id
        now = time.time()
        elapsed = now - self.last_reply[guild_id]
        msg_count = self.message_since_last_reply[guild_id]

        if bot_mentioned:
            return True

        if elapsed < 15:
            return False

        if msg_count < 4:
            return False

        if elapsed > 300:
            return True

        chance = min(0.35, (msg_count - 4) * 0.06)
        return random.random() < chance

    def _build_context_string(self, guild_id: int) -> str:
        context = list(self.context_store[guild_id])
        lines = []
        for msg in context:
            prefix = "🤖" if msg["is_bot"] else "👤"
            lines.append(f"{prefix} [{msg['author_name']} | ID:{msg['author_id']}]: {msg['content']}")
        return "\n".join(lines)

    def _parse_reply_tags(self, text: str):
        text = text.strip()

        delay_seconds = 0
        delay_match = re.match(r'\[DELAY:(\d+)([sm])\](.*)', text, re.DOTALL | re.IGNORECASE)
        if delay_match:
            amount, unit, rest = delay_match.groups()
            delay_seconds = int(amount) * (60 if unit.lower() == "m" else 1)
            delay_seconds = min(delay_seconds, 300)
            text = rest.strip()

        send_type = "reply_mention"
        send_match = re.match(r'\[(REPLY_MENTION|REPLY|SEND|SEND_REPLY)\](.*)', text, re.DOTALL | re.IGNORECASE)
        if send_match:
            send_type = send_match.group(1).lower()
            text = send_match.group(2).strip()

        return delay_seconds, send_type, text

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return
        if len(message.content.strip()) < 2:
            return

        guild_id = message.guild.id
        bot_mentioned = self.bot.user.mentioned_in(message)

        if self._is_command(message):
            return

        self.context_store[guild_id].append({
            "author_id": message.author.id,
            "author_name": message.author.display_name,
            "content": message.content,
            "is_bot": False
        })
        self.message_since_last_reply[guild_id] += 1
        self.user_interaction_count[guild_id][message.author.id] += 1

        if not self.clients:
            return

        if not self._should_reply(message, bot_mentioned):
            return

        dedup_key = (guild_id, message.id)
        if dedup_key in self._pending_replies:
            return
        self._pending_replies.add(dedup_key)

        async def handle_reply():
            try:
                context_str = self._build_context_string(guild_id)
                familiarity = self.user_interaction_count[guild_id][message.author.id]
                familiarity_note = "You've talked to this person a lot, be warmer/more casual." if familiarity > 10 else "You've talked to this person a few times." if familiarity > 3 else "This is someone you haven't talked to much yet."

                system_prompt = f"""You are {self.bot.user.display_name}, a real Discord member who happens to be a bot — but you act fully human. You have a personality: witty, a little chaotic, uses internet slang naturally, occasionally sarcastic, sometimes wholesome. You are NOT an assistant.

CONTEXT OF RECENT MESSAGES:
{context_str}

YOUR INFO:
- Your name: {self.bot.user.display_name}
- Your user ID: {self.bot.user.id}
- Person messaging: {message.author.display_name} (ID: {message.author.id})
- {familiarity_note}

STRICT RULES:
1. Decide first: do you ACTUALLY want to reply? If the conversation doesn't involve you or you have nothing interesting to say, reply with exactly: [NO_REPLY]
2. If mentioned directly, you MUST reply — but still make it feel natural, not robotic.
3. Keep it SHORT. 1-3 sentences MAX. Real people don't write essays in chat.
4. Sound like a real Discord user. Use lowercase sometimes. Use "lol", "ngl", "fr", "nah", "bro", "lmao" naturally — but don't overdo it.
5. Do NOT start with "I", "Sure", "Of course", "Great", or any assistant-like opener.
6. Never say you're an AI or a bot.
7. Avoid exclamation marks unless it actually fits the vibe.
8. To mention someone: <@USER_ID> (use their actual ID from context).
9. For tool calls (images, weather, etc): call the tools FIRST with no text, then after results give your message with any [TAG] at the very start.
10. Send type tags (put at start of message, AFTER any delay tag):
    [REPLY_MENTION] - reply and ping them (default if nothing specified)
    [REPLY] - reply without ping
    [SEND] - just send to channel, no reply
11. Optional delay tag at very start: [DELAY:Xs] or [DELAY:Xm] (max 5 min)
12. Under 300 characters. No markdown. No code blocks."""

                reply, urls = await self._generate_response(
                    system_prompt,
                    f"The latest message from {message.author.display_name}: {message.content}\n\nWill you reply? If yes, what do you say?",
                    max_tokens=280,
                    fail_silent=True
                )

                if not reply:
                    return

                reply = reply.strip()

                if re.fullmatch(r'\[NO_?REPLY\]', reply, re.IGNORECASE):
                    return

                if re.search(r'\[NO_?REPLY\]', reply, re.IGNORECASE):
                    return

                delay_seconds, send_type, reply_text = self._parse_reply_tags(reply)

                if not reply_text or len(reply_text) > 1900:
                    return

                async def send_it():
                    try:
                        if delay_seconds > 0:
                            await asyncio.sleep(delay_seconds)

                        if not message.channel:
                            return

                        chars = len(reply_text)
                        wpm = random.uniform(180, 280)
                        typing_time = min(max((chars / 5) / (wpm / 60), 0.6), 4.5)
                        typing_time += random.uniform(-0.2, 0.5)

                        async with message.channel.typing():
                            await asyncio.sleep(typing_time)

                        if send_type == "reply_mention":
                            await message.reply(reply_text, mention_author=True)
                        elif send_type == "reply":
                            await message.reply(reply_text, mention_author=False)
                        elif send_type == "send":
                            await message.channel.send(reply_text)
                        elif send_type == "send_reply":
                            await message.channel.send(reply_text)
                            await message.reply("\u200b", mention_author=False)

                        for url in urls:
                            await asyncio.sleep(random.uniform(0.3, 0.8))
                            await message.channel.send(url)

                        self.last_reply[guild_id] = time.time()
                        self.message_since_last_reply[guild_id] = 0

                        self.context_store[guild_id].append({
                            "author_id": self.bot.user.id,
                            "author_name": self.bot.user.display_name,
                            "content": reply_text,
                            "is_bot": True
                        })

                    except discord.Forbidden:
                        pass
                    except discord.HTTPException as e:
                        print(f"HTTP error sending reply: {e}")
                    except Exception as e:
                        print(f"Send error: {e}")
                    finally:
                        self._pending_replies.discard(dedup_key)

                self.bot.loop.create_task(send_it())

            except Exception as e:
                print(f"on_message handler error: {e}")
                self._pending_replies.discard(dedup_key)

        self.bot.loop.create_task(handle_reply())

    @commands.hybrid_command(name="ask", description="Ask the AI anything!")
    @app_commands.describe(question="Your question!")
    async def ask(self, ctx: commands.Context, *, question: str):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a friendly, witty Discord bot assistant. Keep responses clear, fun, and under 1800 characters.",
            question
        )
        await ctx.send(f"**Q:** {question}\n**A:** {response}")
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="story", description="Generate a short, silly story!")
    @app_commands.describe(prompt="A prompt for the story!")
    async def story(self, ctx: commands.Context, *, prompt: str = "A random silly story!"):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a creative, funny story writer. Write a SHORT (max 900 chars) silly, lighthearted story. No markdown.",
            f"Write a short story about: {prompt}"
        )
        await ctx.send(f"📖 **Story Time!**\n{response}")
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="roast", description="Lightheartedly roast someone!")
    @app_commands.describe(member="Who to roast!")
    async def roast(self, ctx: commands.Context, member: discord.Member):
        if member.id == self.bot.user.id:
            await ctx.send("Roast myself? Nah, I'm too perfect for that.")
            return
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a playful Discord bot. Write a lighthearted, silly, harmless roast — nothing cruel. Max 400 chars. No markdown.",
            f"Write a friendly, harmless roast for a Discord user named {member.display_name}. Keep it silly and fun!"
        )
        await ctx.send(f"{member.mention} {response}")
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="compliment", description="Give someone a nice compliment!")
    @app_commands.describe(member="Who to compliment!")
    async def compliment(self, ctx: commands.Context, member: discord.Member):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a friendly Discord bot. Write a genuine, fun compliment. Max 400 chars. No markdown.",
            f"Write a fun, genuine compliment for a Discord user named {member.display_name}!"
        )
        await ctx.send(f"{member.mention} {response}")
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="pickupline", description="Get a cheesy pickup line!")
    async def pickupline(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a fun Discord bot. Generate a single, cheesy, silly, harmless pickup line. Max 200 chars. No markdown.",
            "Give me a silly, cheesy pickup line!"
        )
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="fortune", description="Get your fortune told!")
    async def fortune(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a mystical fortune teller bot. Write a short, fun, positive fortune. Max 300 chars. No markdown.",
            "Tell me a short, fun, positive fortune!"
        )
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="insult", description="Generate a funny fake insult (100% harmless!)")
    @app_commands.describe(member="Who to 'insult'!")
    async def insult(self, ctx: commands.Context, member: discord.Member):
        if member.id == self.bot.user.id:
            await ctx.send("I refuse to insult perfection.")
            return
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a silly Discord bot. Generate a harmless, clearly-jokey, exaggerated insult. NOT mean or hurtful. Max 300 chars. No markdown.",
            f"Write a harmless, silly, exaggerated joke insult for {member.display_name}!"
        )
        await ctx.send(f"{member.mention} {response} 😂")
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="advice", description="Get questionable life advice!")
    @app_commands.describe(topic="What do you need advice about?")
    async def advice(self, ctx: commands.Context, *, topic: str = "life"):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a quirky, silly advice giver. Give funny, lighthearted, clearly-not-serious advice. Max 500 chars. No markdown.",
            f"Give funny, silly, lighthearted advice about: {topic}"
        )
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="poem", description="Generate a silly poem!")
    @app_commands.describe(topic="What's the poem about?")
    async def poem(self, ctx: commands.Context, *, topic: str = "something random!"):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a silly poet. Write a short, funny, rhyming poem. Max 8 lines, lighthearted. No markdown.",
            f"Write a short, funny, rhyming poem about: {topic}"
        )
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="ship", description="Ship two users!")
    @app_commands.describe(user1="First user!", user2="Second user!")
    async def ship(self, ctx: commands.Context, user1: discord.Member, user2: discord.Member):
        if user1.id == user2.id:
            await ctx.send("You can't ship someone with themselves lmao")
            return
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a fun shipper bot. Write a short, sweet, silly ship description. Max 400 chars. No markdown.",
            f"Write a fun ship description for {user1.display_name} and {user2.display_name}!"
        )
        await ctx.send(f"🚢 **{user1.display_name} x {user2.display_name}**\n{response}")
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="dadjoke", description="Get a terrible dad joke!")
    async def dadjoke(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a dad joke master. Tell a single, terrible, punny dad joke. Max 300 chars. No markdown.",
            "Tell me a terrible dad joke!"
        )
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="wouldyourather", description="Get a 'Would You Rather' question!")
    async def wouldyourather(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a 'Would You Rather' question generator. Make one funny, lighthearted question. Max 300 chars. No markdown.",
            "Give me a funny, lighthearted 'Would You Rather' question!"
        )
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)


async def setup(bot: commands.Bot):
    await bot.add_cog(FunAI(bot))