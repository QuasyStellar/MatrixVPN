import aiosqlite
import asyncio
from datetime import datetime, timedelta, timezone
from config import DATABASE_PATH


# Инициализация и подключение к базе данных пользователей
async def init_conn_db() -> None:
    """Создает таблицу пользователей в базе данных, если она не существует."""
    try:
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
                    notifications_enabled BOOL
                )
            """
            )

            await db.commit()
        print("Таблица успешно создана или уже существует.")
    except Exception as e:
        print(f"Ошибка при создании таблицы: {e}")


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
                "UPDATE users SET status = 'pending' WHERE id = ? AND status = 'denied'",
                (user_id,),
            )
            await db.commit()
    except Exception as e:
        print(f"Ошибка при добавлении пользователя: {e}")


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

        # Удаление старых конфигураций и добавление новых
        delete_command = f"/root/delete-client.sh ov n{user_id} && /root/delete-client.sh wg n{user_id}"
        add_command = f"/root/add-client.sh ov n{user_id} {days} && /root/add-client.sh wg n{user_id} {days}"

        await execute_command(delete_command, user_id, "удаления")
        await execute_command(add_command, user_id, "добавления")

    except Exception as e:
        print(f"Ошибка при выдаче доступа и создании конфигурации: {e}")


async def execute_command(command: str, user_id: int, action: str) -> None:
    """Выполняет команду оболочки и обрабатывает результат."""
    process = await asyncio.create_subprocess_shell(
        command,
        shell=True,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode == 0:
        print(
            f"{action.capitalize()} пользователя {user_id} выполнено успешно: {stdout.decode()}"
        )
    else:
        print(f"Ошибка {action} пользователя {user_id}: {stderr.decode()}")


async def update_request_status(user_id: int, status: str) -> None:
    """Обновляет статус запроса пользователя."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "UPDATE users SET status = ? WHERE id = ?", (status, user_id)
            )
            await db.commit()
    except Exception as e:
        print(f"Ошибка при обновлении статуса запроса: {e}")


async def check_request(user_id: int) -> str:
    """Проверяет статус запроса пользователя по его ID."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT status FROM users WHERE id = ?", (user_id,)
            ) as cursor:
                return await cursor.fetchone()
    except Exception as e:
        print(f"Ошибка при проверке запроса: {e}")
        return None


async def delete_user(user_id: int) -> None:
    """Удаляет пользователя из базы данных по его ID."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
            await db.commit()
        delete_command = f"/root/delete-client.sh ov n{user_id} && /root/delete-client.sh wg n{user_id}"

        await execute_command(delete_command, user_id, "удаления")
    except Exception as e:
        print(f"Ошибка при удалении пользователя: {e}")


async def get_users_list() -> None:
    """Получает список всех пользователей и записывает его в текстовый файл."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT * FROM users") as cursor:
                rows = await cursor.fetchall()
                with open("users_list.txt", "w") as file:
                    if rows:
                        print(rows)
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
                        file.write(header_line + "\n")
                        file.write("-" * sum(column_widths) + "\n")

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
                            file.write(line + "\n")
                    else:
                        file.write("Нет пользователей в базе данных.\n")
        return "users_list.txt"
    except Exception as e:
        print(f"Ошибка при получении списка пользователей: {e}")
        return None
