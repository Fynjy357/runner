#!src/mail_service/utils.py
"""
Утилиты для работы с базой данных
"""

import sqlite3
import os
from typing import List, Dict, Any
from datetime import datetime, timedelta

def get_db_connection():
    """Получение соединения с базой данных"""
    current_dir = os.path.dirname(__file__)
    parent_dir = os.path.dirname(current_dir)  # src
    db_path = os.path.join(parent_dir, 'runners.db')
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"База данных не найдена: {db_path}")
    
    return sqlite3.connect(db_path)

def get_stage_name(stage_id: int) -> str:
    """Получение названия этапа из таблицы stages"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT stage_name FROM stages 
            WHERE stage_id = ?
        """, (stage_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return result[0]
        else:
            return f"Этап {stage_id}"
            
    except Exception as e:
        print(f"❌ Ошибка получения названия этапа {stage_id}: {e}")
        return f"Этап {stage_id}"

def create_telegram_link(token: str) -> str:
    """Создание полноценной ссылки Telegram бота из токена"""
    if not token:
        return "#"
    
    # Если уже ссылка - возвращаем как есть
    if token.startswith(('http://', 'https://', 't.me/')):
        return token
    
    # Получаем имя бота из переменных окружения
    bot_username = get_bot_username()
    
    if bot_username:
        # Убираем @ если есть
        clean_username = bot_username.replace('@', '')
        return f"https://t.me/{clean_username}?start={token}"
    else:
        # Если имя бота не найдено, используем общий формат
        return f"https://t.me/your_bot_name?start={token}"

def get_bot_username() -> str:
    """Получение имени бота из переменных окружения"""
    try:
        # Получаем путь к .env файлу в корне проекта
        current_dir = os.path.dirname(__file__)
        parent_dir = os.path.dirname(current_dir)  # src
        project_root = os.path.dirname(parent_dir)  # runner
        env_path = os.path.join(project_root, '.env')
        
        # Загружаем переменные из .env файла
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        if key.strip() == 'TELEGRAM_BOT_USERNAME':
                            return value.strip()
        
        # Или из переменных окружения
        return os.getenv('TELEGRAM_BOT_USERNAME', '')
        
    except Exception as e:
        print(f"❌ Ошибка получения имени бота: {e}")
        return ""

def get_recipients_from_db() -> List[Dict[str, Any]]:
    """Получение списка получателей из базы данных"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Получаем получателей, у которых:
        # - status = 1 (готовы к отправке)
        # - И mailing_date отсутствует ИЛИ прошло больше 20 часов с mailing_date
        cursor.execute("""
            SELECT 
                mu.participant_id,
                mu.last_name, 
                mu.first_name, 
                mu.middle_name, 
                mu.email, 
                mu.phone, 
                mu.stage_id,
                lg.universal_link,
                lg.status,
                lg.mailing_date
            FROM manual_upload mu
            LEFT JOIN link_generation lg ON mu.participant_id = lg.participant_id
            WHERE mu.email IS NOT NULL 
                AND mu.email != ''
                AND lg.status = 1
                AND lg.universal_link IS NOT NULL
                AND lg.universal_link != ''
                AND (
                    lg.mailing_date IS NULL 
                    OR datetime(lg.mailing_date) < datetime('now', '-20 hours')
                )
        """)
        
        recipients = []
        for row in cursor.fetchall():
            # Преобразуем токен в полноценную ссылку
            token = row['universal_link']
            telegram_link = create_telegram_link(token)
            
            # Получаем название этапа из таблицы stages
            stage_id = row['stage_id']
            stage_name = get_stage_name(stage_id)
            
            recipient = {
                'participant_id': row['participant_id'],
                'last_name': row['last_name'] or '',
                'first_name': row['first_name'] or '',
                'middle_name': row['middle_name'] or '',
                'email': row['email'],
                'phone': row['phone'],
                'stage_id': stage_id,
                'stage_name': stage_name,  # Добавляем название этапа
                'universal_link': telegram_link,  # Теперь это полноценная ссылка
                'token': token,  # Сохраняем оригинальный токен
                'status': row['status'],
                'mailing_date': row['mailing_date']
            }
            recipients.append(recipient)
        
        conn.close()
        print(f"📧 Найдено получателей для рассылки: {len(recipients)}")
        return recipients
        
    except Exception as e:
        print(f"❌ Ошибка получения получателей из БД: {e}")
        return []

def update_mailing_date(participant_id: int) -> bool:
    """Обновление даты отправки письма"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE link_generation 
            SET mailing_date = CURRENT_TIMESTAMP
            WHERE participant_id = ?
        """, (participant_id,))
        
        conn.commit()
        conn.close()
        print(f"✅ Дата отправки обновлена для participant_id {participant_id}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка обновления даты отправки: {e}")
        return False

def get_recipient_count() -> int:
    """Получение количества получателей"""
    recipients = get_recipients_from_db()
    return len(recipients)
