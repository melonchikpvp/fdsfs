import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота (Railway подставит его автоматически)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8548246370:AAEYqEVTSdslgQNQPAqo6xh_PEcbnRajt6M")

# ID администраторов (кто будет получать уведомления)
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]

# Настройки базы данных (Railway предоставит URL)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot_database.db")

# Режим отладки
DEBUG = os.getenv("DEBUG", "False").lower() == "true"