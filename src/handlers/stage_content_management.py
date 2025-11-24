from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, ContentType
from database import db
import logging

# Получаем логгер из вашей системы
logger = logging.getLogger('bot')

# Создаем роутер
content_router = Router()

# Состояния для FSM
class AddStageContent(StatesGroup):
    waiting_for_stage_selection = State()
    waiting_for_order_number = State()
    waiting_for_message_text = State()
    waiting_for_image_choice = State()
    waiting_for_image = State()
    waiting_for_video_choice = State()
    waiting_for_video = State()
    waiting_for_feedback_choice = State()
    waiting_for_puzzle_answer = State()

# Команда для добавления контента к этапу
@content_router.message(Command("add_stage_content"))
async def add_stage_content_command(message: Message, state: FSMContext):
    """Начало процесса добавления контента к этапу"""
    
    logger.info(f"🚀 Команда /add_stage_content от пользователя {message.from_user.id}")
    
    # Проверяем права пользователя (только админы/модераторы)
    user_role = await get_user_role(message.from_user.id)
    if user_role not in ['admin', 'moderator']:
        await message.answer("❌ У вас нет прав для выполнения этой команды")
        return
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем список этапов
            cursor.execute('SELECT stage_id, stage_name FROM stages ORDER BY stage_id')
            stages = cursor.fetchall()
            
            if not stages:
                await message.answer("❌ Нет доступных этапов. Сначала создайте этап с помощью /add_stage")
                return
            
            # Сохраняем список этапов в состоянии для последующего использования
            stages_dict = {f"Этап {stage_id}: {name}": stage_id for stage_id, name in stages}
            await state.update_data(available_stages=stages_dict)
            
            # Создаем клавиатуру с этапами (ИЗМЕНЕНО: добавляем префикс "Добавить в ")
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text=f"Добавить в этап {stage_id}: {name}")]  # ИЗМЕНЕНО: другой формат
                    for stage_id, name in stages
                ] + [[KeyboardButton(text="❌ Отмена")]],
                resize_keyboard=True
            )
            
            await message.answer(
                "📝 Выберите этап для добавления контента:",
                reply_markup=keyboard
            )
            await state.set_state(AddStageContent.waiting_for_stage_selection)
            logger.info(f"📝 Установлено состояние: waiting_for_stage_selection")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при получении списка этапов: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка")

