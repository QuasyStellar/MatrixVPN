import aiosqlite
import logging
from config.settings import DATABASE_PATH

logger = logging.getLogger(__name__)

db_connection = None

async def get_db_connection():
    global db_connection
    if db_connection is None:
        try:
            db_connection = await aiosqlite.connect(DATABASE_PATH)
            logger.info("Database connection established.")
        except aiosqlite.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    return db_connection


async def close_db_connection():
    global db_connection
    if db_connection:
        await db_connection.close()
        db_connection = None
        logger.info("Database connection closed.")


async def init_conn_db() -> None:
    """Создает таблицу пользователей в базе данных, если она не существует."""
    try:
        db = await get_db_connection()
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
