# camera_manager.py
import os
import logging
import requests
import time
from io import BytesIO
from datetime import datetime
from pathlib import Path
from requests.auth import HTTPDigestAuth
import urllib3
from utils import escape_html, format_timestamp

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class CameraManager:
    """Менеджер для работы с камерами"""
    
    def __init__(self, config):
        self.cameras = self.load_cameras()
        self.screenshots_dir = config['screenshots_dir']
        self.screenshots_dir.mkdir(exist_ok=True)
        self.timeout = config['timeout']
        self.retry_count = config['retry_count']
        self.stats = {
            'total_captures': 0,
            'successful_captures': 0,
            'failed_captures': 0,
            'last_capture_time': None
        }
    
    def load_cameras(self):
        """Загрузка конфигурации камер из .env"""
        cameras = {}
        i = 1
        
        while True:
            name = os.getenv(f'CAMERA_{i}_NAME')
            if not name:
                break
            
            cameras[i] = {
                'id': i,
                'name': name,
                'type': os.getenv(f'CAMERA_{i}_TYPE', 'http').lower(),
                'url': os.getenv(f'CAMERA_{i}_URL', ''),
                'username': os.getenv(f'CAMERA_{i}_USER'),
                'password': os.getenv(f'CAMERA_{i}_PASSWORD'),
                'channel': os.getenv(f'CAMERA_{i}_CHANNEL', '1'),
                'protocol': os.getenv(f'CAMERA_{i}_PROTOCOL', 'http'),
                'resolution': os.getenv(f'CAMERA_{i}_RESOLUTION', '1920x1080'),
                'enabled': os.getenv(f'CAMERA_{i}_ENABLED', 'true').lower() == 'true'
            }
            i += 1
        
        # Фильтруем только включенные камеры
        enabled_cameras = {k: v for k, v in cameras.items() if v['enabled']}
        logger.info(f"Загружено {len(enabled_cameras)} камер (всего {len(cameras)})")
        return enabled_cameras
    
    def get_isapi_snapshot_url(self, camera_config):
        """Формирование URL для ISAPI камер"""
        base_url = camera_config['url'].rstrip('/')
        channel = camera_config['channel']
        
        if 'hikvision' in base_url.lower() or ':8080' in base_url:
            return f"{base_url}/ISAPI/Streaming/channels/{channel}/picture"
        elif 'dahua' in base_url.lower():
            return f"{base_url}/cgi-bin/snapshot.cgi?channel={channel}"
        else:
            return f"{base_url}/ISAPI/Streaming/channels/{channel}/picture"
    
    def capture_from_isapi(self, camera_config):
        """Захват изображения с ISAPI камер (Hikvision/Dahua)"""
        try:
            snapshot_url = self.get_isapi_snapshot_url(camera_config)
            username = camera_config['username']
            password = camera_config['password']
            
            logger.info(f"ISAPI запрос: {snapshot_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/*,*/*;q=0.8',
                'Connection': 'keep-alive'
            }
            
            # Пробуем несколько методов аутентификации
            auth_methods = [
                HTTPDigestAuth(username, password),
                (username, password)
            ]
            
            for attempt in range(self.retry_count):
                for auth in auth_methods:
                    try:
                        response = requests.get(
                            snapshot_url,
                            auth=auth,
                            headers=headers,
                            timeout=self.timeout,
                            verify=False,
                            stream=True
                        )
                        
                        if response.status_code == 200:
                            if 'image' in response.headers.get('content-type', '').lower() or response.content[:4] == b'\xff\xd8\xff\xe0':
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                filename = f"isapi_{camera_config['id']}_{timestamp}.jpg"
                                file_path = self.screenshots_dir / filename
                                
                                with open(file_path, 'wb') as f:
                                    f.write(response.content)
                                
                                logger.info(f"ISAPI изображение сохранено: {file_path}")
                                image_data = BytesIO(response.content)
                                
                                # Возвращаем путь к файлу, данные изображения и успешный результат
                                return {
                                    'file_path': str(file_path),
                                    'image_data': image_data,
                                    'error': None,
                                    'camera_name': camera_config['name']
                                }
                        
                        elif response.status_code == 401:
                            logger.warning(f"ISAPI 401 Unauthorized, метод: {type(auth).__name__}")
                            continue
                    
                    except requests.exceptions.Timeout:
                        logger.warning(f"ISAPI таймаут, попытка {attempt + 1}")
                        continue
                    
                    except requests.exceptions.ConnectionError:
                        logger.warning(f"ISAPI ошибка подключения, попытка {attempt + 1}")
                        continue
            
            error_msg = "ISAPI аутентификация не удалась (401 Unauthorized)"
            return {
                'file_path': None,
                'image_data': None,
                'error': error_msg,
                'camera_name': camera_config['name']
            }
            
        except Exception as e:
            logger.error(f"Ошибка захвата с ISAPI камеры: {e}")
            error_msg = f"Ошибка ISAPI: {escape_html(str(e))}"
            return {
                'file_path': None,
                'image_data': None,
                'error': error_msg,
                'camera_name': camera_config['name']
            }
    
    def capture_from_http(self, camera_config):
        """Захват изображения с HTTP камеры"""
        try:
            url = camera_config['url']
            username = camera_config.get('username')
            password = camera_config.get('password')
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/*,*/*;q=0.8',
                'Connection': 'keep-alive'
            }
            
            auth_methods = []
            if username and password:
                auth_methods.extend([
                    HTTPDigestAuth(username, password),
                    (username, password)
                ])
            
            auth_methods.append(None)
            
            for attempt in range(self.retry_count):
                for auth in auth_methods:
                    try:
                        response = requests.get(
                            url,
                            auth=auth,
                            headers=headers,
                            timeout=self.timeout,
                            verify=False,
                            stream=True
                        )
                        
                        if response.status_code == 200:
                            if 'image' in response.headers.get('content-type', '').lower() or len(response.content) > 100:
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                filename = f"http_{camera_config['id']}_{timestamp}.jpg"
                                file_path = self.screenshots_dir / filename
                                
                                with open(file_path, 'wb') as f:
                                    f.write(response.content)
                                
                                logger.info(f"HTTP изображение сохранено: {file_path}")
                                image_data = BytesIO(response.content)
                                
                                # Возвращаем путь к файлу, данные изображения и успешный результат
                                return {
                                    'file_path': str(file_path),
                                    'image_data': image_data,
                                    'error': None,
                                    'camera_name': camera_config['name']
                                }
                        
                        elif response.status_code == 401:
                            continue
                    
                    except requests.exceptions.Timeout:
                        break
                    
                    except Exception:
                        continue
            
            error_msg = "HTTP аутентификация не удалась"
            return {
                'file_path': None,
                'image_data': None,
                'error': error_msg,
                'camera_name': camera_config['name']
            }
            
        except Exception as e:
            logger.error(f"Ошибка захвата с HTTP камеры: {e}")
            error_msg = f"Ошибка HTTP: {escape_html(str(e))}"
            return {
                'file_path': None,
                'image_data': None,
                'error': error_msg,
                'camera_name': camera_config['name']
            }
    
    def capture_image(self, camera_id):
        """Основная функция захвата изображения"""
        if camera_id not in self.cameras:
            error_msg = f"Камера {camera_id} не найдена"
            return {
                'file_path': None,
                'image_data': None,
                'error': error_msg,
                'camera_name': f'Камера {camera_id}'
            }
        
        camera = self.cameras[camera_id]
        logger.info(f"Захват с камеры {camera_id}: {camera['name']} ({camera['type']})")
        
        self.stats['total_captures'] += 1
        
        if camera['type'] == 'isapi':
            result = self.capture_from_isapi(camera)
        elif camera['type'] == 'http':
            result = self.capture_from_http(camera)
        else:
            error_msg = f"Неподдерживаемый тип камеры: {camera['type']}"
            result = {
                'file_path': None,
                'image_data': None,
                'error': error_msg,
                'camera_name': camera['name']
            }
        
        if result['error']:
            self.stats['failed_captures'] += 1
        else:
            self.stats['successful_captures'] += 1
            self.stats['last_capture_time'] = datetime.now()
        
        return result
    
    def capture_all(self):
        """Захват изображений со всех камер"""
        results = []
        for camera_id in self.cameras:
            result = self.capture_image(camera_id)
            # Добавляем ID камеры в результат
            result['camera_id'] = camera_id
            result['timestamp'] = datetime.now()
            results.append(result)
        
        logger.info(f"Захват со всех камер завершен. Успешно: {len([r for r in results if not r['error']])}, Ошибки: {len([r for r in results if r['error']])}")
        return results
    
    def get_stats(self):
        """Получение статистики работы"""
        return self.stats.copy()
    
    def get_storage_info(self):
        """Информация о хранилище"""
        try:
            files = list(self.screenshots_dir.glob("*.jpg")) + list(self.screenshots_dir.glob("*.png"))
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            
            # Получаем времена создания файлов
            mtimes = [f.stat().st_mtime for f in files if f.is_file()]
            
            return {
                'file_count': len(files),
                'total_size': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'oldest_file': min(mtimes, default=None),
                'newest_file': max(mtimes, default=None)
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о хранилище: {e}")
            return {'file_count': 0, 'total_size': 0, 'total_size_mb': 0}
    
    def cleanup_old_files(self, max_age_days=7):
        """Очистка старых файлов скриншотов"""
        try:
            files = list(self.screenshots_dir.glob("*.jpg")) + list(self.screenshots_dir.glob("*.png"))
            cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
            deleted_count = 0
            
            for file in files:
                if file.stat().st_mtime < cutoff_time:
                    file.unlink()
                    deleted_count += 1
            
            logger.info(f"Очищено {deleted_count} старых файлов скриншотов (старше {max_age_days} дней)")
            return deleted_count
        except Exception as e:
            logger.error(f"Ошибка при очистке старых файлов: {e}")
            return 0