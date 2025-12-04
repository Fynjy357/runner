#!/usr/bin/env python3
"""
Менеджер промокодов - основной класс для работы с промокодами
"""

import pandas as pd
import logging
import os
from typing import Optional, Tuple, Dict, List

# Импортируем db из корня проекта
try:
    from database import db
    print("✅ Импорт database.db успешен")
except ImportError as e:
    print(f"❌ Ошибка импорта database.db: {e}")
    # Альтернативный импорт
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from database import db
        print("✅ Импорт database.db через sys.path успешен")
    except ImportError:
        print("❌ Не удалось импортировать database.db")
        raise

class PromoCodeManager:
    """Класс для управления промокодами"""
    
    def __init__(self, db_instance=None):
        """Инициализация менеджера промокодов"""
        self.db = db_instance or db
        logging.info("PromoCodeManager инициализирован")
    
    def load_promo_codes_from_excel(self, excel_file_path: str) -> Tuple[int, int]:
        """Загрузка промокодов из Excel файла"""
        try:
            if not os.path.exists(excel_file_path):
                logging.error(f"Файл не найден: {excel_file_path}")
                return 0, 0
            
            # Читаем Excel файл
            df = pd.read_excel(excel_file_path)
            
            # Предполагаем, что промокоды в первом столбце
            promo_codes = df.iloc[:, 0].dropna().astype(str).tolist()
            
            if not promo_codes:
                logging.warning("В файле нет промокодов")
                return 0, 0
            
            # Добавляем промокоды в базу
            added, skipped = self.db.add_promo_codes_batch(promo_codes)
            
            logging.info(f"Загружено из Excel: {added} добавлено, {skipped} пропущено")
            return added, skipped
            
        except Exception as e:
            logging.error(f"Ошибка загрузки из Excel: {e}")
            return 0, 0
    
    def load_promo_codes_from_csv(self, csv_file_path: str) -> Tuple[int, int]:
        """Загрузка промокодов из CSV файла"""
        try:
            if not os.path.exists(csv_file_path):
                logging.error(f"Файл не найден: {csv_file_path}")
                return 0, 0
            
            # Читаем CSV файл
            df = pd.read_csv(csv_file_path)
            
            # Предполагаем, что промокоды в первом столбце
            promo_codes = df.iloc[:, 0].dropna().astype(str).tolist()
            
            if not promo_codes:
                logging.warning("В файле нет промокодов")
                return 0, 0
            
            # Добавляем промокоды в базу
            added, skipped = self.db.add_promo_codes_batch(promo_codes)
            
            logging.info(f"Загружено из CSV: {added} добавлено, {skipped} пропущено")
            return added, skipped
            
        except Exception as e:
            logging.error(f"Ошибка загрузки из CSV: {e}")
            return 0, 0
    
    def load_promo_codes_from_txt(self, txt_file_path: str) -> Tuple[int, int]:
        """Загрузка промокодов из текстового файла"""
        try:
            if not os.path.exists(txt_file_path):
                logging.error(f"Файл не найден: {txt_file_path}")
                return 0, 0
            
            # Читаем текстовый файл
            with open(txt_file_path, 'r', encoding='utf-8') as f:
                promo_codes = [line.strip() for line in f if line.strip()]
            
            if not promo_codes:
                logging.warning("В файле нет промокодов")
                return 0, 0
            
            # Добавляем промокоды в базу
            added, skipped = self.db.add_promo_codes_batch(promo_codes)
            
            logging.info(f"Загружено из TXT: {added} добавлено, {skipped} пропущено")
            return added, skipped
            
        except Exception as e:
            logging.error(f"Ошибка загрузки из TXT: {e}")
            return 0, 0
    
    def get_and_assign_promo_code(self, telegram_id: int, username: str = None) -> Optional[str]:
        """Получение и назначение промокода пользователю"""
        try:
            logging.info(f"🔍 Поиск промокода для пользователя {telegram_id} (@{username})")
            
            # Получаем доступный промокод
            promo_code = self.db.get_available_promo_code()
            
            logging.info(f"📊 Результат get_available_promo_code(): {promo_code}")
            
            if not promo_code:
                logging.warning("❌ Нет доступных промокодов")
                return None
            
            # Отмечаем промокод как использованный
            success = self.db.mark_promo_code_as_used(promo_code, telegram_id, username)
            
            logging.info(f"📊 Результат mark_promo_code_as_used(): {success}")
            
            if success:
                logging.info(f"✅ Промокод {promo_code} назначен пользователю {telegram_id}")
                return promo_code
            else:
                logging.error(f"❌ Не удалось назначить промокод {promo_code}")
                return None
                
        except Exception as e:
            logging.error(f"❌ Ошибка назначения промокода: {e}", exc_info=True)
            return None

    
    def send_promo_code_to_user(self, telegram_id: int, username: str = None) -> Dict:
        """Отправка промокода пользователю"""
        try:
            # Получаем доступный промокод
            promo_code = self.get_and_assign_promo_code(telegram_id, username)
            
            if not promo_code:
                return {
                    'success': False,
                    'message': "❌ Извините, в данный момент нет доступных промокодов. Попробуйте позже."
                }
            
            # ✅ ИСПРАВЛЕНИЕ: Возвращаем только промокод, текст формируется в promo_utils
            return {
                'success': True,
                'message': "",  # Пустое сообщение, текст формируется отдельно
                'promo_code': promo_code
            }
            
        except Exception as e:
            logging.error(f"Ошибка отправки промокода пользователю {telegram_id}: {e}")
            return {
                'success': False,
                'message': "❌ Произошла ошибка при выдаче промокода. Попробуйте позже."
            }

    
    def validate_promo_code(self, promo_code: str) -> Dict:
        """Проверка промокода"""
        try:
            info = self.db.get_promo_code_info(promo_code)
            
            if not info:
                return {
                    'valid': False,
                    'message': f"❌ Промокод `{promo_code}` не найден"
                }
            
            if info['status'] == 'used':
                return {
                    'valid': False,
                    'message': f"❌ Промокод `{promo_code}` уже использован"
                }
            
            if info['status'] == 'expired':
                return {
                    'valid': False,
                    'message': f"❌ Промокод `{promo_code}` просрочен"
                }
            
            return {
                'valid': True,
                'message': f"✅ Промокод `{promo_code}` активен\n📅 Создан: {info['created_at']}",
                'info': info
            }
            
        except Exception as e:
            logging.error(f"Ошибка проверки промокода: {e}")
            return {
                'valid': False,
                'message': f"❌ Ошибка проверки промокода: {e}"
            }
    
    def get_promo_codes_report(self) -> str:
        """Получение отчета по промокодам"""
        try:
            stats = self.db.get_promo_codes_stats()
            
            report = "📊 *Отчет по промокодам*\n\n"
            report += f"📋 Всего промокодов: {stats['total']}\n"
            report += f"✅ Активных: {stats['active']}\n"
            report += f"🔄 Использованных: {stats['used']}\n"
            report += f"❌ Просроченных: {stats['expired']}\n"
            
            if stats['total'] > 0:
                usage_percentage = (stats['used'] / stats['total']) * 100
                report += f"\n📈 Использовано: {usage_percentage:.1f}%\n"
            
            return report
            
        except Exception as e:
            logging.error(f"Ошибка получения отчета: {e}")
            return "❌ Ошибка получения отчета"
    
    def get_all_promo_codes_formatted(self, status: str = None) -> str:
        """Получение форматированного списка промокодов"""
        try:
            promo_codes = self.db.get_all_promo_codes(status)
            
            if not promo_codes:
                return "📭 Нет промокодов"
            
            formatted = f"📋 *Список промокодов* ({len(promo_codes)})\n\n"
            
            for i, promo in enumerate(promo_codes, 1):
                status_emoji = {
                    'active': '✅',
                    'used': '🔄',
                    'expired': '❌'
                }.get(promo['status'], '❓')
                
                formatted += f"{i}. {status_emoji} `{promo['promo_code']}` - {promo['status']}\n"
                
                if promo['sent_at']:
                    formatted += f"   📅 Отправлен: {promo['sent_at']}\n"
                    if promo['sent_to_username']:
                        formatted += f"   👤 Пользователь: {promo['sent_to_username']}\n"
                    elif promo['sent_to_telegram_id']:
                        formatted += f"   👤 ID: {promo['sent_to_telegram_id']}\n"
                
                if i % 10 == 0 and i < len(promo_codes):
                    formatted += f"\n... и еще {len(promo_codes) - i} промокодов\n"
                    break
            
            return formatted
            
        except Exception as e:
            logging.error(f"Ошибка получения списка промокодов: {e}")
            return "❌ Ошибка получения списка"
    
    def export_promo_codes_to_file(self, output_path: str, status: str = None) -> bool:
        """Экспорт промокодов в файл"""
        try:
            csv_data = self.db.export_promo_codes_to_csv(status)
            
            if csv_data.startswith("Ошибка"):
                logging.error(f"Ошибка экспорта: {csv_data}")
                return False
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(csv_data)
            
            logging.info(f"Промокоды экспортированы в {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка экспорта в файл: {e}")
            return False

# Создаем глобальный экземпляр
promo_manager = PromoCodeManager()
