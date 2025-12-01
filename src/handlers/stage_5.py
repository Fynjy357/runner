# src/handlers/stage_5.py
import asyncio
import logging
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from database import db
from pathlib import Path

# ✅ ПРАВИЛЬНЫЕ ПУТИ
PROJECT_ROOT = Path(__file__).parent.parent
MEDIA_PATH = PROJECT_ROOT / "media"

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
            if result and result[0] is not None:
                return int(result[0])
            return 1
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

async def save_user_address_to_db(telegram_id: int, address: str, stage: int) -> bool:
    """Сохраняет адрес пользователя в таблицу user_addresses"""
    try:
        username = None
        
        success = db.save_user_address(telegram_id, username, address, stage)
        if success:
            logging.info(f"✅ Адрес сохранен для пользователя {telegram_id}: {address} (этап {stage})")
            return True
        else:
            logging.error(f"❌ Ошибка сохранения адреса для пользователя {telegram_id} (этап {stage})")
            return False
            
    except Exception as e:
        logging.error(f"❌ Ошибка при сохранении адреса пользователя {telegram_id} (этап {stage}): {e}")
        return False

async def send_optimized_video_directly(message_or_callback, video_filename: str):
    """✅ ОПТИМИЗИРОВАННАЯ отправка видео напрямую через FSInputFile"""
    try:
        video_path = MEDIA_PATH / video_filename
        
        if not video_path.exists():
            logging.error(f"❌ Видео файл не найден: {video_path}")
            return False
        
        video = FSInputFile(video_path)
        
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer_video(
                video=video,
                supports_streaming=True
            )
        else:
            await message_or_callback.message.answer_video(
                video=video,
                supports_streaming=True
            )
        
        logging.info(f"✅ Видео {video_filename} отправлено успешно")
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка отправки видео {video_filename}: {e}")
        return False

async def handle_stage_5_address(message: Message, state: FSMContext):
    """✅ ОПТИМИЗИРОВАННАЯ обработка адреса для stage_5"""
    logger = logging.getLogger('bot')
    try:
        user_data = await state.get_data()
        telegram_id = user_data.get('telegram_id', message.from_user.id)
        current_stage = user_data.get('current_stage', 1)
        
        address = message.text.strip()
        
        # ✅ ПРОВЕРКА АДРЕСА
        if not address or len(address) < 5:
            await message.answer(
                "❌ *Пожалуйста, укажите полный адрес.*\n\n"
                "💡 *Пример:* г. Москва, ул. Пушкина, д. 10, ПВЗ СДЭК №123\n\n"
                "📝 *Напишите адрес еще раз:*",
                parse_mode="Markdown"
            )
            return
        
        # ✅ СОХРАНЕНИЕ АДРЕСА
        success = await save_user_address_to_db(telegram_id, address, stage=current_stage)
        
        if not success:
            await message.answer(
                "❌ *Произошла ошибка при сохранении адреса.*\n\n"
                "🔄 Пожалуйста, попробуйте отправить адрес еще раз:",
                parse_mode="Markdown"
            )
            return
        
        # ✅ УСПЕШНОЕ СОХРАНЕНИЕ
        await message.answer(
            "✅ *Адрес успешно сохранен!*\n\n"
            "📦 Ваша реликвия будет доставлена по указанному адресу.",
            parse_mode="Markdown"
        )
        await asyncio.sleep(2)
        
        # ✅ ОБНОВЛЕНИЕ ЭТАПА И ПЕРЕХОД
        next_stage = current_stage + 1
        
        if next_stage <= 4:
            await update_user_stage(telegram_id, next_stage)
            
            stage_names = {1: "первый", 2: "второй", 3: "третий", 4: "четвертый"}
            
            await message.answer(
                f"🎉 *Этап {current_stage} завершен!*\n\n"
                f"🔄 *Автоматически запускаю {stage_names[next_stage]} этап...*",
                parse_mode="Markdown"
            )
            await asyncio.sleep(2)
            
            # ✅ ЗАПУСК СЛЕДУЮЩЕГО ЭТАПА
            stage_handlers = {
                1: handle_stage_1_quest,
                2: handle_stage_2_quest, 
                3: handle_stage_3_quest,
                4: handle_stage_4_quest
            }
            
            handler = stage_handlers.get(next_stage)
            if handler:
                # Создаем fake callback для запуска
                class FakeCallback:
                    def __init__(self, message):
                        self.message = message
                        self.from_user = message.from_user
                
                fake_callback = FakeCallback(message)
                await handler(fake_callback, state)
                
        else:
            # ✅ ФИНАЛЬНОЕ ЗАВЕРШЕНИЕ
            await update_user_stage(telegram_id, 5)
            
            await message.answer(
                "🎊 *УРА! ВСЕ ЭТАПЫ ПРОЙДЕНЫ!*\n\n"
                "✨ *Вы вернули все пропавшие реликвии и спасли Новый год!*\n\n"
                "🏆 *Все реликвии будут доставлены по указанным адресам!*\n\n"
                "💫 *Спасибо за участие в этом невероятном приключении!*",
                parse_mode="Markdown"
            )
            
            await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке адреса stage_5: {e}")
        await message.answer(
            "❌ *Произошла ошибка при обработке адреса.*\n\n"
            "🔄 Пожалуйста, попробуйте отправить адрес еще раз:",
            parse_mode="Markdown"
        )

