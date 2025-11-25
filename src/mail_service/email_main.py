#!src/mail_service/email_main.py
"""
Основной скрипт для запуска системы рассылки
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Добавляем родительскую директорию в путь для импорта
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # src
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Импортируем модули
try:
    from mail_service.email_sender import EmailSender
    from mail_service.config import load_smtp_config_from_env
    from mail_service.scheduler import EmailScheduler
    from mail_service.utils import get_recipients_from_db
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("💡 Запустите скрипт из корневой директории проекта: python src/mail_service/email_main.py")
    sys.exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'mail_service_{datetime.now().strftime("%Y%m%d")}.log', 
                          encoding='utf-8')
    ]
)

logger = logging.getLogger('mail_service_main')

class MailServiceManager:
    def __init__(self):
        self.sender = None
        self.scheduler = None
        
    def initialize(self) -> bool:
        """Инициализация сервиса"""
        try:
            # Загружаем конфигурацию из переменных окружения
            config = load_smtp_config_from_env()
            if not config:
                logger.error("❌ Не удалось загрузить конфигурацию SMTP")
                return False
            
            # Проверяем обязательные параметры
            if not config.email or not config.password:
                logger.error("❌ Email или пароль не установлены")
                logger.info("💡 Установите SMTP_EMAIL и SMTP_PASSWORD в .env файле")
                return False
            
            self.sender = EmailSender(config)
            self.scheduler = EmailScheduler(self.sender)
            
            logger.info("✅ Сервис рассылки инициализирован")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Тестирование соединения"""
        if not self.sender:
            logger.error("❌ Сервис не инициализирован")
            return False
        
        logger.info("🧪 Тестируем SMTP соединение...")
        return self.sender.test_connection()
    
    def send_test_email(self, test_email: str) -> bool:
        """Отправка тестового письма"""
        if not self.sender:
            logger.error("❌ Сервис не инициализирован")
            return False
        
        logger.info(f"🧪 Отправляем тестовое письмо на {test_email}...")
        return self.sender.send_test_email(test_email)
    
    def send_immediate_campaign(self, template_name: str = 'universal_link') -> dict:
        """Немедленная рассылка"""
        if not self.sender:
            logger.error("❌ Сервис не инициализирован")
            return {'error': 'Service not initialized'}
        
        logger.info(f"⚡ Запускаем немедленную рассылку: {template_name}")
        return self.sender.send_bulk_emails(template_name=template_name)
    
    async def start_frequent_scheduler(self, interval_minutes: int = 5, 
                                     template_name: str = 'universal_link'):
        """Запуск частого планировщика"""
        if not self.scheduler:
            logger.error("❌ Сервис не инициализирован")
            return False
        
        logger.info(f"⏰ Запускаем планировщик (интервал: {interval_minutes} минут, шаблон: {template_name})")
        
        # Создаем и запускаем задачу
        self.scheduler._task = asyncio.create_task(
            self.scheduler.start_frequent_scheduler(interval_minutes, template_name)
        )
        
        try:
            await self.scheduler._task
        except asyncio.CancelledError:
            logger.info("Планировщик остановлен")
        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")
    
    async def start_scheduled_campaign(self, send_time: str = "09:00", 
                                     template_name: str = 'universal_link'):
        """Запуск планировщика (для обратной совместимости)"""
        logger.info("⚠️ Используем частый планировщик вместо ежедневного")
        await self.start_frequent_scheduler(5, template_name)
    
    def stop_scheduler(self):
        """Остановка планировщика"""
        if self.scheduler:
            self.scheduler.stop_scheduler()
            logger.info("🛑 Планировщик остановлен")

def print_menu():
    """Печать меню"""
    print("\n" + "="*50)
    print("🎄 СИСТЕМА РАССЫЛКИ НОВОГОДНЕГО КВЕСТА")
    print("="*50)
    print("1. 🧪 Тестировать SMTP соединение")
    print("2. 📧 Отправить тестовое письмо")
    print("3. ⚡ Немедленная рассылка (Universal Link)")
    print("4. ⚡ Немедленная рассылка (Completion)")
    print("5. ⏰ Запустить планировщик (каждые 5 минут)")
    print("6. ⏰ Запустить планировщик с настройкой интервала")
    print("7. 📊 Статистика базы данных")
    print("8. 🛑 Остановить планировщик")
    print("0. ❌ Выход")
    print("="*50)

