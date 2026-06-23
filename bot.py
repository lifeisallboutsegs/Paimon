
import asyncio

from config import Config
from core.bot import Bot
from core.database import Database
from core.json_store import JSONDatabase
from core.logger import setup_logging


async def main() -> None:
    Config.validate()
    logger = setup_logging(Config.LOG_LEVEL)

    if Config.DATABASE_BACKEND == "json":
        db = JSONDatabase(Config.JSON_DIR)
        logger.info("Using JSON database backend")
    else:
        db = Database(Config.SQLITE_PATH)
        logger.info("Using SQLite database backend")

    await db.connect()

    bot = Bot(db)
    try:
        await bot.start(Config.TOKEN)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
