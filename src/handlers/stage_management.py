from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import logging
from database import db

# Создаем роутер
stage_router = Router()

# Состояния для FSM
class AddStage(StatesGroup):
    waiting_for_stage_name = State()

# Команда для добавления этапа
@stage_router.message(Command("add_stage"))
async def add_stage_command(message: Message, state: FSMContext):
    """Начало процесса добавления этапа"""
    
    # Проверяем права пользователя (только админы/модераторы)
    user_role = await get_user_role(message.from_user.id)
    if user_role not in ['admin', 'moderator']:
        await message.answer("❌ У вас нет прав для выполнения этой команды")
        return
    
    await message.answer(
        "📝 Введите название нового этапа:\n\n"
        "Примеры:\n"
        "• Этап 1: Знакомство\n"
        "• Этап 2: Беговая подготовка\n"
        "• Этап 3: Питание\n"
        "• Финальный этап",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AddStage.waiting_for_stage_name)

# Обработчик ввода названия этапа
@stage_router.message(AddStage.waiting_for_stage_name, F.text)
async def process_stage_name(message: Message, state: FSMContext):
    """Обработка введенного названия этапа"""
    stage_name = message.text.strip()
    
    if len(stage_name) < 2:
        await message.answer("❌ Название этапа слишком короткое. Введите название еще раз:")
        return
    
    if len(stage_name) > 100:
        await message.answer("❌ Название этапа слишком длинное. Введите название до 100 символов:")
        return
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем, существует ли уже этап с таким названием
            cursor.execute('SELECT stage_id FROM stages WHERE stage_name = ?', (stage_name,))
            existing_stage = cursor.fetchone()
            
            if existing_stage:
                await message.answer(f"❌ Этап с названием '{stage_name}' уже существует")
                await state.clear()
                return
            
            # Добавляем новый этап
            cursor.execute('INSERT INTO stages (stage_name) VALUES (?)', (stage_name,))
            stage_id = cursor.lastrowid
            
            conn.commit()
            
            await message.answer(
                f"✅ Этап успешно добавлен!\n\n"
                f"🆔 ID этапа: {stage_id}\n"
                f"📝 Название: {stage_name}",
                reply_markup=create_stage_management_keyboard()
            )
            
            logging.info(f"Добавлен новый этап: ID={stage_id}, название='{stage_name}'")
            
    except Exception as e:
        logging.error(f"Ошибка при добавлении этапа: {e}")
        await message.answer("❌ Произошла ошибка при добавлении этапа")
    
    await state.clear()

