import asyncio
import aiosqlite
from pytils import numeral
from aiogram import Bot, types
from aiogram.types import FSInputFile
from datetime import datetime, timezone
from babel.dates import format_datetime
import pytz
import logging

from config.settings import ADMIN_ID, DATABASE_PATH, DELETE_CLIENT_SCRIPT
from services.db_operations import execute_command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

async def safe_send_message(
    bot: Bot,
    db,
    user_id: int,
    message: str,
    parse_mode: str = "HTML",
    reply_markup=None,
) -> bool:
    """Отправляет сообщение пользователю и обрабатывает исключения."""
    try:
        async with db.execute(
            """
            SELECT last_notification_id FROM users WHERE id = ?
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                try:
                    await bot.delete_message(user_id, row[0])
                except types.TelegramAPIError:
                    pass

        sent_message = await bot.send_message(
            user_id, message, parse_mode=parse_mode, reply_markup=reply_markup
        )
        await db.execute(
            """
            UPDATE users SET last_notification_id = ? WHERE id = ?
            """,
            (sent_message.message_id, user_id),
        )
        await db.commit()
        return True
    except types.TelegramForbiddenError:
        logger.warning(f"Пользователь {user_id} заблокировал бота.")
        return False
    except types.TelegramAPIError:
        logger.error(f"Ошибка Telegram API при отправке сообщения пользователю {user_id}:", exc_info=True)
        return False


async def safe_send_animation(
    bot: Bot,
    db,
    user_id: int,
    animation: FSInputFile,
    caption: str,
    parse_mode: str = "HTML",
    reply_markup=None,
) -> bool:
    """Отправляет анимацию пользователю и обрабатывает исключения."""
    try:
        async with db.execute(
            """
            SELECT last_notification_id FROM users WHERE id = ?
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                try:
                    await bot.delete_message(user_id, row[0])
                except types.TelegramAPIError:
                    pass

        sent_message = await bot.send_animation(
            user_id,
            animation,
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        await db.execute(
            """
            UPDATE users SET last_notification_id = ? WHERE id = ?
            """,
            (sent_message.message_id, user_id),
        )
        await db.commit()
        return True
    except types.TelegramForbiddenError:
        logger.warning(f"Пользователь {user_id} заблокировал бота.")
        return False
    except types.TelegramAPIError:
        logger.error(f"Ошибка Telegram API при отправке анимации пользователю {user_id}:", exc_info=True)
        return False


async def notify_pay_days(bot: Bot) -> None:
    """Уведомляет пользователей о приближающемся истечении доступа к MatrixVPN за несколько дней."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            current_date = datetime.now(timezone.utc)
            days_threshold = [3, 1]

            async with db.execute(
                """
                SELECT id, username, access_end_date FROM users
                WHERE access_end_date IS NOT NULL AND status = \"accepted\"
                """
            ) as cursor:
                users = await cursor.fetchall()

            for user in users:
                user_id, username, access_end_date = user
                access_end_date = datetime.fromisoformat(access_end_date)
                remaining_time = access_end_date - current_date
                remaining_days = remaining_time.days

                end_date_formatted = format_datetime(
                    access_end_date.replace(tzinfo=pytz.utc).astimezone(
                        pytz.timezone("Europe/Moscow")
                    ),
                    "d MMMM yyyy 'в' HH:mm",
                    locale="ru",
                )

                if remaining_days in days_threshold:
                    message = (
                        f"<b>⏰ Время идет!</b>\n\n"
                        f"Ваш доступ к <b>MatrixVPN</b> истекает через <b>{numeral.get_plural(remaining_days, 'день, дня, дней')}</b>.\n\n"
                        f"Точная дата и время окончания доступа: <b>{end_date_formatted}</b>\n\n"
                        f"Пожалуйста, <b>произведите оплату</b>, чтобы избежать возвращения в <b>«матрицу»</b>.\n\n"
                    )
                    await safe_send_message(
                        bot, db, user_id, message
                    )
    except (aiosqlite.Error, types.TelegramAPIError):
        logger.error("Ошибка при уведомлении пользователей о днях:", exc_info=True)



async def notify_pay_hour(bot: Bot) -> None:
    """Уведомляет пользователей о приближающемся истечении доступа к MatrixVPN за несколько часов."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            current_date = datetime.now(timezone.utc)
            hours_threshold = [12, 1]

            async with db.execute(
                """
                SELECT id, username, access_end_date FROM users
                WHERE access_end_date IS NOT NULL AND status = \"accepted\"
                """
            ) as cursor:
                users = await cursor.fetchall()

            for user in users:
                user_id, username, access_end_date = user
                access_end_date = datetime.fromisoformat(access_end_date)

                remaining_time = access_end_date - current_date
                remaining_hours = remaining_time.seconds // 3600

                end_date_formatted = format_datetime(
                    access_end_date.replace(tzinfo=pytz.utc).astimezone(
                        pytz.timezone("Europe/Moscow")
                    ),
                    "d MMMM yyyy 'в' HH:mm",
                    locale="ru",
                )

                if remaining_time.days < 1 and remaining_hours in hours_threshold:
                    message = (
                        f"<b>📢 Внимание!</b>\n\n"
                        f"Ваш доступ к <b>MatrixVPN</b> истекает через <b>{numeral.get_plural(remaining_hours, 'час, часа, часов')}</b> ⏳\n\n"
                        f"Точная дата и время окончания доступа: <b>{end_date_formatted}</b>\n\n"
                        f"Пожалуйста, <b>произведите оплату</b>, чтобы избежать возвращения в <b>«матрицу»</b>.\n\n"
                    )
                    await safe_send_message(
                        bot, db, user_id, message
                    )
    except (aiosqlite.Error, types.TelegramAPIError):
        logger.error("Ошибка при уведомлении пользователей о часах:", exc_info=True)



async def make_daily_backup(bot: Bot) -> None:
    """Создает резервную копию базы данных и отправляет ее администратору."""
    try:
        await bot.send_document(
            ADMIN_ID,
            FSInputFile(DATABASE_PATH),
            caption=datetime.now(timezone.utc).isoformat(),
        )
    except (IOError, OSError, types.TelegramAPIError):
        logger.error("Ошибка при создании резервной копии:", exc_info=True)


async def check_users_if_expired(bot: Bot) -> None:
    """Проверяет пользователей с истекшим доступом и уведомляет их об этом."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            current_date = datetime.now(timezone.utc).isoformat()

            async with db.execute(
                """
                    SELECT id, username FROM users
                    WHERE access_end_date IS NOT NULL AND status = \"accepted\" AND access_end_date < ?
                    """,
                (current_date,),
            ) as cursor:
                expired_users = await cursor.fetchall()

            for user in expired_users:
                user_id, username = user

                await db.execute(
                    """
                        UPDATE users SET status = 'expired', access_granted_date = NULL, access_duration = NULL
                        WHERE id = ?
                        """,
                    (user_id,),
                )
                await db.commit()
                await execute_command([DELETE_CLIENT_SCRIPT, "ov", f"n{user_id}"], user_id, "удаления OpenVPN")
                await execute_command([DELETE_CLIENT_SCRIPT, "wg", f"n{user_id}"], user_id, "удаления WireGuard")

                message = (
                    f"<b>🚫 Внимание, @{username}!</b>\n\n"
                    f"Ваша подписка на доступ к <b>MatrixVPN</b> истекла ⏳\n\n"
                    f"Пожалуйста, <b>продлите подписку</b>, чтобы выйти из <b>«матрицы»</b>."
                )
                await safe_send_animation(
                    bot, db, user_id, FSInputFile("assets/expired.gif"), message
                )

                markup = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="Продлить доступ",
                                callback_data=f"approve_access:{user_id}:{username}",
                            )
                        ]
                    ]
                )
                await bot.send_message(
                    ADMIN_ID,
                    f"Доступ пользователя @{username} (ID: {user_id}) истек.",
                    reply_markup=markup,
                )

    except (aiosqlite.Error, types.TelegramAPIError, asyncio.subprocess.SubprocessError, OSError):
        logger.error("Ошибка при обновлении статусов пользователей:", exc_info=True)

async def start_scheduler(bot: Bot) -> None:
    """Запускает планировщик для периодических задач бота."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    scheduler.add_job(
        notify_pay_days,
        trigger="cron",
        hour=16,
        minute=0,
        args=[bot],
        id="notify_pay_days_job",
        replace_existing=True,
    )

    scheduler.add_job(
        notify_pay_hour,
        trigger="cron",
        hour="*",
        args=[bot],
        id="notify_pay_hour_job",
        replace_existing=True,
    )

    scheduler.add_job(
        check_users_if_expired,
        trigger="interval",
        minutes=10,
        args=[bot],
        id="check_users_if_expired_job",
        replace_existing=True,
    )

    scheduler.add_job(
        make_daily_backup,
        trigger="cron",
        hour=22,
        minute=0,
        args=[bot],
        id="make_daily_backup_job",
        replace_existing=True,
    )

    scheduler.start()