async def interactive_mode():
    """Интерактивный режим"""
    manager = MailServiceManager()
    
    if not manager.initialize():
        print("❌ Не удалось инициализировать сервис. Проверьте настройки.")
        return
    
    print("✅ Сервис рассылки готов к работе!")
    
    while True:
        print_menu()
        choice = input("\nВыберите действие: ").strip()
        
        if choice == '1':
            # Тестирование соединения
            if manager.test_connection():
                print("✅ SMTP соединение установлено успешно!")
            else:
                print("❌ Ошибка SMTP соединения!")
        
        elif choice == '2':
            # Тестовое письмо
            test_email = input("Введите email для теста: ").strip()
            if test_email:
                if manager.send_test_email(test_email):
                    print(f"✅ Тестовое письмо отправлено на {test_email}")
                else:
                    print(f"❌ Ошибка отправки на {test_email}")
            else:
                print("⚠️ Email не введен")
        
        elif choice == '3':
            # Немедленная рассылка Universal Link
            print("🚀 Запускаем рассылку с универсальными ссылками...")
            stats = manager.send_immediate_campaign('universal_link')
            print(f"📊 Результат: {stats}")
        
        elif choice == '4':
            # Немедленная рассылка Completion
            print("🚀 Запускаем рассылку Completion...")
            stats = manager.send_immediate_campaign('completion')
            print(f"📊 Результат: {stats}")
        
        elif choice == '5':
            # Запуск планировщика каждые 5 минут
            template = input("Шаблон [universal_link]: ").strip() or "universal_link"
            
            print(f"⏰ Планировщик запущен: каждые 5 минут, шаблон: {template}")
            print("💡 Для остановки нажмите Ctrl+C")
            
            try:
                await manager.start_frequent_scheduler(5, template)
            except KeyboardInterrupt:
                print("\n🛑 Планировщик остановлен пользователем")
                manager.stop_scheduler()
        
        elif choice == '6':
            # Запуск планировщика с настройкой интервала
            try:
                interval = int(input("Интервал в минутах [5]: ").strip() or "5")
                template = input("Шаблон [universal_link]: ").strip() or "universal_link"
                
                print(f"⏰ Планировщик запущен: каждые {interval} минут, шаблон: {template}")
                print("💡 Для остановки нажмите Ctrl+C")
                
                await manager.start_frequent_scheduler(interval, template)
            except ValueError:
                print("❌ Неверный формат интервала")
            except KeyboardInterrupt:
                print("\n🛑 Планировщик остановлен пользователем")
                manager.stop_scheduler()
        
        elif choice == '7':
            # Статистика базы
            recipients = get_recipients_from_db()
            print(f"📊 Получателей для рассылки: {len(recipients)}")
            if recipients:
                print("👥 Примеры:")
                for i, recipient in enumerate(recipients[:3], 1):
                    print(f"  {i}. {recipient['first_name']} {recipient['last_name']} <{recipient['email']}>")
                    print(f"     Ссылка: {recipient.get('universal_link', 'нет')}")
                    print(f"     Статус: {recipient.get('status', 'нет')}")
                    print(f"     Последняя отправка: {recipient.get('mailing_date', 'никогда')}")
        
        elif choice == '8':
            # Остановка планировщика
            manager.stop_scheduler()
            print("🛑 Планировщик остановлен")
        
        elif choice == '0':
            # Выход
            manager.stop_scheduler()
            print("👋 До свидания!")
            break
        
        else:
            print("⚠️ Неверный выбор")
        
        input("\nНажмите Enter для продолжения...")

async def automated_mode():
    """Автоматический режим (для продакшена)"""
    manager = MailServiceManager()
    
    if not manager.initialize():
        logger.error("Не удалось инициализировать сервис")
        return
    
    # Тестируем соединение
    if not manager.test_connection():
        logger.error("SMTP соединение не работает")
        return
    
    logger.info("🚀 Запускаем автоматическую рассылку...")
    
    # Запускаем планировщик каждые 5 минут
    try:
        await manager.start_frequent_scheduler(5, "universal_link")
    except KeyboardInterrupt:
        logger.info("Планировщик остановлен")
    except Exception as e:
        logger.error(f"Ошибка в автоматическом режиме: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Система рассылки Новогоднего Квеста')
    parser.add_argument('--auto', action='store_true', 
                       help='Автоматический режим (для продакшена)')
    parser.add_argument('--test', action='store_true', 
                       help='Тестовый режим (отправка тестового письма)')
    parser.add_argument('--immediate', action='store_true',
                       help='Немедленная рассылка')
    parser.add_argument('--template', default='universal_link',
                       help='Шаблон для рассылки (universal_link/completion)')
    parser.add_argument('--interval', type=int, default=5,
                       help='Интервал планировщика в минутах')
    
    args = parser.parse_args()
    
    if args.auto:
        # Автоматический режим
        asyncio.run(automated_mode())
    elif args.test:
        # Тестовый режим
        manager = MailServiceManager()
        if manager.initialize():
            test_email = input("Введите email для теста: ")
            manager.send_test_email(test_email)
    elif args.immediate:
        # Немедленная рассылка
        manager = MailServiceManager()
        if manager.initialize():
            stats = manager.send_immediate_campaign(args.template)
            print(f"Результат: {stats}")
    else:
        # Интерактивный режим
        asyncio.run(interactive_mode())
