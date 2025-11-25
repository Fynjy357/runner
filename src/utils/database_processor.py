import pandas as pd
import sqlite3
import logging
import os
from datetime import datetime

def fix_table_structure(db_path: str = 'runners.db'):
    """Исправляет структуру таблицы manual_upload"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем текущую структуру
        cursor.execute("PRAGMA table_info(manual_upload)")
        columns = cursor.fetchall()
        
        cursor.execute("PRAGMA index_list(manual_upload)")
        indexes = cursor.fetchall()
        
        print("\n📋 Текущая структура таблицы manual_upload:")
        for col in columns:
            print(f"  {col[1]} ({col[2]}) - PK: {col[5]}")
        
        print("\n📊 Текущие индексы таблицы manual_upload:")
        for idx in indexes:
            print(f"  Индекс: {idx[1]}, Уникальный: {idx[2]}")
        
        # Удаляем проблемный уникальный индекс если он существует
        for idx in indexes:
            if idx[1] == 'sqlite_autoindex_manual_upload_1' and idx[2] == 1:
                print(f"🗑️ Удаляем проблемный уникальный индекс: {idx[1]}")
                # В SQLite нельзя удалить автоматически созданные индексы напрямую
                # Нужно пересоздать таблицу
                break
        
        # Пересоздаем таблицу с правильной структурой
        print("🔄 Пересоздаем таблицу с правильной структурой...")
        
        # Создаем временную таблицу с данными
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS manual_upload_temp AS 
            SELECT * FROM manual_upload
        ''')
        
        # Удаляем старую таблицу
        cursor.execute('DROP TABLE IF EXISTS manual_upload')
        
        # Создаем новую таблицу с правильной структурой
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS manual_upload (
                participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                last_name TEXT NOT NULL,
                first_name TEXT NOT NULL,
                middle_name TEXT,
                email TEXT NOT NULL,
                phone INTEGER NOT NULL,
                stage_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (stage_id) REFERENCES stages(stage_id)
            )
        ''')
        
        # Создаем правильные индексы (не уникальные)
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_manual_upload_stage 
            ON manual_upload(stage_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_manual_upload_email 
            ON manual_upload(email)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_manual_upload_name 
            ON manual_upload(last_name, first_name)
        ''')
        
        # Восстанавливаем данные из временной таблицы
        cursor.execute('''
            INSERT INTO manual_upload 
            (last_name, first_name, middle_name, email, phone, stage_id)
            SELECT last_name, first_name, middle_name, email, phone, stage_id 
            FROM manual_upload_temp
        ''')
        
        # Удаляем временную таблицу
        cursor.execute('DROP TABLE IF EXISTS manual_upload_temp')
        
        conn.commit()
        conn.close()
        
        print("✅ Структура таблицы успешно исправлена")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка исправления структуры таблицы: {e}")
        logging.error(f"Ошибка исправления структуры таблицы: {e}")
        return False

def check_table_structure(db_path: str = 'runners.db'):
    """Проверяет структуру таблицы manual_upload"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Получаем информацию о таблице
        cursor.execute("PRAGMA table_info(manual_upload)")
        columns = cursor.fetchall()
        
        cursor.execute("PRAGMA index_list(manual_upload)")
        indexes = cursor.fetchall()
        
        print("\n📋 Структура таблицы manual_upload:")
        for col in columns:
            print(f"  {col[1]} ({col[2]}) - PK: {col[5]}")
        
        print("\n📊 Индексы таблицы manual_upload:")
        for idx in indexes:
            print(f"  Индекс: {idx[1]}, Уникальный: {idx[2]}")
            
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка проверки структуры таблицы: {e}")

