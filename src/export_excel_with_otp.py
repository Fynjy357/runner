# export_excel_with_otp.py
import requests
import json
import os
import getpass
from urllib.parse import quote

def export_with_otp():
    """Экспорт с OTP кодом"""
    
    # Загружаем сессию
    session_file = os.path.join("..", "russiarunning", "rr_session.json")
    with open(session_file, 'r', encoding='utf-8') as f:
        session_data = json.load(f)
    
    session = requests.Session()
    for name, value in session_data.get('cookies', {}).items():
        session.cookies.set(name, value, domain='.russiarunning.com')
    
    print("🔐 ЭКСПОРТ С OTP КОДОМ")
    print("=" * 40)
    
    # Запрашиваем код из Authenticator
    otp_code = input("📱 Введите код из Authenticator: ").strip()
    
    # Параметры запроса (как в браузере)
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
    print(f"🔗 URL: {export_url[:100]}...")
    
    # Добавляем заголовки как в браузере
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://admin.russiarunning.com/event/OnlineraceTheMysteryoftheLostCollection/participants',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Upgrade-Insecure-Requests': '1'
    }
    
    response = session.get(export_url, headers=headers, stream=True)
    
    print(f"📥 Статус ответа: {response.status_code}")
    print(f"📋 Content-Type: {response.headers.get('content-type', 'N/A')}")
    
    if response.status_code == 200:
        # Проверяем, это файл или HTML страница
        content_type = response.headers.get('content-type', '')
        
        if 'excel' in content_type or 'application/vnd.ms-excel' in content_type:
            # Сохраняем Excel файл
            filename = "participants_export.xlsx"
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"✅ ЭКСПОРТ УСПЕШЕН! Файл сохранен: {filename}")
            print(f"📏 Размер файла: {os.path.getsize(filename)} bytes")
            return True
        else:
            # Это HTML страница (ошибка)
            print("❌ СЕРВЕР ВЕРНУЛ HTML (ОШИБКА)")
            error_file = "server_error.html"
            with open(error_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"📄 Ответ сохранен в: {error_file}")
            return False
    else:
        print(f"❌ ОШИБКА ЭКСПОРТА: {response.status_code}")
        return False

if __name__ == "__main__":
    export_with_otp()
