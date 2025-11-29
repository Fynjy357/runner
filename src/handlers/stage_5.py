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

async def save_user_address_to_db(telegram_id: int, address: str, stage: int) -> bool:
    """Сохраняет адрес пользователя в таблицу user_addresses"""
    try:
        username = None  # Можно добавить получение username из состояния если нужно
        
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

async def handle_stage_5_address(message: Message, state: FSMContext):
    """Обработка адреса пользователя для stage_5 и переход к следующему этапу"""
    logger = logging.getLogger('bot')
    try:
        user_data = await state.get_data()
        telegram_id = user_data.get('telegram_id', message.from_user.id)
        current_stage = user_data.get('current_stage', 1)
        
        address = message.text.strip()
        
        # ✅ ПРОВЕРКА: Адрес не должен быть пустым
        if not address or len(address) < 5:
            await message.answer(
                "❌ *Пожалуйста, укажите полный адрес.*\n\n"
                "💡 *Пример корректного адреса:*\n"
                "г. Москва, ул. Пушкина, д. 10, ПВЗ СДЭК №123\n\n"
                "📝 *Напишите адрес еще раз:*",
                parse_mode="Markdown"
            )
            return
        
        # ✅ СОХРАНЯЕМ АДРЕС В БАЗУ ДАННЫХ
        success = await save_user_address_to_db(telegram_id, address, stage=current_stage)
        
        if success:
            # ✅ УСПЕШНО СОХРАНЕНО - отправляем подтверждение
            await message.answer(
                "✅ *Адрес успешно сохранен!*\n\n"
                "📦 Ваша реликвия будет доставлена по указанному адресу.",
                parse_mode="Markdown"
            )
            await asyncio.sleep(2)
            
            # ✅ ОБНОВЛЯЕМ ЭТАП И ПЕРЕХОДИМ К СЛЕДУЮЩЕМУ
            next_stage = current_stage + 1
            
            if next_stage <= 4:
                # Обновляем этап в БД
                await update_user_stage(telegram_id, next_stage)
                
                # ✅ СООБЩЕНИЕ О ПЕРЕХОДЕ К СЛЕДУЮЩЕМУ ЭТАПУ
                stage_names = {
                    1: "первый",
                    2: "второй", 
                    3: "третий",
                    4: "четвертый"
                }
                
                await message.answer(
                    f"🎉 *Этап {current_stage} завершен!*\n\n"
                    f"🔄 *Автоматически запускаю {stage_names[next_stage]} этап...*",
                    parse_mode="Markdown"
                )
                await asyncio.sleep(2)
                
                # ✅ ЗАПУСКАЕМ СЛЕДУЮЩИЙ ЭТАП
                if next_stage == 1:
                    await handle_stage_1_quest(message, state)
                elif next_stage == 2:
                    await handle_stage_2_quest(message, state)
                elif next_stage == 3:
                    await handle_stage_3_quest(message, state)
                elif next_stage == 4:
                    await handle_stage_4_quest(message, state)
                    
            else:
                # ✅ ФИНАЛЬНОЕ ЗАВЕРШЕНИЕ - все этапы пройдены
                await update_user_stage(telegram_id, 5)  # Завершаем квест
                
                await message.answer(
                    "🎊 *УРА! ВСЕ ЭТАПЫ ПРОЙДЕНЫ!*\n\n"
                    "✨ *Вы вернули все пропавшие реликвии и спасли Новый год!*\n\n"
                    "🏆 *Все реликвии будут доставлены по указанным адресам!*\n\n"
                    "💫 *Спасибо за участие в этом невероятном приключении!*",
                    parse_mode="Markdown"
                )
                
                # Сбрасываем состояние
                await state.clear()
            
        else:
            # ❌ ОШИБКА СОХРАНЕНИЯ АДРЕСА
            await message.answer(
                "❌ *Произошла ошибка при сохранении адреса.*\n\n"
                "🔄 Пожалуйста, попробуйте отправить адрес еще раз:",
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке адреса stage_5: {e}")
        await message.answer(
            "❌ *Произошла ошибка при обработке адреса.*\n\n"
            "🔄 Пожалуйста, попробуйте отправить адрес еще раз:",
            parse_mode="Markdown"
        )

async def handle_stage_5_riddle_answer(message: Message, state: FSMContext):
    """Обработка ответа на загадку для stage_5 с правильным завершением этапа"""
    logger = logging.getLogger('bot')
    try:
        user_data = await state.get_data()
        telegram_id = user_data.get('telegram_id', message.from_user.id)
        current_stage = user_data.get('current_stage', 1)
        
        # ✅ ПРАВИЛЬНЫЕ ОТВЕТЫ ДЛЯ КАЖДОГО ЭТАПА
        correct_answers = {
            1: "маяк",
            2: "компас", 
            3: "магнитофон",
            4: "очередь"
        }
        
        user_answer = message.text.strip().lower()
        correct_answer = correct_answers.get(current_stage, "")
        
        if user_answer == correct_answer:
            # ✅ ПРАВИЛЬНЫЙ ОТВЕТ - показываем сообщение о трофее и запрашиваем адрес
            
            # ✅ СООБЩЕНИЯ О ТРОФЕЯХ ДЛЯ КАЖДОГО ЭТАПА
            trophy_messages = {
                1: (
                    "🎉 *Поздравляем! Вы отгадали загадку!*\n"
                    "И получаете первый трофей:\n\n"
                    "🎁 *Промокод: RUNNER2025*\n"
                    "Скидка 20% на следующий этап!"
                ),
                2: (
                    "🎉 *Поздравляем! Вы отгадали загадку!*\n"
                    "И получаете второй трофей:\n\n"
                    "🎁 *Промокод: GUARDIAN2025*\n"
                    "Скидка 20% на следующий этап!"
                ),
                3: (
                    "🎉 *Поздравляем! Вы отгадали загадку!*\n"
                    "И получаете третий трофей:\n\n"
                    "🎁 *Промокод: SAVIOR2025*\n"
                    "Скидка 20% на следующий этап!"
                ),
                4: (
                    "🎉 *Поздравляем! Вы отгадали загадку!*\n"
                    "И получаете четвертый трофей:\n\n"
                    "🎁 *Промокод: FINAL2025*\n"
                    "Скидка 20% на следующий этап!"
                )
            }
            
            congrats_message = trophy_messages.get(current_stage, "🎉 Поздравляем! Вы отгадали загадку!")
            
            await message.answer(congrats_message, parse_mode="Markdown")
            await asyncio.sleep(3)
            
            # ✅ ЗАПРАШИВАЕМ АДРЕС ДОСТАВКИ
            address_message = (
                "📍 *Свою реликвию ты можешь получить здесь*\n\n"
                "📦 Напишите адрес ближайшего ПВЗ СДЭК или Яндекс Маркет:\n\n"
                "💡 *Пример:* г. Москва, ул. Пушкина, д. 10, ПВЗ СДЭК №123"
            )
            
            await message.answer(address_message, parse_mode="Markdown")
            
            # ✅ ПЕРЕХОДИМ В СОСТОЯНИЕ ОЖИДАНИЯ АДРЕСА
            await state.set_state("waiting_for_address_stage_5")
            
            # ✅ Сохраняем данные о правильном ответе
            await state.update_data(
                riddle_solved=True,
                telegram_id=telegram_id,
                current_stage=current_stage
            )
            
        else:
            # ❌ НЕПРАВИЛЬНЫЙ ОТВЕТ
            attempts_left = user_data.get('attempts_left', 3) - 1
            
            if attempts_left > 0:
                hint_message = f"❌ Неправильный ответ. Попробуйте еще раз. Осталось попыток: {attempts_left}"
                await message.answer(hint_message)
                await state.update_data(attempts_left=attempts_left)
            else:
                # После 3 попыток даем подсказку
                hints = {
                    1: "МА..",
                    2: "КОМП..", 
                    3: "МАГНИТ....",
                    4: "ОЧЕР.."
                }
                hint = hints.get(current_stage, "")
                hint_message = f"💡 Подсказка: {hint}\n\nПопробуйте еще раз!"
                await message.answer(hint_message, parse_mode="Markdown")
                await state.update_data(attempts_left=1)  # Даем еще одну попытку с подсказкой
        
    except Exception as e:
        logger.error(f"Ошибка при обработке ответа stage_5: {e}")
        await message.answer("❌ Ошибка при обработке ответа. Попробуйте еще раз.")

async def handle_stage_5_quest(callback_query: CallbackQuery, state: FSMContext):
    """Автоматический переход по этапам для stage_id = 5 с правильным завершением каждого"""
    try:
        telegram_id = callback_query.from_user.id
        
        # Получаем текущий этап пользователя
        current_stage = await get_user_current_stage(telegram_id)
        
        # Сохраняем текущий этап в состоянии
        await state.update_data(
            telegram_id=telegram_id,
            current_stage=current_stage,
            is_stage_5_user=True,  # Флаг что это пользователь 5-го этапа
            attempts_left=3
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
    # ✅ ДОБАВЛЯЕМ: Обработчик ответов на загадки для stage_5
    dp.message.register(
        handle_stage_5_riddle_answer,
        lambda message: message.text and not message.text.startswith('/')
    )
    
    # ✅ ДОБАВЛЯЕМ: Обработчик адресов для stage_5
    dp.message.register(
        handle_stage_5_address,
        lambda message: message.text and not message.text.startswith('/')
    )
