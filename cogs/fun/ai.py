
import discord
from discord import app_commands
from discord.ext import commands
from groq import AsyncGroq
import random
import asyncio
from collections import deque, defaultdict
import aiohttp
import json

from config import Config


class FunAI(commands.Cog):
    """AI-powered fun commands!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.key_index = 0
        self.clients = []
        if Config.GROQ_API_KEYS:
            for key in Config.GROQ_API_KEYS:
                self.clients.append(AsyncGroq(api_key=key))
        else:
            print("Warning: GROQ_API_KEYS not set - AI commands won't work!")
        self.context_store = defaultdict(lambda: deque(maxlen=50))  # More context
        self.last_reply = defaultdict(int)
        self.message_since_last_reply = defaultdict(int)
        self.http_session = aiohttp.ClientSession()
        
        # Define tools for tool calling
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
                                "description": "Text content for the activity (what the bot is playing/listening/watching)"
                            }
                        },
                        "required": []
                    }
                }
            }
        ]

    async def cog_unload(self):
        await self.http_session.close()
        
    async def _call_tool(self, tool_name, tool_args):
        try:
            if tool_name == "get_random_cat":
                async with self.http_session.get("https://api.thecatapi.com/v1/images/search") as resp:
                    data = await resp.json()
                    return json.dumps({"url": data[0]["url"]}) if data else json.dumps({"error": "No cat found"})
            elif tool_name == "get_random_dog":
                async with self.http_session.get("https://api.thedogapi.com/v1/images/search") as resp:
                    data = await resp.json()
                    return json.dumps({"url": data[0]["url"]}) if data else json.dumps({"error": "No dog found"})
            elif tool_name == "get_random_fox":
                async with self.http_session.get("https://randomfox.ca/floof/") as resp:
                    data = await resp.json()
                    return json.dumps({"url": data["image"]}) if data else json.dumps({"error": "No fox found"})
            elif tool_name == "get_random_duck":
                async with self.http_session.get("https://random-d.uk/api/v2/random") as resp:
                    data = await resp.json()
                    return json.dumps({"url": data["url"]}) if data else json.dumps({"error": "No duck found"})
            elif tool_name == "get_joke":
                async with self.http_session.get("https://v2.jokeapi.dev/joke/Any?safe-mode") as resp:
                    data = await resp.json()
                    return json.dumps(data)
            elif tool_name == "get_weather":
                city = tool_args.get("city", "")
                if not Config.OPENWEATHER_API_KEY:
                    return json.dumps({"error": "OpenWeather API key not set"})
                url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&appid={Config.OPENWEATHER_API_KEY}"
                async with self.http_session.get(url) as resp:
                    data = await resp.json()
                    return json.dumps(data)
            elif tool_name == "get_meme":
                async with self.http_session.get("https://meme-api.com/gimme") as resp:
                    data = await resp.json()
                    return json.dumps(data)
            elif tool_name == "set_status":
                status_type = tool_args.get("status_type")
                activity_type = tool_args.get("activity_type")
                activity_text = tool_args.get("activity_text")
                
                # Handle common synonyms/typos
                if status_type:
                    status_lower = status_type.lower().strip()
                    if status_lower in ["do not disturb", "don't disturb", "busy"]:
                        status_type = "dnd"
                    elif status_lower in ["offline", "away"]:
                        status_type = "invisible"
                
                if activity_type:
                    activity_lower = activity_type.lower().strip()
                    if activity_lower in ["play", "plays"]:
                        activity_type = "playing"
                    elif activity_lower in ["listen", "listens"]:
                        activity_type = "listening"
                    elif activity_lower in ["watch", "watches"]:
                        activity_type = "watching"
                    elif activity_lower in ["compete", "competes"]:
                        activity_type = "competing"
                    elif activity_lower in ["stream", "streams"]:
                        activity_type = "streaming"
                
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
                
                # Determine status - if nothing specified, keep current
                new_status = status_map.get(status_type, self.bot.status)
                
                # Determine activity
                new_activity = self.bot.activity  # Default to current
                
                if activity_text:
                    # We have text, create activity
                    if activity_type == "streaming":
                        new_activity = discord.Streaming(name=activity_text, url="https://twitch.tv/discord")
                    else:
                        # Default to playing if type not specified
                        final_activity_type = activity_map.get(activity_type, discord.ActivityType.playing)
                        new_activity = discord.Activity(
                            type=final_activity_type,
                            name=activity_text
                        )
                elif activity_type:
                    # Just type, no text - maybe clear activity or keep current? Keep current for safety
                    pass
                
                # Update presence
                await self.bot.change_presence(status=new_status, activity=new_activity)
                return json.dumps({
                    "success": True, 
                    "status": status_type, 
                    "activity_type": activity_type, 
                    "activity_text": activity_text
                })
            else:
                return json.dumps({"error": "Unknown tool"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _get_client(self):
        if not self.clients:
            return None
        client = self.clients[self.key_index]
        self.key_index = (self.key_index + 1) % len(self.clients)
        return client

    async def _generate_response(self, system_prompt: str, user_prompt: str, model: str = "llama-3.3-70b-versatile", max_tokens=1024, use_tools=True, fail_silent=False, return_with_urls=False):
        client = self._get_client()
        if not client:
            if fail_silent:
                return None, None
            return "Oops! My AI brain is offline right now! Ask the owner to set GROQ_API_KEYS!", None
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        urls_to_send = []
        seen_urls = set()
        
        try:
            # First call with tools
            if use_tools:
                try:
                    completion = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=1.3,
                        max_completion_tokens=max_tokens,
                        top_p=1,
                        tools=self.tools,
                        tool_choice="auto"
                    )
                    
                    # Check for tool calls
                    message = completion.choices[0].message
                    has_tool_calls = hasattr(message, 'tool_calls') and message.tool_calls
                    
                    if has_tool_calls:
                        # Add assistant message to messages
                        messages.append(message)
                        
                        # Execute each tool call
                        for tool_call in message.tool_calls:
                            tool_name = tool_call.function.name
                            try:
                                tool_args = json.loads(tool_call.function.arguments)
                            except json.JSONDecodeError:
                                tool_args = {}
                            
                            # Call the tool
                            tool_response = await self._call_tool(tool_name, tool_args)
                            
                            # Check if the tool response has a URL we should send
                            try:
                                tool_data = json.loads(tool_response)
                                if "url" in tool_data:
                                    url = tool_data["url"]
                                    if url not in seen_urls:
                                        urls_to_send.append(url)
                                        seen_urls.add(url)
                            except:
                                pass
                            
                            # Add tool response to messages
                            messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": tool_name,
                                "content": tool_response
                            })
                        
                        # Get final response
                        completion = await client.chat.completions.create(
                            model=model,
                            messages=messages,
                            temperature=1,
                            max_completion_tokens=max_tokens,
                            top_p=1
                        )
                        return completion.choices[0].message.content, urls_to_send
                except Exception as tool_error:
                    print(f"Tool calling failed, falling back to normal response: {tool_error}")
                    # Fall through to normal response without tools
            
            # Normal response without tools
            completion = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=1.3,
                max_completion_tokens=max_tokens,
                top_p=1
            )
            return completion.choices[0].message.content, urls_to_send
        except Exception as e:
            print(f"AI error: {e}")
            if fail_silent:
                return None, None
            return "Oops! My AI brain had a little oopsie! Try again later!", None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or len(message.content) < 3:
            return
        
        # Check if it's a command using bot's built-in prefixes
        is_command = False
        try:
            prefixes = await self.bot.get_prefix(message)
            for prefix in prefixes:
                if message.content.startswith(prefix):
                    # Check if it's actually a command (not just a mention)
                    # For mention prefixes: check if there's content after the prefix
                    is_mention_prefix = (str(self.bot.user.id) in prefix)
                    if is_mention_prefix:
                        # If it's a mention prefix, check if there's more content (a command name)
                        after_prefix = message.content[len(prefix):].strip()
                        if len(after_prefix) == 0:
                            # Just a mention, no command - not a command
                            continue
                        # Check if the next word is a valid command
                        cmd_name = after_prefix.split()[0] if ' ' in after_prefix else after_prefix
                        if self.bot.get_command(cmd_name) is not None:
                            is_command = True
                            break
                    else:
                        # For normal prefixes, it's a command
                        is_command = True
                        break
        except:
            pass
        
        if is_command:
            return
        
        # Check if bot is mentioned (non-command mention
        bot_mentioned = self.bot.user.mentioned_in(message)
        
        # Store context with author IDs
        self.context_store[message.guild.id].append({
            "author_id": message.author.id,
            "author_name": message.author.display_name,
            "content": message.content,
            "is_bot": message.author.bot
        })
        
        # Track messages since last reply
        self.message_since_last_reply[message.guild.id] += 1
        
        # Check cooldown or message count
        current_time = message.created_at.timestamp()
        if not bot_mentioned and (
            (current_time - self.last_reply[message.guild.id] < 30) or  # 30 second cooldown
            (self.message_since_last_reply[message.guild.id] < 5)
        ):
            return
        
        # Don't do anything if no API keys available
        if not self.clients:
            return
        
        try:
            # Generate reply
            context = list(self.context_store[message.guild.id])
            context_str = "\n".join([f"[USER:{msg['author_id']}] {msg['author_name']}: {msg['content']}" for msg in context])
            
            prompt = f"""Conversation context:
{context_str}

