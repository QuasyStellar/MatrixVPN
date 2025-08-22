import aiosqlite
from datetime import datetime, timedelta
import pytz
import logging

from config.settings import DATABASE_PATH, CLIENT_SCRIPT_PATH, ADMIN_ID
from services.db_operations import (
    grant_access_and_create_config,
    update_request_status,
    execute_command,
    delete_user,
    add_user,
    get_users_list,
)
from services.messages_manage import broadcast_message
from services.forms import Form # Assuming Forms.py becomes services/forms.py

logger = logging.getLogger(__name__)

# Функция для склонения слова "день"
def get_day_word(days: int) -> str:
    if 10 <= days % 100 <= 20:
        return "дней"
    elif days % 10 == 1:
        return "день"
    elif 2 <= days % 10 <= 4:
        return "дня"
    else:
        return "дней"

# Add other service functions here as they are extracted from handlers
