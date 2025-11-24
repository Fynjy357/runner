# src/utils/logger.py
import logging
import sys
import os

def setup_logging():
    """Настройка логирования"""
    # Создаем папку для логов если её нет
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Настройка формата
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Хендлер для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Хендлер для файла (с правильной кодировкой для Windows)
    file_handler = logging.FileHandler(
        os.path.join(log_dir, 'bot.log'), 
        encoding='utf-8',
        mode='a'  # Явно указываем режим добавления
    )
    file_handler.setFormatter(formatter)
    
    # Создаем логгер для нашего приложения, а не настраиваем корневой
    logger = logging.getLogger('bot')
    logger.setLevel(logging.INFO)
    
    # Очищаем существующие хендлеры
    logger.handlers.clear()
    
    # Добавляем наши хендлеры
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    # Отключаем пропагацию к корневому логгеру
    logger.propagate = False
    
    return logger
