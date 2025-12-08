# # src/handlers/link_generation.py
# from aiogram.filters import Command
# from aiogram.types import Message
# import logging
# import secrets
# import string
# import asyncio
# from typing import Optional
# from datetime import datetime
# from database import db

# def generate_unique_link(length=16):
#     """Генерация уникальной ссылки"""
#     alphabet = string.ascii_letters + string.digits
#     return ''.join(secrets.choice(alphabet) for _ in range(length))

# class LinkGenerationScheduler:
#     """Планировщик для автоматической генерации ссылок"""
    
#     def __init__(self, logger: logging.Logger):
#         self.logger = logger
#         self._task: Optional[asyncio.Task] = None
#         self._stop_event = asyncio.Event()
    
#     async def start_scheduler(self, interval_minutes: int = 5):
#         """Запуск планировщика генерации ссылок"""
#         try:
#             self.logger.info(f"⏰ Планировщик генерации ссылок запущен. Проверка каждые {interval_minutes} минут")
            
#             while not self._stop_event.is_set():
#                 self.logger.info("🔄 Проверяем новых пользователей для генерации ссылок...")
                
#                 try:
#                     # Запускаем автоматическую генерацию ссылок
#                     result = await self.generate_links_automatically()
                    
#                     if result['generated'] > 0:
#                         self.logger.info(f"✅ Автоматически создано {result['generated']} новых ссылок")
#                     else:
#                         self.logger.info("ℹ️ Нет новых пользователей для генерации ссылок")
                    
#                 except Exception as e:
#                     self.logger.error(f"❌ Ошибка при автоматической генерации ссылок: {e}")
                
#                 # Ждем указанное количество минут
#                 self.logger.info(f"⏳ Следующая проверка через {interval_minutes} минут...")
#                 try:
#                     await asyncio.wait_for(
#                         self._stop_event.wait(), 
#                         timeout=interval_minutes * 60
#                     )
#                 except asyncio.TimeoutError:
#                     continue
#                 except asyncio.CancelledError:
#                     self.logger.info("Планировщик генерации ссылок остановлен")
#                     break
        
#         except Exception as e:
#             self.logger.error(f"❌ Ошибка в планировщике генерации ссылок: {e}")
    
#     async def generate_links_automatically(self):
#         """Автоматическая генерация ссылок для новых пользователей"""
#         try:
#             with db.get_connection() as conn:
#                 cursor = conn.cursor()
                
#                 # Получаем всех пользователей из manual_upload без ссылок
#                 cursor.execute('''
#                     SELECT mu.participant_id, mu.last_name, mu.first_name 
#                     FROM manual_upload mu
#                     LEFT JOIN link_generation lg ON mu.participant_id = lg.participant_id
#                     WHERE lg.participant_id IS NULL
#                 ''')
                
#                 users_without_links = cursor.fetchall()
                
#                 if not users_without_links:
#                     return {'generated': 0, 'total': 0}
                
#                 generated_count = 0
                
#                 for participant_id, last_name, first_name in users_without_links:
#                     # Создаем новую ссылку
#                     new_link = generate_unique_link()
#                     cursor.execute('''
#                         INSERT INTO link_generation (participant_id, universal_link, status, mailing_date)
#                         VALUES (?, ?, 1, NULL)
#                     ''', (participant_id, new_link))
#                     generated_count += 1
                    
#                     self.logger.info(f"🤖 Автоматически создана ссылка для participant_id {participant_id}: {last_name} {first_name}")
                
#                 conn.commit()
                
#                 return {
#                     'generated': generated_count,
#                     'total': len(users_without_links),
#                     'timestamp': datetime.now().isoformat()
#                 }
                
#         except Exception as e:
#             self.logger.error(f"❌ Ошибка при автоматической генерации ссылок: {e}")
#             return {'generated': 0, 'total': 0, 'error': str(e)}
    
#     def stop_scheduler(self):
#         """Остановка планировщика"""
#         self._stop_event.set()
#         if self._task and not self._task.done():
#             self._task.cancel()
#         self.logger.info("🛑 Планировщик генерации ссылок остановлен")
    
