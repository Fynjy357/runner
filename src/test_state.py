# test_state.py
import asyncio
import sys
from pathlib import Path

# Добавляем путь к проекту
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from handlers.stage_1 import Stage1States, setup_stage_1_handlers

async def test_state():
    """Тестирование состояния пользователя"""
    # Создаем тестовый бот и диспетчер
    bot = Bot(token="dummy_token")
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Настраиваем обработчики
    setup_stage_1_handlers(dp)
    
    print("✅ Обработчики настроены")
    
    # Проверяем, какие обработчики зарегистрированы
    print("\n📋 Зарегистрированные обработчики сообщений:")
    for handler in dp.message.handlers:
        print(f"  - {handler}")
    
    print("\n📋 Зарегистрированные обработчики callback:")
    for handler in dp.callback_query.handlers:
        print(f"  - {handler}")
    
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_state())
