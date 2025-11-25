# src/handlers/login_pp.py
import asyncio
import subprocess
import sys
import os
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from utils.logger import setup_logging

# Настройка логирования
logger = setup_logging()

# Создаем router для команд RussiaRunning
login_router = Router()

async def login_command(message: Message):
    """
    Команда /login для авторизации в RussiaRunning
    """
    await message.answer("🔐 Запускаю авторизацию в RussiaRunning...")
    
    try:
        # Определяем путь к скриптам RussiaRunning
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        rr_script_path = os.path.join(script_dir, "russia_running_api.py")
        
        # Проверяем существование скрипта
        if not os.path.exists(rr_script_path):
            await message.answer("❌ Скрипт RussiaRunning не найден. Убедитесь, что файлы установлены правильно.")
            return
        
        # Запускаем наш скрипт авторизации
        result = subprocess.run(
            [sys.executable, rr_script_path],
            capture_output=True,
            text=True,
            cwd=script_dir,
            timeout=30
        )
        
        if result.returncode == 0:
            # Успешная авторизация
            output_lines = result.stdout.strip().split('\n')
            
            # Ищем ключевые сообщения в выводе
            success_messages = []
            for line in output_lines:
                if any(keyword in line for keyword in ['✅', 'Успешный', 'АВТОРИЗОВАН', 'сохранена']):
                    success_messages.append(line.strip())
            
            response = "✅ *Авторизация успешна!*\n\n"
            for msg in success_messages[:5]:  # Берем первые 5 важных сообщений
                response += f"• {msg}\n"
            
            # Добавляем быструю проверку
            check_script_path = os.path.join(script_dir, "check_session.py")
            if os.path.exists(check_script_path):
                check_result = subprocess.run(
                    [sys.executable, check_script_path],
                    capture_output=True,
                    text=True,
                    cwd=script_dir,
                    timeout=10
                )
                
                if check_result.returncode == 0:
                    response += "\n🔍 *Проверка сессии:*\n"
                    for line in check_result.stdout.strip().split('\n'):
                        if '✅' in line or '❌' in line:
                            response += f"{line}\n"
            
        else:
            # Ошибка авторизации
            response = "❌ *Ошибка авторизации!*\n\n"
            error_lines = result.stderr.strip().split('\n')
            for line in error_lines[-3:]:  # Берем последние 3 строки ошибки
                if line.strip():
                    response += f"• {line}\n"
        
        await message.answer(response, parse_mode='Markdown')
        logger.info(f"RussiaRunning: команда /login выполнена для пользователя {message.from_user.id}")
        
    except subprocess.TimeoutExpired:
        await message.answer("⏰ Таймаут авторизации. Попробуйте позже.")
        logger.warning("RussiaRunning: таймаут авторизации")
    except Exception as e:
        await message.answer(f"❌ Ошибка при запуске скрипта: {str(e)}")
        logger.error(f"RussiaRunning: ошибка при выполнении /login: {e}")

async def rr_status_command(message: Message):
    """
    Команда /rr_status для проверки статуса сессии
    """
    await message.answer("🔍 Проверяю статус сессии RussiaRunning...")
    
    try:
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        check_script_path = os.path.join(script_dir, "check_session.py")
        
        if not os.path.exists(check_script_path):
            await message.answer("❌ Скрипт проверки сессии не найден.")
            return
        
        # Запускаем проверку сессии
        result = subprocess.run(
            [sys.executable, check_script_path],
            capture_output=True,
            text=True,
            cwd=script_dir,
            timeout=15
        )
        
        if result.returncode == 0:
            response = "📊 *Статус сессии RussiaRunning:*\n\n"
            for line in result.stdout.strip().split('\n'):
                if line.strip() and '===' not in line:  # Пропускаем заголовки
                    response += f"{line}\n"
        else:
            response = "❌ *Не удалось проверить статус сессии*\n\n"
            for line in result.stderr.strip().split('\n')[-2:]:
                if line.strip():
                    response += f"{line}\n"
        
        await message.answer(response, parse_mode='Markdown')
        logger.info(f"RussiaRunning: команда /rr_status выполнена для пользователя {message.from_user.id}")
        
    except subprocess.TimeoutExpired:
        await message.answer("⏰ Таймаут проверки статуса.")
        logger.warning("RussiaRunning: таймаут проверки статуса")
    except Exception as e:
        await message.answer(f"❌ Ошибка при проверке статуса: {str(e)}")
        logger.error(f"RussiaRunning: ошибка при выполнении /rr_status: {e}")

async def rr_logout_command(message: Message):
    """
    Команда /rr_logout для выхода из системы
    """
    await message.answer("🚪 Выполняю выход из системы RussiaRunning...")
    
    try:
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Создаем простой скрипт для выхода
        logout_script = """
from russia_running_api import RussiaRunningAPI
api = RussiaRunningAPI()
if api.load_session():
    api.logout()
    print("✅ Выход выполнен успешно")
else:
    print("❌ Нет активной сессии для выхода")
        """
        
        result = subprocess.run(
            [sys.executable, "-c", logout_script],
            capture_output=True,
            text=True,
            cwd=script_dir,
            timeout=10
        )
        
        if result.returncode == 0:
            response = result.stdout.strip()
        else:
            response = "❌ Ошибка при выходе: " + result.stderr.strip()
        
        await message.answer(response)
        logger.info(f"RussiaRunning: команда /rr_logout выполнена для пользователя {message.from_user.id}")
        
    except subprocess.TimeoutExpired:
        await message.answer("⏰ Таймаут выхода из системы.")
        logger.warning("RussiaRunning: таймаут выхода из системы")
    except Exception as e:
        await message.answer(f"❌ Ошибка при выходе: {str(e)}")
        logger.error(f"RussiaRunning: ошибка при выполнении /rr_logout: {e}")

async def rr_help_command(message: Message):
    """
    Команда /rr_help для справки по RussiaRunning командам
    """
    help_text = """
🤖 *RussiaRunning Commands*

*/login* - Авторизация в RussiaRunning
*/rr_status* - Проверка статуса сессии  
*/rr_logout* - Выход из системы
*/rr_help* - Эта справка

*Как это работает:*
• При первом использовании /login создается сессия
• Сессия сохраняется в файл для повторного использования
• Команда /rr_status показывает текущий статус подключения
• Сессия действительна несколько недель
    """
    
    await message.answer(help_text, parse_mode='Markdown')
    logger.info(f"RussiaRunning: команда /rr_help выполнена для пользователя {message.from_user.id}")

# Регистрируем обработчики команд
login_router.message.register(login_command, Command("login"))
login_router.message.register(rr_status_command, Command("rr_status"))
login_router.message.register(rr_logout_command, Command("rr_logout"))
login_router.message.register(rr_help_command, Command("rr_help"))

def setup_login_handler(dp):
    """
    Функция для настройки обработчиков RussiaRunning в основном dispatcher
    """
    dp.include_router(login_router)
    logger.info("✅ RussiaRunning handlers registered")

# Демонстрация работы (для тестирования)
if __name__ == "__main__":
    print("=== RussiaRunning Bot Commands ===")
    print("Доступные команды:")
    print("/login - Авторизация в RussiaRunning")
    print("/rr_status - Проверка статуса сессии") 
    print("/rr_logout - Выход из системы")
    print("/rr_help - Справка по командам")
