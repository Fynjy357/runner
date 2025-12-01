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
                
                # Таблица 3: Основная - ДОБАВЛЯЕМ current_stage
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS main (
                        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        participant_id INTEGER UNIQUE,
                        telegram_id INTEGER UNIQUE,
                        telegram_username TEXT,
                        role TEXT NOT NULL CHECK(role IN ('admin', 'moderator', 'user')),
                        quest_started INTEGER DEFAULT 0 CHECK(quest_started IN (0, 1)),
                        quest_started_at DATETIME,
                        current_stage INTEGER DEFAULT 1 
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
                
                # ✅ ТАБЛИЦА 9: Адреса пользователей (УПРОЩЕННАЯ ВЕРСИЯ)
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
            "CREATE INDEX IF NOT EXISTS idx_user_addresses_stage ON user_addresses(stage)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)

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

    def get_connection(self):
        """Получение соединения с базой данных"""
        return sqlite3.connect(self.db_path)

# Создаем глобальный экземпляр базы данных
db = Database()
