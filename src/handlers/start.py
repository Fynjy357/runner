from aiogram.filters import Command, CommandStart
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
import logging
import asyncio
import os
from handlers.link_generation import handle_link_click
from database import db

def setup_start_handler(dp, shutdown_manager, logger: logging.Logger, bot_username: str = None):
    """Настройка обработчиков команд /start"""
    
    async def get_user_name_patronymic(telegram_id: int):
        """Получить Имя и Отчество пользователя из manual_upload"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT mu.first_name, mu.middle_name 
                    FROM main m
                    JOIN manual_upload mu ON m.participant_id = mu.participant_id
                    WHERE m.telegram_id = ?
                ''', (telegram_id,))
                
                user_data = cursor.fetchone()
                if user_data:
                    first_name, middle_name = user_data
                    # Формируем строку "Имя Отчество", если отчество есть
                    if middle_name:
                        return f"{first_name} {middle_name}"
                    else:
                        return first_name
                return None
        except Exception as e:
            logger.error(f"Ошибка при получении имени пользователя: {e}")
            return None
    
    async def register_user(telegram_id: int, telegram_username: str = None) -> bool:
        """Регистрация пользователя при обычном /start"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Проверяем, не зарегистрирован ли уже пользователь
                cursor.execute('''
                    SELECT user_id, role FROM main WHERE telegram_id = ?
                ''', (telegram_id,))
                
                existing_user = cursor.fetchone()
                
                if existing_user:
                    user_id, current_role = existing_user
                    logger.info(f"Пользователь {telegram_id} уже зарегистрирован с ролью: {current_role}")
                    
                    # ✅ ПРОВЕРКА: Если админ/модератор - оставляем как есть
                    if current_role in ['admin', 'moderator']:
                        logger.info(f"Админ/модератор {telegram_id} сохраняет свою роль")
                        return True
                    
                    # ✅ СТАРАЯ ЛОГИКА: Просто возвращаем True для обычных пользователей
                    # Не обновляем username, не меняем ничего
                    logger.info(f"Обычный пользователь {telegram_id} уже зарегистрирован")
                    return True
                
                # ✅ СТАРАЯ ЛОГИКА: Регистрируем нового пользователя с ролью 'user'
                cursor.execute('''
                    INSERT INTO main (telegram_id, telegram_username, role)
                    VALUES (?, ?, 'user')
                ''', (telegram_id, telegram_username))
                
                user_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"Зарегистрирован новый пользователь: user_id={user_id}, telegram_id={telegram_id}, username={telegram_username}, role=user")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при регистрации пользователя {telegram_id}: {e}", exc_info=True)
            return False

    async def send_welcome_sequence(message: Message, user_name: str = None, user_stage_id: int = None):
        """Отправка приветственной последовательности с таймаутами"""
        
        # Первое сообщение с приветствием
        if user_name:
            welcome_text = f"🎄 ПРИВЕТСТВУЕМ ТЕБЯ, ТОВАРИЩ-СПОРТСМЕН!"
        else:
            welcome_text = "🎄 ПРИВЕТСТВУЕМ ТЕБЯ, ТОВАРИЩ-СПОРТСМЕН!"
        
        # Отправляем первое сообщение с "бот печатает"
        await message.bot.send_chat_action(message.chat.id, "typing")
        await asyncio.sleep(2)  # Имитация печати
        await message.answer(welcome_text)
        
        # Таймаут 5 секунд
        await asyncio.sleep(5)
        
        # Второе сообщение с детективной историей
        story_text = (
                "🔍 *Спортивно-новогодний комитет сталкивается с чрезвычайной ситуацией, угрожающей проведению Новогодних торжеств.*\n\n"
                "Из уникальной коллекции советских елочных игрушек стали бесследно пропадать бесценные реликвии…\n"
                "*Первой исчезла — раритетная ёлочная игрушка «Дед Мороз со Снегурочкой».*\n\n"
                "🚨 *Неслыханная диверсия!*"
            )
            
        await message.bot.send_chat_action(message.chat.id, "typing")
        await asyncio.sleep(3)  # Имитация печати
        await message.answer(story_text, parse_mode="Markdown")
        
        # Таймаут 5 секунд
        await asyncio.sleep(5)
        
        # Третье сообщение с заданием и картинкой
        mission_text = (
            "🎯 *Вам поручается ответственное задание с погружением на каждом этапе в детективную историю.*\n\n"
            "*Это не просто забег, ведь тебе предстоит:*\n\n"
            "1️⃣ *ВЫЙТИ НА СЛЕД.* Пробежать выбранную дистанцию от 1 км до 15 км\n"
            "2️⃣ *ЗАФИКСИРОВАТЬ УЛИКИ.* Выслать трек о прохождение дистанции\n" 
            "3️⃣ *ВЫПОЛНИТЬ ОПЕРАТИВНОЕ ЗАДАНИЕ.* Разгадать загадку\n"
            "4️⃣ *ПОЛУЧИТЬ ДАЛЬНЕЙШИЕ ИНСТРУКЦИИ.* Получить код и испытать силы на следующем этапе"
        )
        
        await message.bot.send_chat_action(message.chat.id, "typing")
        await asyncio.sleep(3)  # Имитация печати
        
        # ✅ ДОБАВЛЯЕМ: Создаем клавиатуру с кнопками в зависимости от этапа
        keyboard_buttons = []
        
        # Если пользователь на этапе 2, 3 или 4 - добавляем кнопку "познакомиться со всей историей"
        if user_stage_id and user_stage_id in [2, 3, 4]:
            keyboard_buttons.append(
                [InlineKeyboardButton(text="📖 ПОСМОТРЕТЬ ПРЕДЫСТОРИЮ", callback_data="view_history")]
            )
        
        # Всегда добавляем кнопку "начать квест"
        keyboard_buttons.append(
            [InlineKeyboardButton(text="🚀 НАЧАТЬ КВЕСТ", callback_data="start_quest")]
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        # Отправляем картинку с подписью и кнопками
        try:
            # Путь к картинке относительно корня проекта
            image_path = "media/start.jpg"
            
            # Проверяем существование файла
            if not os.path.exists(image_path):
                logger.warning(f"Картинка не найдена по пути: {image_path}")
                # Если картинки нет, отправляем только текст с кнопками
                await message.answer(mission_text, parse_mode="Markdown", reply_markup=keyboard)
                return
            
            # Создаем FSInputFile и отправляем картинку с кнопками
            photo = FSInputFile(image_path)
            await message.answer_photo(
                photo=photo,
                caption=mission_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            logger.info(f"Картинка с кнопками успешно отправлена: {image_path}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке картинки: {e}")
            # Если картинка не загрузилась, отправляем только текст с кнопками
            await message.answer(mission_text, parse_mode="Markdown", reply_markup=keyboard)

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

    @dp.message(CommandStart())
    async def handle_start(message: Message):
        """Обработка команды /start (с параметром ссылки или без)"""
        if shutdown_manager.is_bot_shutting_down():
            await message.answer("Бот находится в процессе перезапуска. Попробуйте позже.")
            return
            
        try:
            # Получаем параметр после /start
            command_parts = message.text.split()
            
            if len(command_parts) > 1:
                universal_link = command_parts[1]  # Параметр после /start
                
                logger.info(f"Пользователь {message.from_user.id} перешел по ссылке: {universal_link}")
                
                success, result_message = handle_link_click(
                    universal_link, 
                    message.from_user.id, 
                    message.from_user.username,
                    logger
                )
                
                if success:
                    # После успешной регистрации получаем Имя и Отчество пользователя
                    user_name = await get_user_name_patronymic(message.from_user.id)
                    
                    # ✅ ДОБАВЛЯЕМ: Получаем stage_id пользователя
                    user_stage_id = await get_user_stage_id(message.from_user.id)
                    
                    # Отправляем приветственную последовательность с stage_id
                    await send_welcome_sequence(message, user_name, user_stage_id)
                    
                else:
                    # Если ссылка невалидна, регистрируем как обычного пользователя
                    registration_success = await register_user(
                        message.from_user.id, 
                        message.from_user.username
                    )
                    
                    if registration_success:
                        await message.answer(
                            f"❌ {result_message}\n\n"
                            "Вы зарегистрированы как обычный пользователь.\n"
                            "Для участия в забеге получите новую ссылку у организатора."
                        )
                    else:
                        await message.answer(f"❌ {result_message}")
                        
            else:
                # Обычный /start без параметра - регистрируем как обычного пользователя
                logger.info(f"Пользователь {message.from_user.id} запустил бота без ссылки")
                
                # Проверяем, не зарегистрирован ли уже пользователь как участник
                user_name = await get_user_name_patronymic(message.from_user.id)
                
                if user_name:
                    # ✅ ДОБАВЛЯЕМ: Получаем stage_id пользователя
                    user_stage_id = await get_user_stage_id(message.from_user.id)
                    
                    # Пользователь уже зарегистрирован как участник - показываем приветствие
                    await send_welcome_sequence(message, user_name, user_stage_id)
                else:
                    # Регистрируем как обычного пользователя
                    telegram_username = message.from_user.username
                    registration_success = await register_user(
                        message.from_user.id, 
                        telegram_username
                    )
                    
                    if registration_success:
                        await message.answer(
                            "👋 Добро пожаловать в бот 'СТАРТАНИ'!\n\n"
                            "Вы успешно зарегистрированы в системе.\n"
                            "Для участия в забеге используйте ссылку от организатора.\n"
                            "Для навигации используйте /menu."
                        )
                    else:
                        await message.answer(
                            "👋 Добро пожаловать в бот 'СТАРТАНИ'!\n\n"
                            "⚠️ Возникла проблема с регистрацией. Попробуйте позже."
                        )
                
        except Exception as e:
            logger.error(f"Ошибка при обработке /start: {e}", exc_info=True)
            await message.answer("❌ Произошла ошибка при регистрации. Попробуйте позже.")