#     def is_running(self) -> bool:
#         """Проверка, работает ли планировщик"""
#         return self._task is not None and not self._task.done()

# # Глобальный экземпляр планировщика
# link_scheduler = None

# def get_link_scheduler(logger: logging.Logger) -> LinkGenerationScheduler:
#     """Получение экземпляра планировщика"""
#     global link_scheduler
#     if link_scheduler is None:
#         link_scheduler = LinkGenerationScheduler(logger)
#     return link_scheduler

# async def start_link_generation_scheduler(logger: logging.Logger, interval_minutes: int = 5) -> bool:
#     """Запуск планировщика генерации ссылок"""
#     try:
#         scheduler = get_link_scheduler(logger)
        
#         if scheduler.is_running():
#             logger.warning("⚠️ Планировщик генерации ссылок уже запущен")
#             return True
        
#         # Запускаем планировщик в фоне
#         scheduler._task = asyncio.create_task(
#             scheduler.start_scheduler(interval_minutes)
#         )
        
#         logger.info(f"✅ Планировщик генерации ссылок запущен (интервал: {interval_minutes} минут)")
#         return True
        
#     except Exception as e:
#         logger.error(f"❌ Ошибка при запуске планировщика генерации ссылок: {e}")
#         return False

# async def stop_link_generation_scheduler() -> bool:
#     """Остановка планировщика генерации ссылок"""
#     global link_scheduler
    
#     try:
#         if link_scheduler:
#             link_scheduler.stop_scheduler()
#             return True
#         return False
        
#     except Exception as e:
#         if link_scheduler and link_scheduler.logger:
#             link_scheduler.logger.error(f"❌ Ошибка при остановке планировщика генерации ссылок: {e}")
#         return False

# def is_link_scheduler_running() -> bool:
#     """Проверка, работает ли планировщик"""
#     global link_scheduler
#     return link_scheduler is not None and link_scheduler.is_running()

# async def get_link_scheduler_status() -> dict:
#     """Получение статуса планировщика"""
#     try:
#         with db.get_connection() as conn:
#             cursor = conn.cursor()
            
#             cursor.execute('''
#                 SELECT 
#                     COUNT(*) as total_users,
#                     SUM(CASE WHEN lg.participant_id IS NOT NULL THEN 1 ELSE 0 END) as users_with_links,
#                     SUM(CASE WHEN lg.participant_id IS NULL THEN 1 ELSE 0 END) as users_without_links
#                 FROM manual_upload mu
#                 LEFT JOIN link_generation lg ON mu.participant_id = lg.participant_id
#             ''')
            
#             stats = cursor.fetchone()
#             total_users, users_with_links, users_without_links = stats
            
#             return {
#                 'scheduler_running': is_link_scheduler_running(),
#                 'total_users': total_users,
#                 'users_with_links': users_with_links,
#                 'users_without_links': users_without_links,
#                 'timestamp': datetime.now().isoformat()
#             }
            
#     except Exception as e:
#         return {
#             'scheduler_running': is_link_scheduler_running(),
#             'error': str(e),
#             'timestamp': datetime.now().isoformat()
#         }

# def setup_link_generation_handler(dp, logger: logging.Logger, bot_username: str):
#     """Настройка обработчика команды генерации ссылок для всех пользователей"""
    
#     # Инициализируем планировщик
#     get_link_scheduler(logger)
    
#     @dp.message(Command("generate_all_links"))
#     async def generate_all_links_command(message: Message):
#         """Генерация ссылок только для пользователей без ссылок из manual_upload"""
#         try:
#             with db.get_connection() as conn:
#                 cursor = conn.cursor()
                
#                 # Получаем всех пользователей из manual_upload
#                 cursor.execute('''
#                     SELECT participant_id, last_name, first_name 
#                     FROM manual_upload
#                 ''')
                
#                 users = cursor.fetchall()
                
