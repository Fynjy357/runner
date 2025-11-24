# src/utils/video_optimizer.py
import asyncio
import os
import subprocess
import logging
import json

def get_video_info(input_path: str) -> dict:
    """Получает информацию о видео файле с помощью FFprobe"""
    try:
        ffprobe_command = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            input_path
        ]
        
        result = subprocess.run(
            ffprobe_command,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            logging.error(f"❌ Ошибка FFprobe: {result.stderr}")
            return {}
    except Exception as e:
        logging.error(f"❌ Ошибка получения информации о видео: {e}")
        return {}

def optimize_hevc_vertical_video(input_path: str, output_path: str = None) -> str:
    """
    Специальная оптимизация для HEVC вертикальных видео (1080x1920)
    Решает проблемы с aspect ratio на iOS устройствах
    """
    if output_path is None:
        base_name = os.path.basename(input_path)
        output_path = os.path.join(os.path.dirname(input_path), f"optimized_{base_name}")
    
    try:
        if not os.path.exists(input_path):
            logging.error(f"❌ Входной видео файл не найден: {input_path}")
            return input_path
        
        logging.info(f"🚀 Оптимизация HEVC вертикального видео: {input_path}")
        
        # ✅ СПЕЦИАЛЬНЫЕ НАСТРОЙКИ ДЛЯ ВЕРТИКАЛЬНЫХ HEVC ВИДЕО
        ffmpeg_command = [
            'ffmpeg',
            '-i', input_path,
            
            # ✅ КОНВЕРТАЦИЯ ИЗ HEVC В H.264 (iOS совместимый)
            '-c:v', 'libx264',
            '-profile:v', 'high',           # High profile для лучшего качества
            '-level', '4.2',                # Уровень для 1080p видео
            '-pix_fmt', 'yuv420p',
            
            # ✅ СОХРАНЕНИЕ ВЕРТИКАЛЬНОГО ASPECT RATIO
            '-vf', 'scale=1080:1920:flags=lanczos,setdar=9/16',
            # Явно указываем размеры и aspect ratio
            
            # ✅ ОПТИМАЛЬНОЕ КАЧЕСТВО ДЛЯ ВЕРТИКАЛЬНОГО ВИДЕО
            '-crf', '22',                   # Хороший баланс качество/размер
            '-preset', 'medium',
            '-maxrate', '2500k',
            '-bufsize', '5000k',
            
            # ✅ АУДИО
            '-c:a', 'aac',
            '-b:a', '192k',
            '-ac', '2',
            
            # ✅ МЕТАДАННЫЕ ДЛЯ iOS
            '-movflags', '+faststart',
            '-f', 'mp4',
            
            # ✅ ДОПОЛНИТЕЛЬНЫЕ ФЛАГИ ДЛЯ СОВМЕСТИМОСТИ
            '-x264-params', 'scenecut=0:open_gop=0:min-keyint=25:keyint=50',
            
            '-y',
            output_path
        ]
        
        logging.info(f"🔧 Команда для HEVC вертикального видео: {' '.join(ffmpeg_command)}")
        
        result = subprocess.run(
            ffmpeg_command,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                optimized_info = get_video_info(output_path)
                
                if optimized_info.get('streams'):
                    for stream in optimized_info['streams']:
                        if stream.get('codec_type') == 'video':
                            width = stream.get('width', 0)
                            height = stream.get('height', 0)
                            dar = stream.get('display_aspect_ratio', 'N/A')
                            logging.info(f"✅ HEVC видео оптимизировано: {width}x{height} (DAR: {dar})")
                            logging.info(f"💾 Размер файла: {file_size} bytes")
                            break
                
                return output_path
            else:
                logging.error(f"❌ Оптимизированный файл не создан: {output_path}")
                return input_path
        else:
            logging.error(f"❌ Ошибка оптимизации HEVC: {result.stderr}")
            return input_path
            
    except Exception as e:
        logging.error(f"❌ Ошибка при оптимизации HEVC видео {input_path}: {e}")
        return input_path

def optimize_video_for_telegram(input_path: str, output_path: str = None) -> str:
    """
    Умная оптимизация видео с автоматическим определением типа
    """
    if output_path is None:
        base_name = os.path.basename(input_path)
        output_path = os.path.join(os.path.dirname(input_path), f"optimized_{base_name}")
    
    try:
        if not os.path.exists(input_path):
            logging.error(f"❌ Входной видео файл не найден: {input_path}")
            return input_path
        
        # Анализируем исходное видео
        video_info = get_video_info(input_path)
        is_hevc = False
        is_vertical = False
        original_width = 0
        original_height = 0
        
        if video_info.get('streams'):
            for stream in video_info['streams']:
                if stream.get('codec_type') == 'video':
                    codec = stream.get('codec_name', '')
                    width = stream.get('width', 0)
                    height = stream.get('height', 0)
                    dar = stream.get('display_aspect_ratio', '')
                    
                    is_hevc = codec.lower() in ['hevc', 'h265']
                    is_vertical = height > width
                    original_width = width
                    original_height = height
                    
                    logging.info(f"📊 Анализ видео: {codec}, {width}x{height}, DAR: {dar}")
                    break
        
        # ✅ ВЫБИРАЕМ ПРАВИЛЬНЫЙ МЕТОД ОПТИМИЗАЦИИ
        if is_hevc and is_vertical and original_height == 1920:
            logging.info("🎯 Обнаружено HEVC вертикальное видео 1080x1920 - применяем специальную оптимизацию")
            return optimize_hevc_vertical_video(input_path, output_path)
        else:
            # Стандартная оптимизация для других видео
            logging.info("🔧 Применяем стандартную оптимизацию")
            return optimize_standard_video(input_path, output_path)
            
    except Exception as e:
        logging.error(f"❌ Ошибка при анализе видео {input_path}: {e}")
        return input_path

def optimize_standard_video(input_path: str, output_path: str = None) -> str:
    """
    Стандартная оптимизация для обычных видео
    """
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
            '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos',
            '-y',
            output_path
        ]
        
        result = subprocess.run(
            ffmpeg_command,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0 and os.path.exists(output_path):
            logging.info(f"✅ Стандартное видео оптимизировано: {input_path}")
            return output_path
        else:
            logging.error(f"❌ Ошибка стандартной оптимизации: {result.stderr}")
            return input_path
            
    except Exception as e:
        logging.error(f"❌ Ошибка при стандартной оптимизации {input_path}: {e}")
        return input_path

async def send_optimized_video(message, video_filename: str, caption: str = ""):
    """
    Отправляет оптимизированное видео с улучшенной обработкой для iOS
    """
    from pathlib import Path
    from aiogram.types import FSInputFile
    
    PROJECT_ROOT = Path(__file__).parent.parent
    MEDIA_PATH = PROJECT_ROOT / "media"
    
    def get_media_file(filename: str) -> str:
        file_path = MEDIA_PATH / filename
        if not file_path.exists():
            logging.error(f"❌ Медиа файл не найден: {file_path}")
        return str(file_path)
    
    try:
        video_path = get_media_file(video_filename)
        
        if not os.path.exists(video_path):
            logging.warning(f"❌ Видео файл не найден: {video_path}")
            if caption:
                await message.answer(caption, parse_mode="Markdown")
            await message.answer("📹 *Видео временно недоступно*", parse_mode="Markdown")
            return False
        
        logging.info(f"🎬 Обработка видео: {video_filename}")
        
        # ✅ УМНАЯ ОПТИМИЗАЦИЯ
        optimized_path = optimize_video_for_telegram(video_path)
        
        # Детальный анализ результата
        if optimized_path != video_path:
            result_info = get_video_info(optimized_path)
            if result_info.get('streams'):
                for stream in result_info['streams']:
                    if stream.get('codec_type') == 'video':
                        width = stream.get('width', 0)
                        height = stream.get('height', 0)
                        codec = stream.get('codec_name', '')
                        dar = stream.get('display_aspect_ratio', 'N/A')
                        logging.info(f"📐 Результат оптимизации: {codec}, {width}x{height}, DAR: {dar}")
                        break
        
        # Отправка видео
        video = FSInputFile(optimized_path)
        
        try:
            # Для вертикальных видео указываем правильные параметры
            if '1080x1920' in str(optimized_path) or 'vertical' in str(optimized_path).lower():
                await message.answer_video(
                    video,
                    caption=caption,
                    parse_mode="Markdown",
                    supports_streaming=True,
                    width=1080,
                    height=1920
                )
            else:
                await message.answer_video(
                    video,
                    caption=caption,
                    parse_mode="Markdown",
                    supports_streaming=True
                )
            
            success = True
            logging.info(f"✅ Видео отправлено: {video_filename}")
            
        except Exception as video_error:
            logging.warning(f"⚠️ Отправка как видео не удалась: {video_error}")
            await message.answer_document(
                video,
                caption=caption,
                parse_mode="Markdown"
            )
            success = True
            logging.info(f"✅ Видео отправлено как документ: {video_filename}")
        
        # Очистка временного файла
        if optimized_path != video_path and os.path.exists(optimized_path):
            try:
                os.remove(optimized_path)
                logging.info(f"🗑️ Временный файл удален: {optimized_path}")
            except Exception as e:
                logging.warning(f"⚠️ Не удалось удалить временный файл: {e}")
        
        await asyncio.sleep(3)
        return success
            
    except Exception as e:
        logging.error(f"❌ Ошибка при отправке видео {video_filename}: {e}")
        if caption:
            await message.answer(caption, parse_mode="Markdown")
        return False
