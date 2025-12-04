#!/usr/bin/env python3
"""
Команды администратора для работы с промокодами
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging
import os
import sys

# Добавляем родительскую директорию в путь Python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from database import db
from .promo_manager import promo_manager

router = Router()

class PromoCodeStates(StatesGroup):
    waiting_for_excel_file = State()
    waiting_for_csv_file = State()
    waiting_for_txt_file = State()
    waiting_for_promo_code = State()
    waiting_for_export_path = State()

@router.message(Command("promo_stats"))
async def cmd_promo_stats(message: Message):
    """Статистика промокодов"""
    try:
        if not await is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав администратора")
            return
        
        report = promo_manager.get_promo_codes_report()
        await message.answer(report, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Ошибка команды promo_stats: {e}")
        await message.answer("❌ Ошибка получения статистики")

@router.message(Command("promo_list"))
async def cmd_promo_list(message: Message):
    """Список промокодов"""
    try:
        if not await is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав администратора")
            return
        
        # Получаем статус из аргументов команды
        args = message.text.split()
        status = None
        if len(args) > 1:
            status = args[1].lower()
            if status not in ['active', 'used', 'expired']:
                await message.answer("❌ Неверный статус. Используйте: active, used, expired")
                return
        
        promo_list = promo_manager.get_all_promo_codes_formatted(status)
        
        # Разбиваем длинное сообщение на части если нужно
        if len(promo_list) > 4000:
            parts = [promo_list[i:i+4000] for i in range(0, len(promo_list), 4000)]
            for part in parts:
                await message.answer(part, parse_mode="Markdown")
        else:
            await message.answer(promo_list, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Ошибка команды promo_list: {e}")
        await message.answer("❌ Ошибка получения списка промокодов")

@router.message(Command("load_promo_excel"))
async def cmd_load_promo_excel(message: Message, state: FSMContext):
    """Загрузка промокодов из Excel"""
    try:
        if not await is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав администратора")
            return
        
        await message.answer(
            "📥 *Загрузка промокодов из Excel*\n\n"
            "Отправьте Excel файл (.xlsx) с промокодами.\n"
            "Промокоды должны быть в первом столбце.",
            parse_mode="Markdown"
        )
        await state.set_state(PromoCodeStates.waiting_for_excel_file)
        
    except Exception as e:
        logging.error(f"Ошибка команды load_promo_excel: {e}")
        await message.answer("❌ Ошибка загрузки промокодов")

@router.message(PromoCodeStates.waiting_for_excel_file, F.document)
async def handle_excel_file(message: Message, state: FSMContext):
    """Обработка Excel файла с промокодами"""
    try:
        if not message.document:
            await message.answer("❌ Пожалуйста, отправьте Excel файл")
            return
        
        if not message.document.file_name.endswith(('.xlsx', '.xls')):
            await message.answer("❌ Файл должен быть в формате Excel (.xlsx или .xls)")
            return
        
        # Скачиваем файл
        file_id = message.document.file_id
        file = await message.bot.get_file(file_id)
        file_path = file.file_path
        
        # Создаем папку для временных файлов
        temp_dir = "temp_promo_files"
        os.makedirs(temp_dir, exist_ok=True)
        
        local_path = os.path.join(temp_dir, message.document.file_name)
        await message.bot.download_file(file_path, local_path)
        
        # Загружаем промокоды
        added, skipped = promo_manager.load_promo_codes_from_excel(local_path)
        
        # Удаляем временный файл
        os.remove(local_path)
        
        await message.answer(
            f"✅ *Промокоды загружены из Excel*\n\n"
            f"📥 Добавлено: {added}\n"
            f"📭 Пропущено (дубликаты): {skipped}",
            parse_mode="Markdown"
        )
        
        await state.clear()
        
    except Exception as e:
        logging.error(f"Ошибка обработки Excel файла: {e}")
        await message.answer(f"❌ Ошибка обработки файла: {e}")
        await state.clear()

@router.message(Command("load_promo_csv"))
async def cmd_load_promo_csv(message: Message, state: FSMContext):
    """Загрузка промокодов из CSV"""
    try:
        if not await is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав администратора")
            return
        
        await message.answer(
            "📥 *Загрузка промокодов из CSV*\n\n"
            "Отправьте CSV файл с промокодами.\n"
            "Промокоды должны быть в первом столбце.",
            parse_mode="Markdown"
        )
        await state.set_state(PromoCodeStates.waiting_for_csv_file)
        
    except Exception as e:
        logging.error(f"Ошибка команды load_promo_csv: {e}")
        await message.answer("❌ Ошибка загрузки промокодов")

@router.message(PromoCodeStates.waiting_for_csv_file, F.document)
async def handle_csv_file(message: Message, state: FSMContext):
    """Обработка CSV файла с промокодами"""
    try:
        if not message.document:
            await message.answer("❌ Пожалуйста, отправьте CSV файл")
            return
        
        if not message.document.file_name.endswith('.csv'):
            await message.answer("❌ Файл должен быть в формате CSV (.csv)")
            return
        
        # Скачиваем файл
        file_id = message.document.file_id
        file = await message.bot.get_file(file_id)
        file_path = file.file_path
        
        # Создаем папку для временных файлов
        temp_dir = "temp_promo_files"
        os.makedirs(temp_dir, exist_ok=True)
        
        local_path = os.path.join(temp_dir, message.document.file_name)
        await message.bot.download_file(file_path, local_path)
        
        # Загружаем промокоды
        added, skipped = promo_manager.load_promo_codes_from_csv(local_path)
        
        # Удаляем временный файл
        os.remove(local_path)
        
        await message.answer(
            f"✅ *Промокоды загружены из CSV*\n\n"
            f"📥 Добавлено: {added}\n"
            f"📭 Пропущено (дубликаты): {skipped}",
            parse_mode="Markdown"
        )
        
        await state.clear()
        
    except Exception as e:
        logging.error(f"Ошибка обработки CSV файла: {e}")
        await message.answer(f"❌ Ошибка обработки файла: {e}")
        await state.clear()

@router.message(Command("load_promo_txt"))
async def cmd_load_promo_txt(message: Message, state: FSMContext):
    """Загрузка промокодов из текстового файла"""
    try:
        if not await is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав администратора")
            return
        
        await message.answer(
            "📥 *Загрузка промокодов из текстового файла*\n\n"
            "Отправьте текстовый файл (.txt) с промокодами.\n"
            "Каждый промокод должен быть на новой строке.",
            parse_mode="Markdown"
        )
        await state.set_state(PromoCodeStates.waiting_for_txt_file)
        
    except Exception as e:
        logging.error(f"Ошибка команды load_promo_txt: {e}")
        await message.answer("❌ Ошибка загрузки промокодов")

@router.message(PromoCodeStates.waiting_for_txt_file, F.document)
async def handle_txt_file(message: Message, state: FSMContext):
    """Обработка текстового файла с промокодами"""
    try:
        if not message.document:
            await message.answer("❌ Пожалуйста, отправьте текстовый файл")
            return
        
        if not message.document.file_name.endswith('.txt'):
            await message.answer("❌ Файл должен быть в формате TXT (.txt)")
            return
        
        # Скачиваем файл
        file_id = message.document.file_id
        file = await message.bot.get_file(file_id)
        file_path = file.file_path
        
        # Создаем папку для временных файлов
        temp_dir = "temp_promo_files"
        os.makedirs(temp_dir, exist_ok=True)
        
        local_path = os.path.join(temp_dir, message.document.file_name)
        await message.bot.download_file(file_path, local_path)
        
        # Загружаем промокоды
        added, skipped = promo_manager.load_promo_codes_from_txt(local_path)
        
        # Удаляем временный файл
        os.remove(local_path)
        
        await message.answer(
            f"✅ *Промокоды загружены из TXT*\n\n"
            f"📥 Добавлено: {added}\n"
            f"📭 Пропущено (дубликаты): {skipped}",
            parse_mode="Markdown"
        )
        
        await state.clear()
        
    except Exception as e:
        logging.error(f"Ошибка обработки TXT файла: {e}")
        await message.answer(f"❌ Ошибка обработки файла: {e}")
        await state.clear()

@router.message(Command("check_promo"))
async def cmd_check_promo(message: Message, state: FSMContext):
    """Проверка промокода"""
    try:
        if not await is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав администратора")
            return
        
        await message.answer(
            "🔍 *Проверка промокода*\n\n"
            "Введите промокод для проверки:",
            parse_mode="Markdown"
        )
        await state.set_state(PromoCodeStates.waiting_for_promo_code)
        
    except Exception as e:
        logging.error(f"Ошибка команды check_promo: {e}")
        await message.answer("❌ Ошибка проверки промокода")

@router.message(PromoCodeStates.waiting_for_promo_code, F.text)
async def handle_promo_check(message: Message, state: FSMContext):
    """Обработка проверки промокода"""
    try:
        promo_code = message.text.strip()
        
        if not promo_code:
            await message.answer("❌ Пожалуйста, введите промокод")
            return
        
        result = promo_manager.validate_promo_code(promo_code)
        await message.answer(result['message'], parse_mode="Markdown")
        
        await state.clear()
        
    except Exception as e:
        logging.error(f"Ошибка проверки промокода: {e}")
        await message.answer(f"❌ Ошибка проверки: {e}")
        await state.clear()

@router.message(Command("export_promo"))
async def cmd_export_promo(message: Message, state: FSMContext):
    """Экспорт промокодов"""
    try:
        if not await is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав администратора")
            return
        
        await message.answer(
            "📤 *Экспорт промокодов*\n\n"
            "Введите путь для сохранения файла (например: promo_export.csv):",
            parse_mode="Markdown"
        )
        await state.set_state(PromoCodeStates.waiting_for_export_path)
        
    except Exception as e:
        logging.error(f"Ошибка команды export_promo: {e}")
        await message.answer("❌ Ошибка экспорта промокодов")

@router.message(PromoCodeStates.waiting_for_export_path, F.text)
async def handle_export_path(message: Message, state: FSMContext):
    """Обработка пути для экспорта"""
    try:
        export_path = message.text.strip()
        
        if not export_path:
            await message.answer("❌ Пожалуйста, введите путь для сохранения")
            return
        
        # Получаем статус из аргументов команды
        args = message.text.split()
        status = None
        if len(args) > 1:
            status = args[1].lower()
            if status not in ['active', 'used', 'expired']:
                await message.answer("❌ Неверный статус. Используйте: active, used, expired")
                return
        
        success = promo_manager.export_promo_codes_to_file(export_path, status)
        
        if success:
            await message.answer(
                f"✅ *Промокоды экспортированы*\n\n"
                f"📁 Файл: {export_path}",
                parse_mode="Markdown"
            )
            
            # Отправляем файл если он небольшой
            try:
                if os.path.exists(export_path) and os.path.getsize(export_path) < 50 * 1024 * 1024:  # 50MB
                    from aiogram.types import FSInputFile
                    file = FSInputFile(export_path)
                    await message.answer_document(file)
            except Exception as file_error:
                logging.warning(f"Не удалось отправить файл: {file_error}")
        else:
            await message.answer("❌ Ошибка экспорта промокодов")
        
        await state.clear()
        
    except Exception as e:
        logging.error(f"Ошибка экспорта промокодов: {e}")
        await message.answer(f"❌ Ошибка экспорта: {e}")
        await state.clear()

@router.message(Command("send_promo"))
async def cmd_send_promo(message: Message):
    """Отправка промокода пользователю (админ)"""
    try:
        if not await is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав администратора")
            return
        
        # Парсим команду: /send_promo <telegram_id> [username]
        args = message.text.split()
        if len(args) < 2:
            await message.answer("❌ Использование: /send_promo <telegram_id> [username]")
            return
        
        telegram_id = int(args[1])
        username = args[2] if len(args) > 2 else None
        
        result = promo_manager.send_promo_code_to_user(telegram_id, username)
        
        if result['success']:
            await message.answer(
                f"✅ *Промокод отправлен*\n\n"
                f"👤 Пользователь: {telegram_id}\n"
                f"🎫 Промокод: {result.get('promo_code')}",
                parse_mode="Markdown"
            )
            
            # Отправляем промокод пользователю
            try:
                await message.bot.send_message(
                    chat_id=telegram_id,
                    text=result['message'],
                    parse_mode="Markdown"
                )
            except Exception as send_error:
                await message.answer(f"⚠️ Промокод сохранен, но не отправлен пользователю: {send_error}")
        else:
            await message.answer(f"❌ {result['message']}")
        
    except Exception as e:
        logging.error(f"Ошибка команды send_promo: {e}")
        await message.answer(f"❌ Ошибка отправки промокода: {e}")

@router.message(Command("my_promo"))
async def cmd_my_promo(message: Message):
    """Проверка промокодов пользователя"""
    try:
        telegram_id = message.from_user.id
        
        from .promo_utils import get_user_promocodes, format_user_promocodes
        user_promos = get_user_promocodes(telegram_id)
        
        response = format_user_promocodes(user_promos)
        await message.answer(response, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Ошибка команды my_promo: {e}")
        await message.answer("❌ Ошибка получения ваших промокодов")

async def is_admin(telegram_id: int) -> bool:
    """Проверка прав администратора"""
    try:
        from database import db
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role FROM main WHERE telegram_id = ?",
                (telegram_id,)
            )
            result = cursor.fetchone()
            return result and result[0] in ['admin', 'moderator']
    except Exception as e:
        logging.error(f"Ошибка проверки прав администратора: {e}")
        return False
