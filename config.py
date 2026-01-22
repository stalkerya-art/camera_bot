# config.py (упрощенная версия)
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
    }
    
    # Загрузка настроек расписания
    schedule_config = {
        'enabled': os.getenv('SCHEDULE_ENABLED', 'false').lower() == 'true',
        'interval_minutes': int(os.getenv('SCHEDULE_INTERVAL', '60')),
        'start_time': os.getenv('SCHEDULE_START', '08:00'),
        'end_time': os.getenv('SCHEDULE_END', '22:00'),
        'days_of_week': os.getenv('SCHEDULE_DAYS', '0,1,2,3,4,5,6').split(','),
    }
    
    config['schedule'] = schedule_config
    
    # Настройки отключения команд
    disabled_commands = os.getenv('DISABLED_COMMANDS', '').split(',')
    config['disabled_commands'] = [cmd.strip().lower() for cmd in disabled_commands if cmd.strip()]
    
    return config