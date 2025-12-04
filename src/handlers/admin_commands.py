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
• `/all` - Показать всех участников розыгрыша
• `/allex` - Экспорт участников в Excel
• `/delete` - Удалить всех участников (с подтверждением)
• `/export_participants` - Обновить участников из PP
• `/update_data` - Выгрузить данные из Excel

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
• `/check_promo` - Проверить промокод
• `/export_promo` - Экспорт промокодов в файл
• `/send_promo <telegram_id> [username]` - Отправить промокод пользователю
• `/my_promo` - Мои промокоды (для пользователей)

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
