# src/handlers/stage_2.py
import asyncio
import os
import re
import sys
import subprocess
from pathlib import Path
from aiogram.types import CallbackQuery, Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from database import db
import logging
from datetime import datetime
from utils.video_optimizer import send_optimized_video

# ✅ ПРАВИЛЬНЫЕ ПУТИ ДЛЯ ВАШЕЙ СТРУКТУРЫ
PROJECT_ROOT = Path(__file__).parent.parent  # src/handlers -> src
MEDIA_PATH = PROJECT_ROOT / "media"  # src/media

# Добавляем путь к модулю deepseek_client
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Импортируем наш AI модуль
from deepseek_client.extract_with_yandexgpt_agent_fixed import extract_data_for_user

# Импортируем общие функции из вашего common_intro.py
from .common_intro import (
    get_common_intro, get_common_photo_request, get_common_processing_message,
    get_common_error_message, get_common_photo_error, get_common_answer_error,
    get_common_wrong_answer, get_common_final_hint,
    save_user_data_to_db, update_user_answer_in_db,
    check_if_stage_5_user, update_user_stage_in_db
)

class Stage2States(StatesGroup):
    waiting_for_image = State()
    waiting_for_riddle_answer = State()
    waiting_for_moderator_decision = State()
    waiting_for_address = State()  # ✅ ДОБАВЛЯЕМ: состояние ожидания адреса

def get_media_file(filename: str) -> str:
    """Получает полный путь к медиа файлу с проверкой существования"""
    file_path = MEDIA_PATH / filename
    if not file_path.exists():
        logging.error(f"Медиа файл не найден: {file_path}")
        # Логируем содержимое папки для отладки
        if MEDIA_PATH.exists():
            media_files = list(MEDIA_PATH.glob("*"))
            logging.info(f"Файлы в {MEDIA_PATH}: {[f.name for f in media_files]}")
        else:
            logging.error(f"Папка media не существует: {MEDIA_PATH}")
    return str(file_path)

async def get_user_id_from_db(telegram_id: int) -> int:
    """Получает user_id из таблицы main по telegram_id"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id FROM main WHERE telegram_id = ?",
                (telegram_id,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        logging.error(f"Ошибка получения user_id для telegram_id {telegram_id}: {e}")
        return None

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

async def save_running_data_to_db(user_id: int, date: str, distance: str, running_data: dict) -> bool:
    """Сохраняет данные о пробежке в таблицу verification"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем корректность данных
            if not date or not distance or date == 'не найдено' or distance == 'не найдено':
                logging.error(f"Не удалось извлечь данные из ответа AI: {running_data}")
                return False
            
            # Извлекаем числовое значение дистанции
            distance_match = re.search(r'(\d+\.?\d*)', distance)
            if not distance_match:
                logging.error(f"Не удалось извлечь числовое значение дистанции из: {distance}")
                return False
            
            distance_km = float(distance_match.group(1))
            
            # Преобразуем дату в формат YYYY-MM-DD
            try:
                # Парсим дату в формате dd.mm.yyyy
                run_date = datetime.strptime(date, '%d.%m.%Y').date()
            except ValueError:
                logging.error(f"Неверный формат даты: {date}")
                return False
            
            # Проверяем дату забега (не ранее 25.11.2025)
            check_date = datetime(2025, 11, 25).date()
            answer_check = 1 if run_date >= check_date else 0
            
            # Сохраняем в таблицу verification
            cursor.execute('''
                INSERT OR REPLACE INTO verification 
                (user_id, distance, run_date, answer_check)
                VALUES (?, ?, ?, ?)
            ''', (user_id, distance_km, run_date.isoformat(), answer_check))
            
            conn.commit()
            logging.info(f"Данные пробежки сохранены для user_id {user_id}: {distance_km} км, {run_date}, check={answer_check}")
            return True
            
    except Exception as e:
        logging.error(f"Ошибка сохранения данных пробежки в БД: {e}")
        return False

