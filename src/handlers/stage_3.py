# src/handlers/stage_3.py
import asyncio
import os
import re
import sys
import subprocess
from pathlib import Path
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
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

class Stage3States(StatesGroup):
    waiting_for_image = State()
    waiting_for_riddle_answer = State()

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


async def analyze_user_image_and_save_results(telegram_id: int, user_id: int, image_path: str, message: Message, state: FSMContext):
    """Анализирует изображение пользователя и сохраняет результаты в verification"""
    logger = logging.getLogger('bot')
    
    try:
        # ✅ Проверяем существование файла
        if not os.path.exists(image_path):
            logger.error(f"Файл не найден: {image_path}")
            await message.answer("❌ Ошибка: файл не найден. Попробуйте отправить скриншот еще раз.")
            return
        
        # ✅ Анализируем с AI - используем универсальную функцию
        running_data = extract_data_for_user(image_path)
        
        if running_data and running_data.get('agent_response'):
            # ✅ Сохраняем данные в таблицу verification с user_id
            agent_data = running_data['agent_response']
            date = agent_data.get('date', 'не найдено')
            distance = agent_data.get('distance', 'не найдено')
            
            # ✅ Сохраняем в БД
            success = await save_running_data_to_db(user_id, date, distance, running_data)
            
            if success:
                await message.answer(
                    f"✅ *Данные пробежки успешно обработаны!*\n\n"
                    f"📅 Дата: {date}\n"
                    f"📏 Дистанция: {distance}\n\n"
                    f"*Продолжаем квест...*", 
                    parse_mode="Markdown"
                )
                
                # ✅ Переходим к следующей части квеста
                await continue_stage_3_quest(message, state)
                
            else:
                await message.answer(
                    "❌ *Не удалось сохранить данные пробежки.*\n"
                    "Попробуйте отправить другой скриншот, где будут видны пройдиная дистанция и дата пробежки.",
                    parse_mode="Markdown"
                )
                return
                
        else:
            await message.answer(
                "❌ *Не удалось распознать данные пробежки.*\n"
                "Попробуйте отправить другой скриншот, где будут видны пройдиная дистанция и дата пробежки.",
                parse_mode="Markdown"
            )
            return
            
    except Exception as ai_error:
        logger.error(f"Ошибка AI анализа: {ai_error}")
        await message.answer(
            "❌ *Ошибка при анализе данных.*\n"
            "Пожалуйста, попробуйте позже или отправьте другой скриншот.",
            parse_mode="Markdown"
        )
        return

async def continue_stage_3_quest(message: Message, state: FSMContext):
    """Продолжение квеста после успешного анализа картинки"""
    try:
        # Продолжаем квест
        await asyncio.sleep(1)
        
        message4 = "🎉 *Поздравляем! Ты добрался до заброшенной станции метро «Советская» и выполнил первую часть задания.*"
        await message.answer(message4, parse_mode="Markdown")
        await asyncio.sleep(2)
        
        message5 = (
            "🔍 В пыльной будке охранника висят те самые часы. Но при попытке вскрыть механизм срабатывает голосовая защита: "
            "*«Назовите пароль»*. На стене проецируется загадка:"
        )
        await message.answer(message5, parse_mode="Markdown")
        await asyncio.sleep(2)
        
        message6 = (
            "💡 *Загадка часов:*\n\n"
            "«Я – чёрный ящик, в нём – магнит.\n"
            "Он голоса ловит, как сито.\n"
            "Ты скажешь слово– он хранит,\n"
            "А после– в точности повторит.\n"
            "Он не живой, но голосит,\n"
            "И в нём душа твоя звенит.\n"
            "Лентой протяжной он поёт,\n"
            "На каждом празднике советском тебя он ждет.»\n\n"
            "*Что это❓ *\n\n"
            "*Напиши свой ответ:*"
        )
        
        await message.answer(message6, parse_mode="Markdown")
        
        # ✅ ДОБАВЛЯЕМ: Проверяем stage_5 и сохраняем в состояние
        telegram_id = message.from_user.id
        is_stage_5_user = await check_if_stage_5_user(telegram_id)
        await state.update_data(is_stage_5_user=is_stage_5_user)
        
        # Переходим в состояние ожидания ответа на загадку
        await state.set_state(Stage3States.waiting_for_riddle_answer)
        
    except Exception as e:
        logging.error(f"Ошибка при продолжении квеста stage_3: {e}")
        await message.answer("❌ Ошибка при продолжении квеста. Попробуйте еще раз.")

async def handle_stage_3_quest(callback_query: CallbackQuery, state: FSMContext):
    """Сценарий квеста для stage_id = 3"""
    try:
        # Сохраняем данные пользователя в состоянии
        await state.update_data(
            telegram_id=callback_query.from_user.id,
            attempts_left=3
        )
        
        # ✅ Отправляем оптимизированное видео с правильным путем (как в этапах 1 и 2)
        await send_optimized_video(
            callback_query.message, 
            "1_logo.mp4"
        )
        
        # Общее вступление с названием этапа из БД
        message1 = get_common_intro(3)
        await callback_query.message.answer(message1, parse_mode="Markdown")
        await asyncio.sleep(3)
        
        # Второе сообщение (специфичное для этапа 3)
        message2 = (
            "🚨 *КАТАСТРОФА!*\n\n"
            "Используя украденные данные, БЕЗЛИКИЙ запустил вирус в центральный сервер спортивно-новогоднего комитета!\n\n"
            "Активирован режим самоуничтожения базы данных. Остановить его можно только аварийным шифром, "
            "спрятанным в настенных часах на заброшенной станции метро «Советская»."
        )
        
        await callback_query.message.answer(message2, parse_mode="Markdown")
        await asyncio.sleep(2)
        
        # ✅ ИСПРАВЛЕНИЕ: Отправляем оптимизированное видео 6_logo.mp4 с тем же подходом как в этапах 1 и 2
        await send_optimized_video(
            callback_query.message,
            "6_logo.mp4",
            "🎬 *Срочно на станцию метро!*"
        )
        
        # Третье сообщение с кнопкой
        message3 = (
            "🏃‍♂️ *Скорей же беги туда!*\n\n"
            f"{get_common_photo_request()}"
        )
        
        await callback_query.message.answer(message3, parse_mode="Markdown")
        
        # Переходим в состояние ожидания изображения
        await state.set_state(Stage3States.waiting_for_image)
        
    except Exception as e:
        logging.error(f"Ошибка в stage_3: {e}")
        await callback_query.message.answer(get_common_error_message())

