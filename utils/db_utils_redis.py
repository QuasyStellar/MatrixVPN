import asyncio

from aredis_om import Migrator, NotFoundError, RedisModelError, MigrationError
from models.user import User, UserStatusType
from exceptions import BotException
import datetime as dt


async def init_conn_db() -> None:
    # Migration
    try:
        await Migrator().run()
    except MigrationError as e:
        raise BotException(e.args and e.args[0]) from None


async def get_user_by_id(user_id: int) -> User:
    """Возвращает информацию о пользователе по его id."""
    return await User.get(user_id)


async def add_user(user_id: int, username: str) -> None:
    """Добавляет нового пользователя в базу данных или обновляет статус существующего пользователя."""
    try:
        user = await User.get(user_id)
        if user.status == UserStatusType.denied:
            user.status = UserStatusType.pending
            await user.save()
    except NotFoundError:
        try:
            await User(
                user_id=user_id,
                username=username,
                status=UserStatusType.pending
            ).save()
        except RedisModelError as e:
            raise BotException(e.args and e.args[0]) from None


async def grant_access_and_create_config(user_id: int, days: int) -> None:
    """Выдает доступ пользователю и создает необходимые конфигурации."""
    try:
        current_date = dt.datetime.now(dt.UTC)
        end_date = (dt.datetime.now(dt.UTC) + dt.timedelta(days=days))
        user = await User.get(user_id)

        user.status = UserStatusType.accepted

        user.access_granted_date = current_date
        user.access_duration = days
        user.access_end_date = end_date

        await user.save()
        # Удаление старых конфигураций и добавление новых
        delete_command = f"/root/delete-client.sh ov n{user_id} && /root/delete-client.sh wg n{user_id}"
        add_command = f"/root/add-client.sh ov n{user_id} {days} && /root/add-client.sh wg n{user_id} {days}"

        await execute_command(delete_command, user_id, "удаления")
        await execute_command(add_command, user_id, "добавления")
    except NotFoundError:
        raise BotException("Not such user")


async def execute_command(command: str, user_id: int, action: str) -> None:
    """Выполняет команду оболочки и обрабатывает результат."""
    # TODO: переделать, ТАК ДЕЛАТЬ ПЛОХО через время у тебя будет 100% RCE на сервере, ты не боишься reverse shell что ли)?
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


async def update_request_status(user_id: int, status: UserStatusType) -> None:
    """Обновляет статус запроса пользователя."""
    try:
        user = await User.get(user_id)

        user.status = status
        await user.save()
    except RedisModelError as e:
        raise BotException(e.args and e.args[0]) from None


async def check_request(user_id: int) -> UserStatusType:
    """Проверяет статус запроса пользователя по его ID."""
    try:
        return (await User.get(user_id)).status
    except NotFoundError:
        raise BotException("Not such User")


async def delete_user(user_id: int) -> None:
    """Удаляет пользователя из базы данных по его ID."""
    try:
        await User.delete(user_id)
        delete_command = f"/root/delete-client.sh ov n{user_id} && /root/delete-client.sh wg n{user_id}"

        await execute_command(delete_command, user_id, "удаления")
    except NotFoundError:
        raise BotException("Not such User")


async def get_users_list() -> list[User]:
    try:
        pks = await User.all_pks()
        tasks = []
        for pk in pks:
            tasks.append(asyncio.create_task(User.get(pk)))

        users: tuple[User] = await asyncio.gather(*tasks)

        return list(users)
    except RedisModelError as e:
        raise BotException(e.args and e.args[0]) from None