# Команда для просмотра всех этапов
@stage_router.message(Command("list_stages"))
async def list_stages_command(message: Message):
    """Показать список всех этапов"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT stage_id, stage_name 
                FROM stages 
                ORDER BY stage_id
            ''')
            
            stages = cursor.fetchall()
            
            if not stages:
                await message.answer("📋 Список этапов пуст")
                return
            
            stages_message = "📋 **Список этапов:**\n\n"
            
            for stage_id, stage_name in stages:
                # Получаем количество пользователей на этом этапе
                cursor.execute('''
                    SELECT COUNT(*) FROM manual_upload WHERE stage_id = ?
                ''', (stage_id,))
                user_count = cursor.fetchone()[0]
                
                stages_message += f"🆔 **{stage_id}**: {stage_name}\n"
                stages_message += f"   👥 Участников: {user_count}\n\n"
            
            await message.answer(stages_message, parse_mode="Markdown")
            
    except Exception as e:
        logging.error(f"Ошибка при получении списка этапов: {e}")
        await message.answer("❌ Произошла ошибка при получении списка этапов")

# Команда для удаления этапа
@stage_router.message(Command("delete_stage"))
async def delete_stage_command(message: Message):
    """Удаление этапа (только для админов)"""
    
    # Проверяем права пользователя (только админы)
    user_role = await get_user_role(message.from_user.id)
    if user_role != 'admin':
        await message.answer("❌ Только администраторы могут удалять этапы")
        return
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем список этапов
            cursor.execute('SELECT stage_id, stage_name FROM stages ORDER BY stage_id')
            stages = cursor.fetchall()
            
            if not stages:
                await message.answer("📋 Нет этапов для удаления")
                return
            
            # Создаем клавиатуру с этапами (ИЗМЕНЕН ФОРМАТ - отличный от content_router)
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text=f"Удалить этап {stage_id}: {name}")]  # ИЗМЕНЕНО: другой формат
                    for stage_id, name in stages
                ] + [[KeyboardButton(text="❌ Отмена")]],
                resize_keyboard=True
            )
            
            await message.answer(
                "🗑️ Выберите этап для удаления:\n\n"
                "⚠️ **Внимание**: Эта операция необратима!\n"
                "При удалении этапа:\n"
                "• Удалятся все пользователи с этого этапа из manual_upload\n"
                "• Удалятся связанные ссылки из link_generation\n"
                "• Обнулятся participant_id в таблице main",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logging.error(f"Ошибка при подготовке удаления этапа: {e}")
        await message.answer("❌ Произошла ошибка")

# Обработчик выбора этапа для удаления - УТОЧНЕННЫЙ ФИЛЬТР
@stage_router.message(F.text.startswith(("❌", "Удалить этап")))  # ИЗМЕНЕНО: другой префикс
async def process_stage_deletion(message: Message):
    """Обработка выбора этапа для удаления с каскадным удалением"""
    
    if message.text == "❌ Отмена":
        await message.answer("✅ Отмена удаления", reply_markup=ReplyKeyboardRemove())
        return
    
    try:
        # Извлекаем ID этапа из текста (формат: "Удалить этап 1: Название этапа")
        stage_id = int(message.text.split(':')[0].replace("Удалить этап ", "").strip())
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем название этапа для подтверждения
            cursor.execute('SELECT stage_name FROM stages WHERE stage_id = ?', (stage_id,))
            stage_data = cursor.fetchone()
            
            if not stage_data:
                await message.answer("❌ Этап не найден", reply_markup=ReplyKeyboardRemove())
                return
            
            stage_name = stage_data[0]
            
            # Получаем количество пользователей на этом этапе
            cursor.execute('SELECT COUNT(*) FROM manual_upload WHERE stage_id = ?', (stage_id,))
            user_count = cursor.fetchone()[0]
            
            if user_count == 0:
                # Если нет пользователей - просто удаляем этап
                cursor.execute('DELETE FROM stages WHERE stage_id = ?', (stage_id,))
                conn.commit()
                
                await message.answer(
                    f"✅ Этап удален:\n\n"
                    f"🆔 ID: {stage_id}\n"
                    f"📝 Название: {stage_name}\n"
                    f"👥 Пользователей: 0",
                    reply_markup=ReplyKeyboardRemove()
                )
                
                logging.info(f"Удален этап: ID={stage_id}, название='{stage_name}'")
                return
            
            # Если есть пользователи - выполняем каскадное удаление
            
            # 1. Получаем всех participant_id с этого этапа
            cursor.execute('SELECT participant_id FROM manual_upload WHERE stage_id = ?', (stage_id,))
            participant_ids = [row[0] for row in cursor.fetchall()]
            
            deleted_users_count = 0
            deleted_links_count = 0
            updated_main_count = 0
            
            # 2. Для каждого participant_id выполняем каскадные операции
            for participant_id in participant_ids:
                # Удаляем из link_generation
                cursor.execute('DELETE FROM link_generation WHERE participant_id = ?', (participant_id,))
                deleted_links_count += cursor.rowcount
                
                # Обнуляем participant_id в таблице main (НЕ удаляем пользователя!)
                cursor.execute('''
                    UPDATE main 
                    SET participant_id = NULL 
                    WHERE participant_id = ?
                ''', (participant_id,))
                updated_main_count += cursor.rowcount
                
                # Удаляем из manual_upload
                cursor.execute('DELETE FROM manual_upload WHERE participant_id = ?', (participant_id,))
                deleted_users_count += cursor.rowcount
            
            # 3. Удаляем сам этап
            cursor.execute('DELETE FROM stages WHERE stage_id = ?', (stage_id,))
            
            conn.commit()
            
            await message.answer(
                f"✅ Этап удален с каскадным удалением:\n\n"
                f"🆔 ID этапа: {stage_id}\n"
                f"📝 Название: {stage_name}\n"
                f"🗑️ Удалено пользователей: {deleted_users_count}\n"
                f"🔗 Удалено ссылок: {deleted_links_count}\n"
                f"🔄 Обновлено записей в main: {updated_main_count}",
                reply_markup=ReplyKeyboardRemove()
            )
            
            logging.info(
                f"Удален этап с каскадным удалением: "
                f"ID={stage_id}, название='{stage_name}', "
                f"пользователей={deleted_users_count}, "
                f"ссылок={deleted_links_count}, "
                f"обновлено main={updated_main_count}"
            )
            
    except ValueError:
        await message.answer("❌ Неверный формат этапа", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        logging.error(f"Ошибка при удалении этапа: {e}")
        await message.answer("❌ Произошла ошибка при удалении этапа", reply_markup=ReplyKeyboardRemove())

# Вспомогательные функции
async def get_user_role(telegram_id: int) -> str:
    """Получить роль пользователя"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT role FROM main WHERE telegram_id = ?', (telegram_id,))
            result = cursor.fetchone()
            return result[0] if result else 'user'
    except Exception:
        return 'user'

def create_stage_management_keyboard():
    """Создать клавиатуру для управления этапами"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/list_stages"), KeyboardButton(text="/add_stage")],
            [KeyboardButton(text="/delete_stage")],
            [KeyboardButton(text="📋 Главное меню")]
        ],
        resize_keyboard=True
    )

# Функция для настройки обработчиков
def setup_stage_handlers(dp):
    """Настройка обработчиков этапов"""
    dp.include_router(stage_router)
