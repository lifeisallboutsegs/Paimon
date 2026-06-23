# Discord Bot — Extensible Starter

A Discord bot built with `discord.py`, designed so you can add basically any
feature without rewiring the foundation. Cogs are isolated, the database
layer is swappable, errors are handled centrally, and both prefix (`!cmd`)
and slash (`/cmd`) commands work out of the box via hybrid commands.

## Folder structure

```
discord-bot/
├── bot.py                 # Entry point — run this
├── config.py              # Loads & validates .env settings
├── requirements.txt
├── .env.example            # Copy to .env and fill in
│
├── core/
│   ├── bot.py             # Bot subclass: cog auto-loading, dynamic prefixes
│   ├── database.py        # SQLite backend (default)
│   ├── json_store.py       # JSON-file backend (alternative, same interface)
│   └── logger.py          # Console + file logging setup
│
├── database/
│   └── schema.sql          # SQLite schema, auto-applied on startup
│
├── cogs/                   # Every feature lives in its own file here
│   ├── errors.py           # Global error handler (loaded first alphabetically isn't required)
│   ├── admin.py             # Owner-only: load/unload/reload cogs, sync slash commands
│   ├── moderation.py        # kick, ban, timeout, warn, warnings, purge
│   ├── utility.py           # ping, userinfo, serverinfo, avatar
│   ├── fun.py                # coinflip, 8ball, roll
│   ├── economy.py           # balance, daily, give (example of using bot.db)
│   └── settings.py          # /config — per-guild prefix, channels, mod role
│
├── utils/
│   ├── embeds.py            # success()/error()/warning()/info() embed builders
│   ├── checks.py             # Permission decorators (mod role, owner/admin)
│   ├── helpers.py            # parse_duration(), human_timedelta_seconds(), etc.
│   └── paginator.py           # Button-based multi-page embed viewer
│
├── data/                    # SQLite file / JSON store lives here (gitignored)
└── logs/                    # bot.log (gitignored)
```

## Setup

1. **Create a bot application**: https://discord.com/developers/applications
   → New Application → Bot tab → copy the token, enable **Message Content
   Intent** and **Server Members Intent**.

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set `DISCORD_TOKEN` and `OWNER_IDS` (your own Discord user
   ID, for owner-only commands like `!reload`).

4. **Invite the bot** to your server with the `bot` and `applications.commands`
   scopes, and at least: Kick Members, Ban Members, Moderate Members, Manage
   Messages (whichever permissions match the commands you'll actually use).

5. **Run it**:
   ```bash
   python bot.py
   ```

6. **Sync slash commands** once it's running (in any server, as the owner):
   ```
   !sync guild
   ```
   Use `!sync global` only when you're ready to publish commands everywhere
   (takes up to an hour to propagate).

## Switching database backends

Set in `.env`:
```
DATABASE_BACKEND=sqlite   # relational, recommended for anything beyond a toy bot
DATABASE_BACKEND=json     # flat JSON files under data/json_store/, zero extra deps
```
Both implement the identical async interface (`get_balance`, `add_warning`,
`set_guild_config`, the generic `kv_set`/`kv_get`, …), so cogs never need to
know or care which one is active. Switch any time — just restart the bot.

## Adding a new feature

This is the whole point of the architecture — adding a feature should never
require touching existing files.

1. Create `cogs/your_feature.py`.
2. Write a `commands.Cog` subclass with `commands.hybrid_command` methods
   (works as both `!cmd` and `/cmd` automatically).
3. Need to store data?
   - Quick & schema-free: use `bot.db.kv_set("your_feature", key, value)` /
     `kv_get(...)` — no migration needed.
   - Structured/relational: add a `CREATE TABLE` to `database/schema.sql`
     (it's safe to add tables — `IF NOT EXISTS` means existing data is
     untouched) and add matching methods to `core/database.py` **and**
     `core/json_store.py` so both backends stay in sync.
4. End the file with:
   ```python
   async def setup(bot):
       await bot.add_cog(YourFeature(bot))
   ```
5. Restart the bot (cogs in `cogs/` are auto-discovered — no registration
   step) or use `!reload your_feature` while it's running.

## Notes

- All moderation/settings commands check a configurable mod role OR the
  relevant Discord permission (see `utils/checks.py`) — server admins set
  the mod role with `/config mod_role`.
- `cogs/errors.py` catches and reports command errors centrally so you don't
  need try/except in every command.
- `utils/paginator.py` gives you a ready-made "back/next" button view for any
  list that's too long for one embed (leaderboards, long warning lists, etc.).
