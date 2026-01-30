# config.py (обновленная версия)
import os
from pathlib import Path
from dotenv import load_dotenv

def load_config():
    """Загрузка конфигурации из .env файла"""
    load_dotenv()
    
    config = {
        'token': os.getenv('TELEGRAM_BOT_TOKEN'),
        'screenshots_dir': Path(os.getenv('SCREENSHOTS_DIR', 'screenshots')),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'timeout': int(os.getenv('TIMEOUT', 15)),
        'retry_count': int(os.getenv('RETRY_COUNT', 3)),
        'admin_chat_id': os.getenv('ADMIN_CHAT_ID'),
        'bot_password': os.getenv('BOT_PASSWORD', ''),
        'allowed_group_id': os.getenv('ALLOWED_GROUP_ID'),
    }
    
    # Загрузка настроек расписания в новом формате
    schedule_enabled = os.getenv('SCHEDULE_ENABLED', 'false').lower() == 'true'
    schedule_config = os.getenv('SCHEDULE_CONFIG')
    
    # Если не указан новый формат, используем старый для обратной совместимости
    if not schedule_config:
        interval_minutes = int(os.getenv('SCHEDULE_INTERVAL', '60'))
        schedule_config = interval_minutes
    
    config['schedule'] = {
        'enabled': schedule_enabled,
        'config': schedule_config
    }
    
    # Настройки отключения команд
    disabled_commands = os.getenv('DISABLED_COMMANDS', '').split(',')
    config['disabled_commands'] = [cmd.strip().lower() for cmd in disabled_commands if cmd.strip()]
    
    return config