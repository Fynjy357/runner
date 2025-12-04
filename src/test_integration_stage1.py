# test_stage_1_promo.py
import asyncio
import sys
import os

# Добавляем путь к текущей директории
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db
from promo.promo_manager import promo_manager

# Создаем мок-объект для message
class MockMessage:
    def __init__(self, telegram_id, username):
        self.from_user = MockUser(telegram_id, username)
        self.chat = MockChat(telegram_id)
        self.bot = MockBot()
        
class MockUser:
    def __init__(self, telegram_id, username):
        self.id = telegram_id
        self.username = username
        self.first_name = username
        
class MockChat:
    def __init__(self, chat_id):
        self.id = chat_id
        
class MockBot:
    async def send_message(self, chat_id, text, parse_mode=None):
        print(f"📨 Бот отправил сообщение в чат {chat_id}:")
        print(f"   Текст: {text[:100]}...")
        return True

async def send_promo_code_to_user(message, telegram_id):
    """Упрощенная версия функции отправки промокода"""
    from promo.promo_utils import send_promo_code_to_user_async
    
    username = message.from_user.username or message.from_user.first_name
    
    print(f"🔍 Отправка промокода пользователю {telegram_id} (@{username})")
    
    result = await send_promo_code_to_user_async(
        telegram_id=telegram_id,
        username=username,
        bot=message.bot,
        chat_id=message.chat.id
    )
    
    return result

