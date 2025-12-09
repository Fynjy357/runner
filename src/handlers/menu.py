# handlers/menu.py
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Router, F
from aiogram.filters import Command
import logging
from database import db  # Импортируем нашу базу данных

# Создаем роутер для меню
menu_router = Router()

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает главное меню с инлайн-кнопками в формате 2×2"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="🏃‍♂️ Регистрация на забег", 
                callback_data="menu_registration"
            ),
            InlineKeyboardButton(
                text="📰 Актуальные новости", 
                url="https://t.me/STARTANI_online"
            )
        ],
        [
            InlineKeyboardButton(
                text="✉️ Написать нам", 
                url="https://t.me/STARTANIchat/18"
            ),
            InlineKeyboardButton(
                text="🎁 Розыгрыш", 
                callback_data="menu_raffle"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_raffle_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для раздела розыгрыша"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="🎯 Принять участие в розыгрыше", 
                callback_data="raffle_participate"
            )
        ],
        [
            InlineKeyboardButton(
                text="📢 Подписаться на группу", 
                url="https://t.me/STARTANI_online"
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Назад", 
                callback_data="menu_back"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_raffle_participation_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру после успешной регистрации на розыгрыш"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="📢 Подписаться на группу", 
                url="https://t.me/STARTANI_online"
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Назад", 
                callback_data="menu_back"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@menu_router.message(Command("menu"))
async def handle_menu_command(message: Message):
    """Обработчик команды /menu"""
    try:
        menu_text = (
            "🎯 *Главное меню бота*\n\n"
            "Здесь вы можете:\n\n"
            "🏃‍♂️ *Регистрация на забег* - зарегистрироваться на ближайшие забеги\n"
            "📰 *Актуальные новости* - следить за последними новостями\n"
            "✉️ *Написать нам* - связаться с организаторами\n"
            "🎁 *Розыгрыш* - участвовать в розыгрышах призов\n\n"
            "Выберите нужный раздел:"
        )
        
        await message.answer(
            menu_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logging.error(f"Ошибка при показе меню: {e}")
        await message.answer("❌ Произошла ошибка при загрузке меню.")

@menu_router.callback_query(F.data == "menu_registration")
async def handle_registration(callback_query):
    """Обработчик кнопки 'Регистрация на забег'"""
    try:
        registration_text = (
            "🏃‍♂️ *Регистрация на забег*\n\n"
            "Для регистрации на ближайшие забеги перейдите по ссылке:\n\n"
            "🌐 *RussiaRunning*: https://russiarunning.com/event/mysticalrun\n\n"
            "📋 *Как зарегистрироваться:*\n"
            "1. Перейдите на сайт RussiaRunning\n"
            "2. Выберите интересующий вас забег\n"
            "3. Заполните форму регистрации\n"
            "4. Оплатите участие\n\n"
            "📞 *Нужна помощь?* Напишите нам через раздел 'Написать нам'"
        )
        
        await callback_query.message.edit_text(
            registration_text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        await callback_query.answer()
        
    except Exception as e:
        logging.error(f"Ошибка при показе регистрации: {e}")
        await callback_query.answer("❌ Ошибка при загрузке информации")

@menu_router.callback_query(F.data == "menu_raffle")
async def handle_raffle(callback_query):
    """Обработчик кнопки 'Розыгрыш'"""
    try:
        # Проверяем, участвует ли пользователь уже в розыгрыше
        telegram_id = callback_query.from_user.id
        telegram_username = callback_query.from_user.username
        is_participating = db.is_user_participating_in_raffle(telegram_id)
        
        raffle_text = (
            "🎁 *Розыгрыш призов*\n\n"
            "🎄 *Ближайший розыгрыш:*\n"
            "📅 *Дата:* 21 декабря 2025 года\n"
            "📍 *Место:* Наш Telegram канал\n\n"
            "🎯 *Как участвовать:*\n"
            "1. Подпишитесь на наш Telegram канал:\n"
            "[STARTANI_online](https://t.me/STARTANI_online)\n"
            "2. Следите за анонсами розыгрыша\n"
            "3. Выполните условия участия\n\n"
            "🏆 *Призы:*\n"
            "• *3 счастливца* получат бесплатный слот на участие в забеге\n"
            "• *10 участников* получат промокод со скидкой 30%\n"
            "• *10 человек* выиграют сувениры СТАРТАНИ в прямом эфире\n\n"
        )
        
        # Добавляем информацию о статусе участия
        if is_participating:
            raffle_text += "✅ *Вы уже участвуете в розыгрыше!*\n\n"
        else:
            raffle_text += "🎯 *Нажмите 'Принять участие', чтобы зарегистрироваться!*\n\n"
            
        raffle_text += "🔔 *Не пропустите! Следите за новостями!*"
        
        await callback_query.message.edit_text(
            raffle_text,
            parse_mode="Markdown",
            reply_markup=get_raffle_keyboard(),
            disable_web_page_preview=True
        )
        await callback_query.answer()
        
    except Exception as e:
        logging.error(f"Ошибка при показе розыгрыша: {e}")
        await callback_query.answer("❌ Ошибка при загрузке информации о розыгрыше")

@menu_router.callback_query(F.data == "menu_back")
async def handle_back(callback_query):
    """Обработчик кнопки 'Назад' - возврат в главное меню"""
    try:
        menu_text = (
            "🎯 *Главное меню бота*\n\n"
            "Здесь вы можете:\n\n"
            "🏃‍♂️ *Регистрация на забег* - зарегистрироваться на ближайшие забеги\n"
            "📰 *Актуальные новости* - следить за последними новостями\n"
            "✉️ *Написать нам* - связаться с организаторами\n"
            "🎁 *Розыгрыш* - участвовать в розыгрышах призов\n\n"
            "Выберите нужный раздел:"
        )
        
        await callback_query.message.edit_text(
            menu_text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        await callback_query.answer()
        
    except Exception as e:
        logging.error(f"Ошибка при возврате в меню: {e}")
        await callback_query.answer("❌ Ошибка при возврате в меню")

@menu_router.callback_query(F.data == "raffle_participate")
async def handle_raffle_participate(callback_query):
    """Обработчик кнопки 'Принять участие в розыгрыше'"""
    try:
        telegram_id = callback_query.from_user.id
        telegram_username = callback_query.from_user.username
        
        # Проверяем, не участвует ли пользователь уже
        if db.is_user_participating_in_raffle(telegram_id):
            success_text = (
                "🎉 *Поздравляем!*\n\n"
                "✅ *Вы уже зарегистрированы на розыгрыш!*\n\n"
                "📅 *Розыгрыш состоится:* 07 декабря 2025 года\n\n"
                "🔔 *Следите за новостями в нашем канале:*\n"
                "[STARTANI_online](https://t.me/STARTANI_online)\n\n"
                "🏆 *Желаем удачи!* 🍀"
            )
        else:
            # Добавляем пользователя в базу данных
            success = db.add_raffle_participant(
                telegram_id=telegram_id,
                telegram_username=telegram_username,
                raffle_id=None  # Можно указать конкретный ID розыгрыша
            )
            
            if success:
                success_text = (
                    "🎉 *Поздравляем!*\n\n"
                    "✅ *Вы успешно зарегистрированы на розыгрыш!*\n\n"
                    "📅 *Розыгрыш состоится:* 07 декабря 2025 года\n\n"
                    "🔔 *Следите за новостями в нашем канале:*\n"
                    "[STARTANI_online](https://t.me/STARTANI_online)\n\n"
                    "🎯 *Не забудьте выполнить условия участия:*\n"
                    "• Подписаться на канал\n"
                    "• Следить за анонсами\n"
                    "• Выполнить дополнительные условия\n\n"
                    "🏆 *Желаем удачи!* 🍀"
                )
            else:
                success_text = (
                    "❌ *Произошла ошибка*\n\n"
                    "Не удалось зарегистрировать вас на розыгрыш.\n"
                    "Попробуйте позже или обратитесь к администратору."
                )
        
        await callback_query.message.edit_text(
            success_text,
            parse_mode="Markdown",
            reply_markup=get_raffle_participation_keyboard(),
            disable_web_page_preview=True
        )
        await callback_query.answer("✅ Вы зарегистрированы на розыгрыш")
        
    except Exception as e:
        logging.error(f"Ошибка при регистрации на розыгрыш: {e}")
        await callback_query.answer("❌ Ошибка при регистрации на розыгрыш")

def setup_menu_handler(dp):
    """Настройка обработчиков меню"""
    dp.include_router(menu_router)