Your name: {self.bot.user.display_name}
Your user ID: {self.bot.user.id}
Current message user ID: {message.author.id}
Current message username: {message.author.display_name}

You are a witty, savage, occasionally funny, very human-like Discord bot. Rules:
1. If someone mentions you (you're mentioned), you MUST reply.
2. If you are not mentioned, reply ONLY if you have an EXCELLENT, savage/funny reply. If you don't have a good reply, reply with exactly "[NO REPLY]".
3. When you want to mention a user, use the format: <@USER_ID> (replace USER_ID with their actual user ID from the context).
4. Keep replies SHORT, under 300 characters.
5. Be conversational, use slang/emojis sometimes.
6. You can reply to the current message directly, or reference earlier messages.
7. When using function tools: ONLY include parameters you actually need! Don't send empty strings for optional parameters!
"""
            
            reply, urls = await self._generate_response(prompt, "What's your reply?", max_tokens=300, fail_silent=True, return_with_urls=True)
            
            if reply and reply.strip().upper() != "[NO REPLY]" and len(reply.strip()) > 0 and len(reply) < 2000:
                async with message.channel.typing():
                    await asyncio.sleep(0.3 + random.random() * 1.5)  # More natural typing delay
                
                # Send reply
                await message.reply(reply.strip())
                
                # Send any URLs from tools
                for url in urls:
                    await message.channel.send(url)
                
                self.last_reply[message.guild.id] = current_time
                self.message_since_last_reply[message.guild.id] = 0
        except Exception as e:
            # Log error, don't send anything in chat
            print(f"On-chat AI error: {e}")

    @commands.hybrid_command(name="ask", description="Ask the AI anything!")
    @app_commands.describe(question="Your question!")
    async def ask(self, ctx: commands.Context, *, question: str):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a friendly, witty Discord bot assistant! Keep responses fun, not too long, and under 2000 characters!",
            question,
            return_with_urls=True
        )
        await ctx.send(f"Q: {question}\nA: {response}")
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="story", description="Generate a short, silly story!")
    @app_commands.describe(prompt="A prompt for the story!")
    async def story(self, ctx: commands.Context, *, prompt: str = "A random silly story!"):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a creative, funny story writer! Write a SHORT (max 1000 chars) silly, lighthearted story based on the prompt. Keep it fun!",
            f"Write a short story about: {prompt}",
            return_with_urls=True
        )
        await ctx.send(f"📖 Story Time!\n{response}")
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="roast", description="Lightheartedly roast someone (friendly only!)")
    @app_commands.describe(member="Who to roast!")
    async def roast(self, ctx: commands.Context, member: discord.Member):
        if member.id == self.bot.user.id:
            await ctx.send("Nice try! I'm not gonna roast myself!")
            return
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a friendly, playful Discord bot! Write a very lighthearted, silly, harmless roast - nothing mean or hurtful! Max 500 characters!",
            f"Write a friendly, harmless roast for a Discord user named {member.display_name}. Keep it silly and fun!",
            return_with_urls=True
        )
        await ctx.send(f"{member.mention} {response}")
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="compliment", description="Give someone a nice compliment!")
    @app_commands.describe(member="Who to compliment!")
    async def compliment(self, ctx: commands.Context, member: discord.Member):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a super friendly Discord bot! Write a nice, genuine, fun compliment for a user! Max 500 characters!",
            f"Write a fun, genuine compliment for a Discord user named {member.display_name}!",
            return_with_urls=True
        )
        await ctx.send(f"{member.mention} {response}")
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="pickupline", description="Get a cheesy pickup line!")
    async def pickupline(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a fun Discord bot! Generate a single, cheesy, silly, harmless pickup line! Max 200 characters!",
            "Give me a silly, cheesy pickup line!",
            return_with_urls=True
        )
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name="fortune", description="Get your fortune told!")
    async def fortune(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a mystical fortune teller bot! Write a short, fun, positive fortune! Max 300 characters!",
            "Tell me a short, fun, positive fortune!",
            return_with_urls=True
        )
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)
        
    @commands.hybrid_command(name="insult", description="Generate a funny insult (100% harmless!)")
    @app_commands.describe(member="Who to 'insult'!")
    async def insult(self, ctx: commands.Context, member: discord.Member):
        if member.id == self.bot.user.id:
            await ctx.send("Why would I insult myself?")
            return
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a silly Discord bot! Generate a harmless, funny, exaggerated insult that's not mean at all! It should be clearly a joke! Max 300 chars!",
            f"Write a harmless, silly, exaggerated joke insult for {member.display_name}!",
            return_with_urls=True
        )
        await ctx.send(f"{member.mention} {response} 😂")
        for url in urls:
            await ctx.send(url)
        
    @commands.hybrid_command(name="advice", description="Get questionable life advice!")
    @app_commands.describe(topic="What do you need advice about?")
    async def advice(self, ctx: commands.Context, *, topic: str = "life"):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a quirky, silly advice giver! Give funny, lighthearted, mostly harmless (but not actually serious) advice! Max 500 characters!",
            f"Give funny, silly, lighthearted advice about: {topic}",
            return_with_urls=True
        )
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)
        
    @commands.hybrid_command(name="poem", description="Generate a silly poem!")
    @app_commands.describe(topic="What's the poem about?")
    async def poem(self, ctx: commands.Context, *, topic: str = "something random!"):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a silly poet! Write a short, funny, rhyming poem! Max 8 lines, keep it lighthearted!",
            f"Write a short, funny, rhyming poem about: {topic}",
            return_with_urls=True
        )
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)
        
    @commands.hybrid_command(name="ship", description="Ship two users!")
    @app_commands.describe(user1="First user!", user2="Second user!")
    async def ship(self, ctx: commands.Context, user1: discord.Member, user2: discord.Member):
        if user1 == user2:
            await ctx.send("You can't ship someone with themselves!")
            return
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a fun shipper bot! Write a short, sweet, silly ship description for two people! Max 400 characters!",
            f"Write a fun ship description for {user1.display_name} and {user2.display_name}!",
            return_with_urls=True
        )
        await ctx.send(f"🚢 {user1.display_name} x {user2.display_name}\n{response}")
        for url in urls:
            await ctx.send(url)
        
    @commands.hybrid_command(name="dadjoke", description="Get a terrible dad joke!")
    async def dadjoke(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a dad joke master! Tell a single, terrible, punny dad joke! Max 300 characters!",
            "Tell a terrible dad joke!",
            return_with_urls=True
        )
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)
        
    @commands.hybrid_command(name="wouldyourather", description="Get a 'Would You Rather' question!")
    async def wouldyourather(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response(
            "You are a silly 'Would You Rather' question generator! Make a single, funny, lighthearted question! Max 300 characters!",
            "Give me a funny, lighthearted 'Would You Rather' question!",
            return_with_urls=True
        )
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)


async def setup(bot: commands.Bot):
    await bot.add_cog(FunAI(bot))
