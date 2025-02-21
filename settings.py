from schemas.settings import Settings
from dotenv import load_dotenv

load_dotenv()

# чёт вместо config.py лучше использовать всё таки .env(переменные среды)
# если что просто раскоменть строчку с настройками внизу
# settings = Settings()