# common_intro.py
"""
Общие элементы для всех этапов квеста
"""

import asyncio


def get_common_intro(stage_id: int) -> str:
    """
    Возвращает общее вступление для всех этапов
    
    Args:
        stage_id: ID этапа
        
    Returns:
        str: Текст вступления с названием этапа
    """
    stage_name = get_stage_name_from_db(stage_id)
    return (
        "🔍 *Подозреваемый, известный как «БЕЗЛИКИЙ», действует нагло и оставляет ироничные улики.*\n\n"
        "Каждая пропавшая игрушка – это часть головоломки от общей детективной истории!\n"
        "Вы вступили в оперативный штаб с целью вернуть утраченные реликвии.\n\n"
        f"*Ваше задание:*\n{stage_name}"
    )


def get_common_photo_request() -> str:
    """
    Возвращает стандартный текст для запроса фото
    
    Returns:
        str: Текст запроса скриншота
    """
    return "📸 *Приложи отчет/трек/скриншот о прохождении дистанции*"


def get_common_processing_message() -> str:
    """
    Возвращает сообщение о обработке скриншота
    
    Returns:
        str: Текст подтверждения обработки
    """
    return "✅ Скриншот получен! Обрабатываем..."


def get_common_error_message() -> str:
    """
    Возвращает стандартное сообщение об ошибке
    
    Returns:
        str: Текст ошибки
    """
    return "❌ Произошла ошибка. Попробуйте позже."


def get_common_photo_error() -> str:
    """
    Возвращает сообщение об ошибке при отправке фото
    
    Returns:
        str: Текст ошибки фото
    """
    return "📸 Пожалуйста, отправьте скриншот трека."


def get_common_answer_error() -> str:
    """
    Возвращает сообщение об ошибке при отправке ответа
    
    Returns:
        str: Текст ошибки ответа
    """
    return "❓ Пожалуйста, напишите ответ на загадку."


def get_common_wrong_answer(attempts_left: int) -> str:
    """
    Возвращает сообщение о неправильном ответе
    
    Args:
        attempts_left: Количество оставшихся попыток
        
    Returns:
        str: Текст сообщения о неправильном ответе
    """
    return f"❌ Неправильно! Осталось попыток: {attempts_left}\nПопробуйте еще раз:"


def get_common_final_hint(hint: str) -> str:
    """
    Возвращает сообщение с финальной подсказкой
    
    Args:
        hint: Текст подсказки
        
    Returns:
        str: Текст сообщения с подсказкой
    """
    return (
        f"❌ Снова неправильно\n\n"
        f"💡 *Подсказка:* {hint}\n\n"
        f"Попробуйте еще раз с подсказкой:"
    )


def save_user_data_to_db(telegram_id: int, image_path: str) -> bool:
    """
    Сохраняет данные пользователя в базу данных
    
    Args:
        telegram_id: ID пользователя в Telegram
        image_path: Путь к сохраненному изображению
        
    Returns:
        bool: Успешно ли сохранение
    """
    try:
        from database import db
        import logging
        
        logging.info(f"Сохранение данных для пользователя {telegram_id}, путь: {image_path}")
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем user_id
            cursor.execute('SELECT user_id FROM main WHERE telegram_id = ?', (telegram_id,))
            user_result = cursor.fetchone()
            
            if user_result:
                user_id = user_result[0]
                logging.info(f"Найден user_id: {user_id} для telegram_id: {telegram_id}")
                
                # Сохраняем в user_data (без stage_number)
                cursor.execute('''
                    INSERT INTO user_data (user_id, image_url, answer_text)
                    VALUES (?, ?, NULL)
                ''', (user_id, image_path))
                
                conn.commit()
                logging.info(f"Успешно сохранены данные для user_id: {user_id}")
                return True
            else:
                logging.warning(f"Не найден user_id для telegram_id: {telegram_id}")
        return False
    except Exception as e:
        import logging
        logging.error(f"Ошибка при сохранении данных пользователя {telegram_id}: {e}")
        return False


