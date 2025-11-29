#!src/mail_service/email_sender.py
"""
Модуль для отправки email через SMTP
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from typing import List, Dict, Any, Optional
import time
from datetime import datetime
import os
from pathlib import Path

# Используем абсолютные импорты
from .config import SMTPConfig
from .email_templates import EmailTemplates
from .utils import get_recipients_from_db, update_mailing_date

logger = logging.getLogger(__name__)

class EmailSender:
    def __init__(self, config: SMTPConfig):
        self.config = config
        self.templates = EmailTemplates()
    
    def attach_header_image(self, message: MIMEMultipart) -> bool:
        """Прикрепляет картинку header.jpg к письму"""
        try:
            # Путь к картинке относительно src/mail_service
            current_dir = Path(__file__).parent  # src/mail_service
            image_path = current_dir.parent / "media" / "header.jpg"  # src/media/header.jpg
            
            logger.info(f"🔍 Ищем картинку по пути: {image_path}")
            
            if image_path.exists():
                with open(image_path, 'rb') as img_file:
                    img_data = img_file.read()
                
                image = MIMEImage(img_data)
                image.add_header('Content-ID', '<header_image>')
                image.add_header('Content-Disposition', 'inline', filename='header.jpg')
                message.attach(image)
                logger.info("✅ Картинка header.jpg прикреплена к письму")
                return True
            else:
                logger.error(f"❌ Файл картинки не найден: {image_path}")
                # Создаем список файлов в папке media для отладки
                media_dir = current_dir.parent / "media"
                if media_dir.exists():
                    files = list(media_dir.iterdir())
                    logger.info(f"📁 Файлы в папке media: {[f.name for f in files]}")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка при прикреплении картинки: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Тестирование SMTP соединения"""
        try:
            logger.info(f"🔧 Тестируем соединение с {self.config.server}:{self.config.port}")
            
            if self.config.use_tls:
                # Для порта 587 используем STARTTLS
                server = smtplib.SMTP(self.config.server, self.config.port, timeout=10)
                server.starttls()
            else:
                # Для порта 465 используем SSL
                server = smtplib.SMTP_SSL(self.config.server, self.config.port, timeout=10)
            
            server.login(self.config.email, self.config.password)
            server.quit()
            
            logger.info("✅ SMTP соединение установлено успешно")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ Ошибка аутентификации: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"❌ Ошибка SMTP: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка соединения: {e}")
            return False
    
    def send_email(self, to_email: str, subject: str, html_content: str, 
                  text_content: str = "", recipient_data: Dict[str, Any] = None) -> bool:
        """Отправка одного email с поддержкой картинок"""
        try:
            # Создаем сообщение с поддержкой вложений
            msg = MIMEMultipart('related')  # Важно: 'related' для встроенных изображений
            msg['Subject'] = subject
            msg['From'] = self.config.email
            msg['To'] = to_email
            
            # Создаем альтернативную часть для текста и HTML
            alternative_part = MIMEMultipart('alternative')
            msg.attach(alternative_part)
            
            # Добавляем текстовую версию
            if text_content:
                text_part = MIMEText(text_content, 'plain', 'utf-8')
                alternative_part.attach(text_part)
            
            # Добавляем HTML версию
            html_part = MIMEText(html_content, 'html', 'utf-8')
            alternative_part.attach(html_part)
            
            # Прикрепляем картинку шапки
            self.attach_header_image(msg)
            
            # Подключаемся к серверу
            if self.config.use_tls:
                server = smtplib.SMTP(self.config.server, self.config.port, timeout=30)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.config.server, self.config.port, timeout=30)
            
            # Логинимся и отправляем
            server.login(self.config.email, self.config.password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"✅ Письмо отправлено: {to_email}")
            return True
            
        except smtplib.SMTPDataError as e:
            logger.error(f"❌ Ошибка данных SMTP для {to_email}: {e}")
            if "Try again later" in str(e):
                logger.info("⏳ Сервер просит повторить позже. Ждем 30 секунд...")
                time.sleep(30)
            return False
        except smtplib.SMTPException as e:
            logger.error(f"❌ Ошибка SMTP для {to_email}: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Неизвестная ошибка для {to_email}: {e}")
            return False
    
    def send_test_email(self, test_email: str) -> bool:
        """Отправка тестового письма с картинкой"""
        try:
            subject = "🧪 Тестовое письмо - Новогодний Квест"
            
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <img src="cid:header_image" alt="🎄 Новогоднее Приключение" style="width: 100%; height: auto;">
                    <div style="padding: 20px;">
                        <h1>🎄 Тестовое письмо</h1>
                        <p>Это тестовое письмо от системы рассылки Новогоднего Квеста.</p>
                        <p>Если вы получили это письмо и видите картинку выше, значит SMTP настройки работают корректно!</p>
                        <p><strong>Время отправки:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p><strong>Картинка в шапке:</strong> ✅ Прикреплена и отображается</p>
                    </div>
                </body>
            </html>
            """
            
            text_content = f"""Тестовое письмо от системы рассылки Новогоднего Квеста.
            
            Время отправки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            Это письмо содержит HTML версию с картинкой в шапке.
            """
            
            return self.send_email(test_email, subject, html_content, text_content)
        except Exception as e:
            logger.error(f"❌ Ошибка отправки тестового письма: {e}")
            return False
    
    def send_bulk_emails(self, template_name: str = 'universal_link') -> dict:
        """Массовая рассылка приветственных писем с универсальными ссылками"""
        recipients = get_recipients_from_db()
        
        if not recipients:
            logger.info("ℹ️ Нет получателей для рассылки (status = 1 и прошло >20 часов с mailing_date)")
            return {'info': 'No recipients found', 'sent': 0, 'failed': 0}
        
        logger.info(f"📧 Начинаем рассылку для {len(recipients)} получателей")
        
        sent_count = 0
        failed_count = 0
        failed_emails = []
        
        for i, recipient in enumerate(recipients, 1):
            email = recipient.get('email')
            participant_id = recipient.get('participant_id')
            universal_link = recipient.get('universal_link')
            stage_name = recipient.get('stage_name', 'новогодний квест')  # Название этапа из БД
            
            if not email:
                logger.warning(f"⚠️ Пропускаем получателя без email: {recipient}")
                continue
            
            if not universal_link:
                logger.warning(f"⚠️ Пропускаем получателя без ссылки: {email}")
                continue
            
            logger.info(f"📨 Отправка {i}/{len(recipients)}: {email} (Этап: {stage_name})")
            
            try:
                # Добавляем название этапа в данные получателя
                recipient['stage_name'] = stage_name
                
                # Получаем шаблон с универсальной ссылкой
                subject, html_content, text_content = self.templates.get_template(
                    template_name, recipient
                )
                
                # Отправляем письмо
                success = self.send_email(
                    email, subject, html_content, text_content, recipient
                )
                
                if success:
                    # Обновляем дату отправки
                    if participant_id:
                        update_mailing_date(participant_id)
                    
                    sent_count += 1
                    logger.info(f"✅ Отправлено {sent_count}/{len(recipients)}: {email}")
                else:
                    failed_count += 1
                    failed_emails.append(email)
                    logger.error(f"❌ Ошибка отправки: {email}")
                
                # Пауза между отправками (2 секунды)
                if i < len(recipients):
                    time.sleep(2)
                    
            except Exception as e:
                failed_count += 1
                failed_emails.append(email)
                logger.error(f"❌ Критическая ошибка для {email}: {e}")
        
        result = {
            'total': len(recipients),
            'sent': sent_count,
            'failed': failed_count,
            'failed_emails': failed_emails,
            'template': template_name
        }
        
        logger.info(f"📊 Результат рассылки: {result}")
        return result
