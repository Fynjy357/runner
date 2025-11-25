# check_session.py - быстрая проверка сессии
import json
import requests
from russia_running_api import RussiaRunningAPI

def quick_check():
    """
    Быстрая проверка работоспособности сессии
    """
    api = RussiaRunningAPI()
    
    print("=== Быстрая проверка сессии ===")
    
    if api.load_session():
        print("✅ Сессия активна")
        
        # Быстрая проверка endpoints
        endpoints = [
            ('/Profile', 'Профиль'),
            ('/Account/OrderList', 'Заказы'),
            ('/events', 'События')
        ]
        
        for endpoint, name in endpoints:
            response = api.session.get(f"{api.base_url}{endpoint}")
            status = "✅" if response.status_code == 200 else "❌"
            print(f"   {status} {name}: {response.status_code}")
    
    else:
        print("❌ Сессия неактивна или не найдена")

if __name__ == "__main__":
    quick_check()
