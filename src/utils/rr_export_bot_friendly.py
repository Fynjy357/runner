# src/utils/rr_export_bot_friendly.py
import asyncio
import requests
import json
import os
import re
import sys
import time
from urllib.parse import quote
from datetime import datetime

# Добавляем путь для импорта основного API
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from russiarunning.russia_running_api import RussiaRunningAPI
except ImportError:
    print("❌ Не удалось импортировать RussiaRunningAPI")
    RussiaRunningAPI = None

class BotFriendlyRussiaRunningExporter:
    """Экспортер для работы с ботом - без интерактивного ввода"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session_file_path = "../russiarunning/rr_session.json"
        self.api = None
        self.two_factor_required = False
        self.last_auth_attempt = None
        self.auth_lock = False
        
        # Установка заголовков браузера
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 YaBrowser/25.8.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        
    def ensure_authenticated(self):
        """Проверяет сессию без интерактивного ввода"""
        if self.auth_lock:
            print("🔒 Аутентификация заблокирована (предыдущая попытка)")
            return False, "Аутентификация временно заблокирована"
            
        print("🔍 Проверяем сессию...")
        
        # Пробуем загрузить существующую сессию
        if self._load_session():
            print("✅ Сессия активна")
            return True, None
        else:
            print("❌ Сессия неактивна или не найдена")
            return self._reauthenticate_without_input()
    
    def _load_session(self):
        """Загружает сессию из файла"""
        try:
            if not os.path.exists(self.session_file_path):
                print(f"📂 Файл сессии не найден: {self.session_file_path}")
                return False
            
            with open(self.session_file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # Восстанавливаем cookies как в работающей системе
            cookies = session_data.get('cookies', {})
            for name, value in cookies.items():
                self.session.cookies.set(name, value, domain='.russiarunning.com')
            
            print(f"✅ Сессия загружена: {session_data.get('username', 'unknown')}")
            
            # Проверяем валидность сессии простым способом
            return self._check_session_validity()
            
        except Exception as e:
            print(f"❌ Ошибка загрузки сессии: {e}")
            return False
    
    def _check_session_validity(self):
        """Проверяет валидность сессии - простой способ"""
        try:
            response = self.session.get(
                "https://admin.russiarunning.com/event/OnlineraceTheMysteryoftheLostCollection/participants",
                allow_redirects=False,
                timeout=10
            )
            
            if response.status_code == 200:
                print("✅ Сессия валидна")
                return True
            elif response.status_code in [302, 401, 403]:
                location = response.headers.get('Location', '')
                print(f"❌ Сессия невалидна (редирект на логин: {location})")
                return False
            else:
                print(f"⚠️ Неожиданный статус: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка проверки сессии: {e}")
            return False
    
    def _reauthenticate_without_input(self):
        """Пытается выполнить аутентификацию без интерактивного ввода"""
        print("🔄 Пытаемся выполнить аутентификацию...")
        
        if not RussiaRunningAPI:
            print("❌ RussiaRunningAPI недоступен")
            return False, "API недоступен"
        
        try:
            self.api = RussiaRunningAPI()
            
            # Пробуем загрузить сессию через API
            if self.api.load_session(self.session_file_path):
                print("✅ Сессия восстановлена через API")
                self.session = self.api.session
                return True, None
            
            # Если не удалось загрузить, проверяем учетные данные
            from dotenv import load_dotenv
            load_dotenv()
            
            username = os.getenv('RR_USERNAME')
            password = os.getenv('RR_PASSWORD')
            
            if not username or not password:
                print("❌ Учетные данные не найдены в .env файле")
                return False, "Учетные данные не найдены в .env"
            
            # Пытаемся выполнить логин до этапа 2FA
            auth_result = self._login_without_2fa(username, password)
            
            if auth_result == "2FA_REQUIRED":
                print("✅ Успешная аутентификация до этапа 2FA")
                # Сохраняем сессию на этом этапе
                self._save_partial_session(username)
                self.session = self.api.session
                self.two_factor_required = True
                return False, "Требуется код 2FA"
            elif auth_result == "BLOCKED":
                print("❌ Аккаунт заблокирован")
                self.auth_lock = True
                # Автоматически разблокируем через 6 минут
                asyncio.create_task(self._unlock_auth_after_timeout(360))
                return False, "Аккаунт заблокирован на 5 минут. Попробуйте позже."
            elif auth_result == "SUCCESS":
                print("✅ Успешная аутентификация без 2FA")
                self.session = self.api.session
                return True, None
            else:
                print("❌ Ошибка аутентификации")
                return False, "Ошибка аутентификации"
                
        except Exception as e:
            print(f"❌ Ошибка при аутентификации: {e}")
            return False, f"Ошибка: {str(e)}"
    
    def _save_partial_session(self, username: str):
        """Сохраняет частичную сессию (после успешного логина до 2FA)"""
        try:
            # Сохраняем cookies как в работающей системе
            session_data = {
                'cookies': dict(self.api.session.cookies),
                'headers': dict(self.api.session.headers),
                'username': username,
                'timestamp': datetime.now().isoformat(),
                'authenticated': False,
                'two_factor_required': True
            }
            
            os.makedirs(os.path.dirname(self.session_file_path), exist_ok=True)
            
            with open(self.session_file_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Частичная сессия сохранена в {self.session_file_path}")
            
        except Exception as e:
            print(f"❌ Ошибка сохранения частичной сессии: {e}")
    
    def _login_without_2fa(self, username: str, password: str) -> str:
        """Выполняет логин до этапа 2FA без интерактивного ввода"""
        try:
            print("📄 Получаем страницу логина...")
            login_page_response = self.api.session.get(f"{self.api.base_url}/login", timeout=10)
            print(f"🔐 Страница логина: {login_page_response.status_code}")
            
            # Создаем multipart данные
            login_fields = {
                'username': username,
                'password': password,
                'returnUrl': '/Account'
            }
            
            multipart_data, content_headers = self.api._create_multipart_data(login_fields)
            
            headers = {
                **content_headers,
                'Referer': f'{self.api.base_url}/login',
                'Origin': self.api.base_url,
            }

            print("🔐 Отправляем логин и пароль...")
            response = self.api.session.post(
                f"{self.api.base_url}/login",
                data=multipart_data,
                headers=headers,
                allow_redirects=False,
                timeout=10
            )
            
            print(f"📥 Ответ сервера: {response.status_code}")
            
            # Обрабатываем ответ
            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get('Success'):
                        print("✅ Первый этап авторизации успешен")
                        if self.api._check_if_2fa_required():
                            return "2FA_REQUIRED"
                        else:
                            if self.api._check_auth():
                                self.api.is_authenticated = True
                                self.api.save_session(self.session_file_path)
                                return "SUCCESS"
                            return "FAILED"
                    else:
                        error_msg = result.get('ErrorMessage', 'Неизвестная ошибка')
                        print(f"❌ Ошибка входа: {error_msg}")
                        
                        # Проверяем блокировку
                        if 'заблокированы' in error_msg or 'blocked' in error_msg.lower():
                            return "BLOCKED"
                        return "FAILED"
                except Exception as e:
                    print(f"❌ Ошибка парсинга JSON: {e}")
                    return "FAILED"
            
            elif response.status_code == 302:
                location = response.headers.get('Location', '')
                print(f"📍 Location: {location}")
                
                if 'TwoFactorAuth' in location:
                    print("🔐 Требуется двухфакторная аутентификация")
                    return "2FA_REQUIRED"
                else:
                    # Следуем за редиректом
                    if location:
                        if location.startswith('/'):
                            location = f"{self.api.base_url}{location}"
                        final_response = self.api.session.get(location, timeout=10)
                    
                    if self.api._check_auth():
                        self.api.is_authenticated = True
                        self.api.save_session(self.session_file_path)
                        print("✅ Успешный вход без 2FA!")
                        return "SUCCESS"
                    return "FAILED"
            
            print("❌ Не удалось войти")
            return "FAILED"
                
        except Exception as e:
            print(f"❌ Ошибка при входе: {e}")
            return "FAILED"

    def complete_2fa_auth(self, otp_code: str) -> bool:
        """Завершает аутентификацию с кодом 2FA"""
        if not self.api:
            # Пытаемся восстановить API из сохраненной сессии
            if not self._load_api_from_session():
                print("❌ API не инициализирован и не удалось восстановить из сессии")
                return False
        
        try:
            print("📄 Получаем страницу 2FA...")
            two_factor_response = self.api.session.get(
                f"{self.api.base_url}/Auth/TwoFactorAuth",
                timeout=10
            )
            
            if two_factor_response.status_code != 200:
                print(f"❌ Не удалось загрузить страницу 2FA: {two_factor_response.status_code}")
                # Пробуем альтернативный URL
                two_factor_response = self.api.session.get(
                    f"{self.api.base_url}/Account/TwoFactorAuth",
                    timeout=10
                )
                if two_factor_response.status_code != 200:
                    print(f"❌ Не удалось загрузить альтернативную страницу 2FA: {two_factor_response.status_code}")
                    return False
            
            # Извлекаем токены из формы если есть
            import re
            response_text = two_factor_response.text
            request_verification_token = None
            
            token_match = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', response_text)
            if token_match:
                request_verification_token = token_match.group(1)
                print(f"🔑 Найден токен: {request_verification_token[:20]}...")
            
            # Создаем multipart данные для 2FA
            two_factor_fields = {
                'code': otp_code,
                'returnUrl': '/Account'
            }
            
            if request_verification_token:
                two_factor_fields['__RequestVerificationToken'] = request_verification_token
            
            multipart_data, content_headers = self.api._create_multipart_data(two_factor_fields)
            
            headers = {
                **content_headers,
                'Referer': f'{self.api.base_url}/Auth/TwoFactorAuth',
                'Origin': self.api.base_url,
            }

            print(f"🔐 Отправляем код 2FA: {otp_code}")
            response = self.api.session.post(
                f"{self.api.base_url}/Auth/TwoFactorAuth",
                data=multipart_data,
                headers=headers,
                allow_redirects=False,
                timeout=10
            )
            
            print(f"📥 Ответ сервера 2FA: {response.status_code}")
            
            # Обрабатываем ответ
            if response.status_code == 200:
                # Проверяем успешность по содержимому
                response_text = response.text.lower()
                
                if 'неверный код' in response_text or 'invalid code' in response_text:
                    print("❌ Неверный код 2FA")
                    return False
                elif 'успех' in response_text or 'success' in response_text or 'добро пожаловать' in response_text:
                    print("✅ Код 2FA принят!")
                    if self.api._check_auth():
                        self.api.is_authenticated = True
                        self.api.save_session(self.session_file_path)
                        self.session = self.api.session
                        self.two_factor_required = False
                        print("✅ Успешный вход с 2FA!")
                        return True
                    else:
                        print("⚠️ Код принят, но проверка авторизации не прошла")
                        return False
                else:
                    # Проверяем авторизацию напрямую
                    if self.api._check_auth():
                        self.api.is_authenticated = True
                        self.api.save_session(self.session_file_path)
                        self.session = self.api.session
                        self.two_factor_required = False
                        print("✅ Успешный вход с 2FA!")
                        return True
                    else:
                        print("❌ Неверный код 2FA или ошибка авторизации")
                        return False
            
            elif response.status_code == 302:
                location = response.headers.get('Location', '')
                print(f"📍 Location header: {location}")
                
                if location:
                    if location.startswith('/'):
                        location = f"{self.api.base_url}{location}"
                    
                    try:
                        final_response = self.api.session.get(location, timeout=10)
                        print(f"📥 Редирект на: {location} - {final_response.status_code}")
                    except Exception as e:
                        print(f"⚠️ Ошибка при переходе по редиректу: {e}")
                
                if self.api._check_auth():
                    self.api.is_authenticated = True
                    self.api.save_session(self.session_file_path)
                    self.session = self.api.session
                    self.two_factor_required = False
                    print("✅ Успешный вход с 2FA!")
                    return True
                else:
                    print("❌ Неверный код 2FA")
                    return False
            else:
                print(f"❌ Неожиданный статус ответа: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка при обработке 2FA: {e}")
            return False

    def _load_api_from_session(self) -> bool:
        """Восстанавливает API из сохраненной сессии"""
        try:
            if not os.path.exists(self.session_file_path):
                return False
            
            with open(self.session_file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            if not session_data.get('two_factor_required'):
                return False
            
            self.api = RussiaRunningAPI()
            
            # Восстанавливаем cookies простым способом
            cookies = session_data.get('cookies', {})
            for name, value in cookies.items():
                self.api.session.cookies.set(name, value, domain='.russiarunning.com')
            
            headers = session_data.get('headers', {})
            self.api.session.headers.update(headers)
            
            self.api.username = session_data.get('username')
            
            print("✅ API восстановлен из сохраненной сессии")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка восстановления API из сессии: {e}")
            return False

    async def _unlock_auth_after_timeout(self, seconds: int):
        """Разблокирует аутентификацию после таймаута"""
        await asyncio.sleep(seconds)
        self.auth_lock = False
        print("🔓 Аутентификация разблокирована")

    def export_participants_excel(self, otp_code: str, use_fixed_name=True):
        """Экспортирует участников в Excel файл"""
        
        # Проверяем сессию
        is_authenticated, message = self.ensure_authenticated()
        
        if not is_authenticated:
            if message == "Требуется код 2FA":
                # Завершаем аутентификацию с кодом 2FA
                if not self.complete_2fa_auth(otp_code):
                    print("❌ Не удалось завершить аутентификацию с 2FA")
                    return None
            else:
                print(f"❌ Не удалось аутентифицироваться: {message}")
                return None
        
        # Параметры запроса
        request_params = {
            "eventCode": "OnlineraceTheMysteryoftheLostCollection",
            "country": None,
            "region": None,
            "city": None,
            "birthYear": None,
            "gender": None,
            "raceId": None,
            "socialCategoryCode": None,
            "runningClub": None,
            "category": None,
            "issueCode": None,
            "specialNomination": None,
            "sortRule": {"Type": 1, "Direction": 1},
            "page": 1,
            "pageSize": 25,
            "relayTeamName": None
        }
        
        # Кодируем параметры
        encoded_params = quote(json.dumps(request_params))
        
        # URL экспорта с OTP кодом
        export_url = f"https://admin.russiarunning.com/ParticipantsAdmin/ExportParticipantsToDocument?requestString={encoded_params}&templateCode=Details&otpCode={otp_code}"
        
        print("🚀 ВЫПОЛНЯЕМ ЭКСПОРТ...")
        
        # Добавляем заголовки
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Referer': 'https://admin.russiarunning.com/event/OnlineraceTheMysteryoftheLostCollection/participants',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Upgrade-Insecure-Requests': '1'
        }
        
        response = self.session.get(export_url, headers=headers, stream=True, timeout=30)
        
        print(f"📥 Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            # Определяем имя файла
            if use_fixed_name:
                filename = "participants_export_current.xls"
            else:
                content_disposition = response.headers.get('content-disposition', '')
                original_filename = self._extract_filename(content_disposition)
                
                if original_filename:
                    filename = original_filename
                else:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"participants_export_{timestamp}.xls"
            
            # Сохраняем файл
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(filename)
            
            print(f"✅ ЭКСПОРТ УСПЕШЕН!")
            print(f"📁 Файл сохранен: {filename}")
            print(f"📏 Размер: {file_size:,} bytes")
            try:
                from .database_processor import process_participants_export
                print("🔄 Обновляем базу данных...")
                if process_participants_export():
                    print("✅ База данных успешно обновлена")
                else:
                    print("⚠️ Ошибка обновления базы данных")
            except ImportError as e:
                print(f"⚠️ Не удалось импортировать database_processor: {e}")
            except Exception as e:
                print(f"⚠️ Ошибка при обновлении базы данных: {e}")
            return filename
        else:
            print(f"❌ ОШИБКА ЭКСПОРТА: {response.status_code}")
            if response.status_code == 403:
                print("🔐 Доступ запрещен. Возможно:")
                print("   • Неверный OTP код")
                print("   • Сессия устарела")
                print("   • Нет прав доступа")
            return None
    
    def _extract_filename(self, content_disposition):
        """Извлекает имя файла из заголовка Content-Disposition"""
        if not content_disposition:
            return None
        
        match = re.search(r"filename\*=UTF-8''(.+)", content_disposition)
        if match:
            import urllib.parse
            return urllib.parse.unquote(match.group(1))
        
        match = re.search(r'filename="([^"]+)"', content_disposition)
        if match:
            return match.group(1)
        
        return None

# Глобальный экземпляр для импорта
rr_exporter = BotFriendlyRussiaRunningExporter()
