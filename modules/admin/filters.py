from aiogram.filters import Filter
from aiogram import types
from config.settings import ADMIN_ID

class IsAdmin(Filter):
    async def __call__(self, message: types.Message) -> bool:
        return message.from_user.id == ADMIN_ID