#                 if not users:
#                     await message.answer("❌ В таблице manual_upload нет пользователей")
#                     return
                
#                 generated_count = 0
#                 skipped_count = 0
                
#                 for participant_id, last_name, first_name in users:
#                     # Проверяем, есть ли уже ссылка для этого пользователя
#                     cursor.execute('''
#                         SELECT universal_link FROM link_generation 
#                         WHERE participant_id = ?
#                     ''', (participant_id,))
                    
#                     existing_link = cursor.fetchone()
                    
#                     if existing_link:
#                         # Если ссылка уже существует - пропускаем, НЕ обновляем
#                         skipped_count += 1
#                         logger.info(f"Пропущен participant_id {participant_id}: ссылка уже существует")
#                     else:
#                         # Создаем новую ссылку только если её нет
#                         new_link = generate_unique_link()
#                         # Устанавливаем mailing_date = NULL, чтобы рассылка могла сразу отправить письмо
#                         cursor.execute('''
#                             INSERT INTO link_generation (participant_id, universal_link, status, mailing_date)
#                             VALUES (?, ?, 1, NULL)
#                         ''', (participant_id, new_link))
#                         generated_count += 1
#                         logger.info(f"Создана ссылка для participant_id {participant_id}: {last_name} {first_name} (mailing_date = NULL)")
                
#                 conn.commit()
                
#                 await message.answer(
#                     f"✅ Ссылки успешно сгенерированы!\n\n"
#                     f"👥 Всего пользователей: {len(users)}\n"
#                     f"🆕 Создано новых ссылок: {generated_count}\n"
#                     f"⏭️ Пропущено (уже есть ссылки): {skipped_count}\n\n"
#                     f"📧 <b>Новые пользователи готовы к рассылке!</b>\n"
#                     f"Используйте команду /get_links чтобы получить ссылки для отправки участникам.",
#                     parse_mode="HTML"
#                 )
                
#         except Exception as e:
#             logger.error(f"Ошибка при генерации ссылок: {e}", exc_info=True)
#             await message.answer("❌ Произошла ошибка при генерации ссылок")

#     @dp.message(Command("start_link_scheduler"))
#     async def start_link_scheduler_command(message: Message):
#         """Запуск автоматической генерации ссылок"""
#         try:
#             if is_link_scheduler_running():
#                 await message.answer("⚠️ Планировщик генерации ссылок уже запущен")
#                 return
            
#             # Запускаем планировщик
#             success = await start_link_generation_scheduler(logger, 5)
            
#             if success:
#                 await message.answer(
#                     "🤖 **Планировщик генерации ссылок запущен!**\n\n"
#                     "⏰ Проверка новых пользователей каждые 5 минут\n"
#                     "🔗 Автоматическое создание ссылок для новых участников\n"
#                     "📧 Готовые ссылки сразу попадают в очередь рассылки\n\n"
#                     "Для остановки используйте /stop_link_scheduler",
#                     parse_mode="Markdown"
#                 )
#                 logger.info("Пользователь запустил планировщик генерации ссылок")
#             else:
#                 await message.answer("❌ Не удалось запустить планировщик генерации ссылок")
            
#         except Exception as e:
#             logger.error(f"Ошибка при запуске планировщика ссылок: {e}")
#             await message.answer("❌ Ошибка при запуске планировщика")

#     @dp.message(Command("stop_link_scheduler"))
#     async def stop_link_scheduler_command(message: Message):
#         """Остановка автоматической генерации ссылок"""
#         try:
#             success = await stop_link_generation_scheduler()
            
#             if success:
#                 await message.answer("🛑 Планировщик генерации ссылок остановлен")
#                 logger.info("Пользователь остановил планировщик генерации ссылок")
#             else:
#                 await message.answer("ℹ️ Планировщик генерации ссылок не запущен")
                
#         except Exception as e:
#             logger.error(f"Ошибка при остановке планировщика ссылок: {e}")
#             await message.answer("❌ Ошибка при остановке планировщика")

