#!/usr/bin/env python3
# src/promo/promo_utils.py
"""
Утилиты для работы с промокодами
"""

import logging
import sys
import os
from typing import List, Dict, Optional
# Добавляем родительскую директорию в путь Python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .promo_manager import promo_manager

async def send_promo_code_to_user_async(telegram_id: int, username: str, bot, chat_id: int):
    """Асинхронная отправка промокода пользователю"""
    logger = logging.getLogger('bot')
    
    try:
        logger.info(f"🔍 Отправка промокода пользователю {telegram_id} (@{username})")
        
        from .promo_manager import promo_manager
        
        result = promo_manager.send_promo_code_to_user(telegram_id, username)
        
        logger.info(f"📊 Результат получения промокода: {result}")
        
        if result.get('success'):
            promo_code = result.get('promo_code', '')
            
            logger.info(f"✅ Промокод для пользователя {telegram_id}: {promo_code}")
            
            # ✅ ИСПРАВЛЕНИЕ: Убираем дублирование, используем только сообщение из менеджера
            message_text = (
                "🎉 *Поздравляем! Вы отгадали загадку!*\n"
                "И получаете первый трофей:\n\n"
                f"🎁 *Промокод:* `{promo_code}`\n"
                "Скидка 20% на следующий этап!"
            )
            
            await bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode="Markdown"
            )
            
            logger.info(f"✅ Промокод отправлен пользователю {telegram_id}")
            return True
        else:
            error_message = result.get('message', 'Не удалось получить промокод')
            logger.warning(f"⚠️ Не удалось получить промокод для пользователя {telegram_id}: {error_message}")
            
            await bot.send_message(
                chat_id=chat_id,
                text=f"🎁 *Бонус:* {error_message}",
                parse_mode="Markdown"
            )
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка отправки промокода пользователю {telegram_id}: {e}", exc_info=True)
        return False


def get_promo_stats_formatted() -> str:
    """Получение форматированной статистики промокодов"""
    try:
        from database import db
        stats = db.get_promo_codes_stats()
        
        report = "📊 *Статистика промокодов*\n\n"
        report += f"📋 Всего промокодов: {stats['total']}\n"
        report += f"✅ Доступных: {stats['active']}\n"
        report += f"🎁 Выданных: {stats['used']}\n"
        
        if stats['total'] > 0:
            usage_percentage = (stats['used'] / stats['total']) * 100
            report += f"📈 Использовано: {usage_percentage:.1f}%\n"
        
        return report
        
    except Exception as e:
        logging.error(f"Ошибка получения статистики промокодов: {e}")
        return "❌ Ошибка получения статистики"

def get_user_promocodes(telegram_id: int) -> List[Dict]:
    """Получение промокодов пользователя"""
    try:
        from database import db
        all_promos = db.get_all_promo_codes('used')
        user_promos = []
        
        for promo in all_promos:
            if promo['sent_to_telegram_id'] == telegram_id:
                user_promos.append(promo)
        
        return user_promos
        
    except Exception as e:
        logging.error(f"Ошибка получения промокодов пользователя {telegram_id}: {e}")
        return []

def format_user_promocodes(promos: List[Dict]) -> str:
    """Форматирование промокодов пользователя для отображения"""
    if not promos:
        return "📭 *У вас пока нет промокодов*\n\n💡 Промокоды выдаются при успешном прохождении этапов квеста."
    
    response = "🎫 *Ваши промокоды:*\n\n"
    
    for i, promo in enumerate(promos, 1):
        response += f"{i}. `{promo['promo_code']}`\n"
        response += f"   📅 Выдан: {promo['sent_at']}\n"
        if promo['status'] == 'used':
            response += f"   ✅ Использован\n"
        else:
            response += f"   ⏳ Ожидает использования\n"
        response += "\n"
    
    return response
