import asyncio
import aiosqlite
from pytils import numeral
from aiogram import Bot, types
from aiogram.types import FSInputFile
from datetime import datetime, timezone, timedelta
from babel.dates import format_datetime
import pytz
import logging
import os

from config.settings import ADMIN_ID, CLIENT_SCRIPT_PATH, TIMEZONE, DATABASE_PATH
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
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            current_date = datetime.now(timezone.utc)
            days_thresholds = [3, 1]

            for days in days_thresholds:
                notification_date = current_date + timedelta(days=days)
                async with db.execute(
                    """
                    SELECT id, username, access_end_date FROM users
                    WHERE status = 'accepted' AND date(access_end_date) = date(?)
                    """,
                    (notification_date.isoformat(),)
                ) as cursor:
                    users = await cursor.fetchall()

                for user in users:
                    user_id, username, access_end_date_str = user
                    access_end_date = datetime.fromisoformat(access_end_date_str)
                    end_date_formatted = format_datetime(
                        access_end_date.replace(tzinfo=pytz.utc).astimezone(
                            pytz.timezone(TIMEZONE)
                        ),
                        "d MMMM yyyy 'в' HH:mm",
                        locale="ru",
                    )

                    message = (
                        f"<b>⏰ Время идет!</b>\n\n"
                        f"Ваш доступ к <b>MatrixVPN</b> истекает через <b>{numeral.get_plural(days, 'день, дня, дней')}</b>.\n\n"
                        f"Точная дата и время окончания доступа: <b>{end_date_formatted}</b>\n\n"
                        f"Пожалуйста, <b>произведите оплату</b>, чтобы избежать возвращения в <b>«матрицу»</b>.\n\n"
                    )
                    await safe_send_message(bot, db, user_id, message)
        except (aiosqlite.Error, types.TelegramAPIError) as e:
            logger.error("Ошибка при уведомлении пользователей о днях:", exc_info=True)


async def notify_pay_hour(bot: Bot) -> None:
    """Уведомляет пользователей о приближающемся истечении доступа к MatrixVPN за несколько часов."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            current_date = datetime.now(timezone.utc)
            hours_thresholds = [12, 1]

            for hours in hours_thresholds:
                notification_date = current_date + timedelta(hours=hours)
                async with db.execute(
                    """
                    SELECT id, username, access_end_date FROM users
                    WHERE status = 'accepted' AND datetime(access_end_date) <= datetime(?, '+1 hour') AND datetime(access_end_date) > datetime(?) 
                    """,
                    (notification_date.isoformat(), notification_date.isoformat())
                ) as cursor:
                    users = await cursor.fetchall()

                for user in users:
                    user_id, username, access_end_date_str = user
                    access_end_date = datetime.fromisoformat(access_end_date_str)
                    end_date_formatted = format_datetime(
                        access_end_date.replace(tzinfo=pytz.utc).astimezone(
                            pytz.timezone(TIMEZONE)
                        ),
                        "d MMMM yyyy 'в' HH:mm",
                        locale="ru",
                    )

                    message = (
                        f"<b>📢 Внимание!</b>\n\n"
                        f"Ваш доступ к <b>MatrixVPN</b> истекает через <b>{numeral.get_plural(hours, 'час, часа, часов')}</b> ⏳\n\n"
                        f"Точная дата и время окончания доступа: <b>{end_date_formatted}</b>\n\n"
                        f"Пожалуйста, <b>произведите оплату</b>, чтобы избежать возвращения в <b>«матрицу»</b>.\n\n"
                    )
                    await safe_send_message(bot, db, user_id, message)
        except (aiosqlite.Error, types.TelegramAPIError) as e:
            logger.error("Ошибка при уведомлении пользователей о часах:", exc_info=True)


async def make_daily_backup(bot: Bot) -> None:
    """Создает резервную копию базы данных и отправляет ее администратору."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        backup_path = f"backup_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M-%S')}.db"
        try:
            async with aiosqlite.connect(backup_path) as backup_db:
                await db.backup(backup_db)
            await bot.send_document(
                ADMIN_ID,
                FSInputFile(backup_path),
                caption=f"Резервная копия базы данных от {datetime.now(timezone.utc).isoformat()}",
            )
            os.remove(backup_path)
        except (IOError, OSError, types.TelegramAPIError, aiosqlite.Error) as e:
            logger.error("Ошибка при создании резервной копии:", exc_info=True)


async def check_users_if_expired(bot: Bot) -> None:
    """Проверяет пользователей с истекшим доступом и уведомляет их об этом."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute("BEGIN")
            current_date = datetime.now(timezone.utc).isoformat()

            async with db.execute(
                """
                    SELECT id, username FROM users
                    WHERE access_end_date IS NOT NULL AND status = "accepted" AND access_end_date < ?
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
                
                delete_ovpn_result = await execute_command([CLIENT_SCRIPT_PATH, "2", f"n{user_id}"], user_id, "удаления OpenVPN")
                delete_wg_result = await execute_command([CLIENT_SCRIPT_PATH, "5", f"n{user_id}"], user_id, "удаления WireGuard")

                if any(result != 0 for result in [delete_ovpn_result, delete_wg_result]):
                    logger.warning(f"Внимание: Не удалось полностью удалить VPN конфигурации для истекшего пользователя {user_id}. Возможно, требуется ручная очистка.")

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
                                callback_data=f"approve_access:{user_id}",
                            )
                        ]
                    ]
                )
                await bot.send_message(
                    ADMIN_ID,
                    f"Доступ пользователя @{username} (ID: {user_id}) истек.",
                    reply_markup=markup,
                )
            await db.commit()
        except aiosqlite.Error as e:
            await db.rollback()
            logger.error("Ошибка при обновлении статусов пользователей (ошибка БД):", exc_info=True)
        except types.TelegramAPIError as e:
            await db.rollback()
            logger.error("Ошибка Telegram API при обновлении статусов пользователей:", exc_info=True)
        except Exception as e: # Catch any other unexpected errors
            await db.rollback()
            logger.error(f"Неожиданная ошибка при обновлении статусов пользователей: {e}", exc_info=True)

async def start_scheduler(bot: Bot) -> None:
    """Запускает планировщик для периодических задач бота."""
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

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