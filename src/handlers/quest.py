# quest.py
import asyncio
import logging
from aiogram.types import CallbackQuery
from aiogram import F
from aiogram.fsm.context import FSMContext
from database import db

# Импортируем обработчики этапов
from .stage_1 import handle_stage_1_quest, setup_stage_1_handlers
from .stage_2 import handle_stage_2_quest, setup_stage_2_handlers
from .stage_3 import handle_stage_3_quest, setup_stage_3_handlers
from .stage_4 import handle_stage_4_quest, setup_stage_4_handlers
from .stage_5 import handle_stage_5_quest, setup_stage_5_handlers

def setup_quest_handler(dp, logger: logging.Logger):
    """Настройка обработчиков квеста"""
    
    async def get_user_stage_id(telegram_id: int):
        """Получить stage_id пользователя из manual_upload через main"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT mu.stage_id 
                    FROM main m
                    JOIN manual_upload mu ON m.participant_id = mu.participant_id
                    WHERE m.telegram_id = ?
                ''', (telegram_id,))
                
                result = cursor.fetchone()
                return result[0] if result else None
                
        except Exception as e:
            logger.error(f"Ошибка при получении stage_id пользователя {telegram_id}: {e}")
            return None

    async def record_quest_start(telegram_id: int, logger: logging.Logger):
        """Запись в БД о начале квеста"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE main 
                    SET quest_started = 1, quest_started_at = CURRENT_TIMESTAMP
                    WHERE telegram_id = ?
                ''', (telegram_id,))
                
                conn.commit()
                logger.info(f"Записано начало квеста для пользователя {telegram_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при записи начала квеста в БД: {e}")
            return False

    async def get_user_current_stage(telegram_id: int) -> int:
        """Получает текущий этап пользователя из БД"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT current_stage FROM main WHERE telegram_id = ?",
                    (telegram_id,)
                )
                result = cursor.fetchone()
                # ✅ ИСПРАВЛЕНИЕ: Преобразуем в int
                if result and result[0] is not None:
                    return int(result[0])
                return 1
        except Exception as e:
            logger.error(f"Ошибка получения current_stage для {telegram_id}: {e}")
            return 1

    async def continue_from_current_stage(callback_query: CallbackQuery, state: FSMContext, current_stage: int):
        """Продолжает квест с текущего этапа для пользователей stage_5"""
        try:
            stage_handlers = {
                1: handle_stage_1_quest,
                2: handle_stage_2_quest,
                3: handle_stage_3_quest,
                4: handle_stage_4_quest
            }
            
            handler = stage_handlers.get(current_stage)
            if handler:
                await callback_query.message.answer(
                    f"🔄 *Продолжаем с этапа {current_stage}...*",
                    parse_mode="Markdown"
                )
                await asyncio.sleep(1)
                await handler(callback_query, state)
            else:
                await handle_stage_1_quest(callback_query, state)
        except Exception as e:
            logger.error(f"Ошибка продолжения квеста с этапа {current_stage}: {e}")
            await handle_stage_1_quest(callback_query, state)

    async def handle_start_quest(callback_query: CallbackQuery, state: FSMContext):
        """Обработка нажатия кнопки 'начать квест'"""
        try:
            await callback_query.answer()
            
            telegram_id = callback_query.from_user.id
            
            # Удаляем предыдущие сообщения
            chat_id = callback_query.message.chat.id
            message_id = callback_query.message.message_id
            
            await callback_query.message.delete()
            
            # Удаляем предыдущие сообщения
            for i in range(1, 4):
                try:
                    await callback_query.bot.delete_message(chat_id, message_id - i)
                except Exception:
                    pass
            
            # Получаем stage_id пользователя
            stage_id = await get_user_stage_id(telegram_id)
            
            if stage_id is None:
                logger.warning(f"Пользователь {telegram_id} не найден в manual_upload")
                await callback_query.message.answer(
                    "❌ Не удалось определить ваш этап квеста. Обратитесь к организаторам."
                )
                return
            
            # ✅ ДОБАВЛЯЕМ: Для пользователей 5-го этапа проверяем current_stage
            if stage_id == 5:
                current_stage = await get_user_current_stage(telegram_id)
                if current_stage > 1:
                    # Пользователь уже начал квест, продолжаем с текущего этапа
                    await continue_from_current_stage(callback_query, state, current_stage)
                    return
            
            # Записываем в БД о начале квеста
            success = await record_quest_start(telegram_id, logger)
            
            if not success:
                await callback_query.message.answer("❌ Ошибка при начале квеста. Попробуйте позже.")
                return
            
            logger.info(f"Пользователь {telegram_id} (stage_id: {stage_id}) начал квест")
            
            # ✅ ДОБАВЛЯЕМ: Для stage_5 всегда начинаем с этапа 1
            actual_stage = 1 if stage_id == 5 else stage_id
            
            # Выбираем сценарий в зависимости от actual_stage
            stage_handlers = {
                1: handle_stage_1_quest,
                2: handle_stage_2_quest,
                3: handle_stage_3_quest,
                4: handle_stage_4_quest,
                5: handle_stage_1_quest  # Для stage_5 начинаем с этапа 1
            }
            
            handler = stage_handlers.get(actual_stage)
            if handler:
                await handler(callback_query, state)
            else:
                # Дефолтный обработчик для неизвестных этапов
                await handle_stage_1_quest(callback_query, state)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке начала квеста: {e}")
            await callback_query.message.answer("❌ Произошла ошибка при начале квеста. Попробуйте позже.")

    # Регистрируем обработчик
    dp.callback_query.register(handle_start_quest, F.data == "start_quest")
    
    # Регистрируем обработчики для этапа 1
    setup_stage_1_handlers(dp)
    # Регистрируем обработчики для этапа 2
    setup_stage_2_handlers(dp)
    # Регистрируем обработчики для этапа 3
    setup_stage_3_handlers(dp)
    # Регистрируем обработчики для этапа 4
    setup_stage_4_handlers(dp)
    # Регистрируем обработчики для этапа 5
    setup_stage_5_handlers(dp)
