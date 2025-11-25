# src/handlers/participants_export.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
import os
from datetime import datetime

# Используем новый экспортер для бота
from utils.rr_export_bot_friendly import rr_exporter

router = Router()

class ExportStates(StatesGroup):
    waiting_for_otp = State()

@router.message(Command("export_participants"))
async def export_participants_command(message: Message, state: FSMContext):
    """Запускает процесс экспорта участников с проверкой сессии"""
    
    await message.answer(
        "🔐 **ЭКСПОРТ УЧАСТНИКОВ**\n\n"
        "📋 **Проверяем сессию...**\n"
        "• Проверка авторизации\n" 
        "• Обновление при необходимости\n"
        "• Подготовка к экспорту\n\n"
        "⏳ Пожалуйста, подождите..."
    )
    
    # Проверяем сессию в отдельном потоке
    processing_msg = await message.answer("🔄 Проверяем авторизацию...")
    
    try:
        def check_session():
            return rr_exporter.ensure_authenticated()
        
        loop = asyncio.get_event_loop()
        session_ok, session_message = await loop.run_in_executor(None, check_session)
        
        if session_ok:
            await processing_msg.edit_text(
                "✅ **СЕССИЯ АКТИВНА**\n\n"
                "Для экспорта данных участников требуется код из Authenticator.\n\n"
                "📱 **Пожалуйста, введите код:**"
            )
            await state.set_state(ExportStates.waiting_for_otp)
            
        elif session_message == "Требуется код 2FA":
            await processing_msg.edit_text(
                "🔐 **ТРЕБУЕТСЯ АВТОРИЗАЦИЯ**\n\n"
                "Для входа в систему требуется код из Google Authenticator.\n\n"
                "📱 **Пожалуйста, введите код 2FA:**"
            )
            await state.set_state(ExportStates.waiting_for_otp)
            
        elif "заблокирован" in session_message.lower():
            await processing_msg.edit_text(
                "🚫 **АККАУНТ ЗАБЛОКИРОВАН**\n\n"
                "Вы ввели неверный пароль 3 раза.\n\n"
                "⏰ **Блокировка снята через:** 5 минут\n"
                "💡 **Рекомендации:**\n"
                "• Подождите 5-10 минут\n"
                "• Проверьте пароль в .env файле\n"
                "• Используйте команду `/session_status` для проверки\n\n"
                "🔄 **Автоматическая разблокировка через 6 минут**"
            )
            
        else:
            await processing_msg.edit_text(
                f"❌ **ОШИБКА АВТОРИЗАЦИИ**\n\n"
                f"Не удалось войти в систему:\n`{session_message}`\n\n"
                f"💡 **Решение:** Запустите `python russia_running_api.py` для ручного входа"
            )
            
    except Exception as e:
        await processing_msg.edit_text(
            f"❌ **ОШИБКА ПРОВЕРКИ СЕССИИ**\n\n"
            f"Произошла ошибка:\n`{str(e)}`\n\n"
            f"Пожалуйста, попробуйте позже."
        )

