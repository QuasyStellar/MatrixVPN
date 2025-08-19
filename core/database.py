import aiosqlite
import logging
from config.settings import DATABASE_PATH

logger = logging.getLogger(__name__)

async def init_conn_db() -> None:
    """Создает таблицу пользователей в базе данных, если она не существует."""
    try:
        logger.info(f"Attempting to connect to database at: {DATABASE_PATH}")
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    status TEXT DEFAULT 'pending',
                    access_granted_date TEXT,
                    access_duration INTEGER,
                    access_end_date TEXT,
                    last_notification_id INTEGER
                )
            """
            )
            await db.commit()
        logger.info("Таблица успешно создана или уже существует.")
    except aiosqlite.Error:
        logger.error("Ошибка при создании таблицы:", exc_info=True)
