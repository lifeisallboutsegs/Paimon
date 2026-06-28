import os
from pathlib import Path
from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

class Config:
    TOKEN: str = os.getenv('DISCORD_TOKEN', '')
    PREFIX: str = os.getenv('DEFAULT_PREFIX', '!')
    OWNER_IDS: set[int] = {int(uid) for uid in os.getenv('OWNER_IDS', '').split(',') if uid.strip().isdigit()}
    BOT_ADMIN_IDS: set[int] = {int(uid) for uid in os.getenv('BOT_ADMIN_IDS', '').split(',') if uid.strip().isdigit()}
    BOT_MODERATOR_IDS: set[int] = {int(uid) for uid in os.getenv('BOT_MODERATOR_IDS', '').split(',') if uid.strip().isdigit()}
    GROQ_API_KEYS: list[str] = []
    single_key = os.getenv('GROQ_API_KEY', '').strip()
    if single_key:
        GROQ_API_KEYS.append(single_key)
    for key in os.getenv('GROQ_API_KEYS', '').split(','):
        stripped = key.strip()
        if stripped and stripped not in GROQ_API_KEYS:
            GROQ_API_KEYS.append(stripped)
    OPENWEATHER_API_KEY: str = os.getenv('OPENWEATHER_API_KEY', '')
    GENIUS_ACCESS_TOKEN: str = os.getenv('GENIUS_ACCESS_TOKEN', 'ohCXKqz-spvgUf4Rq1lGNdJM-Lp2--eetb0VaR5WzROO4rxKFMMVHzTyN0Fsr64u')
    DATABASE_BACKEND: str = os.getenv('DATABASE_BACKEND', 'sqlite').lower()
    SQLITE_PATH: Path = BASE_DIR / 'data' / 'bot.db'
    JSON_DIR: Path = BASE_DIR / 'data' / 'json_store'
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO').upper()

    @classmethod
    def validate(cls) -> None:
        if not cls.TOKEN:
            raise RuntimeError('DISCORD_TOKEN is missing. Copy .env.example to .env and fill it in.')
        cls.SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cls.JSON_DIR.mkdir(parents=True, exist_ok=True)
