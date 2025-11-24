#!src/mail_service/check_system.py
"""
Проверка системы рассылки
"""

import os
import sys

def get_db_path():
    """Возвращает путь к базе данных runners.db в папке src"""
    current_dir = os.path.dirname(__file__) if __file__ else os.getcwd()
    # Поднимаемся на один уровень: mail_service -> src
    parent_dir = os.path.dirname(current_dir)  # src
    return os.path.join(parent_dir, 'runners.db')

def get_env_path():
    """Возвращает путь к .env файлу в корневой директории"""
    current_dir = os.path.dirname(__file__) if __file__ else os.getcwd()
    # Поднимаемся на два уровня: mail_service -> src -> runner
    parent_dir = os.path.dirname(current_dir)  # src
    project_root = os.path.dirname(parent_dir)  # runner
    return os.path.join(project_root, '.env')

def check_system():
    print("🔍 Проверка системы рассылки...")
    
    # Текущая директория - mail_service/
    current_dir = os.path.dirname(__file__) if __file__ else os.getcwd()
    print(f"📁 Текущая директория: {current_dir}")
    
    # Проверка файлов в текущей папке
    required_files = [
        '__init__.py',
        'config.py', 
        'email_sender.py',
        'email_templates.py',
        'scheduler.py',
        'utils.py',
        'email_main.py'
    ]
    
    all_files_ok = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} - НЕ НАЙДЕН!")
            all_files_ok = False
    
    # Проверка .env (ищем в корневой директории проекта)
    env_path = get_env_path()
    
    print(f"🔍 Ищем .env по пути: {env_path}")
    
    if os.path.exists(env_path):
        print(f"✅ .env файл найден: {env_path}")
        
        # Читаем SMTP настройки
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                env_content = f.read()
            
            smtp_settings = {
                'SMTP_SERVER': 'SMTP_SERVER' in env_content,
                'SMTP_EMAIL': 'SMTP_EMAIL' in env_content,
                'SMTP_PASSWORD': 'SMTP_PASSWORD' in env_content
            }
            
            print("🔧 Проверка SMTP настроек в .env:")
            for setting, exists in smtp_settings.items():
                status = "✅" if exists else "❌"
                print(f"   {status} {setting}")
                
        except Exception as e:
            print(f"⚠️ Ошибка чтения .env: {e}")
            
    else:
        print(f"❌ .env файл не найден: {env_path}")
        all_files_ok = False
    
    # Проверка базы данных runners.db (ищем в папке src)
    db_path = get_db_path()
    
    print(f"🔍 Ищем базу данных по пути: {db_path}")
    
    if os.path.exists(db_path):
        print(f"✅ База данных найдена: {db_path}")
        
        # Проверяем таблицы в базе
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Получаем все таблицы
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"📋 Таблицы в базе: {', '.join(tables)}")
            
            # Ищем таблицу с участниками
            participant_tables = ['manual_upload', 'participants', 'users', 'runners']
            found_table = None
            
            for table in participant_tables:
                if table in tables:
                    found_table = table
                    print(f"✅ Найдена таблица участников: {table}")
                    
                    # Показываем структуру таблицы
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns_info = cursor.fetchall()
                    print(f"📊 Структура таблицы {table}:")
                    for col in columns_info:
                        print(f"   - {col[1]} ({col[2]})")
                    
                    # Считаем участников с email
                    if 'email' in [col[1] for col in columns_info]:
                        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE email IS NOT NULL AND email != ''")
                    elif 'user_email' in [col[1] for col in columns_info]:
                        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE user_email IS NOT NULL AND user_email != ''")
                    else:
                        print(f"⚠️ В таблице {table} нет колонки email")
                        continue
                    
                    count = cursor.fetchone()[0]
                    print(f"📧 Участников с email: {count}")
                    break
            
            if not found_table:
                print("❌ Не найдена таблица с участниками")
                all_files_ok = False
                
            conn.close()
            
        except Exception as e:
            print(f"⚠️ Ошибка проверки базы данных: {e}")
            all_files_ok = False
            
    else:
        print(f"❌ База данных не найдена: {db_path}")
        all_files_ok = False
    
    print("\n" + "="*50)
    if all_files_ok:
        print("🎉 Система готова к работе!")
        print("🚀 Запуск: python email_main.py")
    else:
        print("⚠️ Есть проблемы с настройкой системы")
    
    return all_files_ok

if __name__ == "__main__":
    check_system()
