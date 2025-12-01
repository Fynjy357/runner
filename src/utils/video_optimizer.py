# src/utils/video_optimizer.py
import asyncio
import os
import sys
import subprocess
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading


# Импортируем наш логгер
from .logger import setup_logging

# Создаем логгер для этого модуля
logger = setup_logging()

# ✅ ДОБАВЛЯЕМ FFMPEG В PATH (ПОСЛЕ ИНИЦИАЛИЗАЦИИ ЛОГГЕРА)
project_root = Path(__file__).parent.parent.parent
ffmpeg_bin_path = project_root / "ffmpeg" / "bin"

logger.info(f"🔍 Проверяем путь к FFmpeg: {ffmpeg_bin_path}")

if ffmpeg_bin_path.exists():
    if str(ffmpeg_bin_path) not in os.environ['PATH']:
        os.environ['PATH'] = str(ffmpeg_bin_path) + os.pathsep + os.environ['PATH']
        logger.info(f"✅ Добавлен FFmpeg в PATH: {ffmpeg_bin_path}")
    
    # ✅ ИСПРАВЛЕНИЕ: Проверяем наличие ffmpeg для разных ОС
    ffmpeg_exe = ffmpeg_bin_path / "ffmpeg.exe"  # Windows
    ffmpeg_bin = ffmpeg_bin_path / "ffmpeg"      # Linux/Mac
    
    if ffmpeg_exe.exists():
        logger.info(f"✅ FFmpeg.exe найден (Windows): {ffmpeg_exe}")
    elif ffmpeg_bin.exists():
        logger.info(f"✅ FFmpeg найден (Linux/Mac): {ffmpeg_bin}")
    else:
        logger.error(f"❌ FFmpeg не найден в: {ffmpeg_bin_path}")
        # Показываем что есть в папке
        files = list(ffmpeg_bin_path.glob("*"))
        logger.info(f"📁 Файлы в папке bin: {[f.name for f in files]}")
else:
    logger.error(f"❌ Папка FFmpeg не найдена: {ffmpeg_bin_path}")
    # ✅ ИСПРАВЛЕНИЕ: Проверяем системный FFmpeg
    logger.info("🔍 Проверяем системный FFmpeg...")

def get_media_path() -> Path:
    """Получает путь к медиа директории"""
    project_root = Path(__file__).parent.parent.parent
    media_path = project_root / "src" / "media"
    
    logger.info(f"📁 Медиа путь: {media_path}")
    
    if not media_path.exists():
        logger.error(f"❌ Папка media не существует: {media_path}")
        media_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Создана папка media: {media_path}")
    
    return media_path

def get_video_path(video_filename: str) -> str:
    """
    Получает полный путь к видео файлу
    """
    media_path = get_media_path()
    video_path = media_path / video_filename
    
    if video_path.exists():
        logger.info(f"✅ Видео файл найден: {video_path}")
        return str(video_path)
    else:
        logger.error(f"❌ Видео файл не найден: {video_path}")
        return None

