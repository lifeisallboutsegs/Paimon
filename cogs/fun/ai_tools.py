"""
Tool/function schemas for the FunAI cog's Groq tool-calling.

Pulled out of fun_ai.py so the schema list can be read, diffed, and extended
without scrolling through hundreds of lines of cog logic (issue #40).

To add a new tool:
  1. Add its schema dict to TOOLS below.
  2. Implement the matching branch in FunAI._call_tool().
That's it — nothing else in the cog needs to change.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_random_cat",
            "description": "Get a random cat picture",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_random_dog",
            "description": "Get a random dog picture",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_random_fox",
            "description": "Get a random fox picture",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_random_duck",
            "description": "Get a random duck picture",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_random_panda",
            "description": "Get a random panda picture",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_joke",
            "description": "Get a random joke",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "City name"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_meme",
            "description": "Get a random meme image",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_status",
            "description": "Change the bot's presence status and/or activity",
            "parameters": {
                "type": "object",
                "properties": {
                    "status_type": {
                        "type": "string",
                        "description": "Bot presence: online, idle, dnd, invisible",
                        "enum": ["online", "idle", "dnd", "invisible"],
                    },
                    "activity_type": {
                        "type": "string",
                        "description": "Activity type: playing, listening, watching, competing, streaming",
                        "enum": [
                            "playing",
                            "listening",
                            "watching",
                            "competing",
                            "streaming",
                        ],
                    },
                    "activity_text": {
                        "type": "string",
                        "description": "Text for the activity",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mention_user_in_channel",
            "description": (
                "Mention/ping a user in a specific channel by name. Use when asked to "
                "ping or mention someone somewhere. IMPORTANT: if the user gives ANY "
                "reason, note, or context for the mention (e.g. 'remind me to eat "
                "dinner', 'tell him the meeting moved', 'because he's AFK') you MUST "
                "put that exact content in the `message` field — it is not just "
                "flavor text for your own reply, it is what actually gets sent next "
                "to the ping. A mention with a stated reason and an empty `message` "
                "field is wrong and incomplete."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The Discord user ID to mention",
                    },
                    "channel_name": {
                        "type": "string",
                        "description": "The channel name (without #) to send the mention in",
                    },
                    "message": {
                        "type": "string",
                        "description": (
                            "The text to send right after the mention. REQUIRED "
                            "whenever the user gave a reason, note, or message to "
                            "pass along (e.g. 'remind him about dinner' -> message: "
                            "'remind you about eating dinner'). Leave empty only if "
                            "the user asked for a bare ping with no stated reason."
                        ),
                    },
                    "delay": {
                        "type": "number",
                        "description": "Optional delay in seconds before sending the mention (max 300 seconds/5 minutes)",
                    },
                },
                "required": ["user_id", "channel_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_dm",
            "description": "Send a direct message (DM) to a user",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The Discord user ID to DM",
                    },
                    "message": {
                        "type": "string",
                        "description": "The message content to send",
                    },
                    "delay": {
                        "type": "number",
                        "description": "Optional delay in seconds before sending the DM (max 300 seconds/5 minutes)",
                    },
                },
                "required": ["user_id", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_to_channel",
            "description": "Send a message to a specific channel by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "Channel name (without #)",
                    },
                    "message": {
                        "type": "string",
                        "description": "Message content to send",
                    },
                    "delay": {
                        "type": "number",
                        "description": "Optional delay in seconds before sending the message (max 300 seconds/5 minutes)",
                    },
                },
                "required": ["channel_name", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "react_to_message",
            "description": "Add an emoji reaction to the current message",
            "parameters": {
                "type": "object",
                "properties": {
                    "emoji": {
                        "type": "string",
                        "description": "The emoji to react with (unicode emoji like 👍 or custom emoji name)",
                    }
                },
                "required": ["emoji"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_server_info",
            "description": "Get information about the current Discord server",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_info",
            "description": "Get information about a Discord user by their ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The Discord user ID"}
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_channels",
            "description": "List all text channels in the current server",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trivia",
            "description": "Get a random trivia question",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional category: general, science, history, sports, etc",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "urban_dictionary",
            "description": "Look up a word or phrase on Urban Dictionary",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "The word or phrase to look up",
                    }
                },
                "required": ["term"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "translate_text",
            "description": "Translate text to a target language using MyMemory API",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to translate"},
                    "target_lang": {
                        "type": "string",
                        "description": "Target language code (e.g. 'es' for Spanish, 'fr' for French, 'ja' for Japanese)",
                    },
                },
                "required": ["text", "target_lang"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_crypto_price",
            "description": "Get current price of a cryptocurrency",
            "parameters": {
                "type": "object",
                "properties": {
                    "coin": {
                        "type": "string",
                        "description": "Coin name or symbol, e.g. bitcoin, ethereum, BTC",
                    }
                },
                "required": ["coin"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_anime_quote",
            "description": "Get a random anime quote",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_waifu_image",
            "description": "Get a random safe-for-work anime-style waifu image",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "roll_dice",
            "description": "Roll one or more dice with any number of sides",
            "parameters": {
                "type": "object",
                "properties": {
                    "sides": {
                        "type": "integer",
                        "description": "Number of sides on the die (default 6)",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of dice to roll (default 1)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flip_coin",
            "description": "Flip a coin, returns heads or tails",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_quote",
            "description": "Get a random inspirational or motivational quote",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fact",
            "description": "Get a random interesting fact",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pin_message",
            "description": "Pin the current message in the channel (requires bot to have manage messages permission)",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_github_user",
            "description": "Get information about a GitHub user",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "GitHub username"}
                },
                "required": ["username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report_issue_or_abuse",
            "description": "Report an issue or abuse to bot mods/admins/owners",
            "parameters": {
                "type": "object",
                "properties": {
                    "report_type": {
                        "type": "string",
                        "description": "Type: issue or abuse",
                        "enum": ["issue", "abuse"],
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID of the user to report (for abuse reports)",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the report",
                    },
                },
                "required": ["report_type", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_owner_info",
            "description": "Get information about who created the bot or who owns it",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]