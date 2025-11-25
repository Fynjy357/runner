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
                        email TEXT NOT NULL UNIQUE,
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
                
                # Таблица 8: Участники розыгрыша (НОВАЯ ТАБЛИЦА)
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
            "CREATE INDEX IF NOT EXISTS idx_raffle_participants_raffle ON raffle_participants(raffle_id)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)

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