#     @dp.message(Command("link_scheduler_status"))
#     async def link_scheduler_status_command(message: Message):
#         """Статус планировщика генерации ссылок"""
#         try:
#             status_data = await get_link_scheduler_status()
            
#             if status_data.get('error'):
#                 await message.answer("❌ Ошибка при получении статуса планировщика")
#                 return
            
#             if status_data['scheduler_running']:
#                 status = "🟢 **РАБОТАЕТ**"
#                 details = "Автоматически проверяет новых пользователей каждые 5 минут"
#             else:
#                 status = "🔴 **ОСТАНОВЛЕН**"
#                 details = "Используйте /start_link_scheduler для запуска"
            
#             status_message = (
#                 f"🤖 **Статус планировщика генерации ссылок**\n\n"
#                 f"{status}\n"
#                 f"{details}\n\n"
#                 f"📊 **Статистика:**\n"
#                 f"👥 Всего пользователей: {status_data['total_users']}\n"
#                 f"🔗 С ссылками: {status_data['users_with_links']}\n"
#                 f"❌ Без ссылок: {status_data['users_without_links']}\n\n"
#                 f"**Команды:**\n"
#                 f"/start_link_scheduler - запустить\n"
#                 f"/stop_link_scheduler - остановить\n"
#                 f"/generate_all_links - ручная генерация"
#             )
            
#             await message.answer(status_message, parse_mode="Markdown")
            
#         except Exception as e:
#             logger.error(f"Ошибка при получении статуса планировщика: {e}")
#             await message.answer("❌ Ошибка при получении статуса")

#     @dp.message(Command("get_links"))
#     async def get_links_command(message: Message):
#         """Получение всех активных ссылок в формате Telegram ссылок"""
#         try:
#             with db.get_connection() as conn:
#                 cursor = conn.cursor()
                
#                 # Получаем все активные ссылки с информацией о пользователях
#                 cursor.execute('''
#                     SELECT mu.participant_id, mu.last_name, mu.first_name, 
#                         lg.universal_link, lg.status, lg.creation_date, lg.mailing_date
#                     FROM manual_upload mu
#                     LEFT JOIN link_generation lg ON mu.participant_id = lg.participant_id
#                     WHERE lg.status = 1
#                     ORDER BY mu.last_name, mu.first_name
#                 ''')
                
#                 active_links = cursor.fetchall()
                
#                 if not active_links:
#                     await message.answer("❌ Нет активных ссылок. Сначала выполните команду /generate_all_links")
#                     return
                
#                 # Формируем сообщение со ссылками (без Markdown)
#                 links_message = "🔗 Telegram ссылки для регистрации:\n\n"
                
#                 for participant_id, last_name, first_name, universal_link, status, creation_date, mailing_date in active_links:
#                     full_name = f"{last_name} {first_name}"
#                     # Формируем Telegram ссылку
#                     telegram_link = f"https://t.me/{bot_username}?start={universal_link}"
#                     links_message += f"👤 {full_name}\n"
#                     links_message += f"🔗 Ссылка: {telegram_link}\n"
#                     links_message += f"📅 Создана: {creation_date}\n"
                    
#                     # Показываем статус рассылки
#                     if mailing_date is None:
#                         links_message += f"📧 Статус рассылки: ❌ НЕ ОТПРАВЛЕНО\n"
#                     else:
#                         links_message += f"📧 Отправлено: {mailing_date}\n"
                    
#                     links_message += f"🆔 ID: {participant_id}\n\n"
                
#                 # Разбиваем сообщение на части, если оно слишком длинное
#                 if len(links_message) > 4000:
#                     # Отправляем первую часть (без parse_mode)
#                     await message.answer(links_message[:4000])
#                     # Отправляем остальные части
#                     for i in range(4000, len(links_message), 4000):
#                         await message.answer(links_message[i:i+4000])
#                 else:
#                     await message.answer(links_message)
                
#                 logger.info(f"Пользователь {message.from_user.id} запросил список ссылок")
                