async def handle_stage_5_riddle_answer(message: Message, state: FSMContext):
    """✅ ОПТИМИЗИРОВАННАЯ обработка ответов на загадки для stage_5"""
    logger = logging.getLogger('bot')
    try:
        user_data = await state.get_data()
        telegram_id = user_data.get('telegram_id', message.from_user.id)
        current_stage = user_data.get('current_stage', 1)
        attempts_left = user_data.get('attempts_left', 3)
        
        # ✅ ПРАВИЛЬНЫЕ ОТВЕТЫ И ПОДСКАЗКИ
        stage_data = {
            1: {"answer": "маяк", "hint": "МА..", "promo": "RUNNER2025"},
            2: {"answer": "компас", "hint": "КОМП..", "promo": "GUARDIAN2025"}, 
            3: {"answer": "магнитофон", "hint": "МАГНИТ....", "promo": "SAVIOR2025"},
            4: {"answer": "очередь", "hint": "ОЧЕР..", "promo": "HERO2025"}
        }
        
        stage_info = stage_data.get(current_stage, {})
        user_answer = message.text.strip().lower()
        
        if user_answer == stage_info.get("answer", ""):
            # ✅ ПРАВИЛЬНЫЙ ОТВЕТ
            trophy_messages = {
                1: f"🎉 *Поздравляем! Вы отгадали загадку!*\n\n🏆 *Первый трофей!*\n\n🎁 *Промокод: {stage_info['promo']}*\nСкидка 20% на следующий этап!",
                2: f"🎉 *Поздравляем! Вы отгадали загадку!*\n\n🏆 *Второй трофей!*\n\n🎁 *Промокод: {stage_info['promo']}*\nСкидка 20% на следующий этап!",
                3: f"🎉 *Поздравляем! Вы отгадали загадку!*\n\n🏆 *Третий трофей!*\n\n🎁 *Промокод: {stage_info['promo']}*\nСкидка 20% на следующий этап!",
                4: f"🎉 *Поздравляем! Вы отгадали загадку!*\n\n🏆 *Четвертый трофей!*\n\n🎁 *Промокод: {stage_info['promo']}*\nСкидка 20% на следующий этап!"
            }
            
            await message.answer(trophy_messages.get(current_stage, "🎉 Поздравляем!"), parse_mode="Markdown")
            await asyncio.sleep(3)
            
            # ✅ ЗАПРОС АДРЕСА
            await message.answer(
                "📍 *Свою реликвию ты можешь получить здесь*\n\n"
                "📦 Напишите адрес ближайшего ПВЗ СДЭК или Яндекс Маркет:\n\n"
                "💡 *Пример:* г. Москва, ул. Пушкина, д. 10, ПВЗ СДЭК №123",
                parse_mode="Markdown"
            )
            
            await state.update_data(
                riddle_solved=True,
                telegram_id=telegram_id,
                current_stage=current_stage,
                attempts_left=3  # Сбрасываем попытки
            )
            
        else:
            # ❌ НЕПРАВИЛЬНЫЙ ОТВЕТ
            attempts_left -= 1
            
            if attempts_left > 0:
                await message.answer(
                    f"❌ *Неправильный ответ.*\n\n"
                    f"📝 *Попыток осталось: {attempts_left} из 3*\n\n"
                    f"💡 Попробуйте еще раз:",
                    parse_mode="Markdown"
                )
                await state.update_data(attempts_left=attempts_left)
            else:
                # ✅ ПОСЛЕДНЯЯ ПОПЫТКА С ПОДСКАЗКОЙ
                await message.answer(
                    f"❌ *Неправильный ответ.*\n\n"
                    f"💡 *Подсказка:* {stage_info.get('hint', '')}\n\n"
                    f"📝 *Попробуйте еще раз:*",
                    parse_mode="Markdown"
                )
                await state.update_data(attempts_left=1)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке ответа stage_5: {e}")
        await message.answer("❌ Ошибка при обработке ответа. Попробуйте еще раз.")

