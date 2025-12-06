# src/handlers/stage_5.py
import asyncio
import logging
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import F
from database import db
from pathlib import Path

# ✅ ПРАВИЛЬНЫЕ ПУТИ
PROJECT_ROOT = Path(__file__).parent.parent
MEDIA_PATH = PROJECT_ROOT / "media"

# Импортируем обработчики всех этапов
from .stage_1 import Stage1States, handle_stage_1_quest
from .stage_2 import Stage2States, handle_stage_2_quest
from .stage_3 import Stage3States, handle_stage_3_quest
from .stage_4 import Stage4States, handle_stage_4_quest

# ✅ СОЗДАЕМ СОСТОЯНИЯ ДЛЯ STAGE_5
class Stage5States(StatesGroup):
    waiting_for_riddle_answer = State()
    waiting_for_address = State()

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

async def is_stage_completed(telegram_id: int, stage: int) -> bool:
    """Проверяет, завершен ли конкретный этап для пользователя"""
    try:
        return db.is_stage_completed(telegram_id, stage)
    except Exception as e:
        logging.error(f"Ошибка проверки завершения этапа {stage}: {e}")
        return False

async def get_next_uncompleted_stage(telegram_id: int) -> int:
    """Находит следующий незавершенный этап для пользователя"""
    try:
        # Проверяем этапы по порядку
        for stage in range(1, 5):  # Этапы 1-4
            completed = await is_stage_completed(telegram_id, stage)
            if not completed:
                return stage
        # Если все этапы завершены
        return 5
    except Exception as e:
        logging.error(f"Ошибка поиска незавершенного этапа для {telegram_id}: {e}")
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
    """✅ ОПТИМИЗИРОВАННАЯ обработка адреса для stage_5 с исправлением конфликтов состояний"""
    logger = logging.getLogger('bot')
    logger.info(f"🔍 [STAGE_5_ADDRESS] Начало обработки адреса для пользователя {message.from_user.id}")
    
    try:
        # Получаем данные состояния
        user_data = await state.get_data()
        telegram_id = user_data.get('telegram_id', message.from_user.id)
        current_stage = user_data.get('current_stage', 1)
        is_stage_5_user = user_data.get('is_stage_5_user', True)
        
        logger.info(f"🔍 [STAGE_5_ADDRESS] Данные: telegram_id={telegram_id}, current_stage={current_stage}, is_stage_5_user={is_stage_5_user}")
        
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
        
        # ✅ ОТМЕЧАЕМ ЭТАП КАК ЗАВЕРШЕННЫЙ
        if current_stage <= 4:
            try:
                success = db.mark_stage_completed(telegram_id, current_stage)
                if success:
                    logger.info(f"✅ Этап {current_stage} отмечен как завершенный для пользователя {telegram_id}")
                else:
                    logger.error(f"❌ Не удалось отметить этап {current_stage} как завершенный")
            except Exception as e:
                logger.error(f"❌ Ошибка отметки завершения этапа {current_stage}: {e}")
        
        # ✅ ВАЖНОЕ ИСПРАВЛЕНИЕ: ПРИНУДИТЕЛЬНАЯ ОЧИСТКА СОСТОЯНИЙ ПЕРЕД ПЕРЕХОДОМ
        # 1. Сначала очищаем текущее состояние
        await state.clear()
        
        # 2. Затем принудительно очищаем в storage (для всех возможных состояний этапов)
        try:
            from aiogram.fsm.storage.base import StorageKey
            storage = state.storage
            
            # Создаем ключ пользователя
            try:
                user_key = StorageKey(
                    chat_id=telegram_id,
                    user_id=telegram_id,
                    bot_id=storage.bot.id
                )
            except AttributeError:
                user_key = StorageKey(
                    chat_id=telegram_id,
                    user_id=telegram_id,
                    bot_id=telegram_id
                )
            
            # Очищаем состояние
            await storage.set_state(key=user_key, state=None)
            await storage.set_data(key=user_key, data={})
            
            logger.info(f"✅ Состояние пользователя {telegram_id} полностью очищено в storage")
            
        except Exception as storage_error:
            logger.error(f"⚠️ Ошибка очистки storage: {storage_error}")
            # Продолжаем работу даже если очистка storage не удалась
        
        # ✅ НАХОДИМ СЛЕДУЮЩИЙ НЕЗАВЕРШЕННЫЙ ЭТАП
        next_stage = await get_next_uncompleted_stage(telegram_id)
        logger.info(f"🔍 [STAGE_5_ADDRESS] Следующий незавершенный этап: {next_stage}")
        
        if next_stage <= 4:
            # ✅ ВАЖНОЕ ИСПРАВЛЕНИЕ: ОБНОВЛЯЕМ ТЕКУЩИЙ ЭТАП В БАЗЕ ДАННЫХ
            await update_user_stage(telegram_id, next_stage)
            
            stage_names = {1: "первый", 2: "второй", 3: "третий", 4: "четвертый"}
            
            await message.answer(
                f"🎉 *Этап {current_stage} завершен!*\n\n"
                f"🔄 *Автоматически запускаю {stage_names[next_stage]} этап...*",
                parse_mode="Markdown"
            )
            await asyncio.sleep(2)
            
            # ✅ ВАЖНОЕ ИСПРАВЛЕНИЕ: ПЕРЕДАЕМ СВЕЖИЙ STATE В ОБРАБОТЧИК ЭТАПА
            
            # Создаем fake callback для запуска
            class FakeCallback:
                def __init__(self, message):
                    self.message = message
                    self.from_user = message.from_user
            
            fake_callback = FakeCallback(message)
            
            # ✅ ВАЖНОЕ ИСПРАВЛЕНИЕ: Передаем СОЗДАННЫЙ НОВЫЙ STATE, а не текущий
            # Создаем новый FSMContext для следующего этапа
            from aiogram.fsm.context import FSMContext
            from aiogram.fsm.storage.base import StorageKey
            
            try:
                storage = state.storage
                user_key = StorageKey(
                    chat_id=telegram_id,
                    user_id=telegram_id,
                    bot_id=storage.bot.id
                )
                fresh_state = FSMContext(storage=storage, key=user_key)
                
                # ✅ УСТАНАВЛИВАЕМ ФЛАГ ДЛЯ STAGE_5 ПОЛЬЗОВАТЕЛЯ
                await fresh_state.update_data(
                    is_stage_5_user=True,
                    telegram_id=telegram_id,
                    current_stage=next_stage,
                    attempts_left=3
                )
                
                logger.info(f"✅ Создан новый state для этапа {next_stage} с флагом stage_5")
                
            except Exception as state_error:
                logger.error(f"❌ Ошибка создания нового state: {state_error}")
                fresh_state = state  # Используем текущий state как fallback
            
            # ✅ ЗАПУСК СЛЕДУЮЩЕГО ЭТАПА
            stage_handlers = {
                1: handle_stage_1_quest,
                2: handle_stage_2_quest, 
                3: handle_stage_3_quest,
                4: handle_stage_4_quest
            }
            
            handler = stage_handlers.get(next_stage)
            if handler:
                try:
                    await handler(fake_callback, fresh_state)
                    logger.info(f"✅ Этап {next_stage} успешно запущен для пользователя {telegram_id}")
                except Exception as handler_error:
                    logger.error(f"❌ Ошибка запуска обработчика этапа {next_stage}: {handler_error}")
                    
                    # ✅ РЕЗЕРВНЫЙ ВАРИАНТ: Попробуем запустить обработчик напрямую
                    try:
                        # Создаем новое сообщение для запуска
                        backup_message = Message(
                            message_id=message.message_id,
                            date=message.date,
                            chat=message.chat,
                            from_user=message.from_user,
                            text="/menu"
                        )
                        
                        # Имитируем нажатие кнопки меню
                        from aiogram.types import CallbackQuery
                        fake_callback = CallbackQuery(
                            id="backup_callback",
                            from_user=message.from_user,
                            chat_instance="backup",
                            message=message,
                            data=f"stage_{next_stage}"
                        )
                        
                        await handler(fake_callback, fresh_state)
                        
                    except Exception as backup_error:
                        logger.error(f"❌ Ошибка резервного запуска: {backup_error}")
                        await message.answer(
                            f"❌ Ошибка при запуске этапа {next_stage}. Используйте /menu для перехода к этапам.",
                            parse_mode="Markdown"
                        )
            else:
                logger.error(f"❌ Не найден обработчик для этапа {next_stage}")
                await message.answer(
                    "❌ Ошибка при переходе к следующему этапу. Используйте /menu.",
                    parse_mode="Markdown"
                )
                
        else:
            # ✅ ФИНАЛЬНОЕ ЗАВЕРШЕНИЕ
            await update_user_stage(telegram_id, 5)
            
            # ✅ ПРИНУДИТЕЛЬНОЕ ОЧИЩЕНИЕ ВСЕХ СОСТОЯНИЙ ПОСЛЕ ЗАВЕРШЕНИЯ
            try:
                from aiogram.fsm.storage.base import StorageKey
                storage = state.storage
                
                user_key = StorageKey(
                    chat_id=telegram_id,
                    user_id=telegram_id,
                    bot_id=storage.bot.id if hasattr(storage, 'bot') else telegram_id
                )
                
                # Очищаем все возможные состояния
                await storage.set_state(key=user_key, state=None)
                await storage.set_data(key=user_key, data={})
                
            except Exception as final_clear_error:
                logger.error(f"⚠️ Ошибка финальной очистки: {final_clear_error}")
            
            await message.answer(
                "🎊 *УРА! ВСЕ ЭТАПЫ ПРОЙДЕНЫ!*\n\n"
                "✨ *Вы вернули все пропавшие реликвии и спасли Новый год!*\n\n"
                "🏆 *Все реликвии будут доставлены по указанным адресам!*\n\n"
                "💫 *Спасибо за участие в этом невероятном приключении!*",
                parse_mode="Markdown"
            )
            
            logger.info(f"✅ Пользователь {telegram_id} завершил все этапы!")
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при обработке адреса stage_5: {e}", exc_info=True)
        
        # ✅ ПРИНУДИТЕЛЬНАЯ ОЧИСТКА ПРИ ОШИБКЕ
        try:
            await state.clear()
        except Exception as clear_error:
            logger.error(f"❌ Ошибка при очистке состояния: {clear_error}")
        
        await message.answer(
            "❌ *Произошла критическая ошибка при обработке адреса.*\n\n"
            "🔄 Пожалуйста, попробуйте еще раз или используйте /menu для перехода к этапам.",
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
            1: {"answer": "маяк", "hint": "МА.."},
            2: {"answer": "компас", "hint": "КОМП.."}, 
            3: {"answer": "магнитофон", "hint": "МАГНИТ...."},
            4: {"answer": "очередь", "hint": "ОЧЕР.."}
        }
        
        stage_info = stage_data.get(current_stage, {})
        user_answer = message.text.strip().lower()
        
        if user_answer == stage_info.get("answer", ""):
            # ✅ ПРАВИЛЬНЫЙ ОТВЕТ
            trophy_messages = {
                1: f"🎉 *Поздравляем! Вы отгадали загадку!*\n\n🏆 *Первый трофей!*\n\n",
                2: f"🎉 *Поздравляем! Вы отгадали загадку!*\n\n🏆 *Второй трофей!*\n\n",
                3: f"🎉 *Поздравляем! Вы отгадали загадку!*\n\n🏆 *Третий трофей!*\n\n",
                4: f"🎉 *Поздравляем! Вы отгадали загадку!*\n\n🏆 *Четвертый трофей!*\n\n"
            }
            
            await message.answer(trophy_messages.get(current_stage, "🎉 Поздравляем!"), parse_mode="Markdown")
            await asyncio.sleep(3)
            
            # ✅ ЗАПРОС АДРЕСА И ПЕРЕХОД В СОСТОЯНИЕ ОЖИДАНИЯ АДРЕСА
            await message.answer(
                "📍 *Свою реликвию ты можешь получить здесь*\n\n"
                "📦 Напишите адрес ближайшего ПВЗ СДЭК или Яндекс Маркет:\n\n"
                "💡 *Пример:* г. Москва, ул. Пушкина, д. 10, ПВЗ СДЭК №123",
                parse_mode="Markdown"
            )
            
            # ✅ ПЕРЕХОДИМ В СОСТОЯНИЕ ОЖИДАНИЯ АДРЕСА
            await state.set_state(Stage5States.waiting_for_address)
            
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
    """✅ ОПТИМИЗИРОВАННЫЙ запуск stage_5 с автоматическим переходом по этапам и сбросом состояний"""
    try:
        telegram_id = callback_query.from_user.id
        
        # ✅ НАХОДИМ СЛЕДУЮЩИЙ НЕЗАВЕРШЕННЫЙ ЭТАП
        next_stage = await get_next_uncompleted_stage(telegram_id)
        
        logging.info(f"🚀 Пользователь {telegram_id}: следующий незавершенный этап = {next_stage}")
        
        if next_stage <= 4:
            # ✅ ВАЖНО: Сбрасываем состояние перед переходом на новый этап
            await state.clear()
            
            # ✅ СОХРАНЯЕМ ДАННЫЕ В СОСТОЯНИИ
            await state.update_data(
                telegram_id=telegram_id,
                current_stage=next_stage,
                is_stage_5_user=True,  # ✅ Устанавливаем флаг stage_5
                attempts_left=3
            )
            
            # ✅ УСТАНАВЛИВАЕМ КОРРЕКТНОЕ СОСТОЯНИЕ ДЛЯ НОВОГО ЭТАПА
            stage_states = {
                1: Stage1States.waiting_for_image,
                2: Stage2States.waiting_for_image,
                3: Stage3States.waiting_for_image,
                4: Stage4States.waiting_for_image
            }
            
            stage_state = stage_states.get(next_stage)
            if stage_state:
                await state.set_state(stage_state)
                logging.info(f"🔄 Установлено состояние для этапа {next_stage}: {stage_state}")
            else:
                await callback_query.message.answer(
                    "❌ *Ошибка:* Не удалось определить состояние для этапа.",
                    parse_mode="Markdown"
                )
                return
            
            # ✅ ЗАПУСКАЕМ НУЖНЫЙ ЭТАП
            stage_handlers = {
                1: handle_stage_1_quest,
                2: handle_stage_2_quest,
                3: handle_stage_3_quest,
                4: handle_stage_4_quest
            }
            
            handler = stage_handlers.get(next_stage)
            if handler:
                await handler(callback_query, state)
            else:
                await callback_query.message.answer(
                    "❌ *Ошибка:* Не удалось найти обработчик для этапа.",
                    parse_mode="Markdown"
                )
        else:
            # ✅ ВСЕ ЭТАПЫ ПРОЙДЕНЫ
            await state.clear()  # Очищаем состояние, так как квест завершен
            await callback_query.message.answer(
                "🎉 *ПОЗДРАВЛЯЕМ!* Вы прошли все этапы квеста!\n\n"
                "✨ Вы вернули все реликвии и спасли Новый год!\n\n"
                "💫 Спасибо за участие в этом невероятном приключении!",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logging.error(f"Ошибка в stage_5: {e}")
        await state.clear()  # Очищаем состояние в случае ошибки
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
    from aiogram import F
    
    # ✅ Обработчик ответов на загадки - ТОЛЬКО в состоянии waiting_for_riddle_answer
    dp.message.register(
        handle_stage_5_riddle_answer,
        F.state(Stage5States.waiting_for_riddle_answer),
        F.text & ~F.text.startswith('/')
    )
    
    # ✅ Обработчик адресов - ТОЛЬКО в состоянии waiting_for_address
    dp.message.register(
        handle_stage_5_address,
        F.state(Stage5States.waiting_for_address),
        F.text & ~F.text.startswith('/')
    )
    
    # ✅ Обработчик некорректных сообщений в состояниях stage_5
    dp.message.register(
        handle_wrong_stage_5_input,
        F.state(Stage5States.waiting_for_riddle_answer) | F.state(Stage5States.waiting_for_address),
        ~F.text  # Все что не текст
    )
    
    logger = logging.getLogger('bot')
    logger.info("✅ Обработчики этапа 5 настроены с состояниями")

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
