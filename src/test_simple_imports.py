# test_simple_imports.py
import sys
import os

# Добавляем путь к текущей директории
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🔍 Проверка импортов...")
print("=" * 60)

# 1. Проверяем импорт database
try:
    from database import db
    print("✅ database.db - УСПЕШНО")
    
    # Проверяем функции БД
    stats = db.get_promo_codes_stats()
    print(f"   Статистика: {stats}")
    
    # Проверяем доступные промокоды
    promo = db.get_available_promo_code()
    print(f"   Доступный промокод: '{promo}'")
    
except ImportError as e:
    print(f"❌ database.db - ОШИБКА: {e}")
except Exception as e:
    print(f"❌ Ошибка при работе с БД: {e}")

# 2. Проверяем импорт promo_manager
try:
    from promo.promo_manager import PromoCodeManager, promo_manager
    print("✅ promo.promo_manager - УСПЕШНО")
    
    # Проверяем создание экземпляра
    manager = PromoCodeManager()
    print("   Создание PromoCodeManager - УСПЕШНО")
    
    # Проверяем глобальный экземпляр
    if promo_manager:
        print("   Глобальный promo_manager - ДОСТУПЕН")
        
except ImportError as e:
    print(f"❌ promo.promo_manager - ОШИБКА: {e}")
except Exception as e:
    print(f"❌ Ошибка при работе с promo_manager: {e}")

# 3. Проверяем импорт promo_utils
try:
    from promo.promo_utils import (
        send_promo_code_to_user_async,
        get_promo_stats_formatted,
        get_user_promocodes,
        format_user_promocodes
    )
    print("✅ promo.promo_utils - УСПЕШНО")
    
    # Проверяем функции
    stats_formatted = get_promo_stats_formatted()
    print(f"   Форматированная статистика:\n{stats_formatted}")
    
except ImportError as e:
    print(f"❌ promo.promo_utils - ОШИБКА: {e}")
except Exception as e:
    print(f"❌ Ошибка при работе с promo_utils: {e}")

# 4. Проверяем структуру папки promo
print("\n🔍 Проверка структуры папки promo...")
promo_dir = os.path.join(os.path.dirname(__file__), "promo")
if os.path.exists(promo_dir):
    print(f"✅ Папка promo существует: {promo_dir}")
    
    files = os.listdir(promo_dir)
    print(f"   Файлы в папке promo:")
    for file in files:
        file_path = os.path.join(promo_dir, file)
        if os.path.isfile(file_path):
            size = os.path.getsize(file_path)
            print(f"     - {file} ({size} байт)")
else:
    print(f"❌ Папка promo не существует: {promo_dir}")

print("\n" + "=" * 60)
print("ПРОВЕРКА ЗАВЕРШЕНА")
print("=" * 60)
