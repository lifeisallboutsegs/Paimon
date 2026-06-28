from __future__ import annotations

import asyncio

import json

import logging

from datetime import datetime, timezone

from pathlib import Path

from typing import Any

from utils.helpers import xp_for_level

logger = logging.getLogger("bot.json_store")


class JSONDatabase:
    def __init__(self, directory: Path):
        self.directory = directory
        self._lock = asyncio.Lock()
        self._files = {
            "guild_configs": self.directory / "guild_configs.json",
            "warnings": self.directory / "warnings.json",
            "economy": self.directory / "economy.json",
            "levels": self.directory / "levels.json",
            "kv_store": self.directory / "kv_store.json",
        }

    async def connect(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        for path in self._files.values():
            if not path.exists():
                default = "[]" if path.name == "warnings.json" else "{}"
                path.write_text(default, encoding="utf-8")

        logger.info("JSON datastore ready at %s", self.directory)

    async def close(self) -> None:
        pass

    def _read(self, name: str) -> Any:
        return json.loads(self._files[name].read_text(encoding="utf-8"))

    def _write(self, name: str, data: Any) -> None:
        self._files[name].write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def get_guild_config(self, guild_id: int) -> dict:
        async with self._lock:
            data = self._read("guild_configs")
            return data.get(
                str(guild_id),
                {
                    "guild_id": guild_id,
                    "prefix": None,
                    "welcome_channel": None,
                    "log_channel": None,
                    "mod_role": None,
                },
            )

    async def set_guild_config(self, guild_id: int, **fields) -> None:
        async with self._lock:
            data = self._read("guild_configs")
            entry = data.get(str(guild_id), {"guild_id": guild_id})
            entry.update(fields)
            data[str(guild_id)] = entry
            self._write("guild_configs", data)

    async def add_warning(
        self, guild_id: int, user_id: int, moderator_id: int, reason: str
    ) -> int:
        async with self._lock:
            warnings = self._read("warnings")
            new_id = max((w["id"] for w in warnings), default=0) + 1
            warnings.append(
                {
                    "id": new_id,
                    "guild_id": guild_id,
                    "user_id": user_id,
                    "moderator_id": moderator_id,
                    "reason": reason,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            self._write("warnings", warnings)
            return new_id

    async def get_warnings(self, guild_id: int, user_id: int) -> list[dict]:
        async with self._lock:
            warnings = self._read("warnings")
            return [
                w
                for w in warnings
                if w["guild_id"] == guild_id and w["user_id"] == user_id
            ]

    async def clear_warnings(self, guild_id: int, user_id: int) -> None:
        async with self._lock:
            warnings = self._read("warnings")
            warnings = [
                w
                for w in warnings
                if not (w["guild_id"] == guild_id and w["user_id"] == user_id)
            ]
            self._write("warnings", warnings)

    async def get_balance(self, guild_id: int, user_id: int) -> int:
        async with self._lock:
            data = self._read("economy")
            return data.get(f"{guild_id}:{user_id}", {}).get("balance", 0)

    async def add_balance(self, guild_id: int, user_id: int, amount: int) -> int:
        async with self._lock:
            data = self._read("economy")
            key = f"{guild_id}:{user_id}"
            entry = data.get(key, {"balance": 0, "last_daily": None})
            entry["balance"] += amount
            data[key] = entry
            self._write("economy", data)
            return entry["balance"]

    async def set_last_daily(
        self, guild_id: int, user_id: int, iso_timestamp: str
    ) -> None:
        async with self._lock:
            data = self._read("economy")
            key = f"{guild_id}:{user_id}"
            entry = data.get(key, {"balance": 0, "last_daily": None})
            entry["last_daily"] = iso_timestamp
            data[key] = entry
            self._write("economy", data)

    async def get_last_daily(self, guild_id: int, user_id: int) -> str | None:
        async with self._lock:
            data = self._read("economy")
            return data.get(f"{guild_id}:{user_id}", {}).get("last_daily")

    async def get_last_work(self, guild_id: int, user_id: int) -> str | None:
        async with self._lock:
            data = self._read("economy")
            return data.get(f"{guild_id}:{user_id}", {}).get("last_work")

    async def set_last_work(
        self, guild_id: int, user_id: int, iso_timestamp: str
    ) -> None:
        async with self._lock:
            data = self._read("economy")
            key = f"{guild_id}:{user_id}"
            entry = data.get(key, {"balance": 0, "last_daily": None, "last_work": None})
            entry["last_work"] = iso_timestamp
            data[key] = entry
            self._write("economy", data)

    async def get_balance_leaderboard(
        self, guild_id: int, limit: int = 10
    ) -> list[dict]:
        async with self._lock:
            data = self._read("economy")
            rows = []
            for key, entry in data.items():
                gid, uid = key.split(":")
                if int(gid) == guild_id:
                    rows.append(
                        {"user_id": int(uid), "balance": entry.get("balance", 0)}
                    )

            rows.sort(key=lambda r: r["balance"], reverse=True)
            return rows[:limit]

    async def add_xp(
        self, guild_id: int, user_id: int, amount: int, cooldown_seconds: int = 60
    ) -> tuple[bool, int] | None:
        async with self._lock:
            data = self._read("levels")
            key = f"{guild_id}:{user_id}"
            entry = data.get(key, {"xp": 0, "level": 0, "last_xp_at": None})
            now = datetime.now(timezone.utc)
            if entry["last_xp_at"]:
                last = datetime.fromisoformat(entry["last_xp_at"])
                if (now - last).total_seconds() < cooldown_seconds:
                    return None

            xp = entry["xp"] + amount
            level = entry["level"]
            leveled_up = False
            while xp >= xp_for_level(level):
                xp -= xp_for_level(level)
                level += 1
                leveled_up = True

            entry.update({"xp": xp, "level": level, "last_xp_at": now.isoformat()})
            data[key] = entry
            self._write("levels", data)
            return (leveled_up, level)

    async def get_level(self, guild_id: int, user_id: int) -> dict:
        async with self._lock:
            data = self._read("levels")
            entry = data.get(f"{guild_id}:{user_id}", {"xp": 0, "level": 0})
            return {"xp": entry["xp"], "level": entry["level"]}

    async def get_level_leaderboard(self, guild_id: int, limit: int = 10) -> list[dict]:
        async with self._lock:
            data = self._read("levels")
            rows = []
            for key, entry in data.items():
                gid, uid = key.split(":")
                if int(gid) == guild_id:
                    rows.append(
                        {
                            "user_id": int(uid),
                            "xp": entry["xp"],
                            "level": entry["level"],
                        }
                    )

            rows.sort(key=lambda r: (r["level"], r["xp"]), reverse=True)
            return rows[:limit]

    async def kv_set(self, namespace: str, key: str, value: str) -> None:
        async with self._lock:
            data = self._read("kv_store")
            data.setdefault(namespace, {})[key] = value
            self._write("kv_store", data)

    async def kv_get(self, namespace: str, key: str) -> str | None:
        async with self._lock:
            data = self._read("kv_store")
            return data.get(namespace, {}).get(key)

    async def kv_delete(self, namespace: str, key: str) -> None:
        async with self._lock:
            data = self._read("kv_store")
            data.get(namespace, {}).pop(key, None)
            self._write("kv_store", data)

    async def kv_all(self, namespace: str) -> dict[str, str]:
        async with self._lock:
            data = self._read("kv_store")
            return data.get(namespace, {})
