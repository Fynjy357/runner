#!/usr/bin/env python3
"""
Интеграция системы рассылки с ботом
"""

import asyncio
import logging
import os
import sys
from typing import Optional
import concurrent.futures

# Добавляем путь к src для импорта
current_dir = os.path.dirname(__file__)
src_path = current_dir  # src/ уже является корневой папкой

if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Отладочная информация
print(f"📁 Current dir: {current_dir}")
print(f"📁 SRC path: {src_path}")
print(f"📁 Mail service exists: {os.path.exists(os.path.join(current_dir, 'mail_service'))}")

try:
    # Импортируем через полный путь как пакет
    from mail_service.email_main import MailServiceManager
    from mail_service.config import load_smtp_config_from_env
    print("✅ Импорт mail_service успешен!")
    MAIL_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"❌ Ошибка импорта mail_service: {e}")
    print(f"📁 Содержимое mail_service:")
    mail_service_dir = os.path.join(current_dir, 'mail_service')
    if os.path.exists(mail_service_dir):
        for file in os.listdir(mail_service_dir):
            print(f"   - {file}")
    MAIL_SERVICE_AVAILABLE = False

logger = logging.getLogger(__name__)

class MailSchedulerIntegration:
    def __init__(self):
        self.mail_manager: Optional[MailServiceManager] = None
        self.scheduler_task: Optional[asyncio.Task] = None
        self.is_running = False
        
    async def initialize(self) -> bool:
        """Инициализация системы рассылки"""
        if not MAIL_SERVICE_AVAILABLE:
            logger.warning("⚠️ Mail service not available - skipping initialization")
            return False
            
        try:
            # Проверяем наличие SMTP конфигурации
            smtp_config = load_smtp_config_from_env()
            if not smtp_config:
                logger.warning("⚠️ SMTP configuration not found - mail scheduler disabled")
                return False
                
            self.mail_manager = MailServiceManager()
            
            if not self.mail_manager.initialize():
                logger.error("❌ Failed to initialize mail service")
                return False
                
            # Тестируем соединение
            if not self.mail_manager.test_connection():
                logger.warning("⚠️ SMTP connection test failed - mail scheduler disabled")
                return False
                
            logger.info("✅ Mail service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing mail service: {e}")
            return False
    
    async def start_scheduler(self, send_time: str = "09:00", 
                            template_name: str = "universal_link"):
        """Запуск планировщика рассылок (для обратной совместимости)"""
        logger.info("⚠️ Используем частый планировщик вместо ежедневного")
        return await self.start_frequent_scheduler(5, template_name)
    
    async def start_frequent_scheduler(self, interval_minutes: int = 5, 
                                     template_name: str = "universal_link"):
        """Запуск частого планировщика рассылок (каждые N минут)"""
        if not self.mail_manager:
            logger.error("❌ Mail service not initialized")
            return False
            
        try:
            logger.info(f"⏰ Starting frequent mail scheduler (interval: {interval_minutes}min, template: {template_name})")
            
            # Запускаем планировщик в отдельной задаче
            self.scheduler_task = asyncio.create_task(
                self.mail_manager.start_frequent_scheduler(interval_minutes, template_name)
            )
            
            self.is_running = True
            logger.info("✅ Frequent mail scheduler started successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting frequent mail scheduler: {e}")
            return False
    
    async def stop_scheduler(self):
        """Остановка планировщика"""
        if self.mail_manager and self.is_running:
            try:
                self.mail_manager.stop_scheduler()
                
                if self.scheduler_task and not self.scheduler_task.done():
                    self.scheduler_task.cancel()
                    try:
                        await self.scheduler_task
                    except asyncio.CancelledError:
                        pass
                
                self.is_running = False
                logger.info("🛑 Mail scheduler stopped")
                
            except Exception as e:
                logger.error(f"❌ Error stopping mail scheduler: {e}")
    
    async def send_immediate_campaign(self, template_name: str = "universal_link") -> dict:
        """Немедленная рассылка с обработкой таймаутов"""
        if not self.mail_manager:
            return {'error': 'Mail service not initialized'}
            
        try:
            logger.info(f"⚡ Sending immediate campaign: {template_name}")
            
            # Сразу отвечаем пользователю, что рассылка началась
            # чтобы избежать таймаута Telegram
            initial_response = {
                'status': 'started',
                'message': f'Рассылка {template_name} запущена...'
            }
            
            # Запускаем в отдельном потоке, чтобы не блокировать бота
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = await loop.run_in_executor(
                    pool, 
                    self.mail_manager.send_immediate_campaign, 
                    template_name
                )
            
            # Добавляем информацию о шаблоне в результат
            if isinstance(result, dict):
                result['template'] = template_name
                
            return result
            
        except Exception as e:
            logger.error(f"❌ Error sending immediate campaign: {e}")
            return {'error': str(e), 'template': template_name}
    
    def is_mail_service_available(self) -> bool:
        """Проверка доступности сервиса рассылки"""
        return MAIL_SERVICE_AVAILABLE and self.mail_manager is not None

# Глобальный экземпляр для использования во всем приложении
mail_integration = MailSchedulerIntegration()