async def get_moderator_ids() -> list:
    """Получает список ID модераторов из БД"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_id FROM main WHERE role = 'moderator'")
            results = cursor.fetchall()
            return [row[0] for row in results] if results else []
    except Exception as e:
        logging.error(f"Ошибка получения модераторов: {e}")
        return []

async def send_moderator_notification(telegram_id: int, username: str, image_path: str, attempts: int, message: Message):
    """Отправляет уведомление модератору о проблеме с распознаванием"""
    try:
        moderator_ids = await get_moderator_ids()
        if not moderator_ids:
            logging.error("❌ Модераторы не найдены в БД")
            return
        
        # Создаем клавиатуру для модератора
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Проверено", callback_data=f"moderator_approve_2_{telegram_id}"),
                    InlineKeyboardButton(text="❌ Отказать", callback_data=f"moderator_reject_2_{telegram_id}")
                ]
            ]
        )
        
        # Отправляем уведомление всем модераторам
        for moderator_id in moderator_ids:
            try:
                # Отправляем фото скриншота
                photo = FSInputFile(image_path)
                caption = (
                    f"🚨 *ПРОБЛЕМА С РАСПОЗНАВАНИЕМ СКРИНШОТА - ЭТАП 2*\n\n"
                    f"👤 Пользователь: @{username or 'без username'}\n"
                    f"🆔 ID: {telegram_id}\n"
                    f"🔄 Неудачных попыток: {attempts}\n\n"
                    f"📸 *Скриншот пользователя:*"
                )
                
                await message.bot.send_photo(
                    chat_id=moderator_id,
                    photo=photo,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                logging.info(f"✅ Уведомление отправлено модератору {moderator_id} для этапа 2")
                
            except Exception as e:
                logging.error(f"❌ Ошибка отправки уведомления модератору {moderator_id}: {e}")
                
    except Exception as e:
        logging.error(f"❌ Ошибка в функции отправки уведомления модератору: {e}")

async def analyze_user_image_and_save_results(telegram_id: int, user_id: int, image_path: str, message: Message, state: FSMContext):
    """Анализирует изображение пользователя и сохраняет результаты в verification"""
    logger = logging.getLogger('bot')
    
    try:
        # ✅ Получаем текущие данные о попытках
        user_data = await state.get_data()
        recognition_attempts = user_data.get('recognition_attempts', 0) + 1
        await state.update_data(recognition_attempts=recognition_attempts)
        
        # ✅ Проверяем существование файла
        if not os.path.exists(image_path):
            logger.error(f"Файл не найден: {image_path}")
            await message.answer("❌ Ошибка: файл не найден. Попробуйте отправить скриншот еще раз.")
            return
        
        # ✅ Анализируем с AI - используем универсальную функцию
        running_data = extract_data_for_user(image_path)
        
        if running_data and running_data.get('agent_response'):
            agent_data = running_data['agent_response']
            date = agent_data.get('date', 'не найдено')
            distance = agent_data.get('distance', 'не найдено')
            
            # ✅ Проверяем успешность распознавания
            if date != 'не найдено' and distance != 'не найдено':
                # ✅ Сохраняем в БД
                success = await save_running_data_to_db(user_id, date, distance, running_data)
                
                if success:
                    # ✅ Сбрасываем счетчик попыток при успешном распознавании
                    await state.update_data(recognition_attempts=0)
                    
                    await message.answer(
                        f"✅ *Данные пробежки успешно обработаны!*\n\n"
                        f"📅 Дата: {date}\n"
                        f"📏 Дистанция: {distance}\n\n"
                        f"*Продолжаем квест...*", 
                        parse_mode="Markdown"
                    )
                    
                    # ✅ Переходим к следующей части квеста
                    await continue_stage_2_quest(message, state)
                    return
                else:
                    await message.answer(
                        "❌ *Не удалось сохранить данные пробежки.*\n"
                        "Попробуйте отправить другой скриншот, где будут видны пройденные дистанция и дата.",
                        parse_mode="Markdown"
                    )
            else:
                # Данные не распознаны, увеличиваем счетчик
                await handle_recognition_failure(telegram_id, user_id, image_path, message, state, recognition_attempts)
                
        else:
            # AI анализ не удался, увеличиваем счетчик
            await handle_recognition_failure(telegram_id, user_id, image_path, message, state, recognition_attempts)
            
    except Exception as ai_error:
        logger.error(f"Ошибка AI анализа: {ai_error}")
        await handle_recognition_failure(telegram_id, user_id, image_path, message, state, recognition_attempts)

async def handle_recognition_failure(telegram_id: int, user_id: int, image_path: str, message: Message, state: FSMContext, attempts: int):
    """Обработка неудачного распознавания"""
    logger = logging.getLogger('bot')
    
    if attempts >= 3:
        # ✅ После 3 неудачных попыток - уведомляем модератора
        logger.warning(f"🚨 Пользователь {telegram_id} не смог распознать скриншот после {attempts} попыток (этап 2)")
        
        # Получаем username пользователя
        username = message.from_user.username or message.from_user.first_name
        
        # ✅ СОХРАНЯЕМ ДАННЫЕ ДЛЯ ДАЛЬНЕЙШЕГО ПРОДОЛЖЕНИЯ
        await state.update_data(
            last_image_path=image_path,
            user_id=user_id
        )
        
        # Отправляем уведомление модератору
        await send_moderator_notification(telegram_id, username, image_path, attempts, message)
        
        # Сообщаем пользователю
        await message.answer(
            "🔄 *Ваш скриншот отправлен на проверку модератору.*\n\n"
            "📋 Мы проверим его вручную и уведомим вас о результате.\n"
            "⏳ Обычно это занимает несколько минут.",
            parse_mode="Markdown"
        )
        
        # Переходим в состояние ожидания решения модератора
        await state.set_state(Stage2States.waiting_for_moderator_decision)
        
    else:
        # ✅ Меньше 3 попыток - просим отправить другой скриншот
        await message.answer(
            f"❌ *Не удалось распознать данные пробежки.*\n"
            f"Попытка {attempts} из 3\n\n"
            "📸 Попробуйте отправить другой скриншот, где будут четко видны:\n"
            "• Дата пробежки\n"
            "• Пройденная дистанция\n"
            "• Время активности",
            parse_mode="Markdown"
        )

async def send_moderator_approved_quest(bot, telegram_id: int):
    """Отправляет продолжение квеста после одобрения модератором"""
    try:
        # ✅ Продолжаем квест автоматически
        await asyncio.sleep(1)
        
        message5 = "🎉 *Ура! Ты – на складе!*"
        await bot.send_message(
            chat_id=telegram_id,
            text=message5,
            parse_mode="Markdown"
        )
        await asyncio.sleep(2)
        
        message6 = (
            "📹 Камеры уничтожены, но ты, подключаешься к резервному облаку и находишь видеозапись. "
            "Ты видишь не только БЕЗЛИКОГО, но и его сообщника — кого-то из наших! Предательство!\n\n"
            "🔍 Досмотрев запись до конца, ты отслеживаешь куда был спрятан «Снеговик». "
            "Оказывается он стоял на самом входе на склад. Но не всё так просто! "
            "Тебя ждало новое послание на записке, которую оставили рядом.."
        )
        
        await bot.send_message(
            chat_id=telegram_id,
            text=message6
        )
        await asyncio.sleep(2)
        
        # ✅ Отправляем оптимизированное видео БЕЗ подписи
        try:
            await send_optimized_video(
                bot, 
                telegram_id,
                "4_logo.mp4"
            )
        except Exception as video_error:
            logging.error(f"Ошибка отправки видео: {video_error}")
        
        await asyncio.sleep(2)
        
        message7 = (
            "💡 *У меня есть стрелки, но я не время показываю*\n"
            "*А раскрываю карту с обратной стороны*\n\n"
            "*Что я❓*\n\n"
            "*Напиши свой ответ:*"
        )
        
        await bot.send_message(
            chat_id=telegram_id,
            text=message7,
            parse_mode="Markdown"
        )
        
        logging.info(f"✅ Квест продолжен для пользователя {telegram_id} после одобрения модератора (этап 2)")
        
    except Exception as e:
        logging.error(f"Ошибка при отправке квеста после одобрения модератора (этап 2): {e}")

async def force_update_user_state(storage, telegram_id: int, target_state):
    """Принудительное обновление состояния пользователя"""
    try:
        # ✅ ИСПРАВЛЕНИЕ: Создаем ключ без bot.id если его нет
        try:
            # Пробуем создать ключ с bot.id
            user_key = StorageKey(chat_id=telegram_id, user_id=telegram_id, bot_id=storage.bot.id)
        except AttributeError:
            # Если нет bot.id, создаем ключ без него
            user_key = StorageKey(chat_id=telegram_id, user_id=telegram_id, bot_id=telegram_id)
        
        await storage.set_state(key=user_key, state=target_state)
        
        logging.info(f"✅ Принудительно обновлено состояние пользователя {telegram_id} на {target_state} (этап 2)")
        return True
    except Exception as e:
        logging.error(f"❌ Ошибка принудительного обновления состояния (этап 2): {e}")
        return False

async def update_user_state_directly(bot, telegram_id: int, target_state, storage):
    """Прямое обновление состояния пользователя через создание нового контекста"""
    try:
        # ✅ ИСПРАВЛЕНИЕ: Используем правильный формат ключа
        from aiogram.fsm.storage.base import StorageKey
        
        # ✅ ИСПРАВЛЕНИЕ: Создаем ключ без bot.id если его нет
        try:
            # Пробуем создать ключ с bot.id
            user_key = StorageKey(
                chat_id=telegram_id, 
                user_id=telegram_id, 
                bot_id=bot.id
            )
        except AttributeError:
            # Если нет bot.id, создаем ключ без него
            user_key = StorageKey(
                chat_id=telegram_id, 
                user_id=telegram_id, 
                bot_id=telegram_id  # Используем telegram_id как fallback
            )
        
        # Создаем новый FSMContext для пользователя
        user_state = FSMContext(storage=storage, key=user_key)
        
        # ✅ ВАЖНОЕ ИСПРАВЛЕНИЕ: Получаем user_id из БД
        user_id = await get_user_id_from_db(telegram_id)
        is_stage_5_user = await check_if_stage_5_user(telegram_id)
        
        # Устанавливаем новое состояние
        await user_state.set_state(target_state)
        
        # ✅ ВАЖНОЕ ИСПРАВЛЕНИЕ: Сохраняем ВСЕ необходимые данные
        user_state_data = {
            'telegram_id': telegram_id,
            'user_id': user_id,
            'is_stage_5_user': is_stage_5_user,
            'attempts_left': 3,
            'recognition_attempts': 0,
            'quest_continued': True,  # Флаг что квест продолжен
            'moderator_approved': True  # Флаг что модератор одобрил
        }
        await user_state.set_data(user_state_data)
        
        logging.info(f"✅ Состояние пользователя {telegram_id} напрямую обновлено на {target_state} (этап 2)")
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка прямого обновления состояния (этап 2): {e}")
        return False

async def handle_moderator_approve_2(callback_query: CallbackQuery, state: FSMContext):
    """Обработка решения модератора 'Проверено' для этапа 2"""
    try:
        # Извлекаем telegram_id пользователя из callback_data
        telegram_id = int(callback_query.data.split('_')[-1])
        
        # Проверяем что это модератор
        moderator_ids = await get_moderator_ids()
        if callback_query.from_user.id not in moderator_ids:
            await callback_query.answer("❌ У вас нет прав для этого действия", show_alert=True)
            return
        
        # ✅ Получаем сохраненные данные пользователя
        user_data = await state.get_data()
        user_id = user_data.get('user_id')
        
        if not user_id:
            # Если user_id не найден в состоянии, получаем из БД
            user_id = await get_user_id_from_db(telegram_id)
        
        # ✅ Уведомляем модератора
        await callback_query.answer("✅ Скриншот проверен, пользователь продолжает квест (этап 2)", show_alert=True)
        
        # ✅ Обновляем сообщение модератора
        original_caption = callback_query.message.caption or ""
        username_line = original_caption.split('Пользователь: ')[1] if 'Пользователь: ' in original_caption else ""
        username = username_line.split('\n')[0] if username_line else "неизвестно"
        
        updated_caption = (
            "✅ *СКРИНШОТ ПРОВЕРЕН - ЭТАП 2*\n\n"
            f"👤 Пользователь: {username}\n"
            f"🆔 ID: {telegram_id}\n"
            f"✅ Решение принято: @{callback_query.from_user.username or callback_query.from_user.first_name}\n"
            f"🕐 Время: {datetime.now().strftime('%H:%M:%S')}"
        )
        
        await callback_query.message.edit_caption(
            caption=updated_caption,
            parse_mode="Markdown",
            reply_markup=None  # Убираем кнопки
        )
        
        # ✅ Сохраняем фиктивные данные в verification
        today = datetime.now().strftime("%d.%m.%Y")
        fake_running_data = {
            'agent_response': {
                'date': today,
                'distance': '10.00 км'
            }
        }
        
        success = await save_running_data_to_db(user_id, today, '10.00 км', fake_running_data)
        
        if success:
            # ✅ Отправляем сообщение пользователю
            user_message = (
                "✅ *Ваш скриншот проверен модератором!*\n\n"
                "🎉 *Продолжаем квест...*"
            )
            
            await callback_query.bot.send_message(
                chat_id=telegram_id,
                text=user_message,
                parse_mode="Markdown"
            )
            
            # ✅ ВАЖНОЕ ИСПРАВЛЕНИЕ: Отправляем ПРАВИЛЬНЫЙ сценарий этапа 2
            await callback_query.bot.send_message(
                chat_id=telegram_id,
                text="🎉 *Ура! Ты – на складе!*",
                parse_mode="Markdown"
            )
            await asyncio.sleep(2)
            
            await callback_query.bot.send_message(
                chat_id=telegram_id,
                text=(
                    "📹 Камеры уничтожены, но ты, подключаешься к резервному облаку и находишь видеозапись. "
                    "Ты видишь не только БЕЗЛИКОГО, но и его сообщника — кого-то из наших! Предательство!\n\n"
                    "🔍 Досмотрев запись до конца, ты отслеживаешь куда был спрятан «Снеговик». "
                    "Оказывается он стоял на самом входе на склад. Но не всё так просто! "
                    "Тебя ждало новое послание на записке, которую оставили рядом.."
                )
            )
            await asyncio.sleep(2)
            
            # ✅ ИСПРАВЛЕНИЕ: Отправляем видео БЕЗ подписи
            try:
                video_path = get_media_file("4_logo.mp4")
                if os.path.exists(video_path):
                    video = FSInputFile(video_path)
                    await callback_query.bot.send_video(
                        chat_id=telegram_id,
                        video=video
                    )
                else:
                    logging.error(f"Видео файл не найден: {video_path}")
            except Exception as video_error:
                logging.error(f"Ошибка отправки видео: {video_error}")
            
            await asyncio.sleep(2)
            
            # ✅ ВАЖНОЕ ИСПРАВЛЕНИЕ: Отправляем ПРАВИЛЬНУЮ загадку этапа 2
            riddle_message = (
                "💡 *У меня есть стрелки, но я не время показываю*\n"
                "*А раскрываю карту с обратной стороны*\n\n"
                "*Что я❓*\n\n"
                "*Напиши свой ответ:*"
            )
            
            await callback_query.bot.send_message(
                chat_id=telegram_id,
                text=riddle_message,
                parse_mode="Markdown"
            )
            
            # ✅ ВАЖНОЕ ИСПРАВЛЕНИЕ: Обновляем состояние пользователя через прямое обновление
            try:
                # ✅ ИСПРАВЛЕНИЕ: Правильное получение storage
                storage = state.storage
                
                # ✅ ИСПРАВЛЕНИЕ: Используем прямое обновление как основной способ
                success = await update_user_state_directly(
                    callback_query.bot, 
                    telegram_id, 
                    Stage2States.waiting_for_riddle_answer, 
                    storage
                )
                
                if not success:
                    # ✅ АЛЬТЕРНАТИВНЫЙ СПОСОБ: force_update_user_state
                    success = await force_update_user_state(storage, telegram_id, Stage2States.waiting_for_riddle_answer)
                
                if success:
                    logging.info(f"✅ Состояние пользователя {telegram_id} успешно обновлено на waiting_for_riddle_answer (этап 2)")
                    
                else:
                    # ✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Если не удалось обновить состояние, отправляем инструкцию
                    instruction_text = (
                        "🔄 *Квест продолжен, но возникла техническая проблема.*\n\n"
                        "💡 *Для продолжения выполните следующие действия:*\n"
                        "1. Нажмите /start\n" 
                        "2. Выберите этап 2\n"
                        "3. Напишите ответ на загадку: *компас*"
                    )
                    
                    await callback_query.bot.send_message(
                        chat_id=telegram_id,
                        text=instruction_text,
                        parse_mode="Markdown"
                    )
                    
            except Exception as storage_error:
                logging.error(f"❌ Ошибка обновления состояния пользователя {telegram_id} (этап 2): {storage_error}")
                
                # ✅ РЕЗЕРВНЫЙ ВАРИАНТ: Отправляем инструкцию пользователю
                instruction_text = (
                    "🔄 *Квест продолжен!*\n\n"
                    "💡 *Для ответа на загадку выполните:*\n"
                    "1. Нажмите /start\n"
                    "2. Выберите этап 2\n" 
                    "3. Напишите ответ: *компас*"
                )
                
                await callback_query.bot.send_message(
                    chat_id=telegram_id,
                    text=instruction_text,
                    parse_mode="Markdown"
                )
            
        else:
            # Если не удалось сохранить данные, отправляем сообщение об ошибке
            await callback_query.bot.send_message(
                chat_id=telegram_id,
                text="❌ Произошла ошибка при обработке. Пожалуйста, попробуйте еще раз.",
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logging.error(f"Ошибка при обработке решения модератора (этап 2): {e}")
        await callback_query.answer("❌ Ошибка при обработке", show_alert=True)

async def handle_moderator_decision_waiting_2(message: Message, state: FSMContext):
    """Обработчик для состояния ожидания решения модератора (этап 2)"""
    try:
        user_data = await state.get_data()
        telegram_id = message.from_user.id
        
        # ✅ ПРОВЕРЯЕМ: Если квест уже продолжен, сбрасываем состояние
        if user_data.get('quest_continued') or user_data.get('moderator_approved'):
            await state.clear()
            await message.answer(
                "🔄 *Состояние сброшено.*\n\n"
                "💡 Вы уже можете отвечать на загадку. Напишите ответ: *компас*",
                parse_mode="Markdown"
            )
            return
            
        # ✅ ПРОВЕРЯЕМ: Если пользователь пытается отправить еще один скриншот
        if message.photo:
            await message.answer(
                "⏳ *Ожидайте решения модератора по предыдущему скриншоту.*\n\n"
                "📋 Ваш скриншот уже отправлен на проверку. "
                "Мы уведомим вас, как только модератор примет решение.",
                parse_mode="Markdown"
            )
            return
            
        # Стандартное сообщение ожидания
        await message.answer(
            "⏳ *Ожидайте решения модератора по вашему скриншоту.*\n\n"
            "📋 Обычно проверка занимает несколько минут. "
            "Вы получите уведомление, как только модератор примет решение.",
            parse_mode="Markdown"
        )
            
    except Exception as e:
        logging.error(f"Ошибка в обработчике ожидания модератора (этап 2): {e}")
        await message.answer("⏳ Ожидайте решения модератора по вашему скриншоту.")

async def save_user_address_to_db(telegram_id: int, address: str, stage: int = 2) -> bool:
    """Сохраняет адрес пользователя в таблицу user_addresses для этапа 2"""
    try:
        username = None  # Можно добавить получение username из состояния если нужно
        
        success = db.save_user_address(telegram_id, username, address, stage)
        if success:
            logging.info(f"✅ Адрес сохранен для пользователя {telegram_id}: {address} (этап 2)")
            return True
        else:
            logging.error(f"❌ Ошибка сохранения адреса для пользователя {telegram_id} (этап 2)")
            return False
            
    except Exception as e:
        logging.error(f"❌ Ошибка при сохранении адреса пользователя {telegram_id} (этап 2): {e}")
        return False

async def handle_stage_2_riddle_answer(message: Message, state: FSMContext):
    """Обработка ответа на загадку этапа 2 с поддержкой stage_5 и запросом адреса"""
    logger = logging.getLogger('bot')
    try:
        # ✅ ПРОВЕРКА: Получаем данные состояния, если они есть
        try:
            user_data = await state.get_data()
            telegram_id = user_data.get('telegram_id', message.from_user.id)
            attempts_left = user_data.get('attempts_left', 3)
        except:
            # Если состояние недоступно, используем данные из сообщения
            telegram_id = message.from_user.id
            attempts_left = 3
            user_data = {'is_stage_5_user': False}
        
        user_answer = message.text.strip().lower()
        correct_answer = "компас"
        
        attempts_left -= 1
        
        if user_answer == correct_answer:
            # Правильный ответ - обновляем в БД через общую функцию
            update_user_answer_in_db(telegram_id, user_answer)
            
            # ✅ ПРОВЕРКА НА 5-Й ЭТАП
            is_stage_5_user = user_data.get('is_stage_5_user', False)
            
            if is_stage_5_user:
                # ✅ ИСПРАВЛЕНИЕ: Для stage_5 показываем трофей и запрашиваем адрес
                congrats_message = (
                    "🎉 *Поздравляем! Вы отгадали загадку!*\n"
                )
                
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
                await state.set_state(Stage2States.waiting_for_address)
                
                # ✅ Сохраняем данные о правильном ответе
                await state.update_data(
                    riddle_solved=True,
                    telegram_id=telegram_id,
                    is_stage_5_user=True  # ✅ ВАЖНО: сохраняем флаг stage_5
                )
            else:
                # ✅ НОВАЯ ЛОГИКА: Обычное завершение с запросом адреса
                congrats_message = (
                    "🎉 *Поздравляем! Вы отгадали загадку!*\n"
                    "И получаете второй трофей:\n\n"
                    "🎁 *Промокод: GUARDIAN2025*\n"
                    "Скидка 20% на следующий этап!"
                )
                
                await message.answer(congrats_message, parse_mode="Markdown")
                await asyncio.sleep(3)
                
                # ✅ ДОБАВЛЯЕМ: Сообщение с запросом адреса
                address_message = (
                    "📍 *Свою реликвию ты можешь получить здесь*\n\n"
                    "📦 Напишите адрес ближайшего ПВЗ СДЭК или Яндекс Маркет:\n\n"
                    "💡 *Пример:* г. Москва, ул. Пушкина, д. 10, ПВЗ СДЭК №123"
                )
                
                await message.answer(address_message, parse_mode="Markdown")
                
                # ✅ ПЕРЕХОДИМ В СОСТОЯНИЕ ОЖИДАНИЯ АДРЕСА
                await state.set_state(Stage2States.waiting_for_address)
                
                # ✅ Сохраняем данные о правильном ответе
                await state.update_data(
                    riddle_solved=True,
                    telegram_id=telegram_id
                )
            
        else:
            # Неправильный ответ
            if attempts_left > 0:
                hint_message = get_common_wrong_answer(attempts_left)
                await message.answer(hint_message)
                # Сохраняем обновленное количество попыток
                if 'attempts_left' in user_data:
                    await state.update_data(attempts_left=attempts_left)
            else:
                # После 3 попыток даем подсказку
                hint_message = get_common_final_hint("КОМП..")
                await message.answer(hint_message, parse_mode="Markdown")
                if 'attempts_left' in user_data:
                    await state.update_data(attempts_left=1)  # Даем еще одну попытку с подсказкой
        
    except Exception as e:
        logger.error(f"Ошибка при обработке ответа stage_2: {e}")
        await message.answer("❌ Ошибка при обработке ответа. Попробуйте еще раз.")

async def handle_stage_2_address(message: Message, state: FSMContext):
    """Обработка адреса пользователя и завершение этапа 2"""
    logger = logging.getLogger('bot')
    try:
        user_data = await state.get_data()
        telegram_id = user_data.get('telegram_id', message.from_user.id)
        is_stage_5_user = user_data.get('is_stage_5_user', False)
        
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
        success = await save_user_address_to_db(telegram_id, address, stage=2)
        
        if success:
            # ✅ УСПЕШНО СОХРАНЕНО - отправляем подтверждение
            await message.answer(
                "✅ *Адрес успешно сохранен!*\n\n"
                "📦 Ваша реликвия будет доставлена по указанному адресу.",
                parse_mode="Markdown"
            )
            await asyncio.sleep(2)
            
            if is_stage_5_user:
                # ✅ ДЛЯ STAGE_5: Обновляем этап и переходим к следующему
                await update_user_stage_in_db(telegram_id, 3)  # Переходим на этап 3
                
                await message.answer(
                    "🎉 *Этап 2 завершен!*\n\n"
                    "🔄 *Автоматически запускаю следующий этап...*",
                    parse_mode="Markdown"
                )
                await asyncio.sleep(2)
                
                # ✅ ЗАПУСКАЕМ СЛЕДУЮЩИЙ ЭТАП
                from .stage_3 import handle_stage_3_quest
                # Создаем fake callback для запуска
                class FakeCallback:
                    def __init__(self, message):
                        self.message = message
                        self.from_user = message.from_user
                
                fake_callback = FakeCallback(message)
                await handle_stage_3_quest(fake_callback, state)
            else:
                # ✅ ОБЫЧНЫЙ ЗАВЕРШЕНИЕ: Отправляем видео и финальное сообщение
                try:
                    await send_optimized_video(
                        message,
                        "5_logo.mp4"
                    )
                except Exception as video_error:
                    logging.error(f"Ошибка отправки видео: {video_error}")
                
                await asyncio.sleep(2)
                
                # ✅ ФИНАЛЬНОЕ СООБЩЕНИЕ
                final_message = (
                    "🔥 *Готов ли ты к этому?*\n\n"
                    "[➡️ Перейти к следующему этапу](https://your-link-here.com/)"
                )
                
                await message.answer(final_message, parse_mode="Markdown", disable_web_page_preview=True)
                
                # ✅ СБРАСЫВАЕМ СОСТОЯНИЕ ПОЛЬЗОВАТЕЛЯ
                await state.clear()
            
            logging.info(f"✅ Этап 2 завершен для пользователя {telegram_id}. Адрес сохранен: {address}")
            
        else:
            # ❌ ОШИБКА СОХРАНЕНИЯ АДРЕСА
            await message.answer(
                "❌ *Произошла ошибка при сохранении адреса.*\n\n"
                "🔄 Пожалуйста, попробуйте отправить адрес еще раз:",
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке адреса stage_2: {e}")
        await message.answer(
            "❌ *Произошла ошибка при обработке адреса.*\n\n"
            "🔄 Пожалуйста, попробуйте отправить адрес еще раз:",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке адреса stage_2: {e}")
        await message.answer(
            "❌ *Произошла ошибка при обработке адреса.*\n\n"
            "🔄 Пожалуйста, попробуйте отправить адрес еще раз:",
            parse_mode="Markdown"
        )

async def handle_wrong_address_input_2(message: Message, state: FSMContext):
    """Обработчик некорректных сообщений в состоянии ожидания адреса (этап 2)"""
    await message.answer(
        "📍 *Пожалуйста, укажите адрес для доставки реликвии.*\n\n"
        "📦 Напишите адрес ближайшего ПВЗ СДЭК или Яндекс Маркет:\n\n"
        "💡 *Пример:* г. Москва, ул. Пушкина, д. 10, ПВЗ СДЭК №123",
        parse_mode="Markdown"
    )

async def continue_stage_2_quest(message: Message, state: FSMContext):
    """Продолжение квеста после успешного анализа картинки для этапа 2"""
    try:
        # Продолжаем квест
        await asyncio.sleep(1)
        
        message5 = "🎉 *Ура! Ты – на складе!*"
        await message.answer(message5, parse_mode="Markdown")
        await asyncio.sleep(2)
        
        message6 = (
            "📹 Камеры уничтожены, но ты, подключаешься к резервному облаку и находишь видеозапись. "
            "Ты видишь не только БЕЗЛИКОГО, но и его сообщника — кого-то из наших! Предательство!\n\n"
            "🔍 Досмотрев запись до конца, ты отслеживаешь куда был спрятан «Снеговик». "
            "Оказывается он стоял на самом входе на склад. Но не всё так просто! "
            "Тебя ждало новое послание на записке, которую оставили рядом.."
        )
        
        await message.answer(message6)
        await asyncio.sleep(2)
        
        # ✅ Отправляем оптимизированное видео БЕЗ подписи
        try:
            await send_optimized_video(
                message, 
                "4_logo.mp4"
            )
        except Exception as video_error:
            logging.error(f"Ошибка отправки видео: {video_error}")
        
        await asyncio.sleep(2)
        
        message7 = (
            "💡 *У меня есть стрелки, но я не время показываю*\n"
            "*А раскрываю карту с обратной стороны*\n\n"
            "*Что я❓*\n\n"
            "*Напиши свой ответ:*"
        )
        
        await message.answer(message7, parse_mode="Markdown")
        
        # ✅ ДОБАВЛЯЕМ: Проверяем stage_5 и сохраняем в состояние
        telegram_id = message.from_user.id
        is_stage_5_user = await check_if_stage_5_user(telegram_id)
        await state.update_data(is_stage_5_user=is_stage_5_user)
        
        # Переходим в состояние ожидания ответа на загадку
        await state.set_state(Stage2States.waiting_for_riddle_answer)
        
    except Exception as e:
        logging.error(f"Ошибка при продолжении квеста stage_2: {e}")
        await message.answer("❌ Ошибка при продолжении квеста. Попробуйте еще раз.")


async def handle_stage_2_quest(callback_query: CallbackQuery, state: FSMContext):
    """Сценарий квеста для stage_id = 2"""
    try:
        # Сохраняем данные пользователя в состоянии
        await state.update_data(
            telegram_id=callback_query.from_user.id,
            attempts_left=3,
            recognition_attempts=0  # ✅ ДОБАВЛЯЕМ: счетчик попыток распознавания
        )
        
        # ✅ Отправляем оптимизированное видео
        try:
            await send_optimized_video(
                callback_query.message, 
                "1_logo.mp4"
            )
        except Exception as video_error:
            logging.error(f"Ошибка отправки видео: {video_error}")
        
        # Общее вступление с названием этапа из БД
        message1 = get_common_intro(2)
        await callback_query.message.answer(message1, parse_mode="Markdown")
        await asyncio.sleep(3)
        
        # Второе сообщение
        message2 = (
            "⚡ *В спортивно-новогоднем комитете раздор!*\n\n"
            "Пока ты был в порту, БЕЗЛИКИЙ проник в хранилище и украл вторую реликвию «Снеговик». "
            "Хуже того, внутри «Снеговика» находился флеш-носитель с кодами доступа ко всем системам безопасности комитета."
        )
        
        await callback_query.message.answer(message2, parse_mode="Markdown")
        await asyncio.sleep(2)
        
        # Третье сообщение
        message3 = (
            "🤔 *Как БЕЗЛИКИЙ смог провернуть это так легко?*\n\n"
            "Тебе нужно найти зацепку на месте преступления. Необходимо незамедлительно бежать на склад!"
        )
        
        await callback_query.message.answer(message3, parse_mode="Markdown")
        await asyncio.sleep(2)
        
        # Четвертое сообщение с кнопкой
        message4 = (
            "🏃‍♂️ *Вперёд!*\n\n"
            f"{get_common_photo_request()}"
        )
        
        await callback_query.message.answer(message4, parse_mode="Markdown")
        
        # Переходим в состояние ожидания изображения
        await state.set_state(Stage2States.waiting_for_image)
        
    except Exception as e:
        logging.error(f"Ошибка в stage_2: {e}")
        await callback_query.message.answer(get_common_error_message())

async def handle_stage_2_image(message: Message, state: FSMContext):
    """Обработка изображения для этапа 2 с AI анализом"""
    logger = logging.getLogger('bot')
    try:
        user_data = await state.get_data()
        telegram_id = user_data.get('telegram_id')
        
        if not message.photo:
            await message.answer(get_common_photo_error())
            return
        
        # ✅ Получаем user_id из БД
        user_id = await get_user_id_from_db(telegram_id)
        if not user_id:
            await message.answer("❌ Ошибка: пользователь не найден в системе.")
            return
        
        # ✅ Сохраняем user_id в состоянии для дальнейшего использования
        await state.update_data(user_id=user_id)
        
        # ✅ ПРАВИЛЬНЫЙ ПУТЬ ДЛЯ СОХРАНЕНИЯ ИЗОБРАЖЕНИЙ
        stage_folder = MEDIA_PATH / "stage_2"
        os.makedirs(stage_folder, exist_ok=True)
        
        # Получаем файл изображения
        photo = message.photo[-1]
        file_id = photo.file_id
        file = await message.bot.get_file(file_id)
        file_path = file.file_path
        
        # ✅ Генерируем имя файла
        file_extension = os.path.splitext(file_path)[1] or '.jpg'
        filename = f"{telegram_id}_{int(asyncio.get_event_loop().time())}{file_extension}"
        local_path = os.path.join(stage_folder, filename).replace('\\', '/')
        
        # Скачиваем файл
        await message.bot.download_file(file_path, local_path)
        
        # ✅ Сохраняем путь в базу данных через общую функцию
        save_user_data_to_db(telegram_id, local_path)
        
        logger.info(f"Сохранено изображение для пользователя {telegram_id}: {local_path}")
        
        # ✅ Сообщаем что картинка сохранена и переходим к анализу
        await message.answer("✅ *Скриншот сохранен! Теперь анализирую данные пробежки...*", parse_mode="Markdown")
        
        # ✅ Вызываем функцию анализа с передачей user_id
        await analyze_user_image_and_save_results(telegram_id, user_id, local_path, message, state)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения stage_2: {e}")
        await message.answer("❌ Ошибка при обработке скриншота. Попробуйте еще раз.")

async def handle_moderator_reject_2(callback_query: CallbackQuery, state: FSMContext):
    """Обработка решения модератора 'Отказать' для этапа 2"""
    try:
        # Извлекаем telegram_id пользователя из callback_data
        telegram_id = int(callback_query.data.split('_')[-1])
        
        # Проверяем что это модератор
        moderator_ids = await get_moderator_ids()
        if callback_query.from_user.id not in moderator_ids:
            await callback_query.answer("❌ У вас нет прав для этого действия", show_alert=True)
            return
        
        # ✅ Уведомляем модератора
        await callback_query.answer("❌ Пользователю отправлен отказ (этап 2)", show_alert=True)
        
        # ✅ Обновляем сообщение модератора
        original_caption = callback_query.message.caption or ""
        username_line = original_caption.split('Пользователь: ')[1] if 'Пользователь: ' in original_caption else ""
        username = username_line.split('\n')[0] if username_line else "неизвестно"
        
        updated_caption = (
            "❌ *СКРИНШОТ ОТКЛОНЕН - ЭТАП 2*\n\n"
            f"👤 Пользователь: {username}\n"
            f"🆔 ID: {telegram_id}\n"
            f"❌ Решение принято: @{callback_query.from_user.username or callback_query.from_user.first_name}\n"
            f"🕐 Время: {datetime.now().strftime('%H:%M:%S')}"
        )
        
        await callback_query.message.edit_caption(
            caption=updated_caption,
            parse_mode="Markdown",
            reply_markup=None  # Убираем кнопки
        )
        
        # ✅ Отправляем сообщение пользователю об отказе
        user_message = (
            "❌ Ваш скриншот не прошел проверку (этап 2)\n\n"
            "📞 Пожалуйста, свяжитесь с организаторами для уточнения деталей:\n"
            "👤 @a_a_anastasya\n"
            "📧 startani@bk.ru\n\n"
            "Мы поможем решить проблему!"
        )
        
        # Отправляем сообщение пользователю
        await callback_query.bot.send_message(
            chat_id=telegram_id,
            text=user_message
        )
        
        # ✅ Очищаем состояние пользователя через storage
        try:
            storage = state.storage
            user_key = StorageKey(chat_id=telegram_id, user_id=telegram_id, bot_id=storage.bot.id)
            await storage.set_state(key=user_key, state=None)
            await storage.set_data(key=user_key, data={})
            logging.info(f"✅ Состояние пользователя {telegram_id} очищено после отказа модератора (этап 2)")
        except Exception as storage_error:
            logging.error(f"Ошибка очистки состояния пользователя {telegram_id} (этап 2): {storage_error}")
        
    except Exception as e:
        logging.error(f"Ошибка при обработке отказа модератора (этап 2): {e}")
        await callback_query.answer("❌ Ошибка при обработке", show_alert=True)

def setup_stage_2_handlers(dp):
    """Настройка обработчиков для этапа 2"""
    # Обработчик изображений для этапа 2
    dp.message.register(
        handle_stage_2_image,
        Stage2States.waiting_for_image,
        F.photo
    )
    
    # Обработчик текстовых ответов для этапа 2
    dp.message.register(
        handle_stage_2_riddle_answer,
        Stage2States.waiting_for_riddle_answer,
        F.text
    )
    
    # ✅ ДОБАВЛЯЕМ: Обработчик адресов для этапа 2
    dp.message.register(
        handle_stage_2_address,
        Stage2States.waiting_for_address,
        F.text
    )
    
    # ✅ Обработчики решений модератора для этапа 2
    dp.callback_query.register(
        handle_moderator_approve_2,
        F.data.startswith("moderator_approve_2_")
    )
    
    dp.callback_query.register(
        handle_moderator_reject_2,
        F.data.startswith("moderator_reject_2_")
    )
    
    # Обработчик некорректных сообщений в состоянии ожидания изображения
    dp.message.register(
        lambda message: message.answer(get_common_photo_error()),
        Stage2States.waiting_for_image
    )
    
    # Обработчик некорректных сообщений в состоянии ожидания ответа
    dp.message.register(
        lambda message: message.answer(get_common_answer_error()),
        Stage2States.waiting_for_riddle_answer
    )
    
    # ✅ Обработчик некорректных сообщений в состоянии ожидания адреса
    dp.message.register(
        handle_wrong_address_input_2,
        Stage2States.waiting_for_address
    )
    
    # ✅ Обработчик некорректных сообщений в состоянии ожидания решения модератора
    dp.message.register(
        handle_moderator_decision_waiting_2,
        Stage2States.waiting_for_moderator_decision
    )
