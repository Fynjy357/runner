import asyncio
import signal
from aiogram import Dispatcher, Bot
import logging

class ShutdownManager:
    """Менеджер для graceful shutdown бота"""
    
    def __init__(self, bot: Bot, dp: Dispatcher, logger: logging.Logger):
        self.bot = bot
        self.dp = dp
        self.logger = logger
        self.is_shutting_down = False
        
    async def graceful_shutdown(self):
        """Корректное завершение работы"""
        if self.is_shutting_down:
            return
            
        self.is_shutting_down = True
        self.logger.info("Инициировано корректное завершение работы...")
        
        try:
            # Останавливаем polling
            await self.dp.stop_polling()
            self.logger.info("Polling остановлен")
            
            # Закрываем сессию бота
            await self.bot.session.close()
            self.logger.info("Сессия бота закрыта")
            
            self.logger.info("Все ресурсы освобождены")
            
        except Exception as e:
            self.logger.error(f"Ошибка при завершении работы: {e}")

    def signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        self.logger.info(f"Получен сигнал {signum}, завершаем работу...")
        asyncio.create_task(self.graceful_shutdown())

    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        self.logger.info("Обработчики сигналов установлены")

    def is_bot_shutting_down(self):
        """Проверка, завершает ли бот работу"""
        return self.is_shutting_down
