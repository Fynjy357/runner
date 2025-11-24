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

class Stage4States(StatesGroup):
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
                await continue_stage_4_quest(message, state)
                
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

async def continue_stage_4_quest(message: Message, state: FSMContext):
    """Продолжение квеста после успешного анализа картинки"""
    try:
        # Продолжаем квест
        await asyncio.sleep(1)
        
        message5 = "🎉 *Ура! Ты у пульта!*"
        await message.answer(message5, parse_mode="Markdown")
        await asyncio.sleep(2)
        
        message6 = (
            "🔒 *Но система заблокирована финальной загадкой БЕЗЛИКОГО:*"
        )
        await message.answer(message6, parse_mode="Markdown")
        await asyncio.sleep(1)
        
        message7 = (
            "💡 *ФИНАЛЬНАЯ ЗАГАДКА БЕЗЛИКОГО:*\n\n"
            "«Не зверь, но дышит, не река, но течёт,\n"
            "Её результат порою— счастливый билет.\n"
            "За дефицитом, за мечтой вожделенной\n"
            "Стояла она в государстве советском...»\n\n"
            "*ЧТО ЭТО❓*\n\n"
            "*Напиши свой ответ:*"
        )
        
        await message.answer(message7, parse_mode="Markdown")
        
        # ✅ ДОБАВЛЯЕМ: Проверяем stage_5 и сохраняем в состояние
        telegram_id = message.from_user.id
        is_stage_5_user = await check_if_stage_5_user(telegram_id)
        await state.update_data(is_stage_5_user=is_stage_5_user)
        
        # Переходим в состояние ожидания ответа на загадку
        await state.set_state(Stage4States.waiting_for_riddle_answer)
        
    except Exception as e:
        logging.error(f"Ошибка при продолжении квеста stage_4: {e}")
        await message.answer("❌ Ошибка при продолжении квеста. Попробуйте еще раз.")

async def handle_stage_4_quest(callback_query: CallbackQuery, state: FSMContext):
    """Сценарий квеста для stage_id = 4 (финальный этап)"""
    try:
        # Сохраняем данные пользователя в состоянии
        await state.update_data(
            telegram_id=callback_query.from_user.id,
            attempts_left=3
        )
        
        # ✅ Проверяем существование видео файлов
        videos_to_check = ["1_logo.mp4", "8_logo.mp4", "9_logo.mp4"]
        for video in videos_to_check:
            video_path = get_media_file(video)
            if os.path.exists(video_path):
                logging.info(f"✅ Видео файл найден: {video_path}")
            else:
                logging.error(f"❌ Видео файл не найден: {video_path}")
        
        # ✅ Отправляем оптимизированное видео с правильным путем
        await send_optimized_video(
            callback_query.message, 
            "1_logo.mp4"
        )
        
        # Общее вступление с названием этапа из БД
        message1 = get_common_intro(4)
        await callback_query.message.answer(message1, parse_mode="Markdown")
        await asyncio.sleep(3)
        
        # Второе сообщение
        message2 = (
            "🔥 *ФИНАЛ БЛИЗОК!*\n\n"
            "Вы мчитесь к железнодорожной станции.\n\n"
            "Безумный план БЕЗЛИКОГО — навсегда опорочить праздник.\n\n"
            "Он спрятал последнюю реликвию на одной из елок, стоящих на платформе поезда — медаль невозможно отыскать!"
        )
        
        await callback_query.message.answer(message2, parse_mode="Markdown")
        await asyncio.sleep(3)
        
        # ✅ Отправляем оптимизированное видео 8_logo.mp4
        await send_optimized_video(
            callback_query.message,
            "8_logo.mp4",
            "🎬 *Срочно на железнодорожную станцию!*"
        )
        
        # Третье сообщение
        message3 = (
            "🚂 *ПОЕЗД СЛЕДУЕТ ПО ИЗМЕНЁННОМУ БЕЗЛИКИМ МАРШРУТУ В НЕДОСТРОЕННЫЙ ТУПИК, ГДЕ СОЙДЕТ С РЕЛЬС!*\n\n"
            "Вам нужно добраться до пульта системы автоматического управления, чтобы остановить поезд.\n\n"
            "💥 *Это ваш последний забег. Во имя Нового года!*\n\n"
            "🏃‍♂️ *Вперед, товарищ! Беги скорее!*"
        )
        
        await callback_query.message.answer(message3, parse_mode="Markdown")
        await asyncio.sleep(2)
        
        # Четвертое сообщение с кнопкой
        message4 = get_common_photo_request()
        
        await callback_query.message.answer(message4, parse_mode="Markdown")
        
        # Переходим в состояние ожидания изображения
        await state.set_state(Stage4States.waiting_for_image)
        
    except Exception as e:
        logging.error(f"Ошибка в stage_4: {e}")
        await callback_query.message.answer(get_common_error_message())