def update_user_answer_in_db(telegram_id: int, answer: str) -> bool:
    """
    Обновляет ответ пользователя в базе данных
    
    Args:
        telegram_id: ID пользователя в Telegram
        answer: Ответ пользователя
        
    Returns:
        bool: Успешно ли обновление
    """
    try:
        from database import db
        import logging
        
        logging.info(f"Обновление ответа для пользователя {telegram_id}, ответ: {answer}")
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем user_id
            cursor.execute('SELECT user_id FROM main WHERE telegram_id = ?', (telegram_id,))
            user_result = cursor.fetchone()
            
            if user_result:
                user_id = user_result[0]
                logging.info(f"Найден user_id: {user_id} для telegram_id: {telegram_id}")
                
                # Получаем последнюю запись для этого пользователя
                cursor.execute('''
                    SELECT data_id FROM user_data 
                    WHERE user_id = ?
                    ORDER BY data_id DESC LIMIT 1
                ''', (user_id,))
                
                data_result = cursor.fetchone()
                
                if data_result:
                    data_id = data_result[0]
                    logging.info(f"Найдена запись data_id: {data_id} для обновления")
                    
                    # Обновляем ответ в user_data
                    cursor.execute('''
                        UPDATE user_data 
                        SET answer_text = ?
                        WHERE data_id = ?
                    ''', (answer, data_id))
                    
                    conn.commit()
                    logging.info(f"Успешно обновлен ответ для data_id: {data_id}")
                    return True
                else:
                    logging.warning(f"Не найдено записей для user_id: {user_id}")
            else:
                logging.warning(f"Не найден user_id для telegram_id: {telegram_id}")
        return False
    except Exception as e:
        import logging
        logging.error(f"Ошибка при обновлении ответа пользователя {telegram_id}: {e}")
        return False


def get_stage_name_from_db(stage_id: int) -> str:
    """
    Получает название этапа из базы данных
    
    Args:
        stage_id: ID этапа
        
    Returns:
        str: Название этапа из БД
    """
    try:
        from database import db
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT stage_name FROM stages WHERE stage_id = ?', (stage_id,))
            result = cursor.fetchone()
            if result:
                return result[0]
        
        # Если не нашли в БД, возвращаем базовое название
        return f"Этап {stage_id}"
    except Exception as e:
        import logging
        logging.error(f"Ошибка при получении названия этапа {stage_id}: {e}")
        return f"Этап {stage_id}"


# ✅ ДОБАВЛЯЕМ НОВЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С CURRENT_STAGE

async def get_user_current_stage_from_db(telegram_id: int) -> int:
    """
    Получает текущий этап пользователя из базы данных
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        int: Текущий этап пользователя
    """
    try:
        from database import db
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT current_stage FROM main WHERE telegram_id = ?",
                (telegram_id,)
            )
            result = cursor.fetchone()
            return result[0] if result else 1
    except Exception as e:
        import logging
        logging.error(f"Ошибка при получении current_stage для {telegram_id}: {e}")
        return 1


async def update_user_stage_in_db(telegram_id: int, new_stage: int) -> bool:
    """
    Обновляет текущий этап пользователя в базе данных
    
    Args:
        telegram_id: ID пользователя в Telegram
        new_stage: Новый номер этапа
        
    Returns:
        bool: Успешно ли обновление
    """
    try:
        from database import db
        import logging
        
        logging.info(f"Обновление этапа для пользователя {telegram_id} на {new_stage}")
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE main SET current_stage = ? WHERE telegram_id = ?",
                (new_stage, telegram_id)
            )
            conn.commit()
            logging.info(f"Успешно обновлен этап для пользователя {telegram_id} на {new_stage}")
            return True
    except Exception as e:
        import logging
        logging.error(f"Ошибка при обновлении этапа пользователя {telegram_id}: {e}")
        return False


async def check_if_stage_5_user(telegram_id: int) -> bool:
    """
    Проверяет, является ли пользователь участником 5-го этапа
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        bool: True если пользователь stage_5
    """
    try:
        from database import db
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT stage_id FROM manual_upload mu "
                "JOIN main m ON mu.participant_id = m.participant_id "
                "WHERE m.telegram_id = ?",
                (telegram_id,)
            )
            result = cursor.fetchone()
            return result and result[0] == 5  # stage_id = 5 означает 5-й этап
    except Exception as e:
        import logging
        logging.error(f"Ошибка проверки stage_5 пользователя {telegram_id}: {e}")
        return False


