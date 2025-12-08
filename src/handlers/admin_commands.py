# handlers/admin_commands.py
import sys
import os
import logging

# Добавляем путь к src для корректного импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram.types import Message, FSInputFile
from aiogram import Router, F
from aiogram.filters import Command
import pandas as pd
import tempfile
from datetime import datetime
from src.promo import promo_router

try:
    from database import db
    logging.info("✅ Database import successful in admin_commands.py")
except ImportError as e:
    logging.error(f"❌ Database import failed in admin_commands.py: {e}")
    # Создаем заглушку для работы без базы
    class DatabaseStub:
        def get_connection(self):
            raise Exception("Database not available")
        def get_raffle_participants(self):
            return []
        def get_raffle_participants_count(self):
            return 0
    db = DatabaseStub()

# Создаем роутер для административных команд
admin_router = Router()

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role FROM main WHERE telegram_id = ?", 
                (user_id,)
            )
            result = cursor.fetchone()
            return result and result[0] in ['admin', 'moderator']
    except Exception as e:
        logging.error(f"Ошибка проверки прав администратора: {e}")
        return False

@admin_router.message(Command("allex"))
async def export_all_participants_to_excel(message: Message):
    """Экспорт всех участников розыгрыша в Excel файл"""
    temp_file_path = None  # Для отслеживания временного файла
    
    try:
        # Проверяем права администратора
        if not is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return

        # Получаем всех участников
        participants = db.get_raffle_participants()
        
        if not participants:
            await message.answer("📭 Нет зарегистрированных участников розыгрыша.")
            return

        # Создаем DataFrame
        df = pd.DataFrame(participants, 
                         columns=['Telegram ID', 'Username', 'Дата регистрации', 'ID розыгрыша'])
        
        # Форматируем дату
        if len(participants) > 0:
            df['Дата регистрации'] = pd.to_datetime(df['Дата регистрации']).dt.strftime('%d.%m.%Y %H:%M')
        
        # Заменяем None на пустые строки
        df = df.fillna('')
        
        # Создаем временный файл
        current_date = datetime.now().strftime('%d.%m.%Y')
        filename = f"участники_розыгрыша_{current_date}.xlsx"
        temp_file_path = os.path.join(tempfile.gettempdir(), filename)
        
        # Сохраняем в Excel
        with pd.ExcelWriter(temp_file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Участники розыгрыша', index=False)
            
            # Настраиваем ширину колонок
            worksheet = writer.sheets['Участники розыгрыша']
            worksheet.column_dimensions['A'].width = 15  # Telegram ID
            worksheet.column_dimensions['B'].width = 20  # Username
            worksheet.column_dimensions['C'].width = 20  # Дата регистрации
            worksheet.column_dimensions['D'].width = 15  # ID розыгрыша
        
        # Отправляем файл
        await message.answer_document(
            document=FSInputFile(temp_file_path, filename=filename),
            caption=f"📊 *Экспорт участников розыгрыша*\n\n"
                   f"📅 Дата выгрузки: {current_date}\n"
                   f"👥 Всего участников: {len(participants)}\n\n"
                   f"Файл содержит данные всех зарегистрированных участников.",
            parse_mode="Markdown"
        )
        
        logging.info(f"Админ {message.from_user.id} выгрузил список участников в Excel")
        
    except Exception as e:
        logging.error(f"Ошибка при экспорте в Excel: {e}")
        await message.answer("❌ Произошла ошибка при создании файла Excel.")
    
    finally:
        # Удаляем временный файл после отправки
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logging.error(f"Ошибка при удалении временного файла: {e}")

@admin_router.message(Command("all"))
async def show_all_participants(message: Message):
    """Показывает список всех участников розыгрыша"""
    try:
        # Проверяем права администратора
        if not is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return

        # Получаем всех участников
        participants = db.get_raffle_participants()
        
        if not participants:
            await message.answer("📭 Нет зарегистрированных участников розыгрыша.")
            return

        # Формируем сообщение
        participants_text = "📋 *Список участников розыгрыша:*\n\n"
        
        for i, (telegram_id, username, participation_date, raffle_id) in enumerate(participants, 1):
            # Форматируем дату
            if isinstance(participation_date, str):
                date_str = participation_date
            else:
                date_str = participation_date.strftime('%d.%m.%Y %H:%M') if hasattr(participation_date, 'strftime') else str(participation_date)
            
            # Форматируем username
            username_display = f"@{username}" if username else "без username"
            raffle_id_display = raffle_id if raffle_id else "не указан"
            
            participants_text += (
                f"{i}. ID: `{telegram_id}`\n"
                f"   👤: {username_display}\n"
                f"   📅: {date_str}\n"
                f"   🎯 ID розыгрыша: {raffle_id_display}\n\n"
            )
            
            # Разбиваем на части, если сообщение слишком длинное
            if len(participants_text) > 3500:
                await message.answer(participants_text, parse_mode="Markdown")
                participants_text = "📋 *Продолжение списка:*\n\n"

        # Отправляем оставшуюся часть
        if participants_text.strip():
            participants_text += f"\n📊 *Итого: {len(participants)} участников*"
            await message.answer(participants_text, parse_mode="Markdown")
            
        logging.info(f"Админ {message.from_user.id} запросил список участников")
        
    except Exception as e:
        logging.error(f"Ошибка при показе списка участников: {e}")
        await message.answer("❌ Произошла ошибка при получении списка участников.")

@admin_router.message(Command("delete"))
async def delete_all_participants(message: Message):
    """Удаляет всех участников розыгрыша"""
    try:
        # Проверяем права администратора
        if not is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return

        # Получаем количество участников перед удалением
        participants_count = db.get_raffle_participants_count()
        
        if participants_count == 0:
            await message.answer("📭 Нет участников для удаления.")
            return

        # Создаем клавиатуру для подтверждения
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        from aiogram.utils.keyboard import ReplyKeyboardBuilder
        
        builder = ReplyKeyboardBuilder()
        builder.add(KeyboardButton(text="✅ ДА, удалить всех"))
        builder.add(KeyboardButton(text="❌ НЕТ, отменить"))
        confirm_keyboard = builder.as_markup(resize_keyboard=True)

        # Сохраняем состояние для подтверждения
        await message.answer(
            f"⚠️ *ВНИМАНИЕ!*\n\n"
            f"Вы собираетесь удалить *ВСЕХ* участников розыгрыша.\n\n"
            f"📊 Текущее количество участников: *{participants_count}*\n\n"
            f"❓ *Вы уверены?* Это действие нельзя отменить!\n\n"
            f"Нажмите '✅ ДА, удалить всех' для подтверждения или '❌ НЕТ, отменить' для отмены.",
            parse_mode="Markdown",
            reply_markup=confirm_keyboard
        )
        
    except Exception as e:
        logging.error(f"Ошибка при подготовке удаления участников: {e}")
        await message.answer("❌ Произошла ошибка при подготовке удаления.")

@admin_router.message(F.text == "✅ ДА, удалить всех")
async def confirm_delete_all_participants(message: Message):
    """Подтверждение удаления всех участников"""
    try:
        if not is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return

        # Получаем количество участников перед удалением
        participants_count = db.get_raffle_participants_count()
        
        # Удаляем всех участников
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM raffle_participants")
            deleted_count = cursor.rowcount
            conn.commit()
        
        # Убираем клавиатуру подтверждения
        from aiogram.types import ReplyKeyboardRemove
        
        await message.answer(
            f"🗑️ *Удаление завершено!*\n\n"
            f"✅ Удалено участников: *{deleted_count}*\n\n"
            f"База данных участников розыгрыша очищена.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        
        logging.info(f"Админ {message.from_user.id} удалил всех участников розыгрыша ({deleted_count} записей)")
        
    except Exception as e:
        logging.error(f"Ошибка при удалении участников: {e}")
        await message.answer("❌ Произошла ошибка при удалении участников.")

@admin_router.message(F.text == "❌ НЕТ, отменить")
async def cancel_delete_all_participants(message: Message):
    """Отмена удаления всех участников"""
    try:
        from aiogram.types import ReplyKeyboardRemove
        
        await message.answer(
            "✅ Удаление отменено.\n\n"
            "Участники розыгрыша сохранены.",
            reply_markup=ReplyKeyboardRemove()
        )
        
    except Exception as e:
        logging.error(f"Ошибка при отмене удаления: {e}")
        await message.answer("❌ Произошла ошибка при отмене удаления.")


# _________________________________________
@admin_router.message(Command("address"))
async def address_command(message: Message):
    """Выгружает данные об адресах пользователей"""
    try:
        # Проверяем права администратора
        if not is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return

        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # SQL запрос для объединения данных из трех таблиц
            query = """
                SELECT 
                    mu.last_name,
                    mu.first_name,
                    mu.middle_name,
                    mu.phone,
                    mu.email,
                    ua.stage,
                    ua.address,
                    m.telegram_username
                FROM user_addresses ua
                LEFT JOIN main m ON ua.telegram_id = m.telegram_id
                LEFT JOIN manual_upload mu ON mu.participant_id = m.participant_id
                ORDER BY mu.last_name, mu.first_name
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            
            if not results:
                await message.answer("📭 В базе данных нет записей об адресах пользователей.")
                return
            
            # Формируем Excel файл
            df = pd.DataFrame(results, columns=[
                "Фамилия", "Имя", "Отчество", "Телефон", "Email", "Этап", "Адрес", "Telegram username"
            ])
            
            # Создаем временный файл
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xlsx', delete=False) as temp_file:
                temp_filename = temp_file.name
            
            # Сохраняем в Excel
            df.to_excel(temp_filename, index=False, engine='openpyxl')
            
            # Отправляем файл
            file_for_send = FSInputFile(temp_filename)
            await message.answer_document(
                file_for_send,
                caption=f"📋 *Данные об адресах пользователей*\n\n"
                         f"📊 Всего записей: {len(results)}\n"
                         f"📅 Дата выгрузки: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                parse_mode="Markdown"
            )
            
            # Удаляем временный файл
            os.unlink(temp_filename)
            
            logging.info(f"Админ {message.from_user.id} выгрузил данные об адресах ({len(results)} записей)")
            
    except Exception as e:
        logging.error(f"Ошибка при выгрузке адресов: {e}")
        await message.answer("❌ Произошла ошибка при выгрузке данных об адресах.")

@admin_router.message(Command("add"))
async def add_manual_data_command(message: Message):
    """Добавляет данные из Excel файла в таблицу manual_upload"""
    try:
        # Проверяем права администратора
        if not is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return

        await message.answer(
            "📤 *Загрузите Excel файл с данными*\n\n"
            "Файл должен содержать следующие колонки:\n"
            "• Дистанция (stage_id) - цифры 1-5\n"
            "• Фамилия (last_name)\n"
            "• Имя (first_name)\n"
            "• Отчество (middle_name)\n"
            "• Электронная почта (email)\n"
            "• Мобильный телефон (phone)\n\n"
            "📋 *Соответствие этапов:*\n"
            "1 - ГЛАВА 1. «Предательство в Центральном штабе»\n"
            "2 - ГЛАВА 2. «Провал операции»\n"
            "3 - ГЛАВА 3. «Обратный отсчет»\n"
            "4 - ГЛАВА 4. «Последний рейс»\n"
            "5 - Пакет на 4 этапа «Тайна пропавшей коллекции. Полное погружение»",
            parse_mode="Markdown"
        )

    except Exception as e:
        logging.error(f"Ошибка в команде /add: {e}")
        await message.answer("❌ Произошла ошибка при подготовке к загрузке данных.")

def process_manual_upload(file_path):
    """Обрабатывает Excel файл для добавления данных в manual_upload"""
    try:
        # Читаем Excel файл
        df = pd.read_excel(file_path)
        
        # Проверяем наличие необходимых колонок
        required_columns = ['Дистанция', 'Фамилия', 'Имя', 'Отчество', 'Электронная почта', 'Мобильный телефон']
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Отсутствуют колонки: {', '.join(missing_columns)}")

        # Очищаем данные от полностью пустых строк
        df = df.dropna(subset=['Фамилия', 'Имя', 'Электронная почта', 'Мобильный телефон'])
        
        if df.empty:
            raise ValueError("В файле нет данных для добавления.")

        # Словарь для преобразования названий этапов в числовые значения
        stage_mapping = {
            'ГЛАВА 1.  «Предательство в Центральном штабе»': 1,
            'ГЛАВА 2. «Провал операции»': 2,
            'ГЛАВА 3. «Обратный отсчет»': 3,
            'ГЛАВА 4. «Последний рейс»': 4,
            'Пакет на 4 этапа «Тайна пропавшей коллекции. Полное погружение» ': 5,
            'Пакет на 4 этапа «Тайна пропавшей коллекции. Полное погружение»': 5
        }

        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем максимальный participant_id для продолжения нумерации
            cursor.execute("SELECT COALESCE(MAX(participant_id), 0) FROM manual_upload")
            max_participant_id = cursor.fetchone()[0]
            
            added_count = 0
            duplicate_count = 0
            error_count = 0
            
            # Обрабатываем каждую строку
            for index, row in df.iterrows():
                try:
                    # Преобразуем название этапа в числовое значение
                    stage_name = str(row['Дистанция']).strip()
                    
                    # Ищем соответствие в словаре
                    stage_id = None
                    for key, value in stage_mapping.items():
                        if key.strip() == stage_name:
                            stage_id = value
                            break
                    
                    if stage_id is None:
                        error_count += 1
                        continue
                    
                    # Проверяем на дубликаты (телефон + email + этап)
                    cursor.execute("""
                        SELECT COUNT(*) FROM manual_upload 
                        WHERE phone = ? AND email = ? AND stage_id = ?
                    """, (str(row['Мобильный телефон']), str(row['Электронная почта']), stage_id))
                    
                    if cursor.fetchone()[0] > 0:
                        duplicate_count += 1
                        continue
                    
                    # Генерируем новый participant_id
                    max_participant_id += 1
                    
                    # Добавляем запись
                    cursor.execute("""
                        INSERT INTO manual_upload 
                        (participant_id, stage_id, last_name, first_name, middle_name, email, phone)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        max_participant_id,
                        stage_id,
                        str(row['Фамилия']),
                        str(row['Имя']),
                        str(row['Отчество']) if pd.notna(row['Отчество']) else None,
                        str(row['Электронная почта']),
                        str(row['Мобильный телефон'])
                    ))
                    
                    added_count += 1
                    
                except Exception as e:
                    logging.error(f"Ошибка при обработке строки {index}: {e}")
                    error_count += 1
                    continue
            
            conn.commit()
            
            # Формируем статистику по этапам
            stage_stats = {}
            if added_count > 0:
                cursor.execute("""
                    SELECT stage_id, COUNT(*) 
                    FROM manual_upload 
                    WHERE participant_id > ?
                    GROUP BY stage_id
                """, (max_participant_id - added_count,))
                
                for stage_id, count in cursor.fetchall():
                    stage_stats[stage_id] = count
            
            return {
                "added_count": added_count,
                "duplicate_count": duplicate_count,
                "error_count": error_count,
                "stage_stats": stage_stats,
                "max_participant_id": max_participant_id
            }
            
    except Exception as e:
        logging.error(f"Ошибка при обработке Excel файла: {e}")
        raise


