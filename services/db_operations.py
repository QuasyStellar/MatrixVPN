import aiosqlite
import logging
from datetime import datetime, timedelta, timezone
from config.settings import DATABASE_PATH
import aiofiles
from services import vpn_manager

logger = logging.getLogger(__name__)


async def get_user_by_id(user_id: int) -> tuple:
    """Возвращает информацию о пользователе по его ID."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()


async def add_user(user_id: int, username: str) -> None:
    """Добавляет нового пользователя в базу данных или обновляет статус существующего пользователя."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute("BEGIN")
            # get_user_by_id will now open its own connection, which is fine.
            # Alternatively, pass the 'db' object if get_user_by_id was designed to take one.
            # For simplicity and to avoid circular dependencies, keeping get_user_by_id separate is okay.
            user = await get_user_by_id(user_id)
            current_date = datetime.now(timezone.utc).isoformat()

            if user is None:
                await db.execute(
                    "INSERT INTO users (id, username, status, access_granted_date, access_duration, access_end_date, has_used_trial) VALUES (?, ?, 'pending', ?, 0, ?, 0)",
                    (user_id, username, current_date, current_date),
                )
            else:
                if user[2] in ("denied", "expired"):
                    await db.execute(
                        "UPDATE users SET status = 'pending' WHERE id = ?",
                        (user_id,),
                    )
            await db.commit()
        except aiosqlite.Error as e:
            await db.rollback()
            logger.error(f"Transaction failed: {e}", exc_info=True)


async def grant_access_and_create_config(user_id: int, days: int) -> None:
    """Выдает доступ пользователю и создает необходимые конфигурации."""
    await vpn_manager.create_user(user_id)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute("BEGIN")
            current_date = datetime.now(timezone.utc).isoformat()
            end_date = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
            await db.execute(
                """UPDATE users SET status = ?, access_granted_date = ?, access_duration = ?, access_end_date = ? WHERE id = ?""",
                ("accepted", current_date, days, end_date, user_id),
            )
            await db.commit()
        except aiosqlite.Error as e:
            await db.rollback()
            logger.error(f"Transaction failed: {e}", exc_info=True)
            raise


async def update_request_status(user_id: int, status: str) -> None:
    """Обновляет статус запроса пользователя."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                "UPDATE users SET status = ? WHERE id = ?", (status, user_id)
            )
            await db.commit()
        except aiosqlite.Error:
            logger.error("Ошибка при обновлении статуса запроса:", exc_info=True)


async def get_pending_requests() -> list:
    """Возвращает список пользователей с ожидающим статусом."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            async with db.execute(
                "SELECT * FROM users WHERE status = 'pending'"
            ) as cursor:
                return await cursor.fetchall()
        except aiosqlite.Error:
            logger.error("Ошибка при получении списка запросов:", exc_info=True)
            return []


async def get_accepted_users() -> list:
    """Возвращает список пользователей с принятым статусом."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            async with db.execute(
                "SELECT id, username, access_end_date FROM users WHERE status = 'accepted'"
            ) as cursor:
                return await cursor.fetchall()
        except aiosqlite.Error:
            logger.error("Ошибка при получении списка пользователей:", exc_info=True)
            return []


async def update_user_access(user_id: int, access_end_date: str, has_used_trial: int = None) -> None:
    """Обновляет дату окончания доступа пользователя."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute("BEGIN")
            if has_used_trial is not None:
                await db.execute(
                    "UPDATE users SET status = 'accepted', access_end_date = ?, has_used_trial = ? WHERE id = ?",
                    (access_end_date, has_used_trial, user_id),
                )
            else:
                await db.execute(
                    "UPDATE users SET status = 'accepted', access_end_date = ? WHERE id = ?",
                    (access_end_date, user_id),
                )
            await db.commit()
        except aiosqlite.Error:
            await db.rollback()
            logger.error("Ошибка при обновлении доступа пользователя:", exc_info=True)


async def delete_user(user_id: int) -> bool:
    """Удаляет пользователя из базы данных по его ID и удаляет его конфигурации."""
    await vpn_manager.delete_user(user_id)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
            await db.commit()
            return True
        except aiosqlite.Error:
            logger.error("Ошибка при удалении пользователя:", exc_info=True)
            return False


async def get_users_list() -> str:
    """Получает список всех пользователей и записывает его в CSV файл."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            async with db.execute(
                "SELECT id, username, status, access_granted_date, access_duration, access_end_date, last_notification_id, has_used_trial FROM users"
            ) as cursor:
                # Dynamically fetch column names from cursor.description
                column_names = [description[0] for description in cursor.description]
                
                # Change file extension to .csv
                file_name = "users_list.csv"
                async with aiofiles.open(file_name, "w", encoding="utf-8") as file:
                    if column_names:
                        # Write headers, quoted and comma-separated
                        await file.write(",".join(f'"{col}"' for col in column_names) + "\n")
                        
                        async for row in cursor: # Iterate over cursor for optimization
                            # Convert all elements to string, handle None, and quote for CSV
                            formatted_row = [f'"{str(item).replace("\"", "")}"' if item is not None else '""' for item in row]
                            await file.write(",".join(formatted_row) + "\n")
                    else:
                        await file.write("Нет пользователей в базе данных.\n") # This line might need adjustment for CSV
            return file_name
        except (aiosqlite.Error, IOError, OSError):
            logger.error("Ошибка при получении списка пользователей:", exc_info=True)
            return None


async def add_promo_code(code: str, days_duration: int, usage_count: int) -> bool:
    """Добавляет новый промокод в базу данных."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO promo_codes (code, days_duration, is_active, usage_count) VALUES (?, ?, 1, ?)",
                (code, days_duration, usage_count),
            )
            await db.commit()
            logger.info(f"Промокод {code} добавлен.")
            return True
        except aiosqlite.IntegrityError:
            logger.warning(f"Промокод {code} уже существует.")
            return False
        except aiosqlite.Error as e:
            logger.error(f"Ошибка при добавлении промокода {code}: {e}", exc_info=True)
            return False


async def get_promo_code(code: str) -> tuple:
    """Возвращает информацию о промокоде по его коду."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT * FROM promo_codes WHERE code = ?", (code,)) as cursor:
            return await cursor.fetchone()




async def delete_promo_code(code: str) -> bool:
    """Удаляет промокод."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                "DELETE FROM promo_codes WHERE code = ?", (code,)
            )
            await db.commit()
            logger.info(f"Промокод {code} удален.")
            return True
        except aiosqlite.Error as e:
            logger.error(f"Ошибка при удалении промокода {code}: {e}", exc_info=True)
            return False


async def get_all_promo_codes() -> list:
    """Возвращает список всех промокодов."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            async with db.execute("SELECT * FROM promo_codes") as cursor:
                return await cursor.fetchall()
        except aiosqlite.Error as e:
            logger.error(f"Ошибка при получении списка промокодов: {e}", exc_info=True)
            return []



