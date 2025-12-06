import sqlite3
import logging
from datetime import datetime

class Database:
    def __init__(self, db_path: str = 'runners.db'):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Таблица 4: Этапы (создаем первой из-за внешних ключей)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS stages (
                        stage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stage_name TEXT NOT NULL UNIQUE
                    )
                ''')
                
                # Таблица 1: Ручная загрузка
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS manual_upload (
                        participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        last_name TEXT NOT NULL,
                        first_name TEXT NOT NULL,
                        middle_name TEXT,
                        email TEXT NOT NULL,
                        phone INTEGER NOT NULL,
                        stage_id INTEGER NOT NULL,
                        FOREIGN KEY (stage_id) REFERENCES stages(stage_id)
                    )
                ''')
                
                # Таблица 2: Формирование ссылки
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS link_generation (
                        participant_id INTEGER PRIMARY KEY,
                        universal_link TEXT NOT NULL UNIQUE,
                        status INTEGER DEFAULT 0 CHECK(status IN (0, 1)),
                        creation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        mailing_date DATETIME,
                        link_click_date DATETIME,
                        FOREIGN KEY (participant_id) REFERENCES manual_upload(participant_id)
                    )
                ''')
                
                # Таблица 3: Основная - ДОБАВЛЯЕМ current_stage И ПОЛЯ ДЛЯ ОТСЛЕЖИВАНИЯ ЗАВЕРШЕНИЯ ЭТАПОВ
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS main (
                        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        participant_id INTEGER UNIQUE,
                        telegram_id INTEGER UNIQUE,
                        telegram_username TEXT,
                        role TEXT NOT NULL CHECK(role IN ('admin', 'moderator', 'user')),
                        quest_started INTEGER DEFAULT 0 CHECK(quest_started IN (0, 1)),
                        quest_started_at DATETIME,
                        current_stage INTEGER DEFAULT 1,
                        stage_1_completed INTEGER DEFAULT 0 CHECK(stage_1_completed IN (0, 1)),
                        stage_2_completed INTEGER DEFAULT 0 CHECK(stage_2_completed IN (0, 1)),
                        stage_3_completed INTEGER DEFAULT 0 CHECK(stage_3_completed IN (0, 1)),
                        stage_4_completed INTEGER DEFAULT 0 CHECK(stage_4_completed IN (0, 1)),
                        registration_date DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Таблица 5: Суть этапа
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS stage_content (
                        stage_id INTEGER NOT NULL,
                        message_id INTEGER NOT NULL,
                        order_number INTEGER NOT NULL,
                        message_text TEXT,
                        has_image INTEGER DEFAULT 0 CHECK(has_image IN (0, 1)),
                        image_url TEXT,
                        has_video INTEGER DEFAULT 0 CHECK(has_video IN (0, 1)),
                        video_url TEXT,
                        has_feedback INTEGER DEFAULT 0 CHECK(has_feedback IN (0, 1)),
                        puzzle_check TEXT,
                        PRIMARY KEY (stage_id, message_id),
                        FOREIGN KEY (stage_id) REFERENCES stages(stage_id)
                    )
                ''')
                
                # Таблица 6: Данные пользователя (обновленная структура)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_data (
                        data_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        quest_started INTEGER DEFAULT 0 CHECK(quest_started IN (0, 1)),
                        image_url TEXT,
                        answer_text TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES main(user_id)
                    )
                ''')
                
                # Таблица 7: Проверка
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS verification (
                        user_id INTEGER PRIMARY KEY,
                        distance INTEGER NOT NULL,
                        run_date DATE NOT NULL,
                        answer_check INTEGER DEFAULT 0 CHECK(answer_check IN (0, 1)),
                        FOREIGN KEY (user_id) REFERENCES main(user_id)
                    )
                ''')
                
                # Таблица 8: Участники розыгрыша
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS raffle_participants (
                        raffle_participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id INTEGER NOT NULL,
                        telegram_username TEXT,
                        participation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        raffle_id INTEGER,
                        FOREIGN KEY (telegram_id) REFERENCES main(telegram_id),
                        UNIQUE(telegram_id, raffle_id)
                    )
                ''')
                
                # ✅ ТАБЛИЦА 9: Адреса пользователей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_addresses (
                        address_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id INTEGER NOT NULL,
                        telegram_username TEXT,
                        stage INTEGER NOT NULL DEFAULT 1,
                        address TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (telegram_id) REFERENCES main(telegram_id),
                        UNIQUE(telegram_id, stage)
                    )
                ''')
                
                # ✅ ТАБЛИЦА 10: Промокоды
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS promo_codes (
                        promo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        promo_code TEXT NOT NULL UNIQUE,
                        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'used', 'expired')),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        sent_at DATETIME,
                        sent_to_telegram_id INTEGER,
                        sent_to_username TEXT,
                        FOREIGN KEY (sent_to_telegram_id) REFERENCES main(telegram_id)
                    )
                ''')
                
                # Создание индексов
                self._create_indexes(cursor)
                
                conn.commit()
                logging.info("База данных успешно инициализирована")
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка инициализации базы данных: {e}")

    def _create_indexes(self, cursor):
        """Создание индексов для оптимизации"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_manual_upload_email ON manual_upload(email)",
            "CREATE INDEX IF NOT EXISTS idx_manual_upload_stage ON manual_upload(stage_id)",
            "CREATE INDEX IF NOT EXISTS idx_link_generation_status ON link_generation(status)",
            "CREATE INDEX IF NOT EXISTS idx_main_telegram_id ON main(telegram_id)",
            "CREATE INDEX IF NOT EXISTS idx_main_role ON main(role)",
            "CREATE INDEX IF NOT EXISTS idx_main_current_stage ON main(current_stage)", 
            "CREATE INDEX IF NOT EXISTS idx_main_stage_1_completed ON main(stage_1_completed)",
            "CREATE INDEX IF NOT EXISTS idx_main_stage_2_completed ON main(stage_2_completed)",
            "CREATE INDEX IF NOT EXISTS idx_main_stage_3_completed ON main(stage_3_completed)",
            "CREATE INDEX IF NOT EXISTS idx_main_stage_4_completed ON main(stage_4_completed)",
            "CREATE INDEX IF NOT EXISTS idx_stage_content_stage ON stage_content(stage_id)",
            "CREATE INDEX IF NOT EXISTS idx_stage_content_order ON stage_content(order_number)",
            "CREATE INDEX IF NOT EXISTS idx_user_data_user ON user_data(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_data_quest ON user_data(quest_started)",
            "CREATE INDEX IF NOT EXISTS idx_verification_date ON verification(run_date)",
            "CREATE INDEX IF NOT EXISTS idx_raffle_participants_telegram ON raffle_participants(telegram_id)",
            "CREATE INDEX IF NOT EXISTS idx_raffle_participants_date ON raffle_participants(participation_date)",
            "CREATE INDEX IF NOT EXISTS idx_raffle_participants_raffle ON raffle_participants(raffle_id)",
            # ✅ ИНДЕКСЫ ДЛЯ ТАБЛИЦЫ АДРЕСОВ
            "CREATE INDEX IF NOT EXISTS idx_user_addresses_telegram ON user_addresses(telegram_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_addresses_stage ON user_addresses(stage)",
            # ✅ ИНДЕКСЫ ДЛЯ ТАБЛИЦЫ ПРОМОКОДОВ
            "CREATE INDEX IF NOT EXISTS idx_promo_codes_code ON promo_codes(promo_code)",
            "CREATE INDEX IF NOT EXISTS idx_promo_codes_status ON promo_codes(status)",
            "CREATE INDEX IF NOT EXISTS idx_promo_codes_sent_to ON promo_codes(sent_to_telegram_id)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)

    # ✅ МЕТОДЫ ДЛЯ РАБОТЫ С ПРОМОКОДАМИ

    def add_promo_code(self, promo_code: str) -> bool:
        """Добавление нового промокода"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO promo_codes (promo_code, status)
                    VALUES (?, 'active')
                ''', (promo_code.strip().upper(),))
                
                conn.commit()
                logging.info(f"Промокод добавлен: {promo_code}")
                return True
                
        except sqlite3.IntegrityError:
            logging.warning(f"Промокод уже существует: {promo_code}")
            return False
        except sqlite3.Error as e:
            logging.error(f"Ошибка добавления промокода {promo_code}: {e}")
            return False

    def add_promo_codes_batch(self, promo_codes: list) -> tuple:
        """Добавление нескольких промокодов"""
        added = 0
        skipped = 0
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for promo_code in promo_codes:
                    code = promo_code.strip()
                    if not code:
                        continue
                        
                    try:
                        cursor.execute('''
                            INSERT INTO promo_codes (promo_code, status)
                            VALUES (?, 'active')
                        ''', (code,))
                        added += 1
                    except sqlite3.IntegrityError:
                        skipped += 1
                        logging.debug(f"Промокод уже существует: {code}")
                
                conn.commit()
                logging.info(f"Добавлено промокодов: {added}, пропущено (дубликаты): {skipped}")
                return added, skipped
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка пакетного добавления промокодов: {e}")
            return 0, 0

    def get_available_promo_code(self) -> str:
        """Получение доступного промокода"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # ✅ ИСПРАВЛЕНИЕ: Правильная проверка NULL в SQLite
                cursor.execute('''
                    SELECT promo_code FROM promo_codes 
                    WHERE status = 'active' 
                    AND sent_to_telegram_id IS NULL
                    ORDER BY promo_id 
                    LIMIT 1
                ''')
                
                result = cursor.fetchone()
                return result[0] if result else None
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка получения доступного промокода: {e}")
            return None


    def mark_promo_code_as_used(self, promo_code: str, telegram_id: int = None, username: str = None) -> bool:
        """Отметка промокода как использованного"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # ✅ ИСПРАВЛЕНИЕ: Убираем .upper() - ищем как есть
                cursor.execute('''
                    UPDATE promo_codes 
                    SET status = 'used', 
                        sent_at = CURRENT_TIMESTAMP,
                        sent_to_telegram_id = ?,
                        sent_to_username = ?
                    WHERE promo_code = ? 
                    AND status = 'active'
                    AND sent_to_telegram_id IS NULL
                ''', (telegram_id, username, promo_code.strip()))  # ✅ Убрали .upper()
                
                conn.commit()
                if cursor.rowcount > 0:
                    logging.info(f"Промокод {promo_code} отмечен как использованный (пользователь: {telegram_id})")
                    return True
                else:
                    # ✅ ДОБАВЛЯЕМ ОТЛАДКУ: Проверяем почему не обновилось
                    cursor.execute('''
                        SELECT promo_code, status, sent_to_telegram_id 
                        FROM promo_codes 
                        WHERE promo_code = ?
                    ''', (promo_code.strip(),))  # ✅ Убрали .upper()
                    result = cursor.fetchone()
                    if result:
                        logging.warning(f"Промокод в базе: код='{result[0]}', статус='{result[1]}', выдан='{result[2]}'")
                        logging.warning(f"Искали промокод: '{promo_code.strip()}'")
                    else:
                        logging.warning(f"Промокод '{promo_code}' не найден в базе")
                    return False
                    
        except sqlite3.Error as e:
            logging.error(f"Ошибка отметки промокода как использованного: {e}")
            return False



    def get_promo_code_info(self, promo_code: str) -> dict:
        """Получение информации о промокоде"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT promo_id, promo_code, status, created_at, sent_at, 
                           sent_to_telegram_id, sent_to_username
                    FROM promo_codes 
                    WHERE promo_code = ?
                ''', (promo_code.strip(),))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'promo_id': result[0],
                        'promo_code': result[1],
                        'status': result[2],
                        'created_at': result[3],
                        'sent_at': result[4],
                        'sent_to_telegram_id': result[5],
                        'sent_to_username': result[6]
                    }
                return None
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка получения информации о промокоде: {e}")
            return None

    def get_promo_codes_stats(self) -> dict:
        """Получение статистики по промокодам"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                        SUM(CASE WHEN status = 'used' THEN 1 ELSE 0 END) as used,
                        SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END) as expired
                    FROM promo_codes
                ''')
                
                result = cursor.fetchone()
                return {
                    'total': result[0],
                    'active': result[1],
                    'used': result[2],
                    'expired': result[3]
                }
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка получения статистики промокодов: {e}")
            return {'total': 0, 'active': 0, 'used': 0, 'expired': 0}

    def get_all_promo_codes(self, status: str = None) -> list:
        """Получение всех промокодов"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if status:
                    cursor.execute('''
                        SELECT promo_id, promo_code, status, created_at, sent_at, 
                               sent_to_telegram_id, sent_to_username
                        FROM promo_codes 
                        WHERE status = ?
                        ORDER BY created_at DESC
                    ''', (status,))
                else:
                    cursor.execute('''
                        SELECT promo_id, promo_code, status, created_at, sent_at, 
                               sent_to_telegram_id, sent_to_username
                        FROM promo_codes 
                        ORDER BY created_at DESC
                    ''')
                
                results = cursor.fetchall()
                promo_codes = []
                for result in results:
                    promo_codes.append({
                        'promo_id': result[0],
                        'promo_code': result[1],
                        'status': result[2],
                        'created_at': result[3],
                        'sent_at': result[4],
                        'sent_to_telegram_id': result[5],
                        'sent_to_username': result[6]
                    })
                return promo_codes
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка получения всех промокодов: {e}")
            return []

    def delete_promo_code(self, promo_code: str) -> bool:
        """Удаление промокода"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # ✅ ИСПРАВЛЕНИЕ: Используем UPPER() для сравнения без учета регистра
                cursor.execute('''
                    DELETE FROM promo_codes 
                    WHERE UPPER(promo_code) = UPPER(?)
                ''', (promo_code.strip(),))
                
                conn.commit()
                if cursor.rowcount > 0:
                    logging.info(f"Промокод {promo_code} удален")
                    return True
                else:
                    logging.warning(f"Промокод {promo_code} не найден")
                    return False
                    
        except sqlite3.Error as e:
            logging.error(f"Ошибка удаления промокода: {e}")
            return False


    def delete_all_promo_codes(self) -> bool:
        """Удаление всех промокодов"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM promo_codes')
                conn.commit()
                logging.info("Все промокоды удалены")
                return True
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка удаления всех промокодов: {e}")
            return False

    def export_promo_codes_to_csv(self, status: str = None) -> str:
        """Экспорт промокодов в CSV"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if status:
                    cursor.execute('''
                        SELECT promo_code, status, created_at, sent_at, 
                               sent_to_telegram_id, sent_to_username
                        FROM promo_codes 
                        WHERE status = ?
                        ORDER BY created_at DESC
                    ''', (status,))
                else:
                    cursor.execute('''
                        SELECT promo_code, status, created_at, sent_at, 
                               sent_to_telegram_id, sent_to_username
                        FROM promo_codes 
                        ORDER BY created_at DESC
                    ''')
                
                results = cursor.fetchall()
                
                if not results:
                    return "Нет данных для экспорта"
                
                # Заголовки CSV
                csv_data = "promo_code;status;created_at;sent_at;sent_to_telegram_id;sent_to_username\n"
                
                for result in results:
                    promo_code, status, created_at, sent_at, sent_to_telegram_id, sent_to_username = result
                    csv_data += f"{promo_code};{status};{created_at or ''};{sent_at or ''};{sent_to_telegram_id or ''};{sent_to_username or ''}\n"
                
                return csv_data
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка экспорта промокодов в CSV: {e}")
            return f"Ошибка экспорта: {e}"

    # ✅ МЕТОДЫ ДЛЯ РАБОТЫ С ЗАВЕРШЕНИЕМ ЭТАПОВ

    def mark_stage_completed(self, telegram_id: int, stage_number: int) -> bool:
        """Отмечает этап как завершенный"""
        try:
            if stage_number not in [1, 2, 3, 4]:
                logging.error(f"Некорректный номер этапа: {stage_number}")
                return False
                
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                column_name = f"stage_{stage_number}_completed"
                cursor.execute(f'''
                    UPDATE main 
                    SET {column_name} = 1 
                    WHERE telegram_id = ?
                ''', (telegram_id,))
                
                conn.commit()
                if cursor.rowcount > 0:
                    logging.info(f"Этап {stage_number} отмечен как завершенный для пользователя {telegram_id}")
                    return True
                else:
                    logging.warning(f"Пользователь {telegram_id} не найден")
                    return False
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка отметки завершения этапа {stage_number} для пользователя {telegram_id}: {e}")
            return False

    def is_stage_completed(self, telegram_id: int, stage_number: int) -> bool:
        """Проверяет, завершен ли этап"""
        try:
            if stage_number not in [1, 2, 3, 4]:
                logging.error(f"Некорректный номер этапа: {stage_number}")
                return False
                
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                column_name = f"stage_{stage_number}_completed"
                cursor.execute(f'''
                    SELECT {column_name} FROM main 
                    WHERE telegram_id = ?
                ''', (telegram_id,))
                
                result = cursor.fetchone()
                if result:
                    return result[0] == 1
                return False
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка проверки завершения этапа {stage_number} для пользователя {telegram_id}: {e}")
            return False

    def get_completed_stages(self, telegram_id: int) -> list:
        """Получает список завершенных этапов"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT stage_1_completed, stage_2_completed, stage_3_completed, stage_4_completed
                    FROM main 
                    WHERE telegram_id = ?
                ''', (telegram_id,))
                
                result = cursor.fetchone()
                if result:
                    completed_stages = []
                    for i, completed in enumerate(result, start=1):
                        if completed == 1:
                            completed_stages.append(i)
                    return completed_stages
                return []
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка получения завершенных этапов для пользователя {telegram_id}: {e}")
            return []

    def reset_stage_completion(self, telegram_id: int, stage_number: int = None) -> bool:
        """Сбрасывает отметку о завершении этапа"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if stage_number:
                    if stage_number not in [1, 2, 3, 4]:
                        logging.error(f"Некорректный номер этапа: {stage_number}")
                        return False
                    
                    column_name = f"stage_{stage_number}_completed"
                    cursor.execute(f'''
                        UPDATE main 
                        SET {column_name} = 0 
                        WHERE telegram_id = ?
                    ''', (telegram_id,))
                else:
                    # Сбрасываем все этапы
                    cursor.execute('''
                        UPDATE main 
                        SET stage_1_completed = 0,
                            stage_2_completed = 0,
                            stage_3_completed = 0,
                            stage_4_completed = 0
                        WHERE telegram_id = ?
                    ''', (telegram_id,))
                
                conn.commit()
                if cursor.rowcount > 0:
                    if stage_number:
                        logging.info(f"Завершение этапа {stage_number} сброшено для пользователя {telegram_id}")
                    else:
                        logging.info(f"Все завершения этапов сброшены для пользователя {telegram_id}")
                    return True
                else:
                    logging.warning(f"Пользователь {telegram_id} не найден")
                    return False
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка сброса завершения этапа для пользователя {telegram_id}: {e}")
            return False

    # ✅ МЕТОДЫ ДЛЯ РАБОТЫ С АДРЕСАМИ ПОЛЬЗОВАТЕЛЕЙ

    def save_user_address(self, telegram_id: int, telegram_username: str, address: str, stage: int = 1) -> bool:
        """Сохранение или обновление адреса пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO user_addresses 
                    (telegram_id, telegram_username, stage, address, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (telegram_id, telegram_username, stage, address))
                
                conn.commit()
                logging.info(f"Адрес сохранен для пользователя {telegram_id} (этап {stage})")
                return True
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка сохранения адреса пользователя {telegram_id}: {e}")
            return False

    def get_user_address(self, telegram_id: int, stage: int = None):
        """Получение адреса пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if stage:
                    cursor.execute('''
                        SELECT address_id, telegram_id, telegram_username, stage, address, created_at, updated_at
                        FROM user_addresses 
                        WHERE telegram_id = ? AND stage = ?
                    ''', (telegram_id, stage))
                else:
                    cursor.execute('''
                        SELECT address_id, telegram_id, telegram_username, stage, address, created_at, updated_at
                        FROM user_addresses 
                        WHERE telegram_id = ?
                        ORDER BY stage DESC
                        LIMIT 1
                    ''', (telegram_id,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'address_id': result[0],
                        'telegram_id': result[1],
                        'telegram_username': result[2],
                        'stage': result[3],
                        'address': result[4],
                        'created_at': result[5],
                        'updated_at': result[6]
                    }
                return None
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка получения адреса пользователя {telegram_id}: {e}")
            return None

    def update_user_address(self, telegram_id: int, address: str, stage: int = 1) -> bool:
        """Обновление адреса пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE user_addresses 
                    SET address = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE telegram_id = ? AND stage = ?
                ''', (address, telegram_id, stage))
                
                conn.commit()
                if cursor.rowcount > 0:
                    logging.info(f"Адрес обновлен для пользователя {telegram_id} (этап {stage})")
                    return True
                else:
                    logging.warning(f"Адрес не найден для обновления: пользователь {telegram_id}, этап {stage}")
                    return False
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка обновления адреса пользователя {telegram_id}: {e}")
            return False

    def delete_user_address(self, telegram_id: int, stage: int = None) -> bool:
        """Удаление адреса пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if stage:
                    cursor.execute('''
                        DELETE FROM user_addresses 
                        WHERE telegram_id = ? AND stage = ?
                    ''', (telegram_id, stage))
                else:
                    cursor.execute('''
                        DELETE FROM user_addresses 
                        WHERE telegram_id = ?
                    ''', (telegram_id,))
                
                conn.commit()
                logging.info(f"Адрес(а) удален(ы) для пользователя {telegram_id}")
                return True
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка удаления адреса пользователя {telegram_id}: {e}")
            return False

    def export_addresses_to_csv(self, stage: int = None):
        """Экспорт адресов в CSV-формат (возвращает строку)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if stage:
                    cursor.execute('''
                        SELECT telegram_id, telegram_username, stage, address, created_at
                        FROM user_addresses 
                        WHERE stage = ?
                        ORDER BY created_at DESC
                    ''', (stage,))
                else:
                    cursor.execute('''
                        SELECT telegram_id, telegram_username, stage, address, created_at
                        FROM user_addresses 
                        ORDER BY stage, created_at DESC
                    ''')
                
                results = cursor.fetchall()
                
                if not results:
                    return "Нет данных для экспорта"
                
                # Заголовки CSV
                csv_data = "telegram_id;telegram_username;stage;address;created_at\n"
                
                for result in results:
                    telegram_id, telegram_username, stage, address, created_at = result
                    csv_data += f"{telegram_id};{telegram_username or ''};{stage};{address};{created_at}\n"
                
                return csv_data
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка экспорта адресов в CSV: {e}")
            return f"Ошибка экспорта: {e}"

    # МЕТОДЫ ДЛЯ РАБОТЫ С РОЗЫГРЫШЕМ

    def add_raffle_participant(self, telegram_id: int, telegram_username: str = None, raffle_id: int = None) -> bool:
        """Добавление участника в розыгрыш"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO raffle_participants 
                    (telegram_id, telegram_username, raffle_id) 
                    VALUES (?, ?, ?)
                ''', (telegram_id, telegram_username, raffle_id))
                
                conn.commit()
                logging.info(f"Участник {telegram_id} добавлен в розыгрыш {raffle_id}")
                return True
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка добавления участника розыгрыша: {e}")
            return False

    def is_user_participating_in_raffle(self, telegram_id: int, raffle_id: int = None) -> bool:
        """Проверка, участвует ли пользователь в розыгрыше"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if raffle_id:
                    cursor.execute('''
                        SELECT COUNT(*) FROM raffle_participants 
                        WHERE telegram_id = ? AND raffle_id = ?
                    ''', (telegram_id, raffle_id))
                else:
                    cursor.execute('''
                        SELECT COUNT(*) FROM raffle_participants 
                        WHERE telegram_id = ?
                    ''', (telegram_id,))
                
                count = cursor.fetchone()[0]
                return count > 0
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка проверки участия в розыгрыше: {e}")
            return False

    def get_raffle_participants(self, raffle_id: int = None) -> list:
        """Получение списка участников розыгрыша"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if raffle_id:
                    cursor.execute('''
                        SELECT telegram_id, telegram_username, participation_date, raffle_id
                        FROM raffle_participants 
                        WHERE raffle_id = ?
                        ORDER BY participation_date
                    ''', (raffle_id,))
                else:
                    cursor.execute('''
                        SELECT telegram_id, telegram_username, participation_date, raffle_id
                        FROM raffle_participants 
                        ORDER BY participation_date
                    ''')
                
                participants = cursor.fetchall()
                return participants
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка получения участников розыгрыша: {e}")
            return []

    def get_raffle_participants_count(self, raffle_id: int = None) -> int:
        """Получение количества участников розыгрыша"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if raffle_id:
                    cursor.execute('''
                        SELECT COUNT(*) FROM raffle_participants 
                        WHERE raffle_id = ?
                    ''', (raffle_id,))
                else:
                    cursor.execute('''
                        SELECT COUNT(*) FROM raffle_participants
                    ''')
                
                count = cursor.fetchone()[0]
                return count
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка получения количества участников: {e}")
            return 0

    def delete_all_raffle_participants(self) -> bool:
        """Удаление всех участников розыгрыша"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM raffle_participants')
                conn.commit()
                logging.info("Все участники розыгрыша удалены")
                return True
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка удаления всех участников розыгрыша: {e}")
            return False

    def get_user_by_telegram_id(self, telegram_id: int):
        """Получение пользователя по telegram_id"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT user_id, participant_id, telegram_id, telegram_username, 
                            role, quest_started, quest_started_at, current_stage,
                            stage_1_completed, stage_2_completed, stage_3_completed, stage_4_completed,
                            registration_date
                    FROM main 
                    WHERE telegram_id = ?
                ''', (telegram_id,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'user_id': result[0],
                        'participant_id': result[1],
                        'telegram_id': result[2],
                        'telegram_username': result[3],
                        'role': result[4],
                        'quest_started': result[5],
                        'quest_started_at': result[6],
                        'current_stage': result[7],
                        'stage_1_completed': result[8],
                        'stage_2_completed': result[9],
                        'stage_3_completed': result[10],
                        'stage_4_completed': result[11],
                        'registration_date': result[12]
                    }
                return None
                
        except sqlite3.Error as e:
            logging.error(f"Ошибка получения пользователя по telegram_id {telegram_id}: {e}")
            return None
    
    def get_connection(self):
        """Получение соединения с базой данных"""
        return sqlite3.connect(self.db_path)

# Создаем глобальный экземпляр базы данных
db = Database()
