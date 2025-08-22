import aiosqlite # Added import for aiosqlite
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from config.settings import DATABASE_PATH, CLIENT_SCRIPT_PATH
import subprocess # Added import for subprocess
import aiofiles # Added import for aiofiles

logger = logging.getLogger(__name__)

async def get_user_by_id(user_id: int) -> tuple:
    """Возвращает информацию о пользователе по его ID."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()


async def add_user(user_id: int, username: str) -> None:
    """Добавляет нового пользователя в базу данных или обновляет статус существующего пользователя."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (id, username, status) VALUES (?, ?, 'pending')",
                (user_id, username),
            )
            await db.execute(
                "UPDATE users SET status = 'pending' WHERE id = ? AND (status = 'denied' OR status = 'expired')",
                (user_id,),
            )
            await db.commit()
    except aiosqlite.Error:
        logger.error("Ошибка при добавлении пользователя:", exc_info=True)


async def grant_access_and_create_config(user_id: int, days: int) -> None:
    """Выдает доступ пользователю и создает необходимые конфигурации."""
    try:
        current_date = datetime.now(timezone.utc).isoformat()
        end_date = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                """UPDATE users SET status = ?, access_granted_date = ?, access_duration = ?, access_end_date = ? WHERE id = ?""",
                ("accepted", current_date, days, end_date, user_id),
            )
            await db.commit()

        # Удаление старых конфигураций
        delete_ovpn_result = await execute_command([CLIENT_SCRIPT_PATH, "2", f"n{user_id}"], user_id, "удаления OpenVPN")
        delete_wg_result = await execute_command([CLIENT_SCRIPT_PATH, "5", f"n{user_id}"], user_id, "удаления WireGuard")

        # Добавление новых конфигураций
        add_ovpn_result = await execute_command([CLIENT_SCRIPT_PATH, "1", f"n{user_id}", str(days)], user_id, "добавления OpenVPN")
        add_wg_result = await execute_command([CLIENT_SCRIPT_PATH, "4", f"n{user_id}", str(days)], user_id, "добавления WireGuard")

        if any(result != 0 for result in [delete_ovpn_result, delete_wg_result, add_ovpn_result, add_wg_result]):
            logger.critical(f"Внимание: Не удалось полностью настроить VPN для пользователя {user_id}. Откат статуса в базе данных.")
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute("UPDATE users SET status = 'pending' WHERE id = ?", (user_id,))
                await db.commit()

    except aiosqlite.Error:
        logger.error("Ошибка при выдаче доступа и создании конфигурации (ошибка БД):", exc_info=True)
    except Exception as e: # Catch any other unexpected errors
        logger.error(f"Неожиданная ошибка при выдаче доступа и создании конфигурации для пользователя {user_id}: {e}", exc_info=True)


async def execute_command(command_args: list[str], user_id: int, action: str) -> int:
    """Выполняет команду оболочки и обрабатывает результат."""
    process = await asyncio.create_subprocess_exec(
        *command_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode == 0:
        logger.info(
            f"{action.capitalize()} пользователя {user_id} выполнено успешно: {stdout.decode()}"
        )
    else:
        logger.error(f"Ошибка {action} пользователя {user_id}: {stderr.decode()}")
    return process.returncode


async def update_request_status(user_id: int, status: str) -> None:
    """Обновляет статус запроса пользователя."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "UPDATE users SET status = ? WHERE id = ?", (status, user_id)
            )
            await db.commit()
    except aiosqlite.Error:
        logger.error("Ошибка при обновлении статуса запроса:", exc_info=True)


async def check_request(user_id: int) -> str:
    """Проверяет статус запроса пользователя по его ID."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT status FROM users WHERE id = ?", (user_id,)
            ) as cursor:
                return await cursor.fetchone()
    except aiosqlite.Error:
        logger.error("Ошибка при проверке запроса:", exc_info=True)
        return None


async def delete_user(user_id: int) -> None:
    """Удаляет пользователя из базы данных по его ID."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
            await db.commit()
        
        delete_ovpn_result = await execute_command([CLIENT_SCRIPT_PATH, "2", f"n{user_id}"], user_id, "удаления OpenVPN")
        delete_wg_result = await execute_command([CLIENT_SCRIPT_PATH, "5", f"n{user_id}"], user_id, "удаления WireGuard")

        if any(result != 0 for result in [delete_ovpn_result, delete_wg_result]):
            logger.warning(f"Внимание: Не удалось полностью удалить VPN конфигурации для пользователя {user_id}. Возможно, требуется ручная очистка.")

    except aiosqlite.Error:
        logger.error("Ошибка при удалении пользователя (ошибка БД):", exc_info=True)
    except Exception as e: # Catch any other unexpected errors
        logger.error(f"Неожиданная ошибка при удалении пользователя {user_id}: {e}", exc_info=True)


async def get_users_list() -> None:
    """Получает список всех пользователей и записывает его в текстовый файл."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT * FROM users") as cursor:
                rows = await cursor.fetchall()
                async with aiofiles.open("users_list.txt", "w") as file:
                    if rows:
                        column_widths = [40, 40, 40, 40, 40, 40, 40]
                        headers = [
                            "ID",
                            "Username",
                            "Status",
                            "Access Granted Date",
                            "Access Duration",
                            "Access End Date",
                        ]

                        # Запись заголовков таблицы
                        header_line = "".join(
                            f"{header:<{width}}"
                            for header, width in zip(headers, column_widths)
                        )
                        await file.write(header_line + "\n")
                        await file.write("-" * sum(column_widths) + "\n")

                        # Запись данных пользователей
                        for row in rows:
                            formatted_row = [
                                str(row[0]),
                                row[1] if row[1] is not None else "None",
                                row[2] if row[2] is not None else "None",
                                row[3] if row[3] is not None else "None",
                                str(row[4]) if row[4] is not None else "None",
                                row[5] if row[5] is not None else "None",
                            ]

                            line = "".join(
                                f"{item:<{width}}"
                                for item, width in zip(formatted_row, column_widths)
                            )
                            await file.write(line + "\n")
                    else:
                        await file.write("Нет пользователей в базе данных.\n")
        return "users_list.txt"
    except (aiosqlite.Error, IOError, OSError):
        logger.error("Ошибка при получении списка пользователей:", exc_info=True)
        return None