# Обработчик выбора этапа - ИСПРАВЛЕННЫЙ
@content_router.message(
    AddStageContent.waiting_for_stage_selection,
    F.text != "❌ Отмена"
)
async def process_stage_selection(message: Message, state: FSMContext):
    """Обработка выбора этапа для добавления контента"""
    
    logger.info(f"🎯 Обработка выбора этапа: '{message.text}'")
    
    try:
        # Получаем доступные этапы из состояния
        data = await state.get_data()
        available_stages = data.get('available_stages', {})
        
        # Проверяем, есть ли выбранный этап в списке доступных
        if message.text not in available_stages:
            await message.answer("❌ Выбранный этап не найден в списке доступных")
            return
        
        stage_id = available_stages[message.text]
        logger.info(f"🔍 Получен stage_id из словаря: {stage_id}")
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем существование этапа в БД
            cursor.execute('SELECT stage_name FROM stages WHERE stage_id = ?', (stage_id,))
            stage_data = cursor.fetchone()
            
            if not stage_data:
                await message.answer("❌ Этап не найден в базе данных", reply_markup=ReplyKeyboardRemove())
                await state.clear()
                return
            
            stage_name = stage_data[0]
            logger.info(f"✅ Найден этап: {stage_name}")
            
            # Получаем максимальный порядковый номер для этого этапа
            cursor.execute('''
                SELECT MAX(order_number) FROM stage_content WHERE stage_id = ?
            ''', (stage_id,))
            max_order = cursor.fetchone()[0] or 0
            logger.info(f"📊 Максимальный порядковый номер: {max_order}")
            
            await state.update_data(
                stage_id=stage_id,
                stage_name=stage_name,
                next_order=max_order + 1
            )
            
            await message.answer(
                f"📋 Этап: {stage_name}\n"
                f"🆔 ID: {stage_id}\n\n"
                f"📊 Текущий порядковый номер для нового сообщения: {max_order + 1}\n\n"
                f"Введите порядковый номер для нового сообщения (или оставьте {max_order + 1}):",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(AddStageContent.waiting_for_order_number)
            logger.info(f"➡️ Переход в состояние: waiting_for_order_number")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при выборе этапа: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка", reply_markup=ReplyKeyboardRemove())
        await state.clear()

# Обработчик отмены выбора этапа
@content_router.message(
    AddStageContent.waiting_for_stage_selection,
    F.text == "❌ Отмена"
)
async def cancel_stage_selection(message: Message, state: FSMContext):
    """Отмена выбора этапа"""
    logger.info(f"❌ Отмена выбора этапа пользователем {message.from_user.id}")
    await message.answer("✅ Отмена добавления контента", reply_markup=ReplyKeyboardRemove())
    await state.clear()

# Обработчик ввода порядкового номера
@content_router.message(AddStageContent.waiting_for_order_number, F.text)
async def process_order_number(message: Message, state: FSMContext):
    """Обработка ввода порядкового номера"""
    
    logger.info(f"🔢 Обработка порядкового номера: '{message.text}'")
    
    try:
        data = await state.get_data()
        default_order = data['next_order']
        
        order_text = message.text.strip()
        if not order_text:
            order_number = default_order
        else:
            order_number = int(order_text)
        
        if order_number < 1:
            await message.answer("❌ Порядковый номер должен быть положительным числом. Введите еще раз:")
            return
        
        await state.update_data(order_number=order_number)
        logger.info(f"✅ Установлен order_number: {order_number}")
        
        await message.answer(
            "📝 Введите текст сообщения в формате HTML:\n\n"
            "Примеры форматирования:\n"
            "• <b>Жирный текст</b>\n"
            "• <i>Курсив</i>\n"
            "• <u>Подчеркнутый</u>\n"
            "• <code>Моноширинный</code>\n"
            "• <a href='https://example.com'>Ссылка</a>\n\n"
            "⚠️ Внимание: Используйте только разрешенные HTML-теги!",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(AddStageContent.waiting_for_message_text)
        logger.info(f"➡️ Переход в состояние: waiting_for_message_text")
        
    except ValueError:
        logger.error(f"❌ ValueError при обработке порядкового номера: '{message.text}'")
        await message.answer("❌ Введите корректное число для порядкового номера:")
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке порядкового номера: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка", reply_markup=ReplyKeyboardRemove())
        await state.clear()

# Обработчик ввода текста сообщения
@content_router.message(AddStageContent.waiting_for_message_text, F.text)
async def process_message_text(message: Message, state: FSMContext):
    """Обработка ввода текста сообщения"""
    
    logger.info(f"💬 Обработка текста сообщения: '{message.text[:50]}...'")
    
    message_text = message.text.strip()
    
    if len(message_text) < 1:
        await message.answer("❌ Текст сообщения не может быть пустым. Введите текст:")
        return
    
    if len(message_text) > 4000:
        await message.answer("❌ Текст сообщения слишком длинный. Максимум 4000 символов. Введите текст:")
        return
    
    await state.update_data(message_text=message_text)
    logger.info(f"✅ Текст сообщения сохранен, длина: {len(message_text)} символов")
    
    # Спрашиваем про изображение (ИЗМЕНЕНО: используем другие эмодзи для избежания конфликта)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🖼️ Да"), KeyboardButton(text="🚫 Нет")]  # ИЗМЕНЕНО: другие кнопки
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "🖼️ Добавить изображение к сообщению?",
        reply_markup=keyboard
    )
    await state.set_state(AddStageContent.waiting_for_image_choice)
    logger.info(f"➡️ Переход в состояние: waiting_for_image_choice")

# Обработчик выбора изображения
@content_router.message(AddStageContent.waiting_for_image_choice)
async def process_image_choice(message: Message, state: FSMContext):
    """Обработка выбора добавления изображения"""
    
    logger.info(f"🖼️ Обработка выбора изображения: '{message.text}'")
    
    # Проверяем текст сообщения (ИЗМЕНЕНО: новые значения кнопок)
    if message.text == "🖼️ Да":
        has_image = True
        await state.update_data(has_image=1, image_url=None)
        logger.info(f"📸 has_image установлено в: {has_image}")
        
        await message.answer(
            "📤 Отправьте изображение (фото):",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(AddStageContent.waiting_for_image)
        logger.info(f"➡️ Переход в состояние: waiting_for_image")
        
    elif message.text == "🚫 Нет":
        has_image = False
        await state.update_data(has_image=0, image_url=None)
        logger.info(f"📸 has_image установлено в: {has_image}")
        
        # Переходим к выбору видео (ИЗМЕНЕНО: используем другие эмодзи)
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🎥 Да"), KeyboardButton(text="🚫 Нет")]  # ИЗМЕНЕНО: другие кнопки
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            "🎥 Добавить видео к сообщению?",
            reply_markup=keyboard
        )
        await state.set_state(AddStageContent.waiting_for_video_choice)
        logger.info(f"➡️ Переход в состояние: waiting_for_video_choice")
        
    else:
        # Неправильный ввод - показываем клавиатуру снова
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🖼️ Да"), KeyboardButton(text="🚫 Нет")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            "❌ Пожалуйста, выберите один из вариантов:",
            reply_markup=keyboard
        )

