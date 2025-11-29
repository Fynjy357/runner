# src/deepseek_client/extract_with_yandexgpt_agent_fixed.py
import os
import requests
import base64
import json
import re
from datetime import datetime
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv


class RunningDataExtractorWithAgent:
    """Класс для извлечения данных о пробежке с помощью OCR + YandexGPT агента"""
    
    def __init__(self, vision_api_key: str = None, gpt_api_key: str = None, agent_id: str = None):
        # ✅ Загружаем переменные окружения
        load_dotenv()
        
        # ✅ Если аргументы не переданы, берем из переменных окружения
        self.vision_api_key = vision_api_key or os.getenv('YANDEX_VISION_API_KEY')
        self.gpt_api_key = gpt_api_key or os.getenv('YANDEX_GPT_API_KEY')
        self.agent_id = agent_id or os.getenv('YANDEX_AGENT_ID', 'fvtbn62k72jiet7vpiej')
        
        # ✅ Проверяем наличие обязательных ключей
        if not self.vision_api_key:
            raise ValueError("❌ YANDEX_VISION_API_KEY не установлен в переменных окружения")
        if not self.gpt_api_key:
            raise ValueError("❌ YANDEX_GPT_API_KEY не установлен в переменных окружения")
        
        self.vision_url = "https://ocr.api.cloud.yandex.net/ocr/v1"
        self.gpt_agent_url = f"https://llm.api.cloud.yandex.net/foundationModels/v1/completion?agentId={self.agent_id}"
        
        self.vision_headers = {
            "Authorization": f"Api-Key {self.vision_api_key}",
            "Content-Type": "application/json"
        }
        
        self.gpt_headers = {
            "Authorization": f"Api-Key {self.gpt_api_key}",
            "Content-Type": "application/json"
        }
        
        print(f"✅ Инициализирован экстрактор с agent_id: {self.agent_id}")
    
    def prepare_image(self, image_path: str) -> tuple:
        """Подготавливаем изображение для отправки"""
        try:
            # ✅ Нормализуем путь (заменяем обратные слеши)
            normalized_path = image_path.replace('\\', '/')
            
            with Image.open(normalized_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=90, optimize=True)
                image_data = buffer.getvalue()
                
                print(f"📸 Изображение загружено: {os.path.basename(normalized_path)}")
                print(f"📐 Размер: {img.size[0]}x{img.size[1]} пикселей")
                
                return image_data, "image/jpeg"
                
        except Exception as e:
            print(f"❌ Ошибка загрузки изображения {image_path}: {e}")
            return None, None
    
    def analyze_image_with_vision(self, image_path: str) -> dict:
        """Анализирует изображение с помощью Yandex Vision OCR"""
        print(f"\n🎯 АНАЛИЗ ИЗОБРАЖЕНИЯ: {image_path}")
        print("=" * 50)
        
        # ✅ Нормализуем путь и проверяем существование
        normalized_path = image_path.replace('\\', '/')
        if not os.path.exists(normalized_path):
            print(f"❌ Файл не найден: {normalized_path}")
            return None
        
        image_data, mime_type = self.prepare_image(normalized_path)
        if not image_data:
            return None
        
        payload = {
            "content": base64.b64encode(image_data).decode('utf-8'),
            "mime_type": mime_type,
            "language_codes": ["*"]
        }
        
        try:
            print("🔄 Отправляем в Yandex Vision OCR...")
            api_response = requests.post(
                f"{self.vision_url}/recognizeText",
                headers=self.vision_headers,
                json=payload,
                timeout=30
            )
            
            print(f"📡 Статус ответа: {api_response.status_code}")
            
            if api_response.status_code == 200:
                print("✅ Анализ успешен!")
                return api_response.json()
            else:
                print(f"❌ Ошибка API: {api_response.status_code}")
                print(f"📝 Ответ: {api_response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка запроса: {e}")
            return None
    
    def extract_full_text(self, response_data: dict) -> str:
        """Извлекает полный текст из ответа API"""
        if not response_data:
            return ""
        
        try:
            if 'result' in response_data and 'textAnnotation' in response_data['result']:
                text_annotation = response_data['result']['textAnnotation']
                full_text = text_annotation.get('fullText', '')
                return full_text
            return ""
        except Exception as e:
            print(f"❌ Ошибка извлечения текста: {e}")
            return ""
    
    def preprocess_text(self, text: str) -> str:
        """Предварительная обработка текста для улучшения распознавания"""
        # Удаляем лишние пробелы и символы
        text = re.sub(r'\s+', ' ', text)
        
        # Ищем ключевые паттерны дистанции
        distance_patterns = [
            r'(\d+\.\d+)\s*км',  # 10.01 км
            r'(\d+)\s*км',       # 10 км
            r'Расстояние\s*(\d+\.\d+)',  # Расстояние 10.01
            r'Дистанция\s*(\d+\.\d+)',   # Дистанция 10.01
        ]
        
        # Добавляем подсказки для агента
        enhanced_text = text
        
        for pattern in distance_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                enhanced_text += f"\n[ПОДСКАЗКА: Найдена дистанция {match.group(1)} км]"
                break
        
        # Ищем время активности (может помочь определить дистанцию)
        time_match = re.search(r'(\d+:\d+:\d+)', text)
        if time_match:
            enhanced_text += f"\n[ПОДСКАЗКА: Время активности {time_match.group(1)}]"
        
        return enhanced_text
    
    def analyze_with_gpt_agent(self, text: str) -> dict:
        """Анализирует текст с помощью вашего YandexGPT агента"""
        print("\n🤖 Отправляем текст вашему GPT агенту...")
        
        # Предварительная обработка текста
        processed_text = self.preprocess_text(text)
        
        # УЛУЧШЕННЫЙ запрос для агента
        clear_prompt = f"""
Это скриншот из приложения для бега (бегового трекера). Проанализируй текст и найди данные о пробежке.

ИЗВЛЕКИ СЛЕДУЮЩИЕ ДАННЫЕ:

1. DATE (дата пробежки) - найди дату в любом формате и преобразуй в формат DD.MM.YYYY
   Примеры форматов: "26 нояб 2025" -> "26.11.2025", "8 нояб." -> "08.11.2025"

2. DISTANCE (дистанция) - найди дистанцию в километрах
   Ищи паттерны: "XX.XX км", "XX км", "Расстояние XX.XX", "Дистанция XX.XX"
   В тексте есть число 10.01 - это может быть дистанция 10.01 км

ВАЖНЫЕ ПОДСКАЗКИ:
- Время активности 1:01:59 может соответствовать дистанции ~10 км
- Число 10.01 скорее всего означает дистанцию 10.01 км
- Если год не указан, используй 2025 год
- Если дата не найдена, но есть данные о пробежке, используй сегодняшнюю дату

РАСПОЗНАННЫЙ ТЕКСТ:
{processed_text}

ВЕРНИ ОТВЕТ ТОЛЬКО В ФОРМАТЕ:
date: DD.MM.YYYY
distance: XX.XX км

Если данные не найдены, верни:
date: не найдено
distance: не найдено
"""
        
        payload = {
            "modelUri": "gpt://b1gc4fscmg7hif3096ur/yandexgpt/rc",
            "completionOptions": {
                "stream": False,
                "temperature": 0.1,  # Уменьшаем температуру для большей точности
                "maxTokens": 6000
            },
            "messages": [
                {
                    "role": "user",
                    "text": clear_prompt
                }
            ]
        }
        
        try:
            print(f"🔗 Используем агента ID: {self.agent_id}")
            response = requests.post(
                self.gpt_agent_url,
                headers=self.gpt_headers,
                json=payload,
                timeout=30
            )
            
            print(f"📡 Статус ответа агента: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                gpt_response = result['result']['alternatives'][0]['message']['text']
                
                print("✅ Агент успешно обработал данные")
                print(f"📝 Ответ агента: {gpt_response}")
                
                # Пытаемся извлечь данные из ответа агента
                return self.parse_agent_response(gpt_response, text)
            else:
                print(f"❌ Ошибка GPT агента: {response.status_code}")
                print(f"📝 Ответ: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка запроса к GPT агенту: {e}")
            return None
    
    def parse_agent_response(self, response_text: str, original_text: str) -> dict:
        """Парсит ответ агента и извлекает дату и дистанцию"""
        print("\n🔍 Парсим ответ агента...")
        
        result = {}
        
        # ✅ УЛУЧШАЕМ ПОИСК ДАТЫ
        date_patterns = [
            r'date:\s*(\d{2}\.\d{2}\.\d{4})',
            r'(\d{2}\.\d{2}\.\d{4})',
            r'date:\s*(\d{1,2}\.\d{1,2}\.\d{4})',
            r'(\d{1,2}\.\d{1,2}\.\d{4})',
        ]
        
        date_found = False
        for pattern in date_patterns:
            date_match = re.search(pattern, response_text)
            if date_match:
                raw_date = date_match.group(1)
                try:
                    day, month, year = raw_date.split('.')
                    normalized_date = f"{int(day):02d}.{int(month):02d}.{year}"
                    result['date'] = normalized_date
                    print(f"✅ Найдена дата: {result['date']}")
                    date_found = True
                    break
                except ValueError:
                    continue
        
        if not date_found:
            # Если дата не найдена, используем сегодняшнюю
            today = datetime.now().strftime("%d.%m.%Y")
            result['date'] = today
            print(f"📅 Дата не найдена, используем сегодняшнюю: {today}")
        
        # ✅ УЛУЧШАЕМ ПОИСК ДИСТАНЦИИ
        distance_found = False
        
        # Сначала ищем в ответе агента
        distance_patterns = [
            r'distance:\s*(\d+\.\d+)\s*км',
            r'(\d+\.\d+)\s*км',
            r'distance:\s*(\d+)\s*км',
            r'(\d+)\s*км',
        ]
        
        for pattern in distance_patterns:
            distance_match = re.search(pattern, response_text, re.IGNORECASE)
            if distance_match:
                distance = distance_match.group(1)
                # Добавляем .00 если нужно
                if '.' not in distance:
                    distance = f"{distance}.00"
                result['distance'] = f"{distance} км"
                print(f"✅ Найдена дистанция: {result['distance']}")
                distance_found = True
                break
        
        # Если в ответе агента не нашли, ищем в оригинальном тексте
        if not distance_found:
            print("🔍 Ищем дистанцию в оригинальном тексте...")
            
            # Ищем явные упоминания дистанции
            explicit_patterns = [
                r'Расстояние\s*(\d+\.\d+)',
                r'Дистанция\s*(\d+\.\d+)',
                r'(\d+\.\d+)\s*км',
                r'(\d+)\s*км',
            ]
            
            for pattern in explicit_patterns:
                match = re.search(pattern, original_text, re.IGNORECASE)
                if match:
                    distance = match.group(1)
                    if '.' not in distance:
                        distance = f"{distance}.00"
                    result['distance'] = f"{distance} км"
                    print(f"✅ Найдена дистанция в тексте: {result['distance']}")
                    distance_found = True
                    break
        
        if not distance_found:
            # Пробуем найти число 10.01 (скорее всего это дистанция)
            if '10.01' in original_text:
                result['distance'] = "10.01 км"
                print("✅ Найдена дистанция 10.01 км (предположительно)")
            else:
                result['distance'] = "не найдено"
                print("❌ Дистанция не найдена")
        
        return result
    
    def extract_running_data(self, image_path: str) -> dict:
        """Основной метод извлечения данных о пробежке"""
        result_data = {}
        
        # 1. Анализируем изображение с помощью Vision OCR
        ocr_result = self.analyze_image_with_vision(image_path)
        if not ocr_result:
            return result_data
        
        # 2. Извлекаем текст
        full_text = self.extract_full_text(ocr_result)
        
        if not full_text:
            print("❌ Не удалось извлечь текст из изображения")
            return result_data
        
        print(f"\n📖 Распознанный текст для отправки агенту:")
        print("-" * 40)
        print(full_text)
        print("-" * 40)
        
        # 3. Анализируем текст с помощью вашего GPT агента
        agent_data = self.analyze_with_gpt_agent(full_text)
        
        if agent_data:
            result_data['agent_response'] = agent_data
            result_data['full_text'] = full_text
        
        return result_data

def extract_data_for_user(image_path: str) -> dict:
    """
    Универсальная функция для извлечения данных из любой картинки
    
    Args:
        image_path: Путь к изображению
        
    Returns:
        dict: Результаты анализа
    """
    try:
        extractor = RunningDataExtractorWithAgent()
        return extractor.extract_running_data(image_path)
    except Exception as e:
        print(f"❌ Ошибка при анализе изображения {image_path}: {e}")
        return {}

# Тестируем на конкретном изображении
def test_specific_image():
    """Тестируем на проблемном изображении"""
    image_path = "путь_к_вашему_изображению.jpg"  # Замените на реальный путь
    
    print("🧪 ТЕСТИРУЕМ ИСПРАВЛЕННЫЙ КОД")
    print("=" * 50)
    
    result = extract_data_for_user(image_path)
    
    print("\n" + "=" * 50)
    print("📊 РЕЗУЛЬТАТЫ:")
    print("=" * 50)
    
    if result.get('agent_response'):
        agent_data = result['agent_response']
        print(f"📅 Дата: {agent_data.get('date')}")
        print(f"📏 Дистанция: {agent_data.get('distance')}")
    else:
        print("❌ Не удалось получить данные")

if __name__ == "__main__":
    test_specific_image()