async def handle_stage_5_quest(callback_query: CallbackQuery, state: FSMContext):
    """✅ ОПТИМИЗИРОВАННЫЙ запуск stage_5 с автоматическим переходом по этапам"""
    try:
        telegram_id = callback_query.from_user.id
        
        # ✅ ПОЛУЧАЕМ ТЕКУЩИЙ ЭТАП
        current_stage = await get_user_current_stage(telegram_id)
        
        # ✅ СОХРАНЯЕМ ДАННЫЕ В СОСТОЯНИИ
        await state.update_data(
            telegram_id=telegram_id,
            current_stage=current_stage,
            is_stage_5_user=True,
            attempts_left=3
        )
        
        logging.info(f"🚀 Пользователь {telegram_id} продолжает с этапа {current_stage}")
        
        # ✅ АВТОМАТИЧЕСКИЙ ЗАПУСК ЭТАПА
        stage_handlers = {
            1: handle_stage_1_quest,
            2: handle_stage_2_quest,
            3: handle_stage_3_quest, 
            4: handle_stage_4_quest
        }
        
        handler = stage_handlers.get(current_stage)
        
        if handler:
            await handler(callback_query, state)
        else:
            # ✅ ВСЕ ЭТАПЫ ПРОЙДЕНЫ
            await callback_query.message.answer(
                "🎉 *ПОЗДРАВЛЯЕМ!* Вы прошли все этапы квеста!\n\n"
                "✨ Вы вернули все реликвии и спасли Новый год!\n\n"
                "💫 Спасибо за участие в этом невероятном приключении!",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logging.error(f"Ошибка в stage_5: {e}")
        await callback_query.message.answer("❌ Произошла ошибка. Попробуйте позже.")

async def handle_wrong_stage_5_input(message: Message, state: FSMContext):
    """Обработчик некорректных сообщений для stage_5"""
    user_data = await state.get_data()
    current_stage = user_data.get('current_stage', 1)
    
    if current_stage in [1, 2, 3, 4]:
        # Пользователь находится в процессе этапа
        await message.answer(
            "💡 *Сейчас вам нужно ответить на загадку.*\n\n"
            "📝 Напишите ответ на загадку текущего этапа.",
            parse_mode="Markdown"
        )
    else:
        # Все этапы пройдены
        await message.answer(
            "🎉 *Поздравляем! Вы прошли все этапы квеста!*\n\n"
            "✨ Ожидайте доставки ваших реликвий.",
            parse_mode="Markdown"
        )

def setup_stage_5_handlers(dp):
    """Настройка обработчиков для этапа 5"""
    # ✅ Обработчик ответов на загадки
    dp.message.register(
        handle_stage_5_riddle_answer,
        lambda message: message.text and not message.text.startswith('/')
    )
    
    # ✅ Обработчик адресов
    dp.message.register(
        handle_stage_5_address,
        lambda message: message.text and not message.text.startswith('/')
    )
    
    # ✅ Обработчик некорректных сообщений
    dp.message.register(
        handle_wrong_stage_5_input
    )

# ✅ НАСТРОЙКА ЛОГИРОВАНИЯ
logger = logging.getLogger('bot')
if not logger.handlers:
    import os
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/stage_5.log', encoding='utf-8', mode='a')
        ]
    )
