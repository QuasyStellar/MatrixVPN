import asyncpg
import asyncio
from datetime import datetime, timedelta, timezone
from config import POSTGRES_CONFIG


# Инициализация пула соединений
async def init_db_pool():
    """Создает пул соединений с PostgreSQL."""
    global db_pool
    db_pool = await asyncpg.create_pool(**POSTGRES_CONFIG, min_size=1, max_size=10)
    print("Пул соединений с PostgreSQL успешно создан.")


# Закрытие пула соединений
async def close_db_pool():
    """Закрытие пула соединений с PostgreSQL."""
    global db_pool
    if db_pool:
        await db_pool.close()
        print("Пул соединений с PostgreSQL успешно закрыт.")


# Функция для создания таблицы пользователей
async def init_conn_db() -> None:
    """Создает таблицу пользователей в базе данных, если она не существует."""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT,
                    status TEXT DEFAULT 'pending',
                    access_granted_date TIMESTAMPTZ,
                    access_duration INTEGER,
                    access_end_date TIMESTAMPTZ,
                    last_notification_id INTEGER,
                    notifications_enabled BOOLEAN
                );
                """
            )
        print("Таблица успешно создана или уже существует.")
    except Exception as e:
        print(f"Ошибка при создании таблицы: {e}")


# Получение пользователя по ID
async def get_user_by_id(user_id: int) -> tuple:
    """Возвращает информацию о пользователе по его ID."""
    try:
        async with db_pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    except Exception as e:
        print(f"Ошибка при получении пользователя: {e}")
        return None


# Добавление пользователя
async def add_user(user_id: int, username: str) -> None:
    """Добавляет нового пользователя в базу данных или обновляет статус существующего пользователя."""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (id, username, status) VALUES ($1, $2, 'pending') ON CONFLICT (id) DO UPDATE SET username = $2;",
                user_id,
                username,
            )
    except Exception as e:
        print(f"Ошибка при добавлении пользователя: {e}")


# Выдача доступа и создание конфигураций
async def grant_access_and_create_config(user_id: int, days: int) -> None:
    """Выдает доступ пользователю и создает необходимые конфигурации."""
    try:
        current_date = datetime.now(timezone.utc)
        end_date = current_date + timedelta(days=days)

        async with db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE users SET status = $1, access_granted_date = $2, access_duration = $3, access_end_date = $4 WHERE id = $5""",
                "accepted",
                current_date,
                days,
                end_date,
                user_id,
            )

        # Удаление старых конфигураций и добавление новых
        delete_command = f"/root/delete-client.sh ov n{user_id} && /root/delete-client.sh wg n{user_id}"
        add_command = f"/root/add-client.sh ov n{user_id} {days} && /root/add-client.sh wg n{user_id} {days}"

        await execute_command(delete_command, user_id, "удаления")
        await execute_command(add_command, user_id, "добавления")

    except Exception as e:
        print(f"Ошибка при выдаче доступа и создании конфигурации: {e}")


# Выполнение команд оболочки
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


# Обновление статуса запроса пользователя
async def update_request_status(user_id: int, status: str) -> None:
    """Обновляет статус запроса пользователя."""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET status = $1 WHERE id = $2", status, user_id
            )
    except Exception as e:
        print(f"Ошибка при обновлении статуса запроса: {e}")


# Проверка статуса запроса пользователя
async def check_request(user_id: int) -> str:
    """Проверяет статус запроса пользователя по его ID."""
    try:
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT status FROM users WHERE id = $1", user_id
            )
            return result["status"] if result else None
    except Exception as e:
        print(f"Ошибка при проверке запроса: {e}")
        return None


# Удаление пользователя
async def delete_user(user_id: int) -> None:
    """Удаляет пользователя из базы данных по его ID."""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM users WHERE id = $1", user_id)

        delete_command = f"/root/delete-client.sh ov n{user_id} && /root/delete-client.sh wg n{user_id}"
        await execute_command(delete_command, user_id, "удаления")
    except Exception as e:
        print(f"Ошибка при удалении пользователя: {e}")


# Получение списка всех пользователей
async def get_users_list() -> None:
    """Получает список всех пользователей и записывает его в текстовый файл."""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM users")
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
                            str(row["id"]),
                            row["username"] if row["username"] else "None",
                            row["status"] if row["status"] else "None",
                            (
                                row["access_granted_date"]
                                if row["access_granted_date"]
                                else "None"
                            ),
                            (
                                str(row["access_duration"])
                                if row["access_duration"]
                                else "None"
                            ),
                            (
                                row["access_end_date"]
                                if row["access_end_date"]
                                else "None"
                            ),
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