def update_stages_table(db_path: str = 'runners.db'):
    """
    Обновляет таблицу stages с этапами забега
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Очищаем таблицу stages
        cursor.execute('DELETE FROM stages')
        
        # Вставляем этапы
        stages = [
            (1, 'ГЛАВА 1. «Предательство в Центральном штабе»'),
            (2, 'ГЛАВА 2. «Провал операции»'),
            (3, 'ГЛАВА 3. «Обратный отсчет»'),
            (4, 'ГЛАВА 4. «Последний рейс»'),
            (5, 'Пакет на 4 этапа «Тайна пропавшей коллекции. Полное погружение»')
        ]
        
        cursor.executemany('INSERT INTO stages (stage_id, stage_name) VALUES (?, ?)', stages)
        conn.commit()
        conn.close()
        
        print("✅ Таблица stages успешно обновлена")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка обновления таблицы stages: {e}")
        logging.error(f"Ошибка обновления таблицы stages: {e}")
        return False

def process_excel_to_database(excel_file_path: str, db_path: str = 'runners.db'):
    """
    Обрабатывает Excel файл и добавляет новые записи в таблицу manual_upload
    Не удаляет существующие данные, только добавляет новые
    """
    
    # Расширенный словарь для преобразования дистанции в stage_id
    distance_mapping = {
        'ГЛАВА 1. «Предательство в Центральном штабе»': 1,
        'ГЛАВА 1.  «Предательство в Центральном штабе»': 1,
        'ГЛАВА 2. «Провал операции»': 2,
        'ГЛАВА 3. «Обратный отсчет»': 3,
        'ГЛАВА 4. «Последний рейс»': 4,
        'Пакет на 4 этапа «Тайна пропавшей коллекции. Полное погружение»': 5,
        'Пакет на 4 этапа «Тайна пропавшей коллекции. Полное погружение» ': 5,
    }
    
    try:
        # Проверяем существование файла
        if not os.path.exists(excel_file_path):
            logging.error(f"Файл не найден: {excel_file_path}")
            return False
        
        print(f"📖 Читаем файл: {excel_file_path}")
        
        # Читаем Excel файл с указанием движка
        try:
            # Пробуем прочитать как .xls с помощью xlrd
            df = pd.read_excel(excel_file_path, engine='xlrd')
        except Exception as e:
            print(f"⚠️ Не удалось прочитать как .xls: {e}")
            # Пробуем прочитать как .xlsx
            try:
                df = pd.read_excel(excel_file_path, engine='openpyxl')
            except Exception as e2:
                print(f"❌ Не удалось прочитать файл: {e2}")
                return False
        
        print(f"📊 Найдено строк: {len(df)}")
        print(f"📋 Столбцы: {list(df.columns)}")
        
        # Проверяем наличие необходимых столбцов
        required_columns = ['дистанция', 'Фамилия', 'Имя', 'отчество', 'электронная почта', 'Мобильный телефон']
        
        # Ищем подходящие столбцы (с учетом возможных вариаций)
        column_mapping = {}
        available_columns = list(df.columns)
        
        for req_col in required_columns:
            # Ищем точное совпадение
            if req_col in available_columns:
                column_mapping[req_col] = req_col
            else:
                # Ищем частичное совпадение
                found = False
                for avail_col in available_columns:
                    if req_col.lower() in avail_col.lower() or avail_col.lower() in req_col.lower():
                        column_mapping[req_col] = avail_col
                        found = True
                        print(f"🔍 Найден столбец '{avail_col}' для '{req_col}'")
                        break
                if not found:
                    logging.error(f"Не найден столбец: {req_col}")
                    print(f"❌ Не найден столбец: {req_col}")
                    print(f"📋 Доступные столбцы: {available_columns}")
                    return False
        
        # Подключаемся к базе данных
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Получаем количество записей до обновления
        cursor.execute("SELECT COUNT(*) FROM manual_upload")
        count_before = cursor.fetchone()[0]
        print(f"📊 Записей в базе до обновления: {count_before}")
        
        # Обрабатываем каждую строку
        new_count = 0
        skipped_count = 0
        error_count = 0
        
        for index, row in df.iterrows():
            try:
                # Извлекаем данные из строки с использованием mapping
                distance_col = column_mapping['дистанция']
                last_name_col = column_mapping['Фамилия']
                first_name_col = column_mapping['Имя']
                middle_name_col = column_mapping['отчество']
                email_col = column_mapping['электронная почта']
                phone_col = column_mapping['Мобильный телефон']
                
                distance = str(row[distance_col]).strip() if pd.notna(row[distance_col]) else ''
                last_name = str(row[last_name_col]).strip() if pd.notna(row[last_name_col]) else ''
                first_name = str(row[first_name_col]).strip() if pd.notna(row[first_name_col]) else ''
                middle_name = str(row[middle_name_col]).strip() if pd.notna(row[middle_name_col]) else ''
                email = str(row[email_col]).strip() if pd.notna(row[email_col]) else ''
                phone_str = str(row[phone_col]).strip() if pd.notna(row[phone_col]) else ''
                
                # Пропускаем строки с пустыми обязательными полями
                if not last_name or not first_name or not email or not phone_str:
                    if index < 10:
                        print(f"⚠️ Строка {index+1}: пропущены обязательные поля")
                    error_count += 1
                    continue
                
                # Преобразуем дистанцию в stage_id
                stage_id = distance_mapping.get(distance)
                if not stage_id:
                    # Пробуем найти частичное совпадение
                    for key, value in distance_mapping.items():
                        if key.strip() in distance or distance in key.strip():
                            stage_id = value
                            break
                
                if not stage_id:
                    if index < 10:
                        print(f"⚠️ Строка {index+1}: неизвестная дистанция '{distance}'")
                    error_count += 1
                    continue
                
                # Обрабатываем телефон (убираем все нецифровые символы)
                phone_clean = ''.join(filter(str.isdigit, phone_str))
                if not phone_clean:
                    if index < 10:
                        print(f"⚠️ Строка {index+1}: некорректный телефон '{phone_str}'")
                    error_count += 1
                    continue
                
                # Преобразуем телефон в число
                try:
                    phone = int(phone_clean)
                except ValueError:
                    if index < 10:
                        print(f"⚠️ Строка {index+1}: телефон не может быть преобразован в число '{phone_clean}'")
                    error_count += 1
                    continue
                
                # Проверяем, существует ли уже такая запись (только по комбинации ФИО+email+phone+stage)
                cursor.execute('''
                    SELECT participant_id FROM manual_upload 
                    WHERE last_name = ? AND first_name = ? AND email = ? AND phone = ? AND stage_id = ?
                ''', (last_name, first_name, email, phone, stage_id))
                
                existing_record = cursor.fetchone()
                
                if existing_record:
                    # Запись уже существует - пропускаем
                    skipped_count += 1
                    if skipped_count <= 10:
                        print(f"⏭️ Строка {index+1}: запись уже существует - пропускаем")
                    continue
                
                # Вставляем новую запись
                cursor.execute('''
                    INSERT INTO manual_upload 
                    (last_name, first_name, middle_name, email, phone, stage_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (last_name, first_name, middle_name, email, phone, stage_id))
                
                new_count += 1
                
                if new_count <= 10 or new_count % 10 == 0:
                    print(f"✅ Строка {index+1}: добавлена новая запись - {last_name} {first_name} (этап {stage_id})")
                
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e):
                    # Дубликат по уникальному ключу
                    skipped_count += 1
                    if skipped_count <= 10:
                        print(f"⏭️ Строка {index+1}: дубликат по уникальному ключу: {e}")
                else:
                    if index < 10:
                        logging.error(f"Ошибка базы данных в строке {index+1}: {e}")
                error_count += 1
                continue
            except Exception as e:
                if index < 10:
                    logging.error(f"Ошибка обработки строки {index+1}: {e}")
                error_count += 1
                continue
        
        # Сохраняем изменения
        conn.commit()
        
        # Получаем количество записей после обновления
        cursor.execute("SELECT COUNT(*) FROM manual_upload")
        count_after = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"\n✅ Обработка завершена:")
        print(f"📊 Записей в базе до обновления: {count_before}")
        print(f"📊 Записей в базе после обновления: {count_after}")
        print(f"🆕 Добавлено новых записей: {new_count}")
        print(f"⏭️ Пропущено дубликатов: {skipped_count}")
        print(f"❌ Ошибок обработки: {error_count}")
        
        logging.info(f"Обработка завершена: новых - {new_count}, дубликатов - {skipped_count}, ошибок - {error_count}")
        
        # Показываем пример новых данных
        if new_count > 0:
            print("\n📋 Пример новых добавленных данных:")
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT m.last_name, m.first_name, m.middle_name, m.email, m.phone, s.stage_name 
                    FROM manual_upload m 
                    JOIN stages s ON m.stage_id = s.stage_id 
                    ORDER BY m.participant_id DESC
                    LIMIT 10
                ''')
                samples = cursor.fetchall()
                for sample in samples:
                    print(f"   {sample[0]} {sample[1]} {sample[2]} - {sample[3]} - {sample[4]} - {sample[5]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка обработки Excel файла: {e}")
        logging.error(f"Ошибка обработки Excel файла: {e}")
        return False

def process_participants_export():
    """
    Основная функция для обработки экспортированного файла участников
    """
    excel_file_path = "participants_export_current.xls"
    
    print(f"🔍 Ищем файл: {excel_file_path}")
    
    if not os.path.exists(excel_file_path):
        print(f"❌ Файл не найден: {excel_file_path}")
        return False
    
    print(f"✅ Файл найден: {excel_file_path}")
    
    # Исправляем структуру таблицы
    if not fix_table_structure():
        return False
    
    # Проверяем структуру таблицы
    check_table_structure()
    
    # Обновляем таблицу stages
    if not update_stages_table():
        return False
    
    # Обрабатываем Excel файл
    if not process_excel_to_database(excel_file_path):
        return False
    
    print("✅ Данные участников успешно обновлены в базе данных")
    logging.info("✅ Данные участников успешно обновлены в базе данных")
    return True

def update_participants_from_excel():
    """Алиас для обратной совместимости"""
    return process_participants_export()

# Если нужно запустить сразу при импорте
if __name__ == "__main__":
    process_participants_export()