# Обработчик загрузки изображения
@content_router.message(AddStageContent.waiting_for_image, F.content_type == ContentType.PHOTO)
async def process_image_upload(message: Message, state: FSMContext):
    """Обработка загрузки изображения"""
    
    logger.info(f"📸 Получено изображение")
    
    # В реальном приложении здесь нужно сохранить файл и получить URL
    # Для демонстрации используем file_id
    image_file_id = message.photo[-1].file_id
    await state.update_data(image_url=image_file_id)
    logger.info(f"✅ Изображение сохранено, file_id: {image_file_id}")
    
    # После загрузки изображения видео недоступно
    await state.update_data(has_video=0, video_url=None)
    
    # Переходим к выбору обратной связи (ИЗМЕНЕНО: используем другие эмодзи)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Да"), KeyboardButton(text="🚫 Нет")]  # ИЗМЕНЕНО: другие кнопки
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "📝 Нужна ли обратная связь от пользователя?",
        reply_markup=keyboard
    )
    await state.set_state(AddStageContent.waiting_for_feedback_choice)
    logger.info(f"➡️ Переход в состояние: waiting_for_feedback_choice")

# Обработчик выбора видео
@content_router.message(AddStageContent.waiting_for_video_choice)
async def process_video_choice(message: Message, state: FSMContext):
    """Обработка выбора добавления видео"""
    
    logger.info(f"🎥 Обработка выбора видео: '{message.text}'")
    
    # Проверяем текст сообщения (ИЗМЕНЕНО: новые значения кнопок)
    if message.text == "🎥 Да":
        has_video = True
        await state.update_data(has_video=1, video_url=None)
        logger.info(f"✅ has_video установлено в: {has_video}")
        
        await message.answer(
            "📤 Отправьте видео:",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(AddStageContent.waiting_for_video)
        logger.info(f"➡️ Переход в состояние: waiting_for_video")
        
    elif message.text == "🚫 Нет":
        has_video = False
        await state.update_data(has_video=0, video_url=None)
        logger.info(f"✅ has_video установлено в: {has_video}")
        
        # Переходим к выбору обратной связи (ИЗМЕНЕНО: используем другие эмодзи)
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💬 Да"), KeyboardButton(text="🚫 Нет")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            "📝 Нужна ли обратная связь от пользователя?",
            reply_markup=keyboard
        )
        await state.set_state(AddStageContent.waiting_for_feedback_choice)
        logger.info(f"➡️ Переход в состояние: waiting_for_feedback_choice")
        
    else:
        # Неправильный ввод - показываем клавиатуру снова
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🎥 Да"), KeyboardButton(text="🚫 Нет")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            "❌ Пожалуйста, выберите один из вариантов:",
            reply_markup=keyboard
        )

