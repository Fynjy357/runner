#!/src/handlers/mail_management.py
"""
Обработчики для управления рассылкой
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

# Исправляем импорт - из корня src
from mail_integration import mail_integration

router = Router()

@router.message(Command("mail_status"))
async def cmd_mail_status(message: Message):
    """Показать статус системы рассылки"""
    if not mail_integration.is_mail_service_available():
        await message.answer(
            "❌ <b>Система рассылки недоступна</b>\n\n"
            "Возможные причины:\n"
            "• SMTP настройки не настроены\n"
            "• Ошибка подключения к SMTP серверу\n"
            "• Модуль рассылки не установлен",
            parse_mode="HTML"
        )
        return
    
    status_text = "📧 <b>Статус системы рассылки</b>\n\n"
    
    if mail_integration.is_running:
        status_text += "✅ <b>Планировщик: АКТИВЕН</b>\n"
        status_text += "⏰ Интервал: каждые 5 минут\n"
        status_text += "📧 Шаблон: Universal Link\n\n"
        status_text += "🔍 <b>Логика работы:</b>\n"
        status_text += "• Отправка получателям со status=1\n"
        status_text += "• Если прошло >20 часов с mailing_date\n"
        status_text += "• Автоматическая переотправка\n"
    else:
        status_text += "❌ <b>Планировщик: НЕАКТИВЕН</b>\n"
    
    status_text += f"\n📊 Доступность: {'✅ ДОСТУПНА' if mail_integration.is_mail_service_available() else '❌ НЕДОСТУПНА'}"
    
    await message.answer(status_text, parse_mode="HTML")

@router.message(Command("send_mail"))
async def cmd_send_mail(message: Message):
    """Немедленная рассылка (только для админов)"""
    # TODO: Добавить проверку прав администратора
    
    if not mail_integration.is_mail_service_available():
        await message.answer("❌ Система рассылки недоступна")
        return
    
    await message.answer(
        "⚡ <b>Немедленная рассылка</b>\n\n"
        "Выберите шаблон для рассылки:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📱 Universal Link", 
                        callback_data="mail_immediate_universal_link"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🎉 Completion", 
                        callback_data="mail_immediate_completion"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Отмена", 
                        callback_data="mail_cancel"
                    )
                ]
            ]
        )
    )

@router.callback_query(F.data.startswith("mail_immediate_"))
async def process_mail_template(callback: CallbackQuery):
    """Обработка выбора шаблона для рассылки"""
    template_name = callback.data.replace("mail_immediate_", "")
    
    # Сразу отвечаем, чтобы избежать таймаута Telegram
    await callback.answer("⏳ Запускаем рассылку...")
    
    # Отправляем сообщение о начале рассылки
    processing_msg = await callback.message.edit_text(
        f"🚀 <b>Запускаем рассылку:</b> {template_name}\n\n"
        "⏳ Пожалуйста, подождите, это может занять несколько минут...",
        parse_mode="HTML"
    )
    
    try:
        # Запускаем рассылку
        result = await mail_integration.send_immediate_campaign(template_name)
        
        if 'error' in result:
            await processing_msg.edit_text(
                f"❌ <b>Ошибка рассылки:</b>\n<code>{result['error']}</code>",
                parse_mode="HTML"
            )
        else:
            if 'info' in result and result['info'] == 'No recipients found':
                await processing_msg.edit_text(
                    "ℹ️ <b>Нет получателей для рассылки</b>\n\n"
                    "Получатели должны иметь:\n"
                    "• status = 1\n" 
                    "• mailing_date отсутствует ИЛИ прошло >20 часов",
                    parse_mode="HTML"
                )
            else:
                # Форматируем результат
                total = result.get('total', 0)
                sent = result.get('sent', 0)
                failed = result.get('failed', 0)
                failed_emails = result.get('failed_emails', [])
                
                result_text = (
                    f"✅ <b>Рассылка завершена!</b>\n\n"
                    f"📊 <b>Результаты:</b>\n"
                    f"• Всего получателей: {total}\n"
                    f"• Успешно отправлено: {sent}\n"
                    f"• Ошибок: {failed}\n"
                    f"• Шаблон: {result.get('template', template_name)}"
                )
                
                # Добавляем информацию об ошибках, если есть
                if failed_emails:
                    failed_list = "\n".join([f"• {email}" for email in failed_emails[:3]])  # Показываем первые 3
                    if len(failed_emails) > 3:
                        failed_list += f"\n• ... и еще {len(failed_emails) - 3}"
                    result_text += f"\n\n❌ <b>Ошибки отправки:</b>\n{failed_list}"
                
                await processing_msg.edit_text(result_text, parse_mode="HTML")
                
    except Exception as e:
        await processing_msg.edit_text(
            f"❌ <b>Неожиданная ошибка:</b>\n<code>{str(e)}</code>",
            parse_mode="HTML"
        )

@router.callback_query(F.data == "mail_cancel")
async def process_mail_cancel(callback: CallbackQuery):
    """Отмена рассылки"""
    await callback.answer("❌ Рассылка отменена")
    await callback.message.edit_text("❌ Рассылка отменена")

def setup_mail_handlers(dp):
    """Настройка обработчиков управления рассылкой"""
    dp.include_router(router)