# ✅ ВОССТАНАВЛИВАЕМ ФУНКЦИЮ get_stage_history для совместимости
def get_stage_history(stage_number: int) -> dict:
    """
    Возвращает историю для конкретного этапа
    
    Args:
        stage_number: Номер этапа (1-4)
        
    Returns:
        dict: Данные истории этапа
    """
    stage_histories = {
        1: {
            'video': "2_logo.mp4",
            'title': "🎄 *ГЛАВА 1. «Предательство в Центральном штабе»*",
            'story': (
                "🔍 *БЕЗЛИКИЙ вышел на связь.*\n\n"
                "Он не просто вор — он бывший сотрудник спортивно-новогоднего комитета. "
                "Он знает все наши внутренние протоколы. Его цель — не кража, а уничтожение в пыль новогодней магии.\n\n"
                "🎄 Первая игрушка — Дед Мороз со Снегурочкой — уже в его руках. "
                "На месте пропажи найден въездной талон на территорию морского порта – "
                "заброшенного производства по изготовлению деталей для игрушек.\n\n"
                "🏃‍♂️ *Возможно там ты сможешь догнать БЕЗЛИКОГО и вернуть первую реликвию.*"
            ),
            'video2': "3_logo.mp4"
        },
        2: {
            'video': "4_logo.mp4",
            'title': "⚡ *ГЛАВА 2. «Провал операции»*",
            'story': (
                "⚡ *В спортивно-новогоднем комитете раздор!*\n\n"
                "Пока ты был в порту, БЕЗЛИКИЙ проник в хранилище и украл вторую реликвию «Снеговик». "
                "Хуже того, внутри «Снеговика» находился флеш-носитель с кодами доступа ко всем системам безопасности комитета.\n\n"
                "🤔 *Как БЕЗЛИКИЙ смог провернуть это так легко?*\n\n"
                "Тебе нужно найти зацепку на месте преступления. Необходимо незамедлительно бежать на склад!"
            ),
            'video2': "5_logo.mp4"
        },
        3: {
            'video': "6_logo.mp4",
            'title': "🚨 *ГЛАВА 3. «Обратный отсчет»*",
            'story': (
                "🚨 *КАТАСТРОФА!*\n\n"
                "Используя украденные данные, БЕЗЛИКИЙ запустил вирус в центральный сервер спортивно-новогоднего комитета!\n\n"
                "Активирован режим самоуничтожения базы данных. Остановить его можно только аварийным шифром, "
                "спрятанным в настенных часах на заброшенной станции метро «Советская».\n\n"
                "🏃‍♂️ *Срочно на станцию метро!*"
            ),
            'video2': "7_logo.mp4"
        },
        4: {
            'video': "8_logo.mp4",
            'title': "🔥 *ГЛАВА 4. «Последний рейс»*",
            'story': (
                "🔥 *ФИНАЛ БЛИЗОК!*\n\n"
                "Вы мчитесь к железнодорожной станции.\n\n"
                "Безумный план БЕЗЛИКОГО — навсегда опорочить праздник.\n\n"
                "Он спрятал последнюю реликвию на одной из елок, стоящих на платформе поезда — медаль невозможно отыскать!\n\n"
                "🚂 *ПОЕЗД СЛЕДУЕТ ПО ИЗМЕНЁННОМУ БЕЗЛИКИМ МАРШРУТУ В НЕДОСТРОЕННЫЙ ТУПИК, ГДЕ СОЙДЕТ С РЕЛЬС!*\n\n"
                "Вам нужно добраться до пульта системы автоматического управления, чтобы остановить поезд.\n\n"
                "💥 *Это ваш последний забег. Во имя Нового года!*"
            ),
            'video2': "9_logo.mp4"
        }
    }
    
    return stage_histories.get(stage_number, {})


# ✅ ДОБАВЛЯЕМ НОВУЮ ФУНКЦИЮ ДЛЯ ОТПРАВКИ ВИДЕО ЧЕРЕЗ ОПТИМИЗАТОР
async def send_stage_history_video(message, stage_number: int):
    """
    Отправляет видео истории этапа
    
    Args:
        message: Объект сообщения
        stage_number: Номер этапа
        
    Returns:
        bool: Успешно ли отправка
    """
    try:
        from utils.video_optimizer import send_optimized_video
        from aiogram.types import FSInputFile
        from utils.video_optimizer import get_media_path
        import asyncio
        import logging  # ✅ Импортируем logging здесь
        
        history = get_stage_history(stage_number)
        if history:
            # ✅ Отправляем первое видео через оптимизатор (как обычно)
            await send_optimized_video(
                message,
                history['video'],
                history['title']
            )
            
            # Отправляем историю текстом
            await message.answer(history['story'], parse_mode="Markdown")
            await asyncio.sleep(2)

            # ✅ ИСПРАВЛЕНИЕ: Для видео 7_logo.mp4 отправляем БЕЗ оптимизации
            if stage_number == 3 and history.get('video2') == "7_logo.mp4":
                try:
                    media_path = get_media_path()
                    video_path = media_path / "7_logo.mp4"
                    
                    if video_path.exists():
                        video = FSInputFile(str(video_path))
                        await message.answer_video(
                            video=video,
                            supports_streaming=True
                        )
                        logging.info(f"✅ Видео 7_logo.mp4 отправлено напрямую (без оптимизации)")
                    else:
                        logging.error(f"❌ Видео не найдено: {video_path}")
                        await message.answer("🎬 *Продолжаем историю...*", parse_mode="Markdown")
                except Exception as direct_error:
                    logging.error(f"❌ Ошибка прямой отправки 7_logo.mp4: {direct_error}")
                    await message.answer("🎬 *Продолжаем историю...*", parse_mode="Markdown")
            else:
                # ✅ Остальные видео отправляем через оптимизатор
                await send_optimized_video(
                    message,
                    history['video2']
                )

            return True
        return False
        
    except Exception as e:
        # ✅ ИСПРАВЛЕНИЕ: Используем глобальный logging
        import logging
        logging.error(f"Ошибка при отправке истории этапа {stage_number}: {e}")
        return False


