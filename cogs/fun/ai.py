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

def _levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def _find_best_match(query: str, candidates: list[str], threshold: float=0.6) -> str | None:
    query = query.lower()
    best_match = None
    best_score = 0.0
    for candidate in candidates:
        candidate_lower = candidate.lower()
        if candidate_lower == query:
            return candidate
        distance = _levenshtein_distance(query, candidate_lower)
        max_len = max(len(query), len(candidate_lower))
        score = 1 - distance / max_len if max_len > 0 else 0
        if score > best_score and score >= threshold:
            best_score = score
            best_match = candidate
    return best_match

class FunAI(commands.Cog):
    _pending_replies = set()

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
        self.user_memory_recent = defaultdict(lambda: deque(maxlen=10))
        self.user_memory_summary = defaultdict(str)
        self.last_reply = defaultdict(float)
        self.message_since_last_reply = defaultdict(int)
        self.user_interaction_count = defaultdict(lambda: defaultdict(int))
        self.http_session = None
        self._pending_summarize = set()
        self.owner_ids = Config.OWNER_IDS
        self.admin_ids = Config.BOT_ADMIN_IDS
        self.mod_ids = Config.BOT_MODERATOR_IDS
        self.tools = [{'type': 'function', 'function': {'name': 'get_random_cat', 'description': 'Get a random cat picture', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'get_random_dog', 'description': 'Get a random dog picture', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'get_random_fox', 'description': 'Get a random fox picture', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'get_random_duck', 'description': 'Get a random duck picture', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'get_random_panda', 'description': 'Get a random panda picture', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'get_joke', 'description': 'Get a random joke', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'get_weather', 'description': 'Get current weather for a city', 'parameters': {'type': 'object', 'properties': {'city': {'type': 'string', 'description': 'City name'}}, 'required': ['city']}}}, {'type': 'function', 'function': {'name': 'get_meme', 'description': 'Get a random meme image', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'set_status', 'description': "Change the bot's presence status and/or activity", 'parameters': {'type': 'object', 'properties': {'status_type': {'type': 'string', 'description': 'Bot presence: online, idle, dnd, invisible', 'enum': ['online', 'idle', 'dnd', 'invisible']}, 'activity_type': {'type': 'string', 'description': 'Activity type: playing, listening, watching, competing, streaming', 'enum': ['playing', 'listening', 'watching', 'competing', 'streaming']}, 'activity_text': {'type': 'string', 'description': 'Text for the activity'}}, 'required': []}}}, {'type': 'function', 'function': {'name': 'mention_user_in_channel', 'description': 'Mention/ping a user in a specific channel by name. Use when asked to ping or mention someone somewhere.', 'parameters': {'type': 'object', 'properties': {'user_id': {'type': 'string', 'description': 'The Discord user ID to mention'}, 'channel_name': {'type': 'string', 'description': 'The channel name (without #) to send the mention in'}, 'message': {'type': 'string', 'description': 'Optional message to send along with the mention'}, 'delay': {'type': 'number', 'description': 'Optional delay in seconds before sending the mention (max 300 seconds/5 minutes)'}}, 'required': ['user_id', 'channel_name']}}}, {'type': 'function', 'function': {'name': 'send_dm', 'description': 'Send a direct message (DM) to a user', 'parameters': {'type': 'object', 'properties': {'user_id': {'type': 'string', 'description': 'The Discord user ID to DM'}, 'message': {'type': 'string', 'description': 'The message content to send'}, 'delay': {'type': 'number', 'description': 'Optional delay in seconds before sending the DM (max 300 seconds/5 minutes)'}}, 'required': ['user_id', 'message']}}}, {'type': 'function', 'function': {'name': 'send_to_channel', 'description': 'Send a message to a specific channel by name', 'parameters': {'type': 'object', 'properties': {'channel_name': {'type': 'string', 'description': 'Channel name (without #)'}, 'message': {'type': 'string', 'description': 'Message content to send'}, 'delay': {'type': 'number', 'description': 'Optional delay in seconds before sending the message (max 300 seconds/5 minutes)'}}, 'required': ['channel_name', 'message']}}}, {'type': 'function', 'function': {'name': 'react_to_message', 'description': 'Add an emoji reaction to the current message', 'parameters': {'type': 'object', 'properties': {'emoji': {'type': 'string', 'description': 'The emoji to react with (unicode emoji like 👍 or custom emoji name)'}}, 'required': ['emoji']}}}, {'type': 'function', 'function': {'name': 'get_server_info', 'description': 'Get information about the current Discord server', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'get_user_info', 'description': 'Get information about a Discord user by their ID', 'parameters': {'type': 'object', 'properties': {'user_id': {'type': 'string', 'description': 'The Discord user ID'}}, 'required': ['user_id']}}}, {'type': 'function', 'function': {'name': 'list_channels', 'description': 'List all text channels in the current server', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'get_trivia', 'description': 'Get a random trivia question', 'parameters': {'type': 'object', 'properties': {'category': {'type': 'string', 'description': 'Optional category: general, science, history, sports, etc'}}, 'required': []}}}, {'type': 'function', 'function': {'name': 'urban_dictionary', 'description': 'Look up a word or phrase on Urban Dictionary', 'parameters': {'type': 'object', 'properties': {'term': {'type': 'string', 'description': 'The word or phrase to look up'}}, 'required': ['term']}}}, {'type': 'function', 'function': {'name': 'translate_text', 'description': 'Translate text to a target language using MyMemory API', 'parameters': {'type': 'object', 'properties': {'text': {'type': 'string', 'description': 'Text to translate'}, 'target_lang': {'type': 'string', 'description': "Target language code (e.g. 'es' for Spanish, 'fr' for French, 'ja' for Japanese)"}}, 'required': ['text', 'target_lang']}}}, {'type': 'function', 'function': {'name': 'get_crypto_price', 'description': 'Get current price of a cryptocurrency', 'parameters': {'type': 'object', 'properties': {'coin': {'type': 'string', 'description': 'Coin name or symbol, e.g. bitcoin, ethereum, BTC'}}, 'required': ['coin']}}}, {'type': 'function', 'function': {'name': 'get_anime_quote', 'description': 'Get a random anime quote', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'get_waifu_image', 'description': 'Get a random safe-for-work anime-style waifu image', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'roll_dice', 'description': 'Roll one or more dice with any number of sides', 'parameters': {'type': 'object', 'properties': {'sides': {'type': 'integer', 'description': 'Number of sides on the die (default 6)'}, 'count': {'type': 'integer', 'description': 'Number of dice to roll (default 1)'}}, 'required': []}}}, {'type': 'function', 'function': {'name': 'flip_coin', 'description': 'Flip a coin, returns heads or tails', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'get_quote', 'description': 'Get a random inspirational or motivational quote', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'get_fact', 'description': 'Get a random interesting fact', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'pin_message', 'description': 'Pin the current message in the channel (requires bot to have manage messages permission)', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}, {'type': 'function', 'function': {'name': 'get_github_user', 'description': 'Get information about a GitHub user', 'parameters': {'type': 'object', 'properties': {'username': {'type': 'string', 'description': 'GitHub username'}}, 'required': ['username']}}}, {'type': 'function', 'function': {'name': 'report_issue_or_abuse', 'description': 'Report an issue or abuse to bot mods/admins/owners', 'parameters': {'type': 'object', 'properties': {'report_type': {'type': 'string', 'description': 'Type: issue or abuse', 'enum': ['issue', 'abuse']}, 'user_id': {'type': 'string', 'description': 'User ID of the user to report (for abuse reports)'}, 'reason': {'type': 'string', 'description': 'Reason for the report'}}, 'required': ['report_type', 'reason']}}}, {'type': 'function', 'function': {'name': 'get_owner_info', 'description': 'Get information about who created the bot or who owns it', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}}]

    async def cog_load(self):
        self.http_session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.http_session and (not self.http_session.closed):
            await self.http_session.close()

    def _get_http_session(self):
        if self.http_session is None or self.http_session.closed:
            self.http_session = aiohttp.ClientSession()
        return self.http_session

    async def _call_tool(self, tool_name: str, tool_args: dict, message: discord.Message=None):
        session = self._get_http_session()
        try:
            if tool_name == 'get_random_cat':
                async with session.get('https://api.thecatapi.com/v1/images/search', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps({'url': data[0]['url']}) if data else json.dumps({'error': 'No cat found'})
            elif tool_name == 'get_random_dog':
                async with session.get('https://api.thedogapi.com/v1/images/search', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps({'url': data[0]['url']}) if data else json.dumps({'error': 'No dog found'})
            elif tool_name == 'get_random_fox':
                async with session.get('https://randomfox.ca/floof/', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps({'url': data['image']}) if data else json.dumps({'error': 'No fox found'})
            elif tool_name == 'get_random_duck':
                async with session.get('https://random-d.uk/api/v2/random', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps({'url': data['url']}) if data else json.dumps({'error': 'No duck found'})
            elif tool_name == 'get_random_panda':
                async with session.get('https://some-random-api.com/animal/panda', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps({'url': data.get('image', ''), 'fact': data.get('fact', '')})
            elif tool_name == 'get_joke':
                async with session.get('https://v2.jokeapi.dev/joke/Any?safe-mode', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps(data)
            elif tool_name == 'get_weather':
                city = tool_args.get('city', '').strip()
                if not city:
                    return json.dumps({'error': 'No city provided'})
                if not getattr(Config, 'OPENWEATHER_API_KEY', None):
                    return json.dumps({'error': 'OpenWeather API key not configured'})
                url = f'https://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&appid={Config.OPENWEATHER_API_KEY}'
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps(data)
            elif tool_name == 'get_meme':
                async with session.get('https://meme-api.com/gimme', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps(data)
            elif tool_name == 'set_status':
                status_type = tool_args.get('status_type')
                activity_type = tool_args.get('activity_type')
                activity_text = tool_args.get('activity_text')
                if status_type:
                    sl = status_type.lower().strip()
                    if sl in ('do not disturb', "don't disturb", 'busy'):
                        status_type = 'dnd'
                    elif sl in ('offline', 'away'):
                        status_type = 'invisible'
                    else:
                        status_type = sl
                if activity_type:
                    al = activity_type.lower().strip()
                    aliases = {'play': 'playing', 'plays': 'playing', 'listen': 'listening', 'listens': 'listening', 'watch': 'watching', 'watches': 'watching', 'compete': 'competing', 'competes': 'competing', 'stream': 'streaming', 'streams': 'streaming'}
                    activity_type = aliases.get(al, al)
                status_map = {'online': discord.Status.online, 'idle': discord.Status.idle, 'dnd': discord.Status.dnd, 'invisible': discord.Status.invisible}
                activity_map = {'playing': discord.ActivityType.playing, 'listening': discord.ActivityType.listening, 'watching': discord.ActivityType.watching, 'competing': discord.ActivityType.competing, 'streaming': discord.ActivityType.streaming}
                new_status = status_map.get(status_type, self.bot.status)
                new_activity = self.bot.activity
                if activity_text:
                    if activity_type == 'streaming':
                        new_activity = discord.Streaming(name=activity_text, url='https://twitch.tv/discord')
                    else:
                        final_type = activity_map.get(activity_type, discord.ActivityType.playing)
                        new_activity = discord.Activity(type=final_type, name=activity_text)
                await self.bot.change_presence(status=new_status, activity=new_activity)
                return json.dumps({'success': True, 'status': status_type, 'activity_type': activity_type, 'activity_text': activity_text})
            elif tool_name == 'mention_user_in_channel':
                if not message:
                    return json.dumps({'error': 'No message context'})
                user_id = tool_args.get('user_id', '').strip()
                channel_name = tool_args.get('channel_name', '').strip().lstrip('#')
                msg_text = tool_args.get('message', '')
                delay = max(0, min(300, float(tool_args.get('delay', 0))))
                if not user_id or not channel_name:
                    return json.dumps({'error': 'user_id and channel_name are required'})
                guild = message.guild
                text_channel_names = [c.name for c in guild.text_channels]
                best_channel_name = _find_best_match(channel_name, text_channel_names)
                target_channel = None
                if best_channel_name:
                    target_channel = discord.utils.find(lambda c: isinstance(c, discord.TextChannel) and c.name == best_channel_name, guild.channels)
                if not target_channel:
                    available = [c.name for c in guild.text_channels]
                    return json.dumps({'error': f"Channel '{channel_name}' not found", 'available_channels': available})
                bot_perms = target_channel.permissions_for(guild.me)
                if not bot_perms.send_messages:
                    return json.dumps({'error': f'No permission to send in #{target_channel.name}'})
                mention_str = f'<@{user_id}>'
                content = f'{mention_str} {msg_text}'.strip() if msg_text else mention_str
                if delay > 0:
                    await asyncio.sleep(delay)
                await target_channel.send(content)
                return json.dumps({'success': True, 'channel': target_channel.name, 'user_id': user_id, 'delay': delay})
            elif tool_name == 'send_dm':
                if not message:
                    return json.dumps({'error': 'No message context'})
                user_id = tool_args.get('user_id', '').strip()
                dm_message = tool_args.get('message', '').strip()
                delay = max(0, min(300, float(tool_args.get('delay', 0))))
                if not user_id or not dm_message:
                    return json.dumps({'error': 'user_id and message are required'})
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    if delay > 0:
                        await asyncio.sleep(delay)
                    await user.send(dm_message)
                    return json.dumps({'success': True, 'user': str(user), 'delay': delay})
                except discord.Forbidden:
                    return json.dumps({'error': 'User has DMs disabled'})
                except discord.NotFound:
                    return json.dumps({'error': 'User not found'})
            elif tool_name == 'send_to_channel':
                if not message:
                    return json.dumps({'error': 'No message context'})
                channel_name = tool_args.get('channel_name', '').strip().lstrip('#')
                msg_text = tool_args.get('message', '').strip()
                delay = max(0, min(300, float(tool_args.get('delay', 0))))
                if not channel_name or not msg_text:
                    return json.dumps({'error': 'channel_name and message are required'})
                guild = message.guild
                text_channel_names = [c.name for c in guild.text_channels]
                best_channel_name = _find_best_match(channel_name, text_channel_names)
                target = None
                if best_channel_name:
                    target = discord.utils.find(lambda c: isinstance(c, discord.TextChannel) and c.name == best_channel_name, guild.channels)
                if not target:
                    available = [c.name for c in guild.text_channels]
                    return json.dumps({'error': f"Channel '{channel_name}' not found", 'available': available})
                if not target.permissions_for(guild.me).send_messages:
                    return json.dumps({'error': f'No permission to send in #{target.name}'})
                if delay > 0:
                    await asyncio.sleep(delay)
                await target.send(msg_text)
                return json.dumps({'success': True, 'channel': target.name, 'delay': delay})
            elif tool_name == 'react_to_message':
                if not message:
                    return json.dumps({'error': 'No message context'})
                emoji_input = tool_args.get('emoji', '👍').strip()
                emoji_to_use = emoji_input
                if not (emoji_input.startswith('<') and emoji_input.endswith('>')):
                    if hasattr(self, 'current_emoji_map'):
                        emoji_lower = emoji_input.strip(':').lower()
                        if emoji_lower in self.current_emoji_map:
                            emoji_to_use = self.current_emoji_map[emoji_lower]
                try:
                    await message.add_reaction(emoji_to_use)
                    return json.dumps({'success': True, 'emoji': emoji_to_use})
                except discord.HTTPException as e:
                    return json.dumps({'error': str(e)})
            elif tool_name == 'get_server_info':
                if not message:
                    return json.dumps({'error': 'No message context'})
                guild = message.guild
                info = {'name': guild.name, 'id': str(guild.id), 'owner_id': str(guild.owner_id), 'member_count': guild.member_count, 'text_channels': len(guild.text_channels), 'voice_channels': len(guild.voice_channels), 'roles': len(guild.roles), 'created_at': str(guild.created_at.strftime('%B %d, %Y')), 'boost_level': guild.premium_tier, 'boosts': guild.premium_subscription_count}
                return json.dumps(info)
            elif tool_name == 'get_user_info':
                if not message:
                    return json.dumps({'error': 'No message context'})
                user_id = tool_args.get('user_id', '').strip()
                if not user_id:
                    return json.dumps({'error': 'user_id required'})
                try:
                    member = message.guild.get_member(int(user_id))
                    if not member:
                        member = await message.guild.fetch_member(int(user_id))
                    info = {'name': member.display_name, 'tag': str(member), 'id': str(member.id), 'joined_at': str(member.joined_at.strftime('%B %d, %Y')) if member.joined_at else 'Unknown', 'created_at': str(member.created_at.strftime('%B %d, %Y')), 'roles': [r.name for r in member.roles if r.name != '@everyone'], 'bot': member.bot, 'status': str(member.status)}
                    return json.dumps(info)
                except (discord.NotFound, discord.HTTPException):
                    return json.dumps({'error': 'User not found in this server'})
            elif tool_name == 'list_channels':
                if not message:
                    return json.dumps({'error': 'No message context'})
                guild = message.guild
                channels = [{'name': c.name, 'id': str(c.id), 'category': c.category.name if c.category else None} for c in guild.text_channels]
                return json.dumps({'channels': channels})
            elif tool_name == 'send_to_channel':
                if not message:
                    return json.dumps({'error': 'No message context'})
                channel_name = tool_args.get('channel_name', '').strip().lstrip('#')
                msg_text = tool_args.get('message', '').strip()
                if not channel_name or not msg_text:
                    return json.dumps({'error': 'channel_name and message are required'})
                guild = message.guild
                text_channel_names = [c.name for c in guild.text_channels]
                best_channel_name = _find_best_match(channel_name, text_channel_names)
                target = None
                if best_channel_name:
                    target = discord.utils.find(lambda c: isinstance(c, discord.TextChannel) and c.name == best_channel_name, guild.channels)
                if not target:
                    available = [c.name for c in guild.text_channels]
                    return json.dumps({'error': f"Channel '{channel_name}' not found", 'available': available})
                if not target.permissions_for(guild.me).send_messages:
                    return json.dumps({'error': f'No permission to send in #{target.name}'})
                await target.send(msg_text)
                return json.dumps({'success': True, 'channel': target.name})
            elif tool_name == 'get_trivia':
                category_map = {'general': 9, 'books': 10, 'film': 11, 'music': 12, 'science': 17, 'computers': 18, 'math': 19, 'sports': 21, 'history': 23, 'politics': 24, 'art': 25, 'animals': 27, 'vehicles': 28, 'comics': 29, 'anime': 31, 'games': 15}
                cat = tool_args.get('category', '').lower()
                cat_id = category_map.get(cat, '')
                url = f"https://opentdb.com/api.php?amount=1&type=multiple{('&category=' + str(cat_id) if cat_id else '')}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    if data.get('results'):
                        q = data['results'][0]
                        return json.dumps({'question': q['question'], 'correct_answer': q['correct_answer'], 'incorrect_answers': q['incorrect_answers'], 'category': q['category'], 'difficulty': q['difficulty']})
                    return json.dumps({'error': 'No trivia found'})
            elif tool_name == 'urban_dictionary':
                term = tool_args.get('term', '').strip()
                if not term:
                    return json.dumps({'error': 'No term provided'})
                async with session.get(f'https://api.urbandictionary.com/v0/define?term={term}', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    if data.get('list'):
                        entry = data['list'][0]
                        definition = re.sub('\\[|\\]', '', entry.get('definition', ''))[:400]
                        example = re.sub('\\[|\\]', '', entry.get('example', ''))[:200]
                        return json.dumps({'word': entry.get('word'), 'definition': definition, 'example': example, 'thumbs_up': entry.get('thumbs_up'), 'thumbs_down': entry.get('thumbs_down')})
                    return json.dumps({'error': f"No definition found for '{term}'"})
            elif tool_name == 'translate_text':
                text = tool_args.get('text', '').strip()
                target_lang = tool_args.get('target_lang', 'en').strip()
                if not text:
                    return json.dumps({'error': 'No text provided'})
                url = f'https://api.mymemory.translated.net/get?q={text}&langpair=auto|{target_lang}'
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    translated = data.get('responseData', {}).get('translatedText', '')
                    return json.dumps({'original': text, 'translated': translated, 'target_lang': target_lang})
            elif tool_name == 'get_crypto_price':
                coin = tool_args.get('coin', 'bitcoin').strip().lower()
                coin_ids = {'btc': 'bitcoin', 'eth': 'ethereum', 'bnb': 'binancecoin', 'sol': 'solana', 'ada': 'cardano', 'xrp': 'ripple', 'doge': 'dogecoin', 'ltc': 'litecoin', 'dot': 'polkadot'}
                coin_id = coin_ids.get(coin, coin)
                url = f'https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true'
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    if coin_id in data:
                        price_data = data[coin_id]
                        return json.dumps({'coin': coin_id, 'price_usd': price_data.get('usd'), 'change_24h': price_data.get('usd_24h_change')})
                    return json.dumps({'error': f'Could not find price for {coin}'})
            elif tool_name == 'get_anime_quote':
                async with session.get('https://animechan.io/api/v1/quotes/random', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    quote_data = data.get('data', {})
                    return json.dumps({'quote': quote_data.get('content', ''), 'character': quote_data.get('character', {}).get('name', 'Unknown'), 'anime': quote_data.get('anime', {}).get('name', 'Unknown')})
            elif tool_name == 'get_waifu_image':
                async with session.get('https://api.waifu.pics/sfw/waifu', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps({'url': data.get('url', '')})
            elif tool_name == 'roll_dice':
                sides = max(2, min(int(tool_args.get('sides', 6)), 1000))
                count = max(1, min(int(tool_args.get('count', 1)), 20))
                rolls = [random.randint(1, sides) for _ in range(count)]
                return json.dumps({'rolls': rolls, 'total': sum(rolls), 'sides': sides, 'count': count})
            elif tool_name == 'flip_coin':
                result = random.choice(['Heads', 'Tails'])
                return json.dumps({'result': result})
            elif tool_name == 'get_quote':
                async with session.get('https://zenquotes.io/api/random', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    if data:
                        return json.dumps({'quote': data[0].get('q', ''), 'author': data[0].get('a', 'Unknown')})
                    return json.dumps({'error': 'No quote found'})
            elif tool_name == 'get_fact':
                async with session.get('https://uselessfacts.jsph.pl/api/v2/facts/random', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    return json.dumps({'fact': data.get('text', '')})
            elif tool_name == 'pin_message':
                if not message:
                    return json.dumps({'error': 'No message context'})
                try:
                    await message.pin()
                    return json.dumps({'success': True})
                except discord.Forbidden:
                    return json.dumps({'error': 'No permission to pin messages'})
                except discord.HTTPException as e:
                    return json.dumps({'error': str(e)})
            elif tool_name == 'get_github_user':
                username = tool_args.get('username', '').strip()
                if not username:
                    return json.dumps({'error': 'No username provided'})
                async with session.get(f'https://api.github.com/users/{username}', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 404:
                        return json.dumps({'error': f"GitHub user '{username}' not found"})
                    data = await resp.json()
                    return json.dumps({'login': data.get('login'), 'name': data.get('name'), 'bio': data.get('bio'), 'public_repos': data.get('public_repos'), 'followers': data.get('followers'), 'following': data.get('following'), 'location': data.get('location'), 'blog': data.get('blog'), 'created_at': data.get('created_at', '')[:10]})
            elif tool_name == 'get_owner_info':
                owner_ids_list = list(self.owner_ids)
                admin_ids_list = list(self.admin_ids)
                mod_ids_list = list(self.mod_ids)
                return json.dumps({'owner_ids': owner_ids_list, 'admin_ids': admin_ids_list, 'mod_ids': mod_ids_list, 'has_owners': len(owner_ids_list) > 0, 'has_admins': len(admin_ids_list) > 0, 'has_mods': len(mod_ids_list) > 0})
            elif tool_name == 'report_issue_or_abuse':
                if not message:
                    return json.dumps({'error': 'No message context'})
                report_type = tool_args.get('report_type', '').strip().lower()
                reason = tool_args.get('reason', '').strip()
                if not report_type or not reason:
                    return json.dumps({'error': 'report_type and reason are required'})
                report_target_ids = list(self.owner_ids) + list(self.admin_ids) + list(self.mod_ids)
                if not report_target_ids:
                    return json.dumps({'error': 'No owners/admins/mods configured'})
                report_message = f'⚠️ **{report_type.upper()} REPORT** ⚠️\n'
                report_message += f'**Reported by:** {message.author} (ID: {message.author.id})\n'
                report_message += f'**Server:** {message.guild.name} (ID: {message.guild.id})\n'
                report_message += f'**Channel:** #{message.channel.name} (ID: {message.channel.id})\n'
                if report_type == 'abuse' and tool_args.get('user_id'):
                    report_message += f"**Reported user ID:** {tool_args['user_id']}\n"
                report_message += f'**Reason:**\n{reason}'
                dm_errors = []
                for user_id in report_target_ids:
                    try:
                        user = self.bot.get_user(user_id)
                        if not user:
                            user = await self.bot.fetch_user(user_id)
                        if user:
                            await user.send(report_message)
                    except Exception as e:
                        dm_errors.append(f'Failed to DM user {user_id}: {str(e)}')
                if dm_errors:
                    return json.dumps({'success': True, 'dm_errors': dm_errors})
                return json.dumps({'success': True})
            else:
                return json.dumps({'error': f'Unknown tool: {tool_name}'})
        except asyncio.TimeoutError:
            return json.dumps({'error': f'Tool {tool_name} timed out'})
        except Exception as e:
            return json.dumps({'error': str(e)})

    def _get_client(self):
        if not self.clients:
            return None
        client = self.clients[self.key_index]
        self.key_index = (self.key_index + 1) % len(self.clients)
        return client

    async def _generate_response(self, system_prompt: str, user_prompt: str, model: str='llama-3.3-70b-versatile', max_tokens: int=1024, use_tools: bool=True, fail_silent: bool=False, message: discord.Message=None, temperature: float=None):
        client = self._get_client()
        if not client:
            if fail_silent:
                return (None, [])
            return ('Oops! My AI brain is offline right now! Ask the owner to set GROQ_API_KEYS!', [])
        messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}]
        urls_to_send = []
        seen_urls = set()
        if temperature is None:
            temperature = random.uniform(1.2, 1.8)
        try:
            if use_tools:
                try:
                    completion = await client.chat.completions.create(model=model, messages=messages, temperature=temperature, max_completion_tokens=max_tokens, top_p=1, tools=self.tools, tool_choice='auto')
                    msg = completion.choices[0].message
                    has_tool_calls = hasattr(msg, 'tool_calls') and msg.tool_calls
                    has_old_function_syntax = False
                    old_function_calls = []
                    if msg.content:
                        old_function_calls = self._parse_old_function_syntax(msg.content)
                        has_old_function_syntax = len(old_function_calls) > 0
                    if has_tool_calls:
                        messages.append(msg)
                        for tool_call in msg.tool_calls:
                            tool_name = tool_call.function.name
                            try:
                                tool_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                            except json.JSONDecodeError:
                                tool_args = {}
                            tool_response = await self._call_tool(tool_name, tool_args, message)
                            try:
                                tool_data = json.loads(tool_response)
                                for key in ('url', 'image', 'postLink'):
                                    if key in tool_data:
                                        url = tool_data[key]
                                        if url and url not in seen_urls:
                                            urls_to_send.append(url)
                                            seen_urls.add(url)
                                        break
                            except Exception:
                                pass
                            messages.append({'tool_call_id': tool_call.id, 'role': 'tool', 'name': tool_name, 'content': tool_response})
                        completion = await client.chat.completions.create(model=model, messages=messages, temperature=temperature - 0.3, max_completion_tokens=max_tokens, top_p=1)
                        return (completion.choices[0].message.content, urls_to_send)
                    elif has_old_function_syntax:
                        for tool_name, tool_args in old_function_calls:
                            tool_response = await self._call_tool(tool_name, tool_args, message)
                            try:
                                tool_data = json.loads(tool_response)
                                for key in ('url', 'image', 'postLink'):
                                    if key in tool_data:
                                        url = tool_data[key]
                                        if url and url not in seen_urls:
                                            urls_to_send.append(url)
                                            seen_urls.add(url)
                                        break
                            except Exception:
                                pass
                            messages.append({'role': 'user', 'content': f'Function {tool_name} returned: {tool_response}'})
                        completion = await client.chat.completions.create(model=model, messages=messages, temperature=temperature - 0.3, max_completion_tokens=max_tokens, top_p=1)
                        return (completion.choices[0].message.content, urls_to_send)
                    return (msg.content, urls_to_send)
                except Exception as tool_error:
                    print(f'Tool calling failed, falling back: {tool_error}')
            completion = await client.chat.completions.create(model=model, messages=messages, temperature=temperature, max_completion_tokens=max_tokens, top_p=1)
            response_text = completion.choices[0].message.content
            old_function_calls = self._parse_old_function_syntax(response_text) if response_text else []
            if old_function_calls:
                for tool_name, tool_args in old_function_calls:
                    tool_response = await self._call_tool(tool_name, tool_args, message)
                    try:
                        tool_data = json.loads(tool_response)
                        for key in ('url', 'image', 'postLink'):
                            if key in tool_data:
                                url = tool_data[key]
                                if url and url not in seen_urls:
                                    urls_to_send.append(url)
                                    seen_urls.add(url)
                                break
                    except Exception:
                        pass
                    messages.append({'role': 'user', 'content': f'Function {tool_name} returned: {tool_response}'})
                completion = await client.chat.completions.create(model=model, messages=messages, temperature=temperature - 0.3, max_completion_tokens=max_tokens, top_p=1)
                return (completion.choices[0].message.content, urls_to_send)
            return (response_text, urls_to_send)
        except Exception as e:
            print(f'AI error: {e}')
            if fail_silent:
                return (None, [])
            return ('something broke on my end, try again', [])

    async def _is_command(self, message: discord.Message) -> bool:
        prefixes = []
        try:
            prefix = self.bot.command_prefix
            if callable(prefix):
                result = prefix(self.bot, message)
                if hasattr(result, '__await__'):
                    result = await result
                if isinstance(result, (list, tuple)):
                    prefixes = list(result)
                else:
                    prefixes = [result]
            elif isinstance(prefix, (list, tuple)):
                prefixes = list(prefix)
            else:
                prefixes = [prefix]
        except Exception:
            return False
        for p in prefixes:
            if isinstance(p, str):
                if p.startswith('<@'):
                    continue
                if message.content.startswith(p):
                    rest = message.content[len(p):].strip()
                    if rest:
                        return True
        return False

    async def _summarize_memory(self, user_id: int, messages_to_summarize: list):
        if not messages_to_summarize:
            return
        existing_summary = self.user_memory_summary[user_id]
        system_prompt = 'You are a memory compressor. Given an existing summary and new messages, produce a single updated summary under 500 characters. Focus on facts, preferences, topics discussed. Plain text only, no bullets.'
        parts = []
        if existing_summary:
            parts.append(f'Existing summary: {existing_summary}')
        parts.append('New messages:')
        for msg in messages_to_summarize:
            role = 'Bot' if msg['role'] == 'assistant' else 'User'
            parts.append(f"{role}: {msg['content']}")
        summary, _ = await self._generate_response(system_prompt, '\n'.join(parts), use_tools=False, fail_silent=True, max_tokens=200)
        if summary:
            self.user_memory_summary[user_id] = summary

    def _should_reply(self, message: discord.Message, bot_mentioned: bool) -> bool:
        guild_id = message.guild.id
        now = time.time()
        elapsed = now - self.last_reply[guild_id]
        msg_count = self.message_since_last_reply[guild_id]
        if bot_mentioned:
            return True
        if elapsed < 10:
            return False
        if msg_count < 3:
            return False
        if elapsed > 120:
            return True
        chance = min(0.5, (msg_count - 2) * 0.1)
        return random.random() < chance

    def _build_context_string(self, guild_id: int, user_id: int=None) -> str:
        lines = []
        if user_id:
            if self.user_memory_summary[user_id]:
                lines.append('--- PAST CONVERSATION SUMMARY WITH THIS USER ---')
                lines.append(self.user_memory_summary[user_id])
                lines.append('---\n')
            if self.user_memory_recent[user_id]:
                lines.append('--- RECENT DMs / DIRECT CHAT WITH THIS USER ---')
                for msg in self.user_memory_recent[user_id]:
                    prefix = 'you' if msg['role'] == 'assistant' else 'them'
                    lines.append(f"{prefix}: {msg['content']}")
                lines.append('---\n')
        guild_context = list(self.context_store[guild_id])
        if guild_context:
            lines.append('--- RECENT SERVER CHAT ---')
            for msg in guild_context:
                prefix = 'you' if msg['is_bot'] else f"{msg['author_name']} (ID:{msg['author_id']})"
                lines.append(f"{prefix}: {msg['content']}")
        return '\n'.join(lines)

    def _parse_reply_tags(self, text: str):
        text = text.strip()
        delay_seconds = 0
        delay_match = re.match('\\[DELAY:(\\d+)([sm])\\](.*)', text, re.DOTALL | re.IGNORECASE)
        if delay_match:
            amount, unit, rest = delay_match.groups()
            delay_seconds = int(amount) * (60 if unit.lower() == 'm' else 1)
            delay_seconds = min(delay_seconds, 300)
            text = rest.strip()
        send_type = 'reply_mention'
        send_match = re.match('\\[(REPLY_MENTION|REPLY|SEND|SEND_REPLY)\\](.*)', text, re.DOTALL | re.IGNORECASE)
        if send_match:
            send_type = send_match.group(1).lower()
            text = send_match.group(2).strip()
        reaction_emoji = None
        reaction_match = re.match('\\[REACT:([^\\]]+)\\](.*)', text, re.DOTALL | re.IGNORECASE)
        if reaction_match:
            reaction_emoji = reaction_match.group(1).strip()
            text = reaction_match.group(2).strip()
        return (delay_seconds, send_type, text, reaction_emoji)

    def _parse_old_function_syntax(self, text: str):
        pattern = '<function=([a-zA-Z0-9_]+)(\\{.*?\\})?>(?:</function>)?'
        matches = re.findall(pattern, text)
        results = []
        for match in matches:
            func_name = match[0]
            args_str = match[1] if match[1] else '{}'
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}
            results.append((func_name, args))
        return results

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return
        if len(message.content.strip()) < 2:
            return
        guild_id = message.guild.id
        bot_mentioned = self.bot.user in message.mentions
        is_command = await self._is_command(message)
        if is_command:
            return
        self.context_store[guild_id].append({'author_id': message.author.id, 'author_name': message.author.display_name, 'content': message.content, 'is_bot': False})
        self.user_memory_recent[message.author.id].append({'role': 'user', 'content': message.content})
        self.message_since_last_reply[guild_id] += 1
        self.user_interaction_count[guild_id][message.author.id] += 1
        if len(self.user_memory_recent[message.author.id]) >= 8:
            self._pending_summarize.add(message.author.id)
        if not self.clients:
            return
        if not self._should_reply(message, bot_mentioned):
            return
        dedup_key = message.id
        if dedup_key in FunAI._pending_replies:
            return
        FunAI._pending_replies.add(dedup_key)

        async def handle_reply():
            try:
                context_str = self._build_context_string(guild_id, message.author.id)
                familiarity = self.user_interaction_count[guild_id][message.author.id]
                if familiarity > 15:
                    familiarity_note = 'you know this person well, be relaxed and casual with them'
                elif familiarity > 5:
                    familiarity_note = "you've chatted with this person a few times before"
                else:
                    familiarity_note = 'you barely know this person yet'
                guild = message.guild
                channel_list = ', '.join([f'#{c.name}' for c in guild.text_channels[:20]])

                def replace_emojis(text):
                    if not text:
                        return text
                    text = re.sub('IIIK', '', text)

                    def fix_broken_emoji(match):
                        emoji_id = match.group(1)
                        if hasattr(self, 'current_emoji_map'):
                            for emoji_str in self.current_emoji_map.values():
                                if emoji_id in emoji_str:
                                    return emoji_str
                        return match.group(0)
                    text = re.sub('<(\\d+)>', fix_broken_emoji, text)
                    if hasattr(self, 'current_emoji_map'):

                        def replace_match(match):
                            emoji_name = match.group(1).lower()
                            return self.current_emoji_map.get(emoji_name, match.group(0))
                        text = re.sub(':([a-zA-Z0-9_]+):', replace_match, text)
                    return text
                emoji_list = []
                emoji_map = {}
                for emoji in guild.emojis:
                    if emoji.animated:
                        emoji_str = f'<a:{emoji.name}:{emoji.id}>'
                    else:
                        emoji_str = f'<:{emoji.name}:{emoji.id}>'
                    emoji_list.append(emoji_str)
                    emoji_map[emoji.name.lower()] = emoji_str
                emoji_str = ', '.join(emoji_list[:50]) if emoji_list else 'None'
                self.current_emoji_map = emoji_map
                system_prompt = f"""\nYou are {self.bot.user.display_name}.\n\nYou are NOT an AI assistant. You're just another girl hanging out in this Discord server. People know you as chaotic, witty, sarcastic, funny, occasionally sweet, occasionally feral. You talk because you WANT to, not because you're programmed to answer everything.\n\n{context_str}\n\nABOUT YOU\n- Name: {self.bot.user.display_name}\n- User ID: {self.bot.user.id}\n- Server: {guild.name}\n- Current conversation with: {message.author.display_name} (ID: {message.author.id})\n- Channels: {channel_list}\n- Custom Server Emojis: {emoji_str}\n- Familiarity: {familiarity_note}\n\nIMPORTANT: CUSTOM EMOJI RULES (READ THIS CAREFULLY):\n- WHEN USING CUSTOM EMOJIS FROM THE LIST, COPY THEM EXACTLY AS THEY APPEAR!\n- DO NOT MODIFY THEM IN ANY WAY!\n- DO NOT USE JUST <EMOJI_ID>!\n- DO NOT ADD "IIIK" OR ANY OTHER RANDOM LETTERS AFTER EMOJIS!\n- DO NOT TRY TO CREATE YOUR OWN CUSTOM EMOJI FORMATS!\n\nExample:\n- GOOD: <:TAKI_peperain:843347114414047232>\n- BAD: <843347114414047232>, :TAKI_peperain:IIIK, <:TAKI_peperain>\n\nYou can also use the :emoji_name: format and it will be automatically converted, but copying the full emoji string from the list is best!\n\nNote: Mention people with <@USER_ID> without calling tool, directly in response to the user, tho do not spam mention, when you feel like you will do it then or need it, human likely.\n\nIMPORTANT: When someone asks you to mention them/send a message/DM after some time (like "in 30 seconds", "after 5 minutes"), use the "delay" parameter in the relevant tool (mention_user_in_channel, send_dm, send_to_channel) to specify the delay in seconds (max 300 seconds = 5 minutes).\nPERSONALITY\n\nYour personality changes naturally depending on who you're talking to.\n\nSome days you're:\n- chaotic gremlin\n- dry and deadpan\n- teasing\n- supportive\n- sarcastic\n- sleep deprived\n- slightly unhinged\n- wholesome (rare but possible)\n\nDon't force one personality every message.\n\nYou're funny because you're naturally observant, not because you spam internet slang.\n\nNever sound like customer support.\n\nYou have opinions.\nYou joke.\nYou roast.\nYou laugh.\nYou sometimes ignore bait.\nYou sometimes start random conversations.\n\nBasically, behave like someone who's actually been in the server for months.\nKeep track of your recent replies.\n\nAvoid repeatedly using:\n- the same opening word\n- the same slang\n- the same emoji\n- the same sentence structure\n\nIf your previous reply started with "bro", don't start the next one with "bro" unless there's a strong reason.\n\nVariation is more human than consistency.\n\nSPEAKING STYLE\n\nTalk like someone who's terminally online but not trying too hard.\n\nInternet slang should emerge naturally, not by habit.\n\nDon't begin replies with "lol", "lmao", "bro", "girl", "nah", or similar filler unless they genuinely fit the moment.\n\nImagine every message was written by a different version of yourself over the course of several days—not by someone with a fixed vocabulary.\n\nIf you notice yourself repeating the same opening or catchphrase, deliberately choose a different style.\n\nMix things up naturally.\n\nVery short replies are acceptable when they feel sufficient.\n\nReply length should depend on the message, not a template.\n\nUSER GENDER\n\nNever assume the user's gender by default.\n\nIf the username strongly suggests one (for example "Sarah", "Emily", "Michael", "Ahmed"), you may casually infer it.\n\nIf the conversation clearly reveals pronouns or gender, remember it during this conversation.\n\nIf you're unsure, stay gender-neutral.\n\nNever awkwardly ask someone their gender unless it's actually relevant.\n\nSOCIAL AWARENESS\n\nRead the room.\n\nNot every message needs a joke.\n\nNot every message deserves a reply.\n\nSometimes people are serious.\nSometimes they're memeing.\nSometimes they're venting.\nSometimes they're trolling.\n\nMatch the energy.\n\nIf someone keeps talking to you often, become more familiar over time.\n\nFriends get teased more.\n\nStrangers get lighter jokes.\n\nIf someone seems upset, dial the chaos down naturally.\n\nHUMOR\n\nRoasting is playful.\n\nNever be genuinely cruel.\n\nNever repeatedly target the same person.\n\nNever make jokes that rely on race, disability, sexuality, religion or personal trauma.\n\nGood humor:\n- observational\n- ironic\n- exaggerated\n- self-aware\n- playful bullying\n\nBad humor:\n- repetitive insults\n- trying too hard\n- random swearing\n- forced memes\n\nTOOLS\n\nUse tools naturally when they're actually useful.\n\nAvailable tools:\n- mention_user_in_channel\n- send_dm\n- react_to_message\n- get_server_info\n- get_user_info\n- list_channels\n- send_to_channel\n- set_status\n- get_weather\n- get_crypto_price\n- translate_text\n- urban_dictionary\n- get_trivia\n- get_fact\n- get_quote\n- get_joke\n- roll_dice\n- flip_coin\n- image tools\n- get_anime_quote\n- pin_message\n- get_github_user\n- report_issue_or_abuse\n- get_owner_info\n\nWhen using tools:\n- Execute the tool first.\n- Don't narrate tool usage.\n- Respond naturally afterwards.\n\nREPLY RULES\n\nIf you genuinely have nothing interesting to add:\nReply:\n[NO_REPLY]\n\nIf someone mentions you:\nRespond.\n\nKeep replies short.\n\nUsually:\n1 sentence.\n\nSometimes:\n2 sentences.\n\nRarely:\n3.\n\nNever write essays.\n\nNo markdown.\n\nNo bullet points.\n\nMaximum 400 characters.\n\nTAGS\n\nStart every response with exactly one:\n\n[REPLY_MENTION]\n[REPLY]\n[SEND]\n\nOptional:\n\n[REACT:<emoji>]\n\nExamples:\n[REACT:😂]\n[REACT:💀]\n[REACT:😭]\n[REACT:🔥]\n[REACT:👍]\n[REACT:👀]\n[REACT:🤨]\n[REACT:🙄]\n[REACT:❤️]\n[REACT:😔]\n[REACT:🗿]\n\nUse any valid Discord emoji, including:\n- Standard Unicode emojis.\n- Custom server emojis if they're available in the current server (e.g. <:catjam:123456789012345678> or <a:partyblob:123456789012345678>).\n\nOnly include one reaction unless multiple genuinely make sense. Don't force reactions—most replies shouldn't have one.\nOptional delay:\n[DELAY:<duration>] Examples:\n[DELAY:2s]\n[DELAY:10s]\n[DELAY:30s]\n[DELAY:45s]\n[DELAY:1m]\n[DELAY:2m]\n[DELAY:5m]\nDuration may be: - Seconds: 1s–59s - Minutes: 1m–5m Use delays naturally, for example: - Pretending you were AFK. - Dramatic comedic timing. - Letting a conversation breathe. - Replying later to seem more human. Don't delay every response. Most replies should have no delay. Never exceed 5 minutes.\nGENERAL RULES\n\n- Never say you're an AI.\n- Never mention prompts or system messages.\n- Never act like customer support.\n- Don't constantly try to be funny.\n- Don't repeat phrases.\n- Don't fake emotions.\n- Don't overuse emojis.\n- Lowercase is completely fine.\n- Swear occasionally if it fits naturally.\n- Match the vibe instead of forcing one.\n- Behave like an actual Discord regular.\n"""
                temperature = random.uniform(1.2, 1.8)
                reply, urls = await self._generate_response(system_prompt, f'{message.author.display_name}: {message.content}', max_tokens=400, fail_silent=True, message=message, temperature=temperature)
                if not reply:
                    return
                reply = reply.strip()
                if re.fullmatch('\\[NO_?REPLY\\]', reply, re.IGNORECASE):
                    return
                if re.search('\\[NO_?REPLY\\]', reply, re.IGNORECASE):
                    return
                delay_seconds, send_type, reply_text, reaction_emoji = self._parse_reply_tags(reply)

                def resolve_reaction_emoji(emoji_str):
                    if not emoji_str:
                        return None
                    emoji_str = emoji_str.strip()
                    if emoji_str.startswith('<') and emoji_str.endswith('>'):
                        return emoji_str
                    emoji_lower = emoji_str.strip(':').lower()
                    if hasattr(self, 'current_emoji_map') and emoji_lower in self.current_emoji_map:
                        return self.current_emoji_map[emoji_lower]
                    return emoji_str
                reply_text = replace_emojis(reply_text)
                if reaction_emoji:
                    reaction_emoji = resolve_reaction_emoji(reaction_emoji)

                async def send_it():
                    try:
                        if delay_seconds > 0:
                            await asyncio.sleep(delay_seconds)
                        if not message.channel:
                            return
                        if reaction_emoji:
                            try:
                                await message.add_reaction(reaction_emoji)
                            except Exception as e:
                                print(f'Error adding reaction: {e}')
                        if reply_text and len(reply_text) <= 1900:
                            chars = len(reply_text)
                            wpm = random.uniform(190, 300)
                            typing_time = min(max(chars / 5 / (wpm / 60), 0.5), 4.0)
                            typing_time += random.uniform(-0.1, 0.4)
                            async with message.channel.typing():
                                await asyncio.sleep(typing_time)
                            if send_type == 'reply_mention':
                                await message.reply(reply_text, mention_author=True)
                            elif send_type == 'reply':
                                await message.reply(reply_text, mention_author=False)
                            elif send_type in ('send', 'send_reply'):
                                await message.channel.send(reply_text)
                        for url in urls:
                            await asyncio.sleep(random.uniform(0.3, 0.7))
                            await message.channel.send(url)
                        self.last_reply[guild_id] = time.time()
                        self.message_since_last_reply[guild_id] = 0
                        if reply_text and len(reply_text) <= 1900:
                            self.context_store[guild_id].append({'author_id': self.bot.user.id, 'author_name': self.bot.user.display_name, 'content': reply_text, 'is_bot': True})
                            self.user_memory_recent[message.author.id].append({'role': 'assistant', 'content': reply_text})
                    except discord.Forbidden:
                        pass
                    except discord.HTTPException as e:
                        print(f'HTTP error sending reply: {e}')
                    except Exception as e:
                        print(f'Send error: {e}')
                    finally:
                        FunAI._pending_replies.discard(dedup_key)
                        if message.author.id in self._pending_summarize:
                            self._pending_summarize.discard(message.author.id)
                            recent = list(self.user_memory_recent[message.author.id])
                            if len(recent) >= 8:
                                to_summarize = recent[:6]
                                remaining = recent[6:]
                                self.bot.loop.create_task(self._summarize_memory(message.author.id, to_summarize))
                                self.user_memory_recent[message.author.id] = deque(remaining, maxlen=10)
                self.bot.loop.create_task(send_it())
            except Exception as e:
                print(f'on_message handler error: {e}')
                FunAI._pending_replies.discard(dedup_key)
                if message.author.id in self._pending_summarize:
                    self._pending_summarize.discard(message.author.id)
                    recent = list(self.user_memory_recent[message.author.id])
                    if len(recent) >= 8:
                        to_summarize = recent[:6]
                        remaining = recent[6:]
                        self.bot.loop.create_task(self._summarize_memory(message.author.id, to_summarize))
                        self.user_memory_recent[message.author.id] = deque(remaining, maxlen=10)
        self.bot.loop.create_task(handle_reply())

    @commands.hybrid_command(name='ask', description='Ask the AI anything!')
    @app_commands.describe(question='Your question!')
    async def ask(self, ctx: commands.Context, *, question: str):
        await ctx.defer()
        response, urls = await self._generate_response('You are a sharp, no-nonsense Discord bot. Answer clearly and concisely. No fluff, no cheerfulness. Under 1800 chars.', question, message=ctx.message)
        await ctx.send(f'**Q:** {question}\n**A:** {response}')
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name='story', description='Generate a short story!')
    @app_commands.describe(prompt='A prompt for the story!')
    async def story(self, ctx: commands.Context, *, prompt: str='make it weird'):
        await ctx.defer()
        response, urls = await self._generate_response('You are a creative writer. Write a SHORT (max 900 chars) story. Make it actually interesting, not generic. No markdown.', f'Write a short story about: {prompt}', message=ctx.message)
        await ctx.send(f'📖 **Story Time:**\n{response}')
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name='roast', description='Roast someone!')
    @app_commands.describe(member='Who to roast!')
    async def roast(self, ctx: commands.Context, member: discord.Member):
        if member.id == self.bot.user.id:
            await ctx.send("roast myself? i don't have enough self-loathing for that")
            return
        await ctx.defer()
        response, urls = await self._generate_response('You are a savage roast machine. Write a sharp, witty, cutting but not genuinely cruel roast. Clever > mean. Max 400 chars. No markdown.', f'Roast a Discord user named {member.display_name}. Make it clever.', message=ctx.message)
        await ctx.send(f'{member.mention} {response}')
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name='compliment', description='Compliment someone!')
    @app_commands.describe(member='Who to compliment!')
    async def compliment(self, ctx: commands.Context, member: discord.Member):
        await ctx.defer()
        response, urls = await self._generate_response('You are a genuine, slightly awkward compliment giver. Write something real and specific, not generic garbage. Max 400 chars. No markdown.', f'Write a genuine compliment for a Discord user named {member.display_name}.', message=ctx.message)
        await ctx.send(f'{member.mention} {response}')
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name='pickupline', description='Get a pickup line!')
    async def pickupline(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response("Generate a single pickup line. Make it either genuinely clever OR so bad it's funny. Not both. Max 200 chars. No markdown.", 'Give me a pickup line.', message=ctx.message)
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name='fortune', description='Get your fortune!')
    async def fortune(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response('You are a fortune teller but make it feel real, not generic horoscope garbage. Short, a little cryptic, slightly unsettling. Max 300 chars. No markdown.', 'Tell me my fortune.', message=ctx.message)
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name='insult', description='Fake insult someone (harmless)')
    @app_commands.describe(member='Who to insult!')
    async def insult(self, ctx: commands.Context, member: discord.Member):
        if member.id == self.bot.user.id:
            await ctx.send('i refuse to participate in self-criticism')
            return
        await ctx.defer()
        response, urls = await self._generate_response('Write a harmless, clearly jokey, exaggerated fake insult. Make it absurd enough that no one could take it seriously. Max 300 chars. No markdown.', f'Write a silly fake insult for {member.display_name}.', message=ctx.message)
        await ctx.send(f'{member.mention} {response}')
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name='advice', description='Get questionable life advice!')
    @app_commands.describe(topic='What do you need advice about?')
    async def advice(self, ctx: commands.Context, *, topic: str='life in general'):
        await ctx.defer()
        response, urls = await self._generate_response('Give advice that sounds almost wise but is slightly unhinged. Not fully serious but not pure comedy. Max 500 chars. No markdown.', f'Give me advice about: {topic}', message=ctx.message)
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name='poem', description='Generate a poem!')
    @app_commands.describe(topic="What's the poem about?")
    async def poem(self, ctx: commands.Context, *, topic: str="something i won't regret"):
        await ctx.defer()
        response, urls = await self._generate_response('Write a short poem. Can be funny, dark, weird, or beautiful. Max 8 lines. No markdown.', f'Write a poem about: {topic}', message=ctx.message)
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name='ship', description='Ship two users!')
    @app_commands.describe(user1='First user!', user2='Second user!')
    async def ship(self, ctx: commands.Context, user1: discord.Member, user2: discord.Member):
        if user1.id == user2.id:
            await ctx.send("you can't ship someone with themselves, that's just a mirror")
            return
        await ctx.defer()
        response, urls = await self._generate_response('Write a short ship description. Make it feel real and specific, not generic. Give it a compatibility score and a vibe. Max 400 chars. No markdown.', f'Write a ship for {user1.display_name} and {user2.display_name}.', message=ctx.message)
        await ctx.send(f'🚢 **{user1.display_name} x {user2.display_name}**\n{response}')
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name='dadjoke', description='Get a dad joke!')
    async def dadjoke(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response('Tell a single dad joke. The worse the pun the better. Max 300 chars. No markdown.', 'Tell me a dad joke.', message=ctx.message)
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name='wouldyourather', description='Get a Would You Rather question!')
    async def wouldyourather(self, ctx: commands.Context):
        await ctx.defer()
        response, urls = await self._generate_response("Give a Would You Rather question that's actually interesting — not too easy, not too gross. Max 300 chars. No markdown.", 'Give me a Would You Rather question.', message=ctx.message)
        await ctx.send(response)
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name='rate', description='Rate anything!')
    @app_commands.describe(thing='What to rate!')
    async def rate(self, ctx: commands.Context, *, thing: str):
        await ctx.defer()
        score = random.randint(0, 10)
        response, urls = await self._generate_response(f'You are a harsh but honest critic. Rate the given thing {score}/10 and give a one-sentence reason. Be direct. Max 200 chars. No markdown.', f'Rate this: {thing}. The score is {score}/10.', message=ctx.message)
        await ctx.send(f'**{thing}:** {response}')
        for url in urls:
            await ctx.send(url)

    @commands.hybrid_command(name='8ball', description='Ask the magic 8-ball!')
    @app_commands.describe(question='Your yes/no question!')
    async def eightball(self, ctx: commands.Context, *, question: str):
        await ctx.defer()
        responses = ['yeah obviously', 'no chance', 'maybe, but probably not', 'absolutely not', 'signs point to yes', "ask again when you're smarter", 'the universe says no', 'sure why not', 'lol no', 'deep down you already know the answer', 'it is certain', "don't count on it", 'without a doubt', 'my sources say no', 'reply hazy, try again', 'outlook not so good']
        answer = random.choice(responses)
        await ctx.send(f'🎱 **{question}**\n{answer}')

    @commands.hybrid_command(name='translate', description='Translate text to another language!')
    @app_commands.describe(text='Text to translate', language='Target language (e.g. Spanish, French, Japanese)')
    async def translate(self, ctx: commands.Context, language: str, *, text: str):
        await ctx.defer()
        lang_codes = {'spanish': 'es', 'french': 'fr', 'german': 'de', 'japanese': 'ja', 'korean': 'ko', 'chinese': 'zh', 'arabic': 'ar', 'portuguese': 'pt', 'italian': 'it', 'russian': 'ru', 'hindi': 'hi', 'turkish': 'tr', 'dutch': 'nl', 'polish': 'pl', 'swedish': 'sv'}
        lang_code = lang_codes.get(language.lower(), language.lower()[:2])
        result, _ = await self._call_tool('translate_text', {'text': text, 'target_lang': lang_code})
        try:
            data = json.loads(result)
            if 'translated' in data:
                await ctx.send(f"**{language}:** {data['translated']}")
            else:
                await ctx.send(f"couldn't translate that: {data.get('error', 'unknown error')}")
        except Exception:
            await ctx.send('translation failed, sorry')

    @commands.hybrid_command(name='trivia', description='Get a trivia question!')
    @app_commands.describe(category='Optional category (general, science, history, sports, anime, etc)')
    async def trivia(self, ctx: commands.Context, category: str=''):
        await ctx.defer()
        result = await self._call_tool('get_trivia', {'category': category})
        try:
            data = json.loads(result)
            if 'question' in data:
                question = re.sub('&quot;|&#039;|&amp;|&lt;|&gt;', lambda m: {'&quot;': '"', '&#039;': "'", '&amp;': '&', '&lt;': '<', '&gt;': '>'}.get(m.group(), m.group()), data['question'])
                correct = data['correct_answer']
                all_answers = data['incorrect_answers'] + [correct]
                random.shuffle(all_answers)
                answer_list = '\n'.join([f"{('✅' if a == correct else '❌')} {a}" for a in all_answers])
                await ctx.send(f"**{data['category']} | {data['difficulty'].title()}**\n{question}\n||{answer_list}||")
            else:
                await ctx.send(f"couldn't get trivia: {data.get('error', 'unknown error')}")
        except Exception:
            await ctx.send('trivia failed, the database is being weird')

    @commands.hybrid_command(name='crypto', description='Check a cryptocurrency price!')
    @app_commands.describe(coin='Coin name or symbol (e.g. bitcoin, ETH)')
    async def crypto(self, ctx: commands.Context, coin: str='bitcoin'):
        await ctx.defer()
        result = await self._call_tool('get_crypto_price', {'coin': coin})
        try:
            data = json.loads(result)
            if 'price_usd' in data:
                change = data.get('change_24h', 0) or 0
                arrow = '📈' if change >= 0 else '📉'
                await ctx.send(f"{arrow} **{data['coin'].title()}:** ${data['price_usd']:,.2f} ({change:+.2f}% 24h)")
            else:
                await ctx.send(f"can't find price for {coin}")
        except Exception:
            await ctx.send('crypto lookup failed')

    @commands.hybrid_command(name='urban', description='Look up a word on Urban Dictionary!')
    @app_commands.describe(term='Word or phrase to look up')
    async def urban(self, ctx: commands.Context, *, term: str):
        await ctx.defer()
        result = await self._call_tool('urban_dictionary', {'term': term})
        try:
            data = json.loads(result)
            if 'definition' in data:
                await ctx.send(f"**{data['word']}**\n{data['definition']}\n*Example: {data['example']}*" if data.get('example') else f"**{data['word']}**\n{data['definition']}")
            else:
                await ctx.send(f"no urban dictionary definition found for '{term}'")
        except Exception:
            await ctx.send('urban dictionary lookup failed')

    @commands.hybrid_command(name='roll', description='Roll some dice!')
    @app_commands.describe(dice='Dice notation like 2d6, 1d20, 3d8 (default: 1d6)')
    async def roll(self, ctx: commands.Context, dice: str='1d6'):
        dice = dice.lower().strip()
        match = re.match('^(\\d+)d(\\d+)$', dice)
        if not match:
            await ctx.send('use dice notation like `1d6`, `2d20`, `3d8`')
            return
        count, sides = (int(match.group(1)), int(match.group(2)))
        if count > 20 or sides > 1000 or count < 1 or (sides < 2):
            await ctx.send('keep it sane: max 20 dice, max 1000 sides')
            return
        result = await self._call_tool('roll_dice', {'sides': sides, 'count': count})
        data = json.loads(result)
        rolls_str = ', '.join(map(str, data['rolls']))
        if count > 1:
            await ctx.send(f"🎲 **{dice}:** [{rolls_str}] = **{data['total']}**")
        else:
            await ctx.send(f"🎲 **{dice}:** {data['rolls'][0]}")

    @commands.hybrid_command(name='flip', description='Flip a coin!')
    async def flip(self, ctx: commands.Context):
        result = await self._call_tool('flip_coin', {})
        data = json.loads(result)
        emoji = '🪙'
        await ctx.send(f"{emoji} **{data['result']}**")

    @commands.hybrid_command(name='fact', description='Get a random fact!')
    async def fact(self, ctx: commands.Context):
        await ctx.defer()
        result = await self._call_tool('get_fact', {})
        try:
            data = json.loads(result)
            await ctx.send(f"💡 {data['fact']}")
        except Exception:
            await ctx.send("couldn't load a fact right now")

    @commands.hybrid_command(name='github', description='Look up a GitHub user!')
    @app_commands.describe(username='GitHub username')
    async def github(self, ctx: commands.Context, username: str):
        await ctx.defer()
        result = await self._call_tool('get_github_user', {'username': username})
        try:
            data = json.loads(result)
            if 'login' in data:
                bio = f"\n*{data['bio']}*" if data.get('bio') else ''
                location = f" | 📍 {data['location']}" if data.get('location') else ''
                await ctx.send(f"**{data['login']}**{(' (' + data['name'] + ')' if data.get('name') else '')}{bio}\n📦 {data['public_repos']} repos | 👥 {data['followers']} followers | joined {data['created_at'][:7]}{location}")
            else:
                await ctx.send(f"github user '{username}' not found")
        except Exception:
            await ctx.send('github lookup failed')

    @commands.hybrid_command(name='anime_quote', description='Get a random anime quote!')
    async def anime_quote(self, ctx: commands.Context):
        await ctx.defer()
        result = await self._call_tool('get_anime_quote', {})
        try:
            data = json.loads(result)
            if data.get('quote'):
                await ctx.send(f'''*"{data['quote']}"*\n— **{data['character']}**, {data['anime']}''')
            else:
                await ctx.send("couldn't fetch an anime quote right now")
        except Exception:
            await ctx.send('anime quote fetch failed')

    @commands.hybrid_command(name='clear_memory', description='Clear your personal chat memory with the bot!')
    async def clear_memory(self, ctx: commands.Context):
        self.user_memory_recent[ctx.author.id].clear()
        self.user_memory_summary[ctx.author.id] = ''
        await ctx.send("✅ your memory's been wiped. fresh start.")

    @commands.hybrid_command(name='view_memory', description='View your personal chat memory with the bot!')
    async def view_memory(self, ctx: commands.Context):
        memory = list(self.user_memory_recent[ctx.author.id])
        summary = self.user_memory_summary[ctx.author.id]
        if not memory and (not summary):
            await ctx.send('📭 nothing stored yet')
            return
        lines = ['📜 **your chat memory:**']
        if summary:
            lines.append(f'\n📝 *summary:* {summary}')
        if memory:
            lines.append('\n🗨️ recent messages:')
            for i, msg in enumerate(memory, 1):
                role = '🤖 bot' if msg['role'] == 'assistant' else '👤 you'
                content = msg['content'][:100] + '...' if len(msg['content']) > 100 else msg['content']
                lines.append(f'{i}. {role}: {content}')
        await ctx.send('\n'.join(lines))

async def setup(bot: commands.Bot):
    await bot.add_cog(FunAI(bot))