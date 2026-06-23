from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import aiosqlite

from utils.helpers import xp_for_level

logger = logging.getLogger("bot.database")


class Database:
    def __init__(self, path: Path):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON;")
        await self._apply_schema()
        logger.info("Connected to SQLite database at %s", self.path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            logger.info("Database connection closed")

    async def _apply_schema(self) -> None:
        schema_file = Path(__file__).resolve().parent.parent / "database" / "schema.sql"
        sql = schema_file.read_text(encoding="utf-8")
        await self._conn.executescript(sql)
        await self._conn.commit()
        await self._migrate()

    async def _migrate(self) -> None:
        """Lightweight ad-hoc migrations for columns added after initial release.
        SQLite has no 'ADD COLUMN IF NOT EXISTS', so we just try the ALTER TABLE
        and ignore the failure when it means the column is already there."""
        statements = [
            "ALTER TABLE economy ADD COLUMN last_work TEXT",
        ]
        for stmt in statements:
            try:
                await self._conn.execute(stmt)
                await self._conn.commit()
            except Exception as exc:
                if "duplicate column" not in str(exc).lower():
                    logger.warning("Migration skipped (%s): %s", stmt, exc)

    # ---------- generic helpers (use these for any new feature) ----------

    async def execute(self, query: str, params: Iterable[Any] = ()) -> None:
        await self._conn.execute(query, params)
        await self._conn.commit()

    async def fetchone(self, query: str, params: Iterable[Any] = ()) -> aiosqlite.Row | None:
        cursor = await self._conn.execute(query, params)
        row = await cursor.fetchone()
        await cursor.close()
        return row

    async def fetchall(self, query: str, params: Iterable[Any] = ()) -> list[aiosqlite.Row]:
        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()
        return rows

    # ---------- guild config ----------

    async def get_guild_config(self, guild_id: int) -> dict:
        row = await self.fetchone("SELECT * FROM guild_configs WHERE guild_id = ?", (guild_id,))
        if row is None:
            return {
                "guild_id": guild_id, "prefix": None, "welcome_channel": None,
                "log_channel": None, "mod_role": None,
            }
        return dict(row)

    async def set_guild_config(self, guild_id: int, **fields) -> None:
        await self.execute(
            "INSERT INTO guild_configs (guild_id) VALUES (?) "
            "ON CONFLICT(guild_id) DO NOTHING",
            (guild_id,),
        )
        if not fields:
            return
        columns = ", ".join(f"{k} = ?" for k in fields)
        await self.execute(
            f"UPDATE guild_configs SET {columns} WHERE guild_id = ?",
            (*fields.values(), guild_id),
        )

    # ---------- moderation ----------

    async def add_warning(self, guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
        cursor = await self._conn.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, moderator_id, reason),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_warnings(self, guild_id: int, user_id: int) -> list[aiosqlite.Row]:
        return await self.fetchall(
            "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY id DESC",
            (guild_id, user_id),
        )

    async def clear_warnings(self, guild_id: int, user_id: int) -> None:
        await self.execute(
            "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        )

    # ---------- economy ----------

    async def get_balance(self, guild_id: int, user_id: int) -> int:
        row = await self.fetchone(
            "SELECT balance FROM economy WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        )
        return row["balance"] if row else 0

    async def add_balance(self, guild_id: int, user_id: int, amount: int) -> int:
        await self.execute(
            "INSERT INTO economy (guild_id, user_id, balance) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET balance = balance + ?",
            (guild_id, user_id, amount, amount),
        )
        return await self.get_balance(guild_id, user_id)

    async def set_last_daily(self, guild_id: int, user_id: int, iso_timestamp: str) -> None:
        await self.execute(
            "INSERT INTO economy (guild_id, user_id, last_daily) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET last_daily = ?",
            (guild_id, user_id, iso_timestamp, iso_timestamp),
        )

    async def get_last_daily(self, guild_id: int, user_id: int) -> str | None:
        row = await self.fetchone(
            "SELECT last_daily FROM economy WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return row["last_daily"] if row else None

    async def get_last_work(self, guild_id: int, user_id: int) -> str | None:
        row = await self.fetchone(
            "SELECT last_work FROM economy WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        )
        return row["last_work"] if row else None

    async def set_last_work(self, guild_id: int, user_id: int, iso_timestamp: str) -> None:
        await self.execute(
            "INSERT INTO economy (guild_id, user_id, last_work) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET last_work = ?",
            (guild_id, user_id, iso_timestamp, iso_timestamp),
        )

    async def get_balance_leaderboard(self, guild_id: int, limit: int = 10) -> list[aiosqlite.Row]:
        return await self.fetchall(
            "SELECT user_id, balance FROM economy WHERE guild_id = ? ORDER BY balance DESC LIMIT ?",
            (guild_id, limit),
        )

    # ---------- leveling / xp ----------

    async def add_xp(
        self, guild_id: int, user_id: int, amount: int, cooldown_seconds: int = 60
    ) -> tuple[bool, int] | None:
        """Add XP, respecting a per-message cooldown. Returns None if still on cooldown,
        otherwise (leveled_up, new_level)."""
        now = datetime.now(timezone.utc)
        row = await self.fetchone(
            "SELECT xp, level, last_xp_at FROM levels WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        if row and row["last_xp_at"]:
            last = datetime.fromisoformat(row["last_xp_at"])
            if (now - last).total_seconds() < cooldown_seconds:
                return None

        xp = (row["xp"] if row else 0) + amount
        level = row["level"] if row else 0
        leveled_up = False
        while xp >= xp_for_level(level):
            xp -= xp_for_level(level)
            level += 1
            leveled_up = True

        await self.execute(
            "INSERT INTO levels (guild_id, user_id, xp, level, last_xp_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = ?, level = ?, last_xp_at = ?",
            (guild_id, user_id, xp, level, now.isoformat(), xp, level, now.isoformat()),
        )
        return leveled_up, level

    async def get_level(self, guild_id: int, user_id: int) -> dict:
        row = await self.fetchone(
            "SELECT xp, level FROM levels WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        )
        return {"xp": row["xp"], "level": row["level"]} if row else {"xp": 0, "level": 0}

    async def get_level_leaderboard(self, guild_id: int, limit: int = 10) -> list[aiosqlite.Row]:
        return await self.fetchall(
            "SELECT user_id, xp, level FROM levels WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT ?",
            (guild_id, limit),
        )

    # ---------- generic kv store (use this for quick features, no migration needed) ----------

    async def kv_set(self, namespace: str, key: str, value: str) -> None:
        await self.execute(
            "INSERT INTO kv_store (namespace, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(namespace, key) DO UPDATE SET value = ?",
            (namespace, key, value, value),
        )

    async def kv_get(self, namespace: str, key: str) -> str | None:
        row = await self.fetchone(
            "SELECT value FROM kv_store WHERE namespace = ? AND key = ?", (namespace, key)
        )
        return row["value"] if row else None

    async def kv_delete(self, namespace: str, key: str) -> None:
        await self.execute("DELETE FROM kv_store WHERE namespace = ? AND key = ?", (namespace, key))

    async def kv_all(self, namespace: str) -> dict[str, str]:
        rows = await self.fetchall("SELECT key, value FROM kv_store WHERE namespace = ?", (namespace,))
        return {r["key"]: r["value"] for r in rows}