import asyncio
import logging
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from database import db

# Импортируем обработчики всех этапов
from .stage_1 import handle_stage_1_quest
from .stage_2 import handle_stage_2_quest
from .stage_3 import handle_stage_3_quest
from .stage_4 import handle_stage_4_quest

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
            # ✅ ИСПРАВЛЕНИЕ: Преобразуем в int, если результат есть
            if result and result[0] is not None:
                return int(result[0])  # Преобразуем в число
            return 1  # По умолчанию начинаем с 1 этапа
    except Exception as e:
        logging.error(f"Ошибка получения текущего этапа для {telegram_id}: {e}")
        return 1

async def update_user_stage(telegram_id: int, new_stage: int) -> bool:
    """Обновляет текущий этап пользователя в БД"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE main SET current_stage = ? WHERE telegram_id = ?",
                (new_stage, telegram_id)
            )
            conn.commit()
            logging.info(f"Обновлен этап пользователя {telegram_id} на {new_stage}")
            return True
    except Exception as e:
        logging.error(f"Ошибка обновления этапа для {telegram_id}: {e}")
        return False

async def handle_stage_5_quest(callback_query: CallbackQuery, state: FSMContext):
    """Автоматический переход по этапам для stage_id = 5"""
    try:
        telegram_id = callback_query.from_user.id
        
        # Получаем текущий этап пользователя
        current_stage = await get_user_current_stage(telegram_id)
        
        # Сохраняем текущий этап в состоянии
        await state.update_data(
            telegram_id=telegram_id,
            current_stage=current_stage,
            is_stage_5_user=True  # Флаг что это пользователь 5-го этапа
        )
        
        # ✅ ИСПРАВЛЕНИЕ: Убеждаемся, что current_stage - число
        logging.info(f"Пользователь {telegram_id} продолжает с этапа {current_stage} (тип: {type(current_stage)})")
        
        # Автоматически запускаем соответствующий этап
        if current_stage == 1:
            await handle_stage_1_quest(callback_query, state)
        elif current_stage == 2:
            await handle_stage_2_quest(callback_query, state)
        elif current_stage == 3:
            await handle_stage_3_quest(callback_query, state)
        elif current_stage == 4:
            await handle_stage_4_quest(callback_query, state)
        else:
            # Если все этапы пройдены
            await callback_query.message.answer(
                "🎉 *ПОЗДРАВЛЯЕМ!* Вы прошли все этапы квеста!\n\n"
                "✨ Вы вернули все реликвии и спасли Новый год!\n\n"
                "💫 Спасибо за участие в этом невероятном приключении!",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logging.error(f"Ошибка в stage_5: {e}")
        await callback_query.message.answer("❌ Произошла ошибка. Попробуйте позже.")

def setup_stage_5_handlers(dp):
    """Настройка обработчиков для этапа 5"""
    # Обработчик запуска 5-го этапа
    # (добавляется в основном файле вместе с другими этапами)
    pass
