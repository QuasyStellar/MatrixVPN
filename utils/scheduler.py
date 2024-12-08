from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from utils.scheduler_tasks import (
    notify_pay_days,
    notify_pay_hour,
    check_users_if_expired,
    make_daily_backup,
)


async def start_scheduler(bot: Bot) -> None:
    """Запускает планировщик для периодических задач бота."""
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    # Ежедневное уведомление за 7, 3 и 1 день до окончания доступа
    scheduler.add_job(
        notify_pay_days,
        trigger="cron",
        hour=16,
        minute=0,
        args=[bot],
        id="notify_pay_days_job",
        replace_existing=True,
    )

    # Уведомление за 12, 6, 3 и 1 час до окончания доступа
    scheduler.add_job(
        notify_pay_hour,
        trigger="cron",
        hour="*",
        args=[bot],
        id="notify_pay_hour_job",
        replace_existing=True,
    )

    # Проверка пользователей с истекшим доступом каждые 10 минут
    scheduler.add_job(
        check_users_if_expired,
        trigger="interval",
        minutes=10,
        args=[bot],
        id="check_users_if_expired_job",
        replace_existing=True,
    )

    # Ежедневный бэкап базы данных в 22:00
    scheduler.add_job(
        make_daily_backup,
        trigger="cron",
        hour=22,
        minute=0,
        args=[bot],
        id="make_daily_backup_job",
        replace_existing=True,
    )

    # Запуск планировщика
    scheduler.start()
