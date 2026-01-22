# test_camera.py - тестирование подключения к камерам
import os
from dotenv import load_dotenv
import requests
from datetime import datetime

load_dotenv()

def test_camera(camera_id):
    """Тестирование подключения к камере"""
    name = os.getenv(f'CAMERA_{camera_id}_NAME')
    url = os.getenv(f'CAMERA_{camera_id}_URL')
    username = os.getenv(f'CAMERA_{camera_id}_USER')
    password = os.getenv(f'CAMERA_{camera_id}_PASSWORD')
    
    if not name or not url:
        print(f"❌ Камера {camera_id}: Не настроена")
        return False
    
    print(f"\n🔍 Тестирование камеры {camera_id}: {name}")
    print(f"   URL: {url}")
    print(f"   Пользователь: {username or 'не указан'}")
    
    try:
        auth = (username, password) if username and password else None
        start_time = datetime.now()
        
        response = requests.get(url, auth=auth, timeout=10, stream=True)
        response.raise_for_status()
        
        end_time = datetime.now()
        time_diff = (end_time - start_time).total_seconds()
        
        content_type = response.headers.get('content-type', '')
        size = len(response.content) // 1024
        
        print(f"✅ Успешно!")
        print(f"   Время ответа: {time_diff:.2f} сек")
        print(f"   Content-Type: {content_type}")
        print(f"   Размер: {size} КБ")
        
        return True
        
    except requests.exceptions.Timeout:
        print(f"❌ Таймаут (10 сек)")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Ошибка подключения")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {str(e)[:50]}")
        return False

def main():
    print("📡 Тестирование подключения к камерам")
    print("=" * 50)
    
    camera_id = 1
    total = 0
    success = 0
    
    while True:
        if not os.getenv(f'CAMERA_{camera_id}_NAME'):
            break
        
        if test_camera(camera_id):
            success += 1
        total += 1
        camera_id += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Итоги: {success}/{total} камер работают")
    
    if success == 0 and total > 0:
        print("\n⚠️  Рекомендации:")
        print("1. Проверьте IP-адреса камер")
        print("2. Убедитесь, что камеры включены")
        print("3. Проверьте логин и пароль")
        print("4. Убедитесь, что компьютер и камера в одной сети")

if __name__ == '__main__':
    main()