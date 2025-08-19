from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config.settings import TOKEN

# Инициализация бота и Dispatcher
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)