# Обработчик загрузки видео
@content_router.message(AddStageContent.waiting_for_video, F.content_type == ContentType.VIDEO)
async def process_video_upload(message: Message, state: FSMContext):
    """Обработка загрузки видео"""
    
    logger.info(f"🎥 Получено видео")
    
    # В реальном приложении здесь нужно сохранить файл и получить URL
    # Для демонстрации используем file_id
    video_file_id = message.video.file_id
    await state.update_data(video_url=video_file_id)
    logger.info(f"✅ Видео сохранено, file_id: {video_file_id}")
    
    # Переходим к выбору обратной связи (ИЗМЕНЕНО: используем другие эмодзи)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Да"), KeyboardButton(text="🚫 Нет")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "📝 Нужна ли обратная связь от пользователя?",
        reply_markup=keyboard
    )
    await state.set_state(AddStageContent.waiting_for_feedback_choice)
    logger.info(f"➡️ Переход в состояние: waiting_for_feedback_choice")

# Обработчик выбора обратной связи - ИСПРАВЛЕННЫЙ (без конфликта с stage_management.py)
@content_router.message(AddStageContent.waiting_for_feedback_choice)
async def process_feedback_choice(message: Message, state: FSMContext):
    """Обработка выбора обратной связи"""
    
    logger.info(f"📝 Обработка обратной связи: '{message.text}'")
    
    # Проверяем текст сообщения (ИЗМЕНЕНО: новые значения кнопок)
    if message.text == "💬 Да":
        has_feedback = True
        await state.update_data(has_feedback=1)
        logger.info(f"✅ has_feedback установлено в: {has_feedback}")
        
        await message.answer(
            "🔐 Введите правильный ответ на загадку/вопрос для проверки:",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(AddStageContent.waiting_for_puzzle_answer)
        logger.info(f"➡️ Переход в состояние: waiting_for_puzzle_answer")
        
    elif message.text == "🚫 Нет":
        has_feedback = False
        await state.update_data(has_feedback=0, puzzle_check=None)
        logger.info(f"✅ has_feedback установлено в: {has_feedback}")
        
        # Сохраняем контент без обратной связи
        logger.info("💾 Переход к сохранению контента без обратной связи")
        await save_stage_content(message, state)
        
    else:
        # Неправильный ввод - показываем клавиатуру снова
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💬 Да"), KeyboardButton(text="🚫 Нет")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            "❌ Пожалуйста, выберите один из вариантов:",
            reply_markup=keyboard
        )

# Обработчик ввода ответа на загадку
@content_router.message(AddStageContent.waiting_for_puzzle_answer, F.text)
async def process_puzzle_answer(message: Message, state: FSMContext):
    """Обработка ввода ответа на загадку"""
    
    logger.info(f"🔐 Обработка ответа на загадку: '{message.text}'")
    
    puzzle_answer = message.text.strip()
    
    if len(puzzle_answer) < 1:
        await message.answer("❌ Ответ не может быть пустым. Введите ответ:")
        return
    
    await state.update_data(puzzle_check=puzzle_answer)
    logger.info(f"✅ Ответ на загадку сохранен: '{puzzle_answer}'")
    await save_stage_content(message, state)

