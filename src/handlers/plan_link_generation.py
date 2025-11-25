# src/handlers/plan_link_generation.py
"""
Планировщик для автоматической генерации ссылок
"""

import asyncio
import logging
import secrets
import string
from typing import Optional
from datetime import datetime

from database import db

def generate_unique_link(length=16):
    """Генерация уникальной ссылки"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

class LinkGenerationScheduler:
    """Планировщик для автоматической генерации ссылок"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
    
    async def start_scheduler(self, interval_minutes: int = 5):
        """Запуск планировщика генерации ссылок"""
        try:
            self.logger.info(f"⏰ Планировщик генерации ссылок запущен. Проверка каждые {interval_minutes} минут")
            
            while not self._stop_event.is_set():
                self.logger.info("🔄 Проверяем новых пользователей для генерации ссылок...")
                
                try:
                    # Запускаем автоматическую генерацию ссылок
                    result = await self.generate_links_automatically()
                    
                    if result['generated'] > 0:
                        self.logger.info(f"✅ Автоматически создано {result['generated']} новых ссылок")
                    else:
                        self.logger.info("ℹ️ Нет новых пользователей для генерации ссылок")
                    
                except Exception as e:
                    self.logger.error(f"❌ Ошибка при автоматической генерации ссылок: {e}")
                
                # Ждем указанное количество минут
                self.logger.info(f"⏳ Следующая проверка через {interval_minutes} минут...")
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), 
                        timeout=interval_minutes * 60
                    )
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    self.logger.info("Планировщик генерации ссылок остановлен")
                    break
        
        except Exception as e:
            self.logger.error(f"❌ Ошибка в планировщике генерации ссылок: {e}")
    
    async def generate_links_automatically(self):
        """Автоматическая генерация ссылок для новых пользователей"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Получаем всех пользователей из manual_upload без ссылок
                cursor.execute('''
                    SELECT mu.participant_id, mu.last_name, mu.first_name 
                    FROM manual_upload mu
                    LEFT JOIN link_generation lg ON mu.participant_id = lg.participant_id
                    WHERE lg.participant_id IS NULL
                ''')
                
                users_without_links = cursor.fetchall()
                
                if not users_without_links:
                    return {'generated': 0, 'total': 0}
                
                generated_count = 0
                
                for participant_id, last_name, first_name in users_without_links:
                    # Создаем новую ссылку
                    new_link = generate_unique_link()
                    cursor.execute('''
                        INSERT INTO link_generation (participant_id, universal_link, status, mailing_date)
                        VALUES (?, ?, 1, NULL)
                    ''', (participant_id, new_link))
                    generated_count += 1
                    
                    self.logger.info(f"🤖 Автоматически создана ссылка для participant_id {participant_id}: {last_name} {first_name}")
                
                conn.commit()
                
                return {
                    'generated': generated_count,
                    'total': len(users_without_links),
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка при автоматической генерации ссылок: {e}")
            return {'generated': 0, 'total': 0, 'error': str(e)}
    
    def stop_scheduler(self):
        """Остановка планировщика"""
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
        self.logger.info("🛑 Планировщик генерации ссылок остановлен")
    
    def is_running(self) -> bool:
        """Проверка, работает ли планировщик"""
        return self._task is not None and not self._task.done()

# Глобальный экземпляр планировщика
link_scheduler = None

def get_link_scheduler(logger: logging.Logger) -> LinkGenerationScheduler:
    """Получение экземпляра планировщика"""
    global link_scheduler
    if link_scheduler is None:
        link_scheduler = LinkGenerationScheduler(logger)
    return link_scheduler

async def start_link_generation_scheduler(logger: logging.Logger, interval_minutes: int = 5) -> bool:
    """Запуск планировщика генерации ссылок"""
    try:
        scheduler = get_link_scheduler(logger)
        
        if scheduler.is_running():
            logger.warning("⚠️ Планировщик генерации ссылок уже запущен")
            return True
        
        # Запускаем планировщик в фоне
        scheduler._task = asyncio.create_task(
            scheduler.start_scheduler(interval_minutes)
        )
        
        logger.info(f"✅ Планировщик генерации ссылок запущен (интервал: {interval_minutes} минут)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске планировщика генерации ссылок: {e}")
        return False

async def stop_link_generation_scheduler() -> bool:
    """Остановка планировщика генерации ссылок"""
    global link_scheduler
    
    try:
        if link_scheduler:
            link_scheduler.stop_scheduler()
            return True
        return False
        
    except Exception as e:
        if link_scheduler and link_scheduler.logger:
            link_scheduler.logger.error(f"❌ Ошибка при остановке планировщика генерации ссылок: {e}")
        return False

def is_link_scheduler_running() -> bool:
    """Проверка, работает ли планировщик"""
    global link_scheduler
    return link_scheduler is not None and link_scheduler.is_running()

async def get_link_scheduler_status() -> dict:
    """Получение статуса планировщика"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_users,
                    SUM(CASE WHEN lg.participant_id IS NOT NULL THEN 1 ELSE 0 END) as users_with_links,
                    SUM(CASE WHEN lg.participant_id IS NULL THEN 1 ELSE 0 END) as users_without_links
                FROM manual_upload mu
                LEFT JOIN link_generation lg ON mu.participant_id = lg.participant_id
            ''')
            
            stats = cursor.fetchone()
            total_users, users_with_links, users_without_links = stats
            
            return {
                'scheduler_running': is_link_scheduler_running(),
                'total_users': total_users,
                'users_with_links': users_with_links,
                'users_without_links': users_without_links,
                'timestamp': datetime.now().isoformat()
            }
            
    except Exception as e:
        return {
            'scheduler_running': is_link_scheduler_running(),
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }
