
CREATE TABLE IF NOT EXISTS guild_configs (
    guild_id        INTEGER PRIMARY KEY,
    prefix          TEXT,
    welcome_channel INTEGER,
    log_channel     INTEGER,
    mod_role        INTEGER
);

-- Moderation warnings
CREATE TABLE IF NOT EXISTS warnings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id     INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason       TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_warnings_guild_user ON warnings (guild_id, user_id);

-- Simple per-guild economy system
CREATE TABLE IF NOT EXISTS economy (
    guild_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    balance    INTEGER NOT NULL DEFAULT 0,
    last_daily TEXT,
    PRIMARY KEY (guild_id, user_id)
);

-- XP / leveling system
CREATE TABLE IF NOT EXISTS levels (
    guild_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    xp         INTEGER NOT NULL DEFAULT 0,
    level      INTEGER NOT NULL DEFAULT 0,
    last_xp_at TEXT,
    PRIMARY KEY (guild_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_levels_guild_rank ON levels (guild_id, level DESC, xp DESC);

-- Generic key/value store any future cog can use without a migration
-- (tags, sticky notes, reaction roles, custom counters, etc.)
CREATE TABLE IF NOT EXISTS kv_store (
    namespace TEXT NOT NULL,
    key       TEXT NOT NULL,
    value     TEXT NOT NULL,
    PRIMARY KEY (namespace, key)
);