async def handle_stage_3_image(message: Message, state: FSMContext):
    """Обработка изображения для этапа 3 с AI анализом"""
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
        stage_folder = MEDIA_PATH / "stage_3"
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
        logger.error(f"Ошибка при обработке изображения stage_3: {e}")
        await message.answer("❌ Ошибка при обработке скриншота. Попробуйте еще раз.")

async def handle_stage_3_riddle_answer(message: Message, state: FSMContext):
    """Обработка ответа на загадку этапа 3 с поддержкой stage_5"""
    logger = logging.getLogger('bot')
    try:
        user_data = await state.get_data()
        telegram_id = user_data.get('telegram_id')
        attempts_left = user_data.get('attempts_left', 3)
        
        user_answer = message.text.strip().lower()
        correct_answer = "магнитофон"
        
        attempts_left -= 1
        await state.update_data(attempts_left=attempts_left)
        
        if user_answer == correct_answer:
            # Правильный ответ - обновляем в БД через общую функцию
            update_user_answer_in_db(telegram_id, user_answer)
            
            # ✅ ПРОВЕРКА НА 5-Й ЭТАП
            is_stage_5_user = user_data.get('is_stage_5_user', False)
            
            if is_stage_5_user:
                # Обновляем этап в БД
                await update_user_stage_in_db(telegram_id, 4)  # Переходим на этап 4
                
                # Автоматически запускаем следующий этап
                await message.answer(
                    "🎉 *Отлично! Этап 3 пройден!*\n\n"
                    "🔄 *Автоматически запускаю следующий этап...*",
                    parse_mode="Markdown"
                )
                await asyncio.sleep(2)
                
                # Запускаем следующий этап
                from .stage_4 import handle_stage_4_quest
                # Создаем fake callback для запуска
                class FakeCallback:
                    def __init__(self, message):
                        self.message = message
                        self.from_user = message.from_user
                
                fake_callback = FakeCallback(message)
                await handle_stage_4_quest(fake_callback, state)
            else:
                # Обычное завершение для пользователей отдельных этапов
                congrats_message = (
                    "🎉 *Поздравляем! Вы отгадали загадку!*\n"
                    "И получаете третий трофей:\n\n"
                    "🎁 *Промокод: SAVIOR2025*\n"
                    "Скидка 20% на следующий этап!"
                )
                
                await message.answer(congrats_message, parse_mode="Markdown")
                await asyncio.sleep(3)
                
                # ✅ ИСПРАВЛЕНИЕ: Отправляем оптимизированное видео 7_logo.mp4 с тем же подходом как в этапах 1 и 2
                await send_optimized_video(
                    message,
                    "7_logo.mp4",
                    "🎬 *Финальное видео этапа*"
                )
                
                # Финальное сообщение
                final_message = (
                    "🚨 *УКРАДЕНА ПОСЛЕДНЯЯ РЕЛИКВИЯ «ЛОШАДЬ»!*\n\n"
                    "🔥 *Это крайний рубеж! Надежда вся на тебя!*\n\n"
                    "[➡️ Перейти к следующему этапу](https://your-link-here.com)"
                )
                
                await message.answer(final_message, parse_mode="Markdown", disable_web_page_preview=True)
                
                # Сбрасываем состояние
                await state.clear()
            
        else:
            # Неправильный ответ
            if attempts_left > 0:
                hint_message = get_common_wrong_answer(attempts_left)
                await message.answer(hint_message)
            else:
                # После 3 попыток даем подсказку
                hint_message = get_common_final_hint("МАГНИТ....")
                await message.answer(hint_message, parse_mode="Markdown")
                await state.update_data(attempts_left=1)  # Даем еще одну попытку с подсказкой
        
    except Exception as e:
        logger.error(f"Ошибка при обработке ответа stage_3: {e}")
        await message.answer("❌ Ошибка при обработке ответа. Попробуйте еще раз.")

def setup_stage_3_handlers(dp):
    """Настройка обработчиков для этапа 3"""
    # Обработчик изображений для этапа 3
    dp.message.register(
        handle_stage_3_image,
        Stage3States.waiting_for_image,
        F.photo
    )
    
    # Обработчик текстовых ответов для этапа 3
    dp.message.register(
        handle_stage_3_riddle_answer,
        Stage3States.waiting_for_riddle_answer,
        F.text
    )
    
    # Обработчик некорректных сообщений в состоянии ожидания изображения
    dp.message.register(
        lambda message: message.answer(get_common_photo_error()),
        Stage3States.waiting_for_image
    )
    
    # Обработчик некорректных сообщений в состоянии ожидания ответа
    dp.message.register(
        lambda message: message.answer(get_common_answer_error()),
        Stage3States.waiting_for_riddle_answer
    )
