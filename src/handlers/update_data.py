# update_data.py
import logging
import os
from datetime import datetime
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram import F
import pandas as pd


# Исправляем импорт - используем правильное имя функции
try:
    from utils.database_processor import process_participants_export
except ImportError:
    # Альтернативный вариант импорта
    try:
        from database_processor import process_participants_export
    except ImportError as e:
        logging.error(f"Ошибка импорта database_processor: {e}")
        # Создаем заглушку для отладки
        def process_participants_export():
            logging.error("Функция process_participants_export не найдена")
            return False

from database import db

# Создаем роутер
update_router = Router()

# Список администраторов (добавьте сюда Telegram ID админов)
ADMIN_IDS = [123456789, 987654321]  # Замените на реальные ID

@update_router.message(Command("update_data"))
async def update_data_command(message: Message):
    """Команда для обновления данных из Excel файла"""
    
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    
    # Проверяем права пользователя (админы из списка или пользователи с ролью admin/moderator)
    is_admin = False
    
    # Проверяем по списку администраторов
    if user_id in ADMIN_IDS:
        is_admin = True
        logging.info(f"Пользователь {user_id} ({username}) авторизован как администратор (список)")
    else:
        # Проверяем в базе данных
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT role FROM main WHERE telegram_id = ?", (user_id,))
                user_data = cursor.fetchone()
                
                if user_data and user_data[0] in ['admin', 'moderator']:
                    is_admin = True
                    logging.info(f"Пользователь {user_id} ({username}) авторизован как {user_data[0]}")
                else:
                    logging.warning(f"Пользователь {user_id} ({username}) не имеет прав доступа")
                    
        except Exception as e:
            logging.error(f"Ошибка проверки прав: {e}")
            await message.answer("❌ Ошибка проверки прав доступа.")
            return
    
    if not is_admin:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Отправляем сообщение о начале процесса
    status_message = await message.answer("🔄 Начинаю обновление данных из Excel файла...")
    
    try:
        # Сначала проверяем наличие файла
        file_path = "participants_export_current.xls"
        if not os.path.exists(file_path):
            await status_message.edit_text(
                f"❌ Файл не найден: {file_path}\n\n"
                f"Сначала выполните экспорт данных с помощью команды /export_data"
            )
            return
        
        # Получаем информацию о файле
        file_size = os.path.getsize(file_path)
        file_time = os.path.getmtime(file_path)
        modified_time = datetime.fromtimestamp(file_time).strftime('%Y-%m-%d %H:%M:%S')
        
        file_info = f"📁 Файл найден:\nРазмер: {file_size:,} байт\nИзменен: {modified_time}\n\n"
        await status_message.edit_text(f"{file_info}🔄 Обрабатываю данные...")
        
        # Получаем статистику до обновления
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM manual_upload")
            count_before = cursor.fetchone()[0]
        
        # Вызываем функцию обновления данных
        success = process_participants_export()
        
        if success:
            # Получаем статистику из базы данных
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Количество участников
                cursor.execute("SELECT COUNT(*) FROM manual_upload")
                total_participants = cursor.fetchone()[0]
                
                # Распределение по этапам
                cursor.execute('''
                    SELECT s.stage_name, COUNT(m.participant_id) 
                    FROM manual_upload m 
                    JOIN stages s ON m.stage_id = s.stage_id 
                    GROUP BY s.stage_name
                    ORDER BY s.stage_id
                ''')
                stage_stats = cursor.fetchall()
                
                # Формируем сообщение со статистикой
                added_count = total_participants - count_before
                
                stats_text = f"✅ Данные успешно обновлены!\n\n"
                stats_text += f"📊 Статистика обновления:\n"
                stats_text += f"• Записей до обновления: {count_before}\n"
                stats_text += f"• Записей после обновления: {total_participants}\n"
                stats_text += f"• Добавлено новых записей: {added_count}\n\n"
                
                stats_text += f"📋 Распределение по этапам:\n"
                
                for stage_name, count in stage_stats:
                    # Сокращаем длинные названия для лучшего отображения
                    short_name = stage_name
                    if len(stage_name) > 30:
                        short_name = stage_name[:27] + "..."
                    stats_text += f"• {short_name}: {count} участников\n"
                
                await status_message.edit_text(stats_text)
                
        else:
            await status_message.edit_text(
                "❌ Ошибка при обновлении данных.\n\n"
                "Возможные причины:\n"
                "• Неправильный формат Excel файла\n"
                "• Проблемы с базой данных\n\n"
                "Проверьте логи для подробной информации."
            )
            
    except Exception as e:
        logging.error(f"Ошибка при обновлении данных: {e}")
        await status_message.edit_text(f"❌ Произошла ошибка: {str(e)}")

