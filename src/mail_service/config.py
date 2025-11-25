#!src/mail_service/config.py
"""
Конфигурация SMTP
"""

import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class SMTPConfig:
    server: str
    port: int
    email: str
    password: str
    use_tls: bool = True

def load_smtp_config_from_env() -> Optional[SMTPConfig]:
    """Загрузка конфигурации SMTP из переменных окружения"""
    try:
        # Получаем путь к .env файлу в корне проекта
        current_dir = os.path.dirname(__file__)
        parent_dir = os.path.dirname(current_dir)  # src
        project_root = os.path.dirname(parent_dir)  # runner
        env_path = os.path.join(project_root, '.env')
        
        # Загружаем переменные из .env файла
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
        
        # Получаем настройки напрямую из переменных окружения
        server = os.getenv('SMTP_SERVER')
        email = os.getenv('SMTP_EMAIL')
        password = os.getenv('SMTP_PASSWORD')
        
        if not all([server, email, password]):
            print("❌ Не все SMTP настройки найдены")
            print(f"   Сервер: {server}")
            print(f"   Email: {email}")
            print(f"   Пароль: {'*' * len(password) if password else 'НЕТ'}")
            return None
        
        # Определяем порт по умолчанию
        port = int(os.getenv('SMTP_PORT', '465'))
        
        # Определяем использование TLS (для порта 587)
        use_tls = port == 587
        
        return SMTPConfig(
            server=server,
            port=port,
            email=email,
            password=password,
            use_tls=use_tls
        )
        
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        return None
