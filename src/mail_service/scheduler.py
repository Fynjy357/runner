#!src/mail_service/scheduler.py
"""
Планировщик для регулярной рассылки
"""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

class EmailScheduler:
    def __init__(self, email_sender):
        self.email_sender = email_sender
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
    
    async def start_frequent_scheduler(self, interval_minutes: int = 5, 
                                     template_name: str = 'universal_link'):
        """Запуск частой рассылки каждые N минут"""
        try:
            logger.info(f"⏰ Планировщик запущен. Проверка каждые {interval_minutes} минут")
            
            while not self._stop_event.is_set():
                logger.info("🔄 Проверяем получателей для рассылки...")
                
                try:
                    # Запускаем рассылку
                    result = self.email_sender.send_bulk_emails(template_name)
                    
                    if result.get('sent', 0) > 0:
                        logger.info(f"✅ Отправлено {result['sent']} писем")
                    else:
                        logger.info("ℹ️ Нет получателей для отправки (status=1 и прошло >20 часов)")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка в рассылке: {e}")
                
                # Ждем указанное количество минут
                logger.info(f"⏳ Следующая проверка через {interval_minutes} минут...")
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), 
                        timeout=interval_minutes * 60
                    )
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    logger.info("Планировщик остановлен")
                    break
        
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике: {e}")
    
    async def start_daily_scheduler(self, send_time: str = "09:00", 
                                  template_name: str = 'universal_link'):
        """Запуск ежедневной рассылки (для обратной совместимости)"""
        logger.warning("⚠️ Ежедневная рассылка устарела, используем частую проверку")
        await self.start_frequent_scheduler(5, template_name)
    
    def stop_scheduler(self):
        """Остановка планировщика"""
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("🛑 Планировщик остановлен")
    
    def is_running(self) -> bool:
        """Проверка, работает ли планировщик"""
        return self._task is not None and not self._task.done()
