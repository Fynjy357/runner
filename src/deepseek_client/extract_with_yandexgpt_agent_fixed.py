# src/deepseek_client/extract_with_yandexgpt_agent_fixed.py
import os
import requests
import base64
import json
import re
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
    
    def analyze_with_gpt_agent(self, text: str) -> dict:
        """Анализирует текст с помощью вашего YandexGPT агента"""
        print("\n🤖 Отправляем текст вашему GPT агенту...")
        
        # Создаем четкий запрос для агента
        clear_prompt = f"""
Это текст из приложения для бега. Извлеки две переменные:

1. date (дата пробежки в формате dd.mm.yyyy) - преобразуй любые форматы дат в dd.mm.yyyy
2. distance (дистанция в формате XX.XX км)

ВАЖНО: Если видишь дату типа "8 нояб." - преобразуй в "08.11.2025"
Если год не указан - используй 2025 год.

Текст:
{text}

Верни ответ ТОЛЬКО в формате:
date: dd.mm.yyyy
distance: XX.XX км

Если данные не найдены, верни:
date: не найдено
distance: не найдено
"""
        
        payload = {
            "modelUri": "gpt://b1gc4fscmg7hif3096ur/yandexgpt/rc",
            "completionOptions": {
                "stream": False,
                "temperature": 0.3,
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
                return self.parse_agent_response(gpt_response)
            else:
                print(f"❌ Ошибка GPT агента: {response.status_code}")
                print(f"📝 Ответ: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка запроса к GPT агенту: {e}")
            return None
    
    def parse_agent_response(self, response_text: str) -> dict:
        """Парсит ответ агента и извлекает дату и дистанцию"""
        print("\n🔍 Парсим ответ агента...")
        
        result = {}
        
        # ✅ УЛУЧШАЕМ ПОИСК ДАТЫ - разные форматы
        date_patterns = [
            r'date:\s*(\d{2}\.\d{2}\.\d{4})',  # date: 08.11.2025
            r'(\d{2}\.\d{2}\.\d{4})',          # 08.11.2025
            r'date:\s*(\d{1,2}\.\d{1,2}\.\d{4})',  # date: 8.11.2025
            r'(\d{1,2}\.\d{1,2}\.\d{4})',      # 8.11.2025
        ]
        
        date_found = False
        for pattern in date_patterns:
            date_match = re.search(pattern, response_text)
            if date_match:
                raw_date = date_match.group(1)
                # ✅ НОРМАЛИЗУЕМ ДАТУ (добавляем ведущие нули)
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
            result['date'] = "не найдено"
            print("❌ Дата не найдена")
        
        # ✅ Ищем дистанцию
        distance_match = re.search(r'distance:\s*(\d+\.\d+)\s*км', response_text, re.IGNORECASE)
        if distance_match:
            result['distance'] = f"{distance_match.group(1)} км"
            print(f"✅ Найдена дистанция: {result['distance']}")
        else:
            # Альтернативный поиск дистанции
            distance_match_alt = re.search(r'(\d+\.\d+)\s*км', response_text)
            if distance_match_alt:
                result['distance'] = f"{distance_match_alt.group(1)} км"
                print(f"✅ Найдена дистанция: {result['distance']}")
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

def main():
    """Основная функция для извлечения данных о пробежке"""
    load_dotenv()
    
    # ✅ Теперь можно анализировать ЛЮБУЮ картинку
    image_path = "../media/stage_1/764400696_1342567.jpg"  # Это только пример
    
    if not os.path.exists(image_path):
        print(f"❌ Изображение не найдено по пути: {image_path}")
        print("💡 Укажите путь к существующему изображению")
        return
    
    print(f"📁 Путь к изображению: {image_path}")
    print("=" * 60)
    
    # ✅ Используем универсальную функцию
    running_data = extract_data_for_user(image_path)
    
    # Выводим результаты
    print("\n" + "=" * 60)
    print("🏃‍♂️ РЕЗУЛЬТАТЫ АНАЛИЗА ПРОБЕЖКИ:")
    print("=" * 60)
    
    if running_data.get('agent_response'):
        agent_data = running_data['agent_response']
        
        print("📊 ДАННЫЕ ОТ GPT АГЕНТА:")
        print(f"📅 Дата пробежки: {agent_data.get('date', 'не найдено')}")
        print(f"📏 Дистанция: {agent_data.get('distance', 'не найдено')}")
    
    else:
        print("❌ Не удалось получить данные от агента")
    
    # Сохраняем в файл
    output_file = "running_analysis_agent_result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(running_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Полные результаты сохранены в: {output_file}")

if __name__ == "__main__":
    main()