async def handle_stage_4_image(message: Message, state: FSMContext):
    """Обработка изображения для этапа 4 с AI анализом"""
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
        stage_folder = MEDIA_PATH / "stage_4"
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
        logger.error(f"Ошибка при обработке изображения stage_4: {e}")
        await message.answer("❌ Ошибка при обработке скриншота. Попробуйте еще раз.")

async def handle_stage_4_riddle_answer(message: Message, state: FSMContext):
    """Обработка ответа на загадку этапа 4 с поддержкой stage_5"""
    logger = logging.getLogger('bot')
    try:
        user_data = await state.get_data()
        telegram_id = user_data.get('telegram_id')
        attempts_left = user_data.get('attempts_left', 3)
        
        user_answer = message.text.strip().lower()
        correct_answer = "очередь"
        
        attempts_left -= 1
        await state.update_data(attempts_left=attempts_left)
        
        if user_answer == correct_answer:
            # ✅ Сохраняем правильный ответ в БД
            update_user_answer_in_db(telegram_id, user_answer)
            
            # ✅ ПРОВЕРКА НА 5-Й ЭТАП
            is_stage_5_user = user_data.get('is_stage_5_user', False)
            
            if is_stage_5_user:
                # ✅ ФИНАЛЬНЫЙ ЭТАП - обновляем на завершение
                await update_user_stage_in_db(telegram_id, 5)  # Завершаем квест
                
                # Сообщение о завершении для stage_5 пользователей
                congrats_message = (
                    "🎉 *ПОЗДРАВЛЯЕМ! КОД ПРИНЯТ!*\n\n"
                    "🛑 *Поезд с оглушительным рычанием останавливается.*\n\n"
                    "🌟 *Последняя медаль - «Лошадь» спасена!*"
                )
            else:
                # Обычное завершение для пользователей отдельных этапов
                congrats_message = (
                    "🎉 *ПОЗДРАВЛЯЕМ! КОД ПРИНЯТ!*\n\n"
                    "🛑 *Поезд с оглушительным рычанием останавливается.*\n\n"
                    "🌟 *Последняя медаль - «Лошадь» спасена!*"
                )
            
            await message.answer(congrats_message, parse_mode="Markdown")
            await asyncio.sleep(3)
            
            # ✅ Отправляем оптимизированное видео 9_logo.mp4
            await send_optimized_video(
                message,
                "9_logo.mp4",
                "🎬 *ФИНАЛЬНОЕ ВИДЕО КВЕСТА*"
            )
            
            # Финальное сообщение
            final_message = (
                "🎊 *УРА! ДЕЛО ЗАКРЫТО!*\n\n"
                "✨ *Мы вернули все пропавшие реликвии, преодолели большое количество увлекательных и захватывающих километров, "
                "разгадывая загадки БЕЗЛИКОГО!*\n\n"
                "🎄 *ПРАЗДНИК СПАСЁН!*\n\n"
                "🌟 *Эта история стала по-настоящему волшебной!*\n\n"
                "💫 *Спасибо за участие в этом невероятном приключении!*"
            )
            
            await message.answer(final_message, parse_mode="Markdown")
            
            # Сбрасываем состояние
            await state.clear()
            
        else:
            # Неправильный ответ
            if attempts_left > 0:
                hint_message = get_common_wrong_answer(attempts_left)
                await message.answer(hint_message)
            else:
                # После 3 попыток даем финальную подсказку
                hint_message = get_common_final_hint("ОЧЕР..")
                await message.answer(hint_message, parse_mode="Markdown")
                await state.update_data(attempts_left=1)  # Даем еще одну попытку с подсказкой
        
    except Exception as e:
        logger.error(f"Ошибка при обработке ответа stage_4: {e}")
        await message.answer("❌ Ошибка при обработке ответа. Попробуйте еще раз.")

def setup_stage_4_handlers(dp):
    """Настройка обработчиков для этапа 4"""
    # Обработчик изображений для этапа 4
    dp.message.register(
        handle_stage_4_image,
        Stage4States.waiting_for_image,
        F.photo
    )
    
    # Обработчик текстовых ответов для этапа 4
    dp.message.register(
        handle_stage_4_riddle_answer,
        Stage4States.waiting_for_riddle_answer,
        F.text
    )
    
    # Обработчик некорректных сообщений в состоянии ожидания изображения
    dp.message.register(
        lambda message: message.answer(get_common_photo_error()),
        Stage4States.waiting_for_image
    )
    
    # Обработчик некорректных сообщений в состоянии ожидания ответа
    dp.message.register(
        lambda message: message.answer(get_common_answer_error()),
        Stage4States.waiting_for_riddle_answer
    )
