import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'runners.db')
    
    @classmethod
    def validate(cls):
        """Проверка наличия обязательных переменных"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не установлен в .env файле")