async def test_stage_1_promo_flow():
    """Тестирование полного цикла выдачи промокода в этапе 1"""
    print("🔍 Тестирование выдачи промокода в этапе 1...")
    
    # 1. Очищаем все промокоды
    print("\n1. Очищаем все промокоды...")
    db.delete_all_promo_codes()
    stats = db.get_promo_codes_stats()
    print(f"   Статистика после очистки: {stats}")
    
    # 2. Добавляем тестовые промокоды
    print("\n2. Добавляем тестовые промокоды...")
    promo_codes = ["STAGE1PROMO001", "STAGE1PROMO002", "STAGE1PROMO003"]
    added, skipped = db.add_promo_codes_batch(promo_codes)
    print(f"   Добавлено: {added}, Пропущено: {skipped}")
    
    # 3. Проверяем статистику
    stats = db.get_promo_codes_stats()
    print(f"   Статистика после добавления: {stats}")
    
    # 4. Создаем тестового пользователя в БД
    print("\n3. Создаем тестового пользователя...")
    telegram_id = 999999999  # Тестовый ID
    username = "test_user_stage1"
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO main 
                (telegram_id, telegram_username, role, current_stage, registration_date)
                VALUES (?, ?, 'user', 1, datetime('now'))
            ''', (telegram_id, username))
            conn.commit()
        print(f"   ✅ Тестовый пользователь создан: {telegram_id} (@{username})")
    except Exception as e:
        print(f"   ❌ Ошибка создания пользователя: {e}")
    
    # 5. Проверяем доступные промокоды
    print("\n4. Проверяем доступные промокоды...")
    available_promo = db.get_available_promo_code()
    print(f"   Доступный промокод: '{available_promo}'")
    
    # 6. Тестируем функцию отправки промокода через менеджер
    print("\n5. Тестируем функцию отправки промокода через менеджер...")
    result = promo_manager.send_promo_code_to_user(telegram_id, username)
    print(f"   Результат send_promo_code_to_user():")
    print(f"     Успех: {result.get('success')}")
    print(f"     Промокод: {result.get('promo_code')}")
    print(f"     Сообщение: {result.get('message')[:50]}...")
    
    # 7. Проверяем статистику после выдачи
    print("\n6. Проверяем статистику после выдачи...")
    stats = db.get_promo_codes_stats()
    print(f"   Статистика после выдачи: {stats}")
    
    # 8. Проверяем информацию о выданном промокоде
    print("\n7. Проверяем информацию о выданном промокоде...")
    if result.get('promo_code'):
        promo_info = db.get_promo_code_info(result['promo_code'])
        if promo_info:
            print(f"   Промокод: {promo_info['promo_code']}")
            print(f"   Статус: {promo_info['status']}")
            print(f"   Выдан пользователю: {promo_info['sent_to_telegram_id']}")
            print(f"   Имя пользователя: {promo_info['sent_to_username']}")
            print(f"   Время выдачи: {promo_info['sent_at']}")
        else:
            print("   ❌ Информация о промокоде не найдена")
    
    # 9. Проверяем промокоды пользователя
    print("\n8. Проверяем промокоды пользователя...")
    from promo.promo_utils import get_user_promocodes
    user_promos = get_user_promocodes(telegram_id)
    print(f"   У пользователя {len(user_promos)} промокодов:")
    for promo in user_promos:
        print(f"     - {promo['promo_code']} ({promo['status']}) - {promo['sent_at']}")
    
    # 10. Проверяем форматирование промокодов пользователя
    print("\n9. Проверяем форматирование промокодов пользователя...")
    from promo.promo_utils import format_user_promocodes
    formatted = format_user_promocodes(user_promos)
    print(f"   Форматированный вывод:\n{formatted[:200]}...")
    
    # 11. Тестируем функцию из stage_1.py
    print("\n10. Тестируем функцию send_promo_code_to_user из stage_1...")
    mock_message = MockMessage(telegram_id, username)
    success = await send_promo_code_to_user(mock_message, telegram_id)
    print(f"   Результат: {success}")
    
    print("\n🎉 Тестирование завершено!")

def test_direct_db_functions():
    """Прямое тестирование функций БД"""
    print("\n🔍 Прямое тестирование функций БД...")
    
    # 1. Проверяем все функции промокодов
    print("\n1. Проверяем все функции промокодов:")
    
    # get_available_promo_code
    promo = db.get_available_promo_code()
    print(f"   get_available_promo_code(): '{promo}'")
    
    # get_promo_codes_stats
    stats = db.get_promo_codes_stats()
    print(f"   get_promo_codes_stats(): {stats}")
    
    # get_all_promo_codes
    all_promos = db.get_all_promo_codes()
    print(f"   get_all_promo_codes(): {len(all_promos)} промокодов")
    
    # get_all_promo_codes с фильтром
    active_promos = db.get_all_promo_codes('active')
    print(f"   get_all_promo_codes('active'): {len(active_promos)} активных")
    
    used_promos = db.get_all_promo_codes('used')
    print(f"   get_all_promo_codes('used'): {len(used_promos)} использованных")
    
    # 2. Проверяем функцию mark_stage_completed
    print("\n2. Проверяем функцию mark_stage_completed:")
    telegram_id = 999999999
    
    # Сначала проверяем текущий статус
    stage_completed = db.is_stage_completed(telegram_id, 1)
    print(f"   is_stage_completed({telegram_id}, 1): {stage_completed}")
    
    # Отмечаем этап как завершенный
    success = db.mark_stage_completed(telegram_id, 1)
    print(f"   mark_stage_completed({telegram_id}, 1): {success}")
    
    # Проверяем снова
    stage_completed = db.is_stage_completed(telegram_id, 1)
    print(f"   is_stage_completed({telegram_id}, 1) после отметки: {stage_completed}")
    
    # 3. Проверяем функцию save_user_address
    print("\n3. Проверяем функцию save_user_address:")
    address = "г. Москва, ул. Тестовая, д. 1, ПВЗ СДЭК №999"
    success = db.save_user_address(telegram_id, "test_user_stage1", address, 1)
    print(f"   save_user_address({telegram_id}, ...): {success}")
    
    # Получаем адрес
    saved_address = db.get_user_address(telegram_id, 1)
    if saved_address:
        print(f"   get_user_address({telegram_id}, 1): {saved_address['address']}")
    else:
        print(f"   get_user_address({telegram_id}, 1): не найден")
    
    print("\n✅ Прямое тестирование завершено!")

if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ВЫДАЧИ ПРОМОКОДОВ В ЭТАПЕ 1")
    print("=" * 60)
    
    # Запускаем асинхронный тест
    asyncio.run(test_stage_1_promo_flow())
    
    # Запускаем прямое тестирование
    test_direct_db_functions()
    
    print("\n" + "=" * 60)
    print("ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
    print("=" * 60)
