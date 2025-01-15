from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
import asyncpg
from config import TOKEN, POSTGRES_CONFIG

# Инициализация хранилища для FSM
storage = MemoryStorage()

# Инициализация бота
bot = Bot(token=TOKEN)

# Инициализация диспетчера
dp = Dispatcher(storage=storage)

# Переменная для хранения пула соединений с базой данных
db_pool: asyncpg.Pool = None


# Функции для инициализации и закрытия соединений с базой данных
async def init_db_pool():
    """Инициализация пула соединений с PostgreSQL."""
    global db_pool
    db_pool = await asyncpg.create_pool(**POSTGRES_CONFIG, min_size=1, max_size=10)
    print("Пул соединений с PostgreSQL успешно создан.")


async def close_db_pool():
    """Закрытие пула соединений с PostgreSQL."""
    global db_pool
    if db_pool:
        await db_pool.close()
        print("Пул соединений с PostgreSQL успешно закрыт.")
