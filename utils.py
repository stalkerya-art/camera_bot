# utils.py
import html
import re
from datetime import datetime

def escape_html(text):
    """Экранирование специальных символов для HTML"""
    if not text:
        return ""
    return html.escape(str(text))

def format_timestamp(timestamp=None, format_str="%Y-%m-%d %H:%M:%S"):
    """Форматирование времени"""
    if timestamp is None:
        timestamp = datetime.now()
    return timestamp.strftime(format_str)

def humanize_size(size_bytes):
    """Конвертация размера в человекочитаемый формат"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def parse_time(time_str):
    """Парсинг времени из строки"""
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        return datetime.strptime("08:00", "%H:%M").time()