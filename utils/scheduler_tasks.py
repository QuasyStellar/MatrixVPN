import asyncio
import aiosqlite
from pytils import numeral
from aiogram import Bot, types
from aiogram.types import FSInputFile
from datetime import datetime, timezone
from babel.dates import format_datetime
import pytz

from config import ADMIN_ID, DATABASE_PATH


async def notify_pay_days(bot: Bot) -> None:
    """Уведомляет пользователей о приближающемся истечении доступа к MatrixVPN за несколько дней."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            current_date = datetime.now(timezone.utc)
            # Пороговые значения для уведомлений о днях
            days_threshold = [7, 3, 1]

            async with db.execute(
                """
                SELECT id, username, access_end_date FROM users
                WHERE access_end_date IS NOT NULL AND status = "accepted"
            """
            ) as cursor:
                users = await cursor.fetchall()

            for user in users:
                user_id, username, access_end_date = user
                access_end_date = datetime.fromisoformat(access_end_date)
                remaining_time = access_end_date - current_date
                remaining_days = remaining_time.days

                # Форматирование даты окончания доступа
                end_date_formatted = format_datetime(
                    access_end_date.replace(tzinfo=pytz.utc).astimezone(
                        pytz.timezone("Europe/Moscow")
                    ),
                    "d MMMM yyyy 'в' HH:mm",
                    locale="ru",
                )

                if remaining_days in days_threshold:
                    message = (
                        f"<b>⏰ Время идет, @{username}!</b>\n\n"
                        f"Ваш доступ к <b>MatrixVPN</b> истекает через <b>{numeral.get_plural(remaining_days, 'день, дня, дней')}</b>.\n\n"
                        f"Точная дата и время окончания доступа: <b>{end_date_formatted}</b>\n\n"
                        f"Пожалуйста, <b>произведите оплату</b>, чтобы избежать возвращения в <b>«матрицу»</b>.\n\n"
                    )
                    await bot.send_message(user_id, message, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка при уведомлении пользователей о днях: {e}")


async def notify_pay_hour(bot: Bot) -> None:
    """Уведомляет пользователей о приближающемся истечении доступа к MatrixVPN за несколько часов."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            current_date = datetime.now(timezone.utc)
            # Пороговые значения для уведомлений о часах
            hours_threshold = [12, 6, 1]

            async with db.execute(
                """
                SELECT id, username, access_end_date FROM users
                WHERE access_end_date IS NOT NULL AND status = "accepted"
            """
            ) as cursor:
                users = await cursor.fetchall()

            for user in users:
                user_id, username, access_end_date = user
                access_end_date = datetime.fromisoformat(access_end_date)

                remaining_time = access_end_date - current_date
                remaining_hours = remaining_time.seconds // 3600

                # Форматирование даты окончания доступа
                end_date_formatted = format_datetime(
                    access_end_date.replace(tzinfo=pytz.utc).astimezone(
                        pytz.timezone("Europe/Moscow")
                    ),
                    "d MMMM yyyy 'в' HH:mm",
                    locale="ru",
                )

                if remaining_time.days < 1 and remaining_hours in hours_threshold:
                    message = (
                        f"<b>📢 Внимание, @{username}!</b>\n\n"
                        f"Ваш доступ к <b>MatrixVPN</b> истекает через <b>{numeral.get_plural(remaining_hours, 'час, часа, часов')}</b> ⏳.\n\n"
                        f"Точная дата и время окончания доступа: <b>{end_date_formatted}</b>\n\n"
                        f"Пожалуйста, <b>произведите оплату</b>, чтобы избежать возвращения в <b>«матрицу»</b>.\n\n"
                    )
                    await bot.send_message(user_id, message, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка при уведомлении пользователей о часах: {e}")


async def make_daily_backup(bot: Bot) -> None:
    """Создает резервную копию базы данных и отправляет ее администратору."""
    try:
        await bot.send_document(
            ADMIN_ID,
            FSInputFile(DATABASE_PATH),
            caption=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        print(f"Ошибка при создании резервной копии: {e}")


async def check_users_if_expired(bot: Bot) -> None:
    """Проверяет пользователей с истекшим доступом и уведомляет их об этом."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
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

                # Обновление статуса пользователя на 'expired'
                await db.execute(
                    """
                    UPDATE users SET status = 'expired', access_granted_date = NULL, access_duration = NULL
                    WHERE id = ?
                """,
                    (user_id,),
                )

                # Удаление доступа
                command = f"/root/delete-client.sh ov {user_id} && /root/delete-client.sh wg {user_id}"
                process = await asyncio.create_subprocess_shell(command, shell=True)
                await process.communicate()

                # Уведомление пользователя о просрочке доступа
                message = (
                    f"<b>🚫 Внимание, @{username}!</b>\n\n"
                    f"Ваша подписка на доступ к <b>MatrixVPN</b> истекла ⏳.\n\n"
                    f"Пожалуйста, <b>продлите подписку</b>, чтобы избежать возвращения в <b>«матрицу»</b>."
                )
                await bot.send_animation(
                    user_id,
                    FSInputFile("assets/expired.gif"),
                    caption=message,
                    parse_mode="HTML",
                )

                # Уведомление администратора о просрочке доступа
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

            await db.commit()
    except Exception as e:
        print(f"Ошибка при обновлении статусов пользователей: {e}")
