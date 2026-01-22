# test_isapi.py
import os
import requests
from requests.auth import HTTPDigestAuth
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def test_isapi_camera(camera_id):
    """Тестирование ISAPI камеры"""
    name = os.getenv(f'CAMERA_{camera_id}_NAME')
    base_url = os.getenv(f'CAMERA_{camera_id}_URL')
    username = os.getenv(f'CAMERA_{camera_id}_USER')
    password = os.getenv(f'CAMERA_{camera_id}_PASSWORD')
    channel = os.getenv(f'CAMERA_{camera_id}_CHANNEL', '1')
    
    if not name or not base_url:
        print(f"❌ Камера {camera_id}: Не настроена")
        return False
    
    print(f"\n🔍 Тестирование ISAPI камеры {camera_id}: {name}")
    print(f"   Базовая URL: {base_url}")
    print(f"   Пользователь: {username}")
    print(f"   Канал: {channel}")
    
    # Формируем URL для снимка
    snapshot_url = f"{base_url.rstrip('/')}/ISAPI/Streaming/channels/{channel}/picture"
    print(f"   Snapshot URL: {snapshot_url}")
    
    # Пробуем разные методы аутентификации
    auth_methods = [
        ('Digest', HTTPDigestAuth(username, password)),
        ('Basic', (username, password)),
        ('None', None)
    ]
    
    for method_name, auth in auth_methods:
        try:
            print(f"\n   Пробуем {method_name} аутентификацию...")
            start_time = datetime.now()
            
            response = requests.get(
                snapshot_url,
                auth=auth,
                timeout=15,
                verify=False,
                headers={'Accept': 'image/*'}
            )
            
            end_time = datetime.now()
            time_diff = (end_time - start_time).total_seconds()
            
            print(f"   Статус: {response.status_code}")
            print(f"   Время: {time_diff:.2f} сек")
            print(f"   Content-Type: {response.headers.get('content-type')}")
            print(f"   Размер: {len(response.content)} байт")
            
            if response.status_code == 200:
                # Проверяем, что это изображение
                if 'image' in response.headers.get('content-type', '').lower() or response.content[:2] == b'\xff\xd8':
                    print(f"   ✅ Успешно! Метод: {method_name}")
                    
                    # Сохраняем тестовый снимок
                    filename = f"test_isapi_{camera_id}_{method_name}.jpg"
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    print(f"   📁 Сохранен: {filename}")
                    
                    return True
                else:
                    print(f"   ❌ Не изображение")
            elif response.status_code == 401:
                print(f"   ❌ 401 Unauthorized")
            else:
                print(f"   ❌ Ошибка HTTP: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"   ❌ Таймаут (15 сек)")
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Ошибка подключения")
        except Exception as e:
            print(f"   ❌ Ошибка: {str(e)[:50]}")
    
    return False

def main():
    print("📡 Тестирование ISAPI камер")
    print("=" * 60)
    
    camera_id = 1
    total = 0
    success = 0
    
    while True:
        name = os.getenv(f'CAMERA_{camera_id}_NAME')
        cam_type = os.getenv(f'CAMERA_{camera_id}_TYPE', '').lower()
        
        if not name:
            break
        
        if cam_type == 'isapi':
            if test_isapi_camera(camera_id):
                success += 1
            total += 1
        
        camera_id += 1
    
    print("\n" + "=" * 60)
    if total > 0:
        print(f"📊 Итоги ISAPI камер: {success}/{total} работают")
    else:
        print("ℹ️  ISAPI камеры не найдены в конфигурации")

if __name__ == '__main__':
    main()