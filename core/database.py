import aiosqlite
import logging
from config.settings import DATABASE_PATH

logger = logging.getLogger(__name__)


async def init_conn_db() -> None:
    """Создает таблицу пользователей в базе данных, если она не существует."""
    try:
        # Use async with for connection management
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
                    last_notification_id INTEGER,
                    has_used_trial INTEGER DEFAULT 0
                )
                """
            )
            # Check if has_used_trial column exists and add it if not (for existing databases)
            cursor = await db.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in await cursor.fetchall()]
            if 'has_used_trial' not in columns:
                await db.execute('ALTER TABLE users ADD COLUMN has_used_trial INTEGER DEFAULT 0')
                logger.info("Added 'has_used_trial' column to 'users' table.")
            await db.commit()
        logger.info("Таблица успешно создана или уже существует.")
    except aiosqlite.Error:
        logger.error("Ошибка при создании таблицы:", exc_info=True)

    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS promo_codes (
                    code TEXT PRIMARY KEY,
                    days_duration INTEGER NOT NULL,
                    is_active INTEGER DEFAULT 1
                )
                """
            )
            await db.commit()
        logger.info("Таблица promo_codes успешно создана или уже существует.")
    except aiosqlite.Error:
        logger.error("Ошибка при создании таблицы promo_codes:", exc_info=True)