#         except Exception as e:
#             logger.error(f"Ошибка при получении списка ссылок: {e}", exc_info=True)
#             await message.answer("❌ Произошла ошибка при получении списка ссылок")

#     @dp.message(Command("get_links_compact"))
#     async def get_links_compact_command(message: Message):
#         """Компактный вывод ссылок (только ссылки)"""
#         try:
#             with db.get_connection() as conn:
#                 cursor = conn.cursor()
                
#                 cursor.execute('''
#                     SELECT mu.last_name, mu.first_name, lg.universal_link, lg.mailing_date
#                     FROM manual_upload mu
#                     JOIN link_generation lg ON mu.participant_id = lg.participant_id
#                     WHERE lg.status = 1
#                     ORDER BY mu.last_name, mu.first_name
#                 ''')
                
#                 active_links = cursor.fetchall()
                
#                 if not active_links:
#                     await message.answer("❌ Нет активных ссылок")
#                     return
                
#                 links_message = "🔗 **Ссылки для отправки:**\n\n"
                
#                 for last_name, first_name, universal_link, mailing_date in active_links:
#                     telegram_link = f"https://t.me/{bot_username}?start={universal_link}"
#                     status_icon = "❌" if mailing_date is None else "✅"
#                     links_message += f"{status_icon} {last_name} {first_name}:\n{telegram_link}\n\n"
                
#                 await message.answer(links_message, parse_mode="Markdown")
                
#         except Exception as e:
#             logger.error(f"Ошибка при получении компактного списка ссылок: {e}", exc_info=True)
#             await message.answer("❌ Произошла ошибка")

#     @dp.message(Command("get_link_stats"))
#     async def get_link_stats_command(message: Message):
#         """Получение статистики по ссылкам"""
#         try:
#             with db.get_connection() as conn:
#                 cursor = conn.cursor()
                
#                 # Статистика по ссылкам
#                 cursor.execute('''
#                     SELECT 
#                         COUNT(*) as total_users,
#                         SUM(CASE WHEN lg.participant_id IS NOT NULL THEN 1 ELSE 0 END) as users_with_links,
#                         SUM(CASE WHEN lg.status = 1 THEN 1 ELSE 0 END) as active_links,
#                         SUM(CASE WHEN lg.status = 0 THEN 1 ELSE 0 END) as used_links,
#                         SUM(CASE WHEN m.participant_id IS NOT NULL THEN 1 ELSE 0 END) as registered_users,
#                         SUM(CASE WHEN lg.mailing_date IS NULL AND lg.status = 1 THEN 1 ELSE 0 END) as pending_mailing
#                     FROM manual_upload mu
#                     LEFT JOIN link_generation lg ON mu.participant_id = lg.participant_id
#                     LEFT JOIN main m ON mu.participant_id = m.participant_id
#                 ''')
                
#                 stats = cursor.fetchone()
#                 total_users, users_with_links, active_links, used_links, registered_users, pending_mailing = stats
                
#                 stats_message = (
#                     "📊 **Статистика ссылок:**\n\n"
#                     f"👥 Всего пользователей: {total_users}\n"
#                     f"🔗 Пользователей с ссылками: {users_with_links}\n"
#                     f"✅ Активных ссылок: {active_links}\n"
#                     f"❌ Использованных ссылок: {used_links}\n"
#                     f"🎯 Зарегистрированных: {registered_users}\n"
#                     f"📧 Ожидают рассылки: {pending_mailing}\n\n"
#                     f"📈 Охват: {registered_users}/{total_users} ({registered_users/total_users*100:.1f}%)"
#                 )
                
#                 await message.answer(stats_message, parse_mode="Markdown")
#                 logger.info(f"Пользователь {message.from_user.id} запросил статистику ссылок")
                
#         except Exception as e:
#             logger.error(f"Ошибка при получении статистики: {e}", exc_info=True)
#             await message.answer("❌ Произошла ошибка при получении статистики")