@admin_router.message(F.document)
async def handle_manual_excel_upload(message: Message):
    """Обрабатывает загруженный Excel файл для добавления данных в manual_upload"""
    try:
        if not is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return

        # Проверяем, что это Excel файл
        if not (message.document.file_name.endswith('.xlsx') or 
                message.document.file_name.endswith('.xls')):
            await message.answer("❌ Пожалуйста, загрузите файл в формате Excel (.xlsx или .xls)")
            return

        # Скачиваем файл
        file_info = await message.bot.get_file(message.document.file_id)
        downloaded_file = await message.bot.download_file(file_info.file_path)

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx', delete=False) as temp_file:
            temp_filename = temp_file.name
            temp_file.write(downloaded_file.getvalue())

        try:
            # Обрабатываем файл
            result = process_manual_upload(temp_filename)
            
            # Формируем отчет
            report = f"""
📊 *Результат обработки файла:*

✅ Добавлено записей: {result['added_count']}
⚠️ Пропущено дубликатов: {result['duplicate_count']}
❌ Ошибок обработки: {result['error_count']}

📋 *Статистика по этапам:*
"""
            
            # Добавляем статистику по этапам
            for stage_id, count in result['stage_stats'].items():
                report += f"• Этап {stage_id}: {count} записей\n"
            
            await message.answer(report, parse_mode="Markdown")
            logging.info(f"Админ {message.from_user.id} добавил {result['added_count']} записей в manual_upload")
            
        except ValueError as e:
            await message.answer(f"❌ {str(e)}")
        except Exception as e:
            logging.error(f"Ошибка при чтении Excel файла: {e}")
            await message.answer("❌ Ошибка при чтении Excel файла. Проверьте формат файла.")
        
        finally:
            # Удаляем временный файл
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)
            
    except Exception as e:
        logging.error(f"Ошибка при обработке Excel файла: {e}")
        await message.answer("❌ Произошла ошибка при обработке файла.")
