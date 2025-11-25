# russia_running_api.py - исправленная версия с 2FA
import requests
import json
import time
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

class RussiaRunningAPI:
    """
    Полный API клиент для RussiaRunning с поддержкой двухфакторной аутентификации
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://russiarunning.com"
        self.is_authenticated = False
        self.username = None
        self.two_factor_required = False
        
        # Установка заголовков браузера
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 YaBrowser/25.8.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        
        logging.basicConfig(level=logging.INFO, format='%(message)s')
        self.logger = logging.getLogger(__name__)

    def _create_multipart_data(self, fields: dict) -> tuple:
        """Создает multipart/form-data"""
        boundary = "----WebKitFormBoundary" + "".join([str(i) for i in range(10)])
        
        data_parts = []
        for name, value in fields.items():
            data_parts.append(f'--{boundary}')
            data_parts.append(f'Content-Disposition: form-data; name="{name}"')
            data_parts.append('')
            data_parts.append(str(value))
        
        data_parts.append(f'--{boundary}--')
        data_parts.append('')
        
        multipart_data = '\r\n'.join(data_parts)
        
        headers = {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(multipart_data)),
        }
        
        return multipart_data, headers

    def login(self, username: str = None, password: str = None) -> bool:
        """
        Выполняет вход в систему с поддержкой 2FA
        """
        if not username or not password:
            username = os.getenv('RR_USERNAME')
            password = os.getenv('RR_PASSWORD')
        
        if not username or not password:
            self.logger.error("❌ Не указаны учетные данные")
            return False
        
        self.username = username
        
        try:
            self.logger.info("📄 Получаем страницу логина...")
            login_page_response = self.session.get(f"{self.base_url}/login")
            self.logger.info(f"🔐 Страница логина: {login_page_response.status_code}")
            
            # Создаем multipart данные с правильными полями
            login_fields = {
                'username': username,  # Правильное имя поля
                'password': password,  # Правильное имя поля
                'returnUrl': '/Account'
            }
            
            multipart_data, content_headers = self._create_multipart_data(login_fields)
            
            headers = {
                **content_headers,
                'Referer': f'{self.base_url}/login',
                'Origin': self.base_url,
            }

            self.logger.info("🔐 Отправляем логин и пароль...")
            response = self.session.post(
                f"{self.base_url}/login",
                data=multipart_data,
                headers=headers,
                allow_redirects=False
            )
            
            self.logger.info(f"📥 Ответ сервера: {response.status_code}")
            
            # Обрабатываем ответ
            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get('Success'):
                        self.logger.info("✅ Первый этап авторизации успешен")
                        
                        # Проверяем, требуется ли 2FA
                        if self._check_if_2fa_required():
                            self.logger.info("🔐 Требуется двухфакторная аутентификация")
                            return self._handle_two_factor_auth()
                        else:
                            # Без 2FA - проверяем авторизацию
                            if self._check_auth():
                                self.is_authenticated = True
                                self.save_session()
                                self.logger.info("✅ Успешный вход без 2FA!")
                                return True
                    
                    else:
                        error_msg = result.get('ErrorMessage', 'Неизвестная ошибка')
                        self.logger.error(f"❌ Ошибка входа: {error_msg}")
                        return False
                        
                except Exception as e:
                    self.logger.error(f"❌ Ошибка парсинга JSON: {e}")
                    return False
            
            # Если редирект на 2FA
            elif response.status_code == 302:
                location = response.headers.get('Location', '')
                self.logger.info(f"📍 Location: {location}")
                
                if 'TwoFactorAuth' in location:
                    self.logger.info("🔐 Требуется двухфакторная аутентификация")
                    return self._handle_two_factor_auth()
                else:
                    # Следуем за редиректом
                    if location:
                        final_response = self.session.get(location)
                    
                    if self._check_auth():
                        self.is_authenticated = True
                        self.save_session()
                        self.logger.info("✅ Успешный вход!")
                        return True
            
            self.logger.error("❌ Не удалось войти")
            return False
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка при входе: {e}")
            return False

    def _check_if_2fa_required(self) -> bool:
        """Проверяет, требуется ли 2FA"""
        try:
            # Проверяем, перенаправляет ли нас на страницу 2FA
            profile_response = self.session.get(f"{self.base_url}/Profile", allow_redirects=False)
            if profile_response.status_code == 302:
                location = profile_response.headers.get('Location', '')
                return 'TwoFactorAuth' in location
            
            # Пробуем получить страницу 2FA
            two_factor_response = self.session.get(f"{self.base_url}/Auth/TwoFactorAuth", allow_redirects=False)
            return two_factor_response.status_code == 200
            
        except:
            return False

    def _handle_two_factor_auth(self) -> bool:
        """
        Обрабатывает двухфакторную аутентификацию
        """
        try:
            self.logger.info("📄 Получаем страницу 2FA...")
            two_factor_response = self.session.get(f"{self.base_url}/Auth/TwoFactorAuth")
            
            if two_factor_response.status_code != 200:
                self.logger.error(f"❌ Не удалось загрузить страницу 2FA: {two_factor_response.status_code}")
                return False
            
            # Запрашиваем код 2FA у пользователя
            print("\n📱 Требуется двухфакторная аутентификация")
            print("Откройте приложение Google Authenticator и введите 6-значный код")
            
            # Даем 3 попытки для ввода кода
            for attempt in range(3):
                two_factor_code = input(f"Попытка {attempt + 1}/3 - Введите код из Google Authenticator: ").strip()
                
                if len(two_factor_code) != 6 or not two_factor_code.isdigit():
                    print("❌ Код должен содержать 6 цифр")
                    continue
                
                # Создаем multipart данные для 2FA
                two_factor_fields = {
                    'code': two_factor_code,
                    'returnUrl': '/Account'
                }
                
                multipart_data, content_headers = self._create_multipart_data(two_factor_fields)
                
                headers = {
                    **content_headers,
                    'Referer': f'{self.base_url}/Auth/TwoFactorAuth',
                    'Origin': self.base_url,
                }

                self.logger.info(f"🔐 Отправляем код 2FA: {two_factor_code}")
                response = self.session.post(
                    f"{self.base_url}/Auth/TwoFactorAuth",
                    data=multipart_data,
                    headers=headers,
                    allow_redirects=False
                )
                
                self.logger.info(f"📥 Ответ сервера 2FA: {response.status_code}")
                self.logger.info(f"📄 Content-Type: {response.headers.get('Content-Type', 'unknown')}")
                
                # Обрабатываем разные типы ответов
                if response.status_code == 200:
                    content_type = response.headers.get('Content-Type', '').lower()
                    
                    # Если это JSON
                    if 'application/json' in content_type:
                        try:
                            result = response.json()
                            if result.get('Success'):
                                self.logger.info("✅ Код 2FA принят!")
                                
                                # Проверяем авторизацию
                                if self._check_auth():
                                    self.is_authenticated = True
                                    self.save_session()
                                    self.logger.info("✅ Успешный вход с 2FA!")
                                    return True
                            else:
                                error_msg = result.get('ErrorMessage', 'Неверный код')
                                print(f"❌ {error_msg}")
                                continue
                                
                        except Exception as e:
                            self.logger.error(f"❌ Ошибка парсинга JSON 2FA: {e}")
                            print("❌ Неверный код 2FA")
                    
                    # Если это HTML (вероятно страница с ошибкой)
                    elif 'text/html' in content_type:
                        response_text = response.text.lower()
                        
                        # Проверяем наличие ошибок в HTML
                        if 'неверный код' in response_text or 'invalid code' in response_text:
                            print("❌ Неверный код 2FA")
                            continue
                        elif 'успех' in response_text or 'success' in response_text:
                            self.logger.info("✅ Код 2FA принят (HTML ответ)!")
                            
                            # Проверяем авторизацию
                            if self._check_auth():
                                self.is_authenticated = True
                                self.save_session()
                                self.logger.info("✅ Успешный вход с 2FA!")
                                return True
                        else:
                            # Неизвестный HTML ответ - проверяем авторизацию
                            self.logger.info("📄 Получен HTML ответ, проверяем авторизацию...")
                            if self._check_auth():
                                self.is_authenticated = True
                                self.save_session()
                                self.logger.info("✅ Успешный вход с 2FA!")
                                return True
                            else:
                                print("❌ Неверный код 2FA")
                                continue
                    
                    else:
                        # Неизвестный тип контента - проверяем авторизацию
                        self.logger.info(f"📄 Неизвестный тип контента: {content_type}")
                        if self._check_auth():
                            self.is_authenticated = True
                            self.save_session()
                            self.logger.info("✅ Успешный вход с 2FA!")
                            return True
                        else:
                            print("❌ Неверный код 2FA")
                            continue
                
                elif response.status_code == 302:
                    location = response.headers.get('Location', '')
                    self.logger.info(f"📍 Location header: {location}")
                    
                    if location:
                        # Обрабатываем относительные URL
                        if location.startswith('/'):
                            location = f"{self.base_url}{location}"
                        
                        # Следуем за редиректом
                        try:
                            final_response = self.session.get(location)
                            self.logger.info(f"📥 Редирект на: {location} - {final_response.status_code}")
                        except Exception as e:
                            self.logger.error(f"❌ Ошибка при переходе по редиректу: {e}")
                            continue
                    
                    # Проверяем авторизацию после редиректа
                    time.sleep(1)  # Даем серверу время
                    if self._check_auth():
                        self.is_authenticated = True
                        self.save_session()
                        self.logger.info("✅ Успешный вход с 2FA!")
                        return True
                    else:
                        print("❌ Неверный код 2FA")
                else:
                    print(f"❌ Неожиданный статус ответа: {response.status_code}")
                    self.logger.info(f"📄 Тело ответа (первые 500 символов): {response.text[:500]}")
            
            self.logger.error("❌ Превышено количество попыток 2FA")
            return False
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка при обработке 2FA: {e}")
            return False

    def _check_auth(self) -> bool:
        """
        Внутренняя проверка авторизации
        """
        try:
            response = self.session.get(f"{self.base_url}/Account", allow_redirects=False)
            if response.status_code == 301 and response.headers.get('Location') == '/Profile':
                return True
            
            # Альтернативная проверка
            profile_response = self.session.get(f"{self.base_url}/Profile", allow_redirects=False)
            return profile_response.status_code == 200
            
        except:
            return False

    def get_profile(self) -> dict:
        """
        Получает информацию профиля
        """
        if not self.is_authenticated:
            self.logger.error("❌ Не авторизован")
            return {}
        
        try:
            response = self.session.get(f"{self.base_url}/Profile")
            if response.status_code == 200:
                return {
                    'status': 'success',
                    'html_length': len(response.text),
                    'url': f"{self.base_url}/Profile"
                }
            return {'status': 'error', 'code': response.status_code}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def get_events(self, page: int = 1) -> dict:
        """
        Получает список событий
        """
        if not self.is_authenticated:
            self.logger.error("❌ Не авторизован")
            return {}
        
        try:
            response = self.session.get(f"{self.base_url}/events")
            if response.status_code == 200:
                return {
                    'status': 'success',
                    'endpoint': '/events',
                    'data': 'available'
                }
            return {'status': 'error', 'message': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def get_orders(self) -> dict:
        """
        Получает список заказов/регистраций
        """
        if not self.is_authenticated:
            self.logger.error("❌ Не авторизован")
            return {}
        
        try:
            response = self.session.get(f"{self.base_url}/Account/OrderList")
            if response.status_code == 200:
                return {
                    'status': 'success',
                    'endpoint': '/Account/OrderList',
                    'html_length': len(response.text)
                }
            return {'status': 'error', 'message': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def save_session(self, filename: str = "rr_session.json"):
        """
        Сохраняет сессию
        """
        session_data = {
            'cookies': dict(self.session.cookies),
            'headers': dict(self.session.headers),
            'username': self.username,
            'timestamp': datetime.now().isoformat(),
            'authenticated': self.is_authenticated
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"💾 Сессия сохранена в {filename}")

    def load_session(self, filename: str = "rr_session.json") -> bool:
        """
        Загружает сессию
        """
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            cookies = session_data.get('cookies', {})
            for name, value in cookies.items():
                self.session.cookies.set(name, value)
            
            headers = session_data.get('headers', {})
            self.session.headers.update(headers)
            
            self.username = session_data.get('username')
            
            if self._check_auth():
                self.is_authenticated = True
                self.logger.info("✅ Сессия восстановлена")
                return True
            else:
                self.logger.warning("❌ Сессия неактивна")
                return False
                
        except FileNotFoundError:
            self.logger.warning("📂 Файл сессии не найден")
            return False
        except Exception as e:
            self.logger.warning(f"❌ Ошибка загрузки сессии: {e}")
            return False

def main():
    """
    Демонстрация работы API с 2FA
    """
    api = RussiaRunningAPI()
    
    print("=" * 50)
    print("🔐 RussiaRunning Авторизация с 2FA")
    print("=" * 50)
    
    # Пробуем загрузить существующую сессию
    if api.load_session():
        print("✅ Используем существующую сессию")
    else:
        print("🔐 Выполняем вход...")
        
        # Запрашиваем учетные данные
        username = os.getenv('RR_USERNAME')
        password = os.getenv('RR_PASSWORD')
        
        if not username:
            username = input("📧 Введите email/username: ").strip()
        if not password:
            password = input("🔑 Введите пароль: ").strip()
        
        if not api.login(username, password):
            print("❌ Не удалось войти")
            return
    
    print(f"\n📊 Статус: {'АВТОРИЗОВАН' if api.is_authenticated else 'НЕ АВТОРИЗОВАН'}")
    
    if api.is_authenticated:
        # Получаем профиль
        print(f"\n👤 Получаем профиль...")
        profile = api.get_profile()
        print(f"   Профиль: {profile}")
        
        # Получаем список забегов
        print(f"\n🏃 Получаем список забегов...")
        events = api.get_events()
        print(f"   События: {events}")
        
        # Получаем заказы
        print(f"\n📦 Получаем заказы...")
        orders = api.get_orders()
        print(f"   Заказы: {orders}")
    
    print(f"\n✅ Демонстрация завершена!")
    if api.is_authenticated:
        print(f"💾 Сессия сохранена для повторного использования")

if __name__ == "__main__":
    main()