@router.message(ExportStates.waiting_for_otp)
async def process_otp_code(message: Message, state: FSMContext):
    """Обрабатывает введенный OTP код"""
    
    otp_code = message.text.strip()
    
    if not otp_code.isdigit() or len(otp_code) != 6:
        await message.answer(
            "❌ **НЕВЕРНЫЙ ФОРМАТ КОДА**\n\n"
            "Код должен состоять из 6 цифр.\n"
            "Пожалуйста, введите код еще раз:"
        )
        return
    
    # Отправляем сообщение о начале экспорта
    processing_msg = await message.answer(
        "⏳ **ВЫПОЛНЯЕМ ЭКСПОРТ...**\n\n"
        "Это может занять несколько секунд..."
    )
    
    try:
        def run_export():
            return rr_exporter.export_participants_excel(otp_code, use_fixed_name=True)
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_export)
        
        if result:
            filename = result
            file_size = os.path.getsize(filename)
            
            mod_time = os.path.getmtime(filename)
            mod_time_str = datetime.fromtimestamp(mod_time).strftime('%d.%m.%Y %H:%M:%S')
            
            await processing_msg.edit_text(
                f"✅ **ЭКСПОРТ УСПЕШНО ЗАВЕРШЕН!**\n\n"
                f"📁 **Файл:** `{filename}`\n"
                f"📏 **Размер:** {file_size:,} bytes\n"
                f"🕐 **Обновлен:** {mod_time_str}\n\n"
                f"📊 **Содержит данные всех участников события**\n"
                f"🏃 **Событие:** OnlineraceTheMysteryoftheLostCollection"
            )
            
            with open(filename, 'rb') as f:
                file_data = f.read()
            
            document = BufferedInputFile(
                file=file_data,
                filename=filename
            )
            
            await message.answer_document(
                document=document,
                caption=f"📊 Экспорт участников - {filename}\n🕐 Обновлен: {mod_time_str}"
            )
                
        else:
            await processing_msg.edit_text(
                "❌ **ОШИБКА ЭКСПОРТА**\n\n"
                "Не удалось выполнить экспорт. Возможные причины:\n"
                "• Неверный код Authenticator\n"
                "• Проблемы с подключением\n"
                "• Технические работы на сайте\n\n"
                "Попробуйте позже или проверьте код."
            )
            
    except Exception as e:
        await processing_msg.edit_text(
            f"❌ **КРИТИЧЕСКАЯ ОШИБКА**\n\n"
            f"Произошла ошибка при экспорте:\n"
            f"`{str(e)}`\n\n"
            f"Пожалуйста, попробуйте позже."
        )
    
    await state.clear()

@router.message(Command("export_help"))
async def export_help_command(message: Message):
    """Показывает справку по экспорту"""
    
    help_text = (
        "📊 **КОМАНДА ЭКСПОРТА УЧАСТНИКОВ**\n\n"
        "**Команда:** `/export_participants`\n\n"
        "**Что делает:**\n"
        "• Автоматически проверяет сессию\n"
        "• Обновляет авторизацию при необходимости\n" 
        "• Экспортирует всех участников события\n"
        "• Сохраняет в Excel файл\n"
        "• Отправляет файл в чат\n\n"
        "**Требуется:**\n"
        "• Код из Google Authenticator\n"
        "• Учетные данные в .env файле\n\n"
        "💡 **Совет:** Код действителен 30 секунд"
    )
    
    await message.answer(help_text)

@router.message(Command("session_status"))
async def session_status_command(message: Message):
    """Показывает статус текущей сессии"""
    
    try:
        def check_status():
            return rr_exporter.ensure_authenticated()
        
        loop = asyncio.get_event_loop()
        session_ok, session_message = await loop.run_in_executor(None, check_status)
        
        if session_ok:
            status_text = (
                "🟢 **СТАТУС СЕССИИ: АКТИВНА**\n\n"
                "✅ Сессия действительна\n"
                "✅ Готова к экспорту\n"
                "✅ Авторизация подтверждена"
            )
        else:
            if session_message == "Требуется код 2FA":
                status_text = (
                    "🟡 **СТАТУС СЕССИИ: ТРЕБУЕТСЯ 2FA**\n\n"
                    "🔐 Требуется код из Authenticator\n"
                    "📱 Используйте `/export_participants`\n"
                    "💾 Учетные данные загружены"
                )
            elif "заблокирован" in session_message.lower():
                status_text = (
                    "🔴 **СТАТУС СЕССИИ: ЗАБЛОКИРОВАН**\n\n"
                    "🚫 Аккаунт временно заблокирован\n"
                    "⏰ Разблокировка через 5 минут\n"
                    "💡 Подождите и попробуйте снова"
                )
            else:
                status_text = (
                    "🔴 **СТАТУС СЕССИИ: НЕАКТИВНА**\n\n"
                    f"❌ Проблема: `{session_message}`\n"
                    "💡 Запустите `python russia_running_api.py` для ручного входа"
                )
        
        await message.answer(status_text)
        
    except Exception as e:
        await message.answer(
            f"❌ **ОШИБКА ПРОВЕРКИ СТАТУСА**\n\n"
            f"`{str(e)}`"
        )

def setup_participants_export_handler(dp):
    dp.include_router(router)
