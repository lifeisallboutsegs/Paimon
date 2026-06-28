import re
from datetime import datetime, timezone
_DURATION_RE = re.compile('(\\d+)([smhdw])')
_UNIT_SECONDS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}

def parse_duration(text: str) -> int | None:
    """Parse strings like '10m', '2h30m', '1d' into total seconds. Returns None if invalid."""
    matches = _DURATION_RE.findall(text.lower())
    if not matches:
        return None
    return sum((int(value) * _UNIT_SECONDS[unit] for value, unit in matches))

def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def xp_for_level(level: int) -> int:
    """XP required to advance FROM `level` to `level + 1`. Used by the leveling system
    in both database backends so the formula only has to live in one place."""
    return 5 * level ** 2 + 50 * level + 100

def human_timedelta_seconds(seconds: int) -> str:
    periods = [('day', 86400), ('hour', 3600), ('minute', 60), ('second', 1)]
    parts = []
    for name, length in periods:
        value, seconds = divmod(seconds, length)
        if value:
            parts.append(f"{value} {name}{('s' if value != 1 else '')}")
    return ', '.join(parts) if parts else '0 seconds'