@update_router.message(Command("data_stats"))
async def data_stats_command(message: Message):
    """Команда для показа статистики данных"""
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Общая статистика
            cursor.execute("SELECT COUNT(*) FROM manual_upload")
            total_participants = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT email) FROM manual_upload")
            unique_emails = cursor.fetchone()[0]
            
            # Статистика по этапам
            cursor.execute('''
                SELECT s.stage_name, COUNT(m.participant_id) 
                FROM manual_upload m 
                JOIN stages s ON m.stage_id = s.stage_id 
                GROUP BY s.stage_name
                ORDER BY s.stage_id
            ''')
            stage_stats = cursor.fetchall()
            
            # Статистика по дням регистрации
            cursor.execute('''
                SELECT DATE(registration_date), COUNT(*) 
                FROM manual_upload 
                WHERE registration_date IS NOT NULL
                GROUP BY DATE(registration_date)
                ORDER BY DATE(registration_date) DESC
                LIMIT 7
            ''')
            date_stats = cursor.fetchall()
            
            # Формируем сообщение со статистикой
            stats_text = "📊 Статистика данных:\n\n"
            stats_text += f"👥 Всего участников: {total_participants}\n"
            stats_text += f"📧 Уникальных email: {unique_emails}\n\n"
            
            stats_text += "📋 Распределение по этапам:\n"
            for stage_name, count in stage_stats:
                short_name = stage_name[:25] + "..." if len(stage_name) > 25 else stage_name
                stats_text += f"• {short_name}: {count}\n"
            
            if date_stats:
                stats_text += "\n📅 Регистрации за последние 7 дней:\n"
                for date_str, count in date_stats:
                    stats_text += f"• {date_str}: {count}\n"
            
            await message.answer(stats_text)
            
    except Exception as e:
        logging.error(f"Ошибка получения статистики: {e}")
        await message.answer("❌ Ошибка при получении статистики данных")

@update_router.message(Command("check_file"))
async def check_file_command(message: Message):
    """Команда для проверки Excel файла"""
    
    file_path = "participants_export_current.xls"
    
    if not os.path.exists(file_path):
        await message.answer(f"❌ Файл не найден: {file_path}")
        return
    
    try:
        # Получаем информацию о файле
        file_size = os.path.getsize(file_path)
        file_time = os.path.getmtime(file_path)
        modified_time = datetime.fromtimestamp(file_time).strftime('%Y-%m-%d %H:%M:%S')
        
        # Пробуем прочитать файл
        try:
            df = pd.read_excel(file_path, engine='xlrd')
        except:
            try:
                df = pd.read_excel(file_path, engine='openpyxl')
            except Exception as e:
                await message.answer(
                    f"❌ Ошибка чтения файла:\n{str(e)}\n\n"
                    f"📁 Файл: {file_path}\n"
                    f"📏 Размер: {file_size:,} байт\n"
                    f"🕐 Изменен: {modified_time}"
                )
                return
        
        # Формируем информацию о файле
        info_text = f"✅ Файл проверен успешно!\n\n"
        info_text += f"📁 Файл: {file_path}\n"
        info_text += f"📏 Размер: {file_size:,} байт\n"
        info_text += f"🕐 Изменен: {modified_time}\n\n"
        info_text += f"📊 Строк: {len(df)}\n"
        info_text += f"📋 Столбцов: {len(df.columns)}\n\n"
        info_text += "📋 Столбцы:\n"
        
        for i, column in enumerate(df.columns, 1):
            info_text += f"{i}. {column}\n"
        
        # Показываем первые 3 строки для примера
        info_text += "\n📄 Пример данных (первые 3 строки):\n"
        for i in range(min(3, len(df))):
            row_data = []
            for col in df.columns[:5]:  # Показываем первые 5 столбцов
                value = str(df.iloc[i][col])[:20] + "..." if len(str(df.iloc[i][col])) > 20 else str(df.iloc[i][col])
                row_data.append(f"{col[:10]}: {value}")
            info_text += f"Строка {i+1}: {' | '.join(row_data)}\n"
        
        await message.answer(info_text[:4000])  # Ограничение Telegram
        
    except Exception as e:
        logging.error(f"Ошибка проверки файла: {e}")
        await message.answer(f"❌ Ошибка при проверке файла: {str(e)}")

@update_router.message(Command("clear_data"))
async def clear_data_command(message: Message):
    """Команда для очистки данных"""
    
    user_id = message.from_user.id
    
    # Проверяем права (только администраторы)
    is_admin = False
    if user_id in ADMIN_IDS:
        is_admin = True
    else:
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT role FROM main WHERE telegram_id = ?", (user_id,))
                user_data = cursor.fetchone()
                if user_data and user_data[0] == 'admin':
                    is_admin = True
        except:
            pass
    
    if not is_admin:
        await message.answer("❌ У вас нет прав для очистки данных.")
        return
    
    # Создаем клавиатуру для подтверждения
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да, очистить все данные")],
            [KeyboardButton(text="❌ Нет, отменить")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "⚠️ ВНИМАНИЕ! Вы собираетесь очистить ВСЕ данные участников.\n\n"
        "Это действие невозможно отменить!\n\n"
        "Подтвердите очистку данных:",
        reply_markup=keyboard
    )

@update_router.message(F.text == "✅ Да, очистить все данные")
async def confirm_clear_data(message: Message):
    """Подтверждение очистки данных"""
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем количество записей перед очисткой
            cursor.execute("SELECT COUNT(*) FROM manual_upload")
            count_before = cursor.fetchone()[0]
            
            # Очищаем таблицу
            cursor.execute("DELETE FROM manual_upload")
            conn.commit()
            
            # Получаем количество записей после очистки
            cursor.execute("SELECT COUNT(*) FROM manual_upload")
            count_after = cursor.fetchone()[0]
            
        await message.answer(
            f"✅ Данные успешно очищены!\n\n"
            f"📊 Статистика:\n"
            f"• Записей до очистки: {count_before}\n"
            f"• Записей после очистки: {count_after}",
            reply_markup=ReplyKeyboardRemove()
        )
        
    except Exception as e:
        logging.error(f"Ошибка очистки данных: {e}")
        await message.answer(
            f"❌ Ошибка при очистке данных: {str(e)}",
            reply_markup=ReplyKeyboardRemove()
        )

@update_router.message(F.text == "❌ Нет, отменить")
async def cancel_clear_data(message: Message):
    """Отмена очистки данных"""
    await message.answer(
        "✅ Очистка данных отменена.",
        reply_markup=ReplyKeyboardRemove()
    )
