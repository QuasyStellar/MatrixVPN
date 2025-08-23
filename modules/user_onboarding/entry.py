from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from aiogram.filters.command import Command

from modules.user_onboarding.services import process_start_command

import logging

logger = logging.getLogger(__name__)

user_onboarding_entry_router = Router()


@user_onboarding_entry_router.message(Command("start"))
async def start_handler(
    message: types.Message = None, user_id: int = None, state: FSMContext = None
) -> None:
    """Отображает начальное меню в зависимости от статуса пользователя."""
    if state:
        await state.clear()
    await process_start_command(message=message, user_id=user_id)