# ___________________

@admin_router.message(Command("admin_help"))
async def admin_help_command(message: Message):
    """Показывает все доступные административные команды"""
    try:
        # Проверяем права администратора
        if not is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return

        help_text = """
🔧 *СПРАВКА ПО АДМИНИСТРАТИВНЫМ КОМАНДАМ*

📊 *Управление участниками:*
• `/add` - Обновить пользователей из файла Excel
• `/address` - Выгрузить данные об адресах пользователей
• `/all` - Показать всех участников розыгрыша (-)
• `/allex` - Экспорт участников в Excel
• `/delete` - Удалить всех участников розыгрыша (с подтверждением) (-)
• `/export_participants` - Обновить участников из PP (-)
• `/update_data` - Выгрузить данные из Excel (-)

📧 *Рассылки:*
• `/send_mail` - Отправить рассылку
• `/mail_status` - Статус рассылки

🔗 *Ссылки:*
• `/generate_all_links` - Сгенерировать все ссылки

🎫 *Промокоды:*
• `/promo_stats` - Статистика промокодов
• `/promo_list [status]` - Список промокодов (active/used/expired)
• `/load_promo_excel` - Загрузить промокоды из Excel
• `/load_promo_csv` - Загрузить промокоды из CSV
• `/load_promo_txt` - Загрузить промокоды из TXT
• `/check_promo` - Проверить промокод (-)
• `/export_promo` - Экспорт промокодов в файл (-)
• `/send_promo <telegram_id> [username]` - Отправить промокод пользователю (-)
• `/my_promo` - Мои промокоды (для пользователей) (-)

📋 *Общие:*
• `/admin_help` - Эта справка

⚠️ *Примечания:*
- Команды работают только для администраторов и модераторов
- Для некоторых команд требуется подтверждение
- Все действия логируются
        """

        await message.answer(help_text, parse_mode="Markdown")
        
        logging.info(f"Админ {message.from_user.id} запросил справку по командам")
        
    except Exception as e:
        logging.error(f"Ошибка при показе справки: {e}")
        await message.answer("❌ Произошла ошибка при показе справки.")

def setup_admin_handler(dp):
    """Настройка обработчиков административных команд"""
    dp.include_router(admin_router)
    dp.include_router(promo_router)
