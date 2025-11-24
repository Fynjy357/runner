# src/main.py
from aiogram import Bot, Dispatcher
import asyncio
from utils.config import Config
from utils.logger import setup_logging
from utils.shutdown import ShutdownManager
from handlers.start import setup_start_handler
from handlers.link_generation import setup_link_generation_handler
from handlers.stage_management import setup_stage_handlers
from handlers.quest import setup_quest_handler
from handlers.login_pp import setup_login_handler
from handlers.mail_management import setup_mail_handlers
from handlers.participants_export import setup_participants_export_handler
from handlers.update_data import update_router
from handlers.menu import setup_menu_handler
from handlers.admin_commands import setup_admin_handler

# Импортируем интеграцию с рассылкой из текущей директории
from mail_integration import mail_integration


from database import db

# Настройка логирования
logger = setup_logging()

# Инициализация бота
Config.validate()
bot = Bot(token=Config.BOT_TOKEN)
dp = Dispatcher()

# Инициализация менеджера завершения работы
shutdown_manager = ShutdownManager(bot, dp, logger)

async def get_bot_username():
    """Получение username бота"""
    try:
        bot_info = await bot.get_me()
        return bot_info.username
    except Exception as e:
        logger.error(f"Ошибка при получении информации о боте: {e}")
        return None

@dp.startup()
async def on_startup():
    """Вызывается при запуске бота"""
    logger.info("=" * 50)
    logger.info("Бот запускается...")
    
    # Получаем username бота
    bot_username = await get_bot_username()
    if bot_username:
        logger.info(f"Бот: @{bot_username}")
        # Настраиваем обработчики с username бота
        setup_start_handler(dp, shutdown_manager, logger, bot_username)
        setup_link_generation_handler(dp, logger, bot_username)
        setup_stage_handlers(dp)
        setup_quest_handler(dp, logger)
        setup_login_handler(dp)
        setup_mail_handlers(dp)
        setup_participants_export_handler(dp)
        dp.include_router(update_router)
        setup_menu_handler(dp)
        setup_admin_handler(dp)
        
        logger.info("✅ Все обработчики успешно зарегистрированы")
        logger.info("✅ Обработчик квеста зарегистрирован")
        
    else:
        logger.error("Не удалось получить username бота")
        raise RuntimeError("Не удалось получить username бота")
    
    logger.info(f"Токен бота: {'*' * 10}{Config.BOT_TOKEN[-5:]}")
    logger.info(f"Путь к БД: {Config.DATABASE_PATH}")
    
    # Инициализация БД при запуске бота
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Проверяем, что таблицы созданы
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            table_names = [table[0] for table in tables]
            logger.info(f"Доступные таблицы в БД: {table_names}")
            
            # Проверяем наличие колонки quest_started в таблице main
            cursor.execute("PRAGMA table_info(main)")
            columns = cursor.fetchall()
            column_names = [column[1] for column in columns]
            logger.info(f"Колонки в таблице main: {column_names}")
            
            # Проверяем количество пользователей в manual_upload
            cursor.execute("SELECT COUNT(*) FROM manual_upload")
            user_count = cursor.fetchone()[0]
            logger.info(f"Пользователей в manual_upload: {user_count}")
            
    except Exception as e:
        logger.error(f"Ошибка при инициализации БД: {e}", exc_info=True)
        raise
    
    # ЗАПУСК АВТОМАТИЧЕСКОЙ ГЕНЕРАЦИИ ССЫЛОК
    logger.info("🤖 Запуск автоматической генерации ссылок...")
    try:
        from handlers.link_generation import start_link_generation_scheduler
        link_scheduler_started = await start_link_generation_scheduler(logger, 5)
        
        if link_scheduler_started:
            logger.info("✅ Планировщик генерации ссылок успешно запущен")
            logger.info("   ⏰ Интервал: каждые 5 минут")
            logger.info("   🔄 Логика: автоматическое создание ссылок для новых пользователей")
        else:
            logger.warning("⚠️ Не удалось запустить планировщик генерации ссылок")
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске планировщика генерации ссылок: {e}")
    
    # ЗАПУСК ПЛАНИРОВЩИКА РАССЫЛОК
    logger.info("📧 Инициализация системы рассылки...")
    mail_initialized = await mail_integration.initialize()
    
    if mail_initialized:
        # Запускаем частый планировщик (каждые 5 минут)
        scheduler_started = await mail_integration.start_frequent_scheduler(
            interval_minutes=5, 
            template_name="universal_link"
        )
        
        if scheduler_started:
            logger.info("✅ Планировщик рассылок успешно запущен")
            logger.info("   ⏰ Интервал: каждые 5 минут")
            logger.info("   📧 Шаблон: universal_link")
            logger.info("   🔄 Логика: отправка получателям со status=1, если прошло >20 часов с mailing_date")
        else:
            logger.warning("⚠️ Не удалось запустить планировщик рассылок")
    else:
        logger.warning("⚠️ Система рассылки недоступна - проверьте SMTP настройки")
    
    logger.info("=" * 50)

@dp.shutdown()
async def on_shutdown():
    """Вызывается при завершении работы бота"""
    logger.info("=" * 50)
    logger.info("Бот завершает работу...")
    
    # Останавливаем планировщик генерации ссылок
    logger.info("🛑 Останавливаем планировщик генерации ссылок...")
    try:
        from handlers.link_generation import stop_link_generation_scheduler
        await stop_link_generation_scheduler()
        logger.info("✅ Планировщик генерации ссылок остановлен")
    except Exception as e:
        logger.error(f"❌ Ошибка при остановке планировщика генерации ссылок: {e}")
    
    # Останавливаем планировщик рассылок
    if mail_integration.is_mail_service_available():
        logger.info("🛑 Останавливаем планировщик рассылок...")
        await mail_integration.stop_scheduler()
        logger.info("✅ Планировщик рассылок остановлен")
    
    logger.info("=" * 50)

async def main():
    """Основная функция запуска бота"""
    try:
        # Настраиваем обработчики сигналов
        shutdown_manager.setup_signal_handlers()
        
        logger.info("Запуск бота...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Непредвиденная ошибка: {e}", exc_info=True)
    finally:
        logger.info("Работа бота завершена")
        # Принудительно закрываем хендлеры файлов
        for handler in logger.handlers:
            if hasattr(handler, 'close'):
                handler.close()