async def save_stage_content(message: Message, state: FSMContext):
    """Сохранение контента этапа в базу данных"""
    
    logger.info(f"💾 Начало сохранения контента, состояние: {await state.get_state()}")
    
    try:
        data = await state.get_data()
        logger.info(f"📦 Данные для сохранения: {data}")
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Генерируем message_id
            cursor.execute('SELECT COALESCE(MAX(message_id), 0) + 1 FROM stage_content')
            result = cursor.fetchone()
            message_id = result[0] if result else 1
            logger.info(f"🆔 Сгенерирован message_id: {message_id}")
            
            # Вставляем данные в таблицу stage_content
            cursor.execute('''
                INSERT INTO stage_content (
                    stage_id, message_id, order_number, message_text,
                    has_image, image_url, has_video, video_url,
                    has_feedback, puzzle_check
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['stage_id'],
                message_id,
                data['order_number'],
                data['message_text'],
                data.get('has_image', 0),
                data.get('image_url'),
                data.get('has_video', 0),
                data.get('video_url'),
                data.get('has_feedback', 0),
                data.get('puzzle_check')
            ))
            
            conn.commit()
            logger.info(f"✅ Контент успешно сохранен в БД, message_id: {message_id}")
            
            # Формируем информационное сообщение
            info_message = (
                f"✅ Контент успешно добавлен к этапу!\n\n"
                f"📋 Этап: {data['stage_name']}\n"
                f"🆔 ID этапа: {data['stage_id']}\n"
                f"📝 ID сообщения: {message_id}\n"
                f"🔢 Порядковый номер: {data['order_number']}\n"
            )
            
            if data.get('has_image'):
                info_message += f"🖼️ Изображение: ✅\n"
            if data.get('has_video'):
                info_message += f"🎥 Видео: ✅\n"
            if data.get('has_feedback'):
                info_message += f"📝 Обратная связь: ✅\n"
                info_message += f"🔐 Правильный ответ: {data.get('puzzle_check', 'не указан')}\n"
            
            await message.answer(
                info_message,
                reply_markup=create_content_management_keyboard()
            )
            
            logger.info(
                f"🎉 Успешно добавлен контент: stage_id={data['stage_id']}, "
                f"message_id={message_id}, order={data['order_number']}"
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении контента этапа: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при сохранении контента")
    
    await state.clear()
    logger.info("🧹 Состояние очищено")

# Вспомогательные функции
async def get_user_role(telegram_id: int) -> str:
    """Получить роль пользователя"""
    logger.debug(f"👤 Получение роли пользователя: {telegram_id}")
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT role FROM main WHERE telegram_id = ?', (telegram_id,))
            result = cursor.fetchone()
            role = result[0] if result else 'user'
            logger.debug(f"✅ Роль пользователя {telegram_id}: {role}")
            return role
    except Exception as e:
        logger.error(f"❌ Ошибка при получении роли пользователя: {e}", exc_info=True)
        return 'user'

def create_content_management_keyboard():
    """Создать клавиатуру для управления контентом"""
    logger.debug("⌨️ Создание клавиатуры управления контентом")
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/view_stage_content"), KeyboardButton(text="/add_stage_content")],
            [KeyboardButton(text="/view_message_details"), KeyboardButton(text="/delete_stage_content")],
            [KeyboardButton(text="/edit_stage_content")],
            [KeyboardButton(text="📋 Главное меню")]
        ],
        resize_keyboard=True
    )

# Команда для отмены текущей операции
@content_router.message(Command("cancel"))
async def cancel_operation(message: Message, state: FSMContext):
    """Отмена текущей операции"""
    current_state = await state.get_state()
    logger.info(f"❌ Отмена операции пользователем {message.from_user.id}, состояние: {current_state}")
    
    if current_state is None:
        await message.answer("❌ Нет активной операции для отмены")
        return
    
    await state.clear()
    await message.answer(
        "✅ Операция отменена",
        reply_markup=ReplyKeyboardRemove()
    )
    logger.info("✅ Состояние очищено после отмены")

# Обработчик для всех необработанных сообщений в состоянии выбора обратной связи
@content_router.message(AddStageContent.waiting_for_feedback_choice)
async def unhandled_feedback_choice(message: Message, state: FSMContext):
    """Обработчик для необработанных сообщений в состоянии выбора обратной связи"""
    logger.warning(f"⚠️ Необработанное сообщение в состоянии feedback_choice: '{message.text}'")
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Да"), KeyboardButton(text="🚫 Нет")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "❌ Пожалуйста, выберите один из вариантов:\n"
        "💬 Да - добавить обратную связь\n"
        "🚫 Нет - продолжить без обратной связи",
        reply_markup=keyboard
    )

# Обработчик для всех необработанных сообщений в состоянии ввода ответа на загадку
@content_router.message(AddStageContent.waiting_for_puzzle_answer)
async def unhandled_puzzle_answer(message: Message, state: FSMContext):
    """Обработчик для необработанных сообщений в состоянии ввода ответа на загадку"""
    logger.warning(f"⚠️ Необработанное сообщение в состоянии puzzle_answer: '{message.text}', тип: {message.content_type}")
    
    await message.answer(
        "❌ Пожалуйста, введите текстовый ответ на загадку/вопрос.\n"
        "Ответ будет использоваться для проверки правильности ответов пользователей."
    )

# Функция для настройки обработчиков
def setup_stage_content_handlers(dp):
    """Настройка обработчиков контента этапов"""
    logger.info("🔧 Настройка обработчиков контента этапов")
    dp.include_router(content_router)

if __name__ == "__main__":
    logger.info("🚀 Модуль stage_content_handlers загружен")