#     @dp.message(Command("reset_mailing_dates"))
#     async def reset_mailing_dates_command(message: Message):
#         """Сброс mailing_date для всех активных ссылок (для тестирования)"""
#         try:
#             with db.get_connection() as conn:
#                 cursor = conn.cursor()
                
#                 # Сбрасываем mailing_date для всех активных ссылок
#                 cursor.execute('''
#                     UPDATE link_generation 
#                     SET mailing_date = NULL 
#                     WHERE status = 1
#                 ''')
                
#                 affected_rows = cursor.rowcount
#                 conn.commit()
                
#                 await message.answer(
#                     f"🔄 Сброшены даты рассылки для {affected_rows} активных ссылок\n\n"
#                     f"📧 Теперь все активные пользователи готовы к рассылке!",
#                     parse_mode="HTML"
#                 )
#                 logger.info(f"Сброшены mailing_date для {affected_rows} активных ссылок")
                
#         except Exception as e:
#             logger.error(f"Ошибка при сбросе mailing_date: {e}", exc_info=True)
#             await message.answer("❌ Произошла ошибка при сбросе дат рассылки")

# # Функция для обработки перехода по ссылке
# def handle_link_click(universal_link: str, telegram_id: int, telegram_username: str = None, logger: logging.Logger = None):
#     """Обработка перехода по ссылке и регистрация участника"""
#     try:
#         with db.get_connection() as conn:
#             cursor = conn.cursor()
            
#             # Находим ссылку и проверяем её активность
#             cursor.execute('''
#                 SELECT lg.participant_id, mu.last_name, mu.first_name, lg.status
#                 FROM link_generation lg
#                 JOIN manual_upload mu ON lg.participant_id = mu.participant_id
#                 WHERE lg.universal_link = ?
#             ''', (universal_link,))
            
#             link_data = cursor.fetchone()
            
#             if not link_data:
#                 return False, "Ссылка не найдена или недействительна"
            
#             participant_id, last_name, first_name, status = link_data
            
#             if status == 0:
#                 return False, "Эта ссылка уже использована"
            
#             # Проверяем, не зарегистрирован ли уже этот participant_id
#             cursor.execute('''
#                 SELECT user_id FROM main WHERE participant_id = ?
#             ''', (participant_id,))
            
#             existing_registration = cursor.fetchone()
            
#             if existing_registration:
#                 return False, "Этот участник уже зарегистрирован"
            
#             # Проверяем, не зарегистрирован ли уже этот telegram_id
#             cursor.execute('''
#                 SELECT user_id FROM main WHERE telegram_id = ?
#             ''', (telegram_id,))
            
#             existing_telegram_user = cursor.fetchone()
            
#             if existing_telegram_user:
#                 # Обновляем существующую запись пользователя
#                 cursor.execute('''
#                     UPDATE main 
#                     SET participant_id = ?, role = 'user'
#                     WHERE telegram_id = ?
#                 ''', (participant_id, telegram_id))
#                 user_id = existing_telegram_user[0]
#             else:
#                 # Создаем новую запись пользователя
#                 cursor.execute('''
#                     INSERT INTO main (participant_id, telegram_id, telegram_username, role)
#                     VALUES (?, ?, ?, 'user')
#                 ''', (participant_id, telegram_id, telegram_username))
#                 user_id = cursor.lastrowid
            
#             # Деактивируем ссылку
#             cursor.execute('''
#                 UPDATE link_generation 
#                 SET status = 0, link_click_date = CURRENT_TIMESTAMP
#                 WHERE universal_link = ?
#             ''', (universal_link,))
            
#             conn.commit()
            
#             if logger:
#                 logger.info(f"Участник зарегистрирован: user_id={user_id}, participant_id={participant_id}, telegram_id={telegram_id}")
            
#             return True, f"🎉 Поздравляем! Вы успешно зарегистрированы как участник: {last_name} {first_name}"
            
#     except Exception as e:
#         if logger:
#             logger.error(f"Ошибка при обработке ссылки {universal_link}: {e}", exc_info=True)
#         return False, "Произошла ошибка при регистрации. Попробуйте позже."