def is_ffmpeg_available() -> bool:
    """Проверяет доступность FFmpeg в системе"""
    try:
        # ✅ ИСПРАВЛЕНИЕ: Используем универсальную команду
        result = subprocess.run(
            ['ffmpeg', '-version'], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        available = result.returncode == 0
        if available:
            logger.info("✅ FFmpeg доступен в системе")
            # Логируем версию FFmpeg
            version_line = result.stdout.split('\n')[0] if result.stdout else "неизвестно"
            logger.info(f"📋 Версия FFmpeg: {version_line}")
        else:
            logger.warning("⚠️ FFmpeg не доступен")
        return available
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.warning(f"⚠️ FFmpeg не доступен: {e}")
        
        # ✅ ИСПРАВЛЕНИЕ: Проверяем альтернативные пути
        try:
            # Проверяем системный ffmpeg
            result = subprocess.run(
                ['which', 'ffmpeg'], 
                capture_output=True, 
                text=True
            )
            if result.returncode == 0:
                ffmpeg_path = result.stdout.strip()
                logger.info(f"✅ Найден системный FFmpeg: {ffmpeg_path}")
                return True
        except Exception:
            pass
            
        return False

def optimize_standard_video(input_path: str, output_path: str = None) -> str:
    """
    Стандартная оптимизация для обычных видео
    """
    if not input_path or not os.path.exists(input_path):
        logger.error(f"❌ Входной видео файл не найден для оптимизации: {input_path}")
        return input_path
    
    if output_path is None:
        base_name = os.path.basename(input_path)
        output_path = os.path.join(os.path.dirname(input_path), f"optimized_{base_name}")
    
    try:
        ffmpeg_command = [
            'ffmpeg',
            '-i', input_path,
            '-c:v', 'libx264',
            '-profile:v', 'main',
            '-level', '4.0',
            '-pix_fmt', 'yuv420p',
            '-crf', '23',
            '-preset', 'medium',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-y',
            output_path
        ]
        
        logger.info(f"🔄 Запускаем оптимизацию: {os.path.basename(input_path)}")
        logger.debug(f"Команда FFmpeg: {' '.join(ffmpeg_command)}")
        
        result = subprocess.run(
            ffmpeg_command,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0 and os.path.exists(output_path):
            # Проверяем размер оптимизированного файла
            original_size = os.path.getsize(input_path)
            optimized_size = os.path.getsize(output_path)
            compression_ratio = (1 - optimized_size / original_size) * 100
            
            logger.info(f"✅ Видео оптимизировано: {os.path.basename(input_path)} -> {os.path.basename(output_path)}")
            logger.info(f"📊 Сжатие: {original_size/1024/1024:.1f}MB → {optimized_size/1024/1024:.1f}MB ({compression_ratio:.1f}%)")
            return output_path
        else:
            logger.error(f"❌ Ошибка оптимизации: {result.stderr}")
            return input_path
            
    except subprocess.TimeoutExpired:
        logger.error(f"❌ Таймаут оптимизации видео: {os.path.basename(input_path)}")
        return input_path
    except Exception as e:
        logger.error(f"❌ Ошибка при оптимизации {os.path.basename(input_path)}: {e}")
        return input_path

def pre_optimize_all_videos():
    """Предварительно оптимизирует все видео при запуске в фоновом режиме"""
    
    def optimize_in_background():
        """Фоновая оптимизация"""
        logger.info("🎬 Начинаем фоновую оптимизацию видео...")
        
        if not is_ffmpeg_available():
            logger.warning("⚠️ FFmpeg недоступен - пропускаем предварительную оптимизацию")
            return
        
        media_path = get_media_path()
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv']
        
        def optimize_single_video(file_path):
            """Оптимизирует один видео файл"""
            try:
                file_name = os.path.basename(file_path)
                
                # ✅ ВАЖНО: Пропускаем уже оптимизированные файлы!
                if file_name.startswith('optimized_'):
                    logger.info(f"⏭️ Пропускаем уже оптимизированный файл: {file_name}")
                    return file_path
                
                if any(file_path.endswith(ext) for ext in video_extensions):
                    # Создаем имя для оптимизированной версии
                    optimized_name = f"optimized_{file_name}"
                    optimized_path = os.path.join(os.path.dirname(file_path), optimized_name)
                    
                    # Оптимизируем только если файл еще не существует
                    if not os.path.exists(optimized_path):
                        logger.info(f"🔄 Предварительная оптимизация: {file_name}")
                        result = optimize_standard_video(file_path, optimized_path)
                        if result != file_path:
                            logger.info(f"✅ Предварительно оптимизирован: {file_name}")
                        else:
                            logger.warning(f"⚠️ Не удалось оптимизировать: {file_name}")
                    else:
                        logger.info(f"ℹ️ Оптимизированная версия уже существует: {optimized_name}")
                return file_path
            except Exception as e:
                logger.error(f"❌ Ошибка при предварительной оптимизации {os.path.basename(file_path)}: {e}")
                return file_path
        
        # Собираем все видео файлы (ИСКЛЮЧАЯ уже оптимизированные)
        video_files = []
        for file_name in os.listdir(media_path):
            file_path = os.path.join(media_path, file_name)
            
            # ✅ ВАЖНО: Пропускаем уже оптимизированные файлы
            if file_name.startswith('optimized_'):
                continue
                
            if (os.path.isfile(file_path) and 
                any(file_name.lower().endswith(ext) for ext in video_extensions)):
                video_files.append(file_path)
        
        if video_files:
            logger.info(f"🎬 Найдено {len(video_files)} оригинальных видео файлов для оптимизации:")
            for video in video_files:
                logger.info(f"   📹 {os.path.basename(video)}")
            
            logger.info("🔄 Начинаем многопоточную оптимизацию...")
            
            # Оптимизируем в несколько потоков
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(optimize_single_video, video_files))
            
            # Подсчитываем результаты
            optimized_count = sum(1 for result in results if result and "optimized" in result)
            logger.info(f"✅ Предварительная оптимизация завершена. Обработано: {len(video_files)} файлов")
        else:
            logger.info("ℹ️ Оригинальные видео файлы для оптимизации не найдены")
            
            # Показываем существующие оптимизированные файлы
            optimized_files = [f for f in os.listdir(media_path) if f.startswith('optimized_')]
            if optimized_files:
                logger.info(f"ℹ️ Найдено {len(optimized_files)} уже оптимизированных файлов:")
                for opt_file in optimized_files[:5]:  # Показываем первые 5
                    logger.info(f"   ✅ {opt_file}")
                if len(optimized_files) > 5:
                    logger.info(f"   ... и еще {len(optimized_files) - 5} файлов")
    
    # Запускаем в фоновом потоке
    background_thread = threading.Thread(
        target=optimize_in_background, 
        daemon=True,
        name="VideoOptimizer"
    )
    background_thread.start()
    logger.info("🚀 Запущен фоновый процесс предварительной оптимизации видео")

def get_optimized_video_path(original_path: str) -> str:
    """
    Возвращает путь к оптимизированной версии видео, если она существует
    """
    if not original_path or not os.path.exists(original_path):
        return original_path
    
    base_name = os.path.basename(original_path)
    
    # ✅ ВАЖНО: Если файл уже оптимизирован, используем его
    if base_name.startswith('optimized_'):
        logger.info(f"✅ Файл уже оптимизирован: {base_name}")
        return original_path
    
    optimized_name = f"optimized_{base_name}"
    optimized_path = os.path.join(os.path.dirname(original_path), optimized_name)
    
    if os.path.exists(optimized_path):
        logger.info(f"✅ Используем предварительно оптимизированную версию: {optimized_name}")
        return optimized_path
    else:
        logger.info(f"ℹ️ Оптимизированная версия не найдена, используем оригинал: {base_name}")
        return original_path

async def send_optimized_video(message, video_filename: str, caption: str = ""):
    """
    Отправляет оптимизированное видео (использует предварительно созданные версии)
    """
    from aiogram.types import FSInputFile
    
    try:
        # ✅ Находим файл
        video_path = get_video_path(video_filename)
        
        if not video_path:
            logger.error(f"❌ Видео файл не найден: {video_filename}")
            if caption:
                await message.answer(caption, parse_mode="Markdown")
            await message.answer("📹 *Видео временно недоступно*", parse_mode="Markdown")
            return False
        
        logger.info(f"🎬 Отправляем видео: {video_filename}")
        
        # ✅ ИСПОЛЬЗУЕМ ПРЕДВАРИТЕЛЬНО ОПТИМИЗИРОВАННУЮ ВЕРСИЮ
        final_video_path = get_optimized_video_path(video_path)
        
        # ✅ ОТПРАВКА ВИДЕО
        video = FSInputFile(final_video_path)
        
        try:
            await message.answer_video(
                video,
                caption=caption,
                parse_mode="Markdown",
                supports_streaming=True
            )
            
            success = True
            logger.info(f"✅ Видео успешно отправлено: {video_filename}")
            
        except Exception as video_error:
            logger.warning(f"⚠️ Отправка как видео не удалась: {video_error}")
            # Пробуем отправить как документ
            try:
                await message.answer_document(
                    video,
                    caption=caption,
                    parse_mode="Markdown"
                )
                success = True
                logger.info(f"✅ Видео отправлено как документ: {video_filename}")
            except Exception as doc_error:
                logger.error(f"❌ Ошибка отправки как документ: {doc_error}")
                success = False
        
        await asyncio.sleep(1)
        return success
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при отправке видео {video_filename}: {e}")
        if caption:
            await message.answer(caption, parse_mode="Markdown")
        return False

# Автоматически запускаем предварительную оптимизацию при импорте
logger.info("📦 Импортирован модуль video_optimizer - запускаем предварительную оптимизацию")
pre_optimize_all_videos()
