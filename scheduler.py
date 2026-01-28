# scheduler.py
import logging
import threading
import time
import re
from datetime import datetime, timedelta
from typing import Optional, List, Union
import os
from telegram import InputMediaPhoto

logger = logging.getLogger(__name__)

class CameraScheduler:
    """Планировщик с поддержкой cron-расписаний"""
    
    def __init__(self, camera_manager, bot, chat_id, schedule_config: Union[str, List[str], int] = 60):
        """
        Инициализация планировщика
        
        Args:
            schedule_config: Конфигурация расписания:
                - int: интервал в минутах (режим интервала)
                - str: cron-выражение (например, "0 9-18 * * *")
                - List[str]: список конкретных времени (например, ["09:00", "13:30", "18:00"])
        """
        self.camera_manager = camera_manager
        self.bot = bot
        self.chat_id = chat_id
        
        # Режимы работы
        self.mode = "interval"  # По умолчанию интервальный режим
        self.schedule_config = schedule_config
        
        # Для интервального режима
        self.interval_minutes = 60
        
        # Для cron-режима
        self.cron_expression = None
        self.cron_parts = None
        
        # Для режима списка времени
        self.time_list = None
        
        # Инициализация в зависимости от типа конфига
        self._parse_schedule_config(schedule_config)
        
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        self.execution_count = 0
        self.last_execution: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        
        logger.info(f"Планировщик инициализирован в режиме '{self.mode}'")
    
    def _parse_schedule_config(self, config):
        """Парсинг конфигурации расписания"""
        if isinstance(config, int):
            self.mode = "interval"
            self.interval_minutes = config
            logger.info(f"Интервальный режим: {self.interval_minutes} минут")
                    
        elif isinstance(config, str):
            # Проверяем, является ли строкой cron-выражением
            if self._is_cron_expression(config):
               self.mode = "cron"
               self.cron_expression = config
               self.cron_parts = self._parse_cron_expression(config)
               logger.info(f"Cron-режим: {config}")
            else:
            # Разбиваем по пробелам или запятым
                self.mode = "time_list"
             # Разделяем по запятым или пробелам
                if ',' in config:
                    self.time_list = [t.strip() for t in config.split(',') if t.strip()]
                else:
                    self.time_list = [t.strip() for t in config.split() if t.strip()]
                logger.info(f"Режим списка времени: {self.time_list}")
        
                         
    def _is_cron_expression(self, expression: str) -> bool:
        """Проверяет, является ли строка cron-выражением"""
        # Простая проверка - cron обычно имеет 5 частей, разделенных пробелами
        parts = expression.strip().split()
        return len(parts) == 5
    
    def _parse_cron_expression(self, expression: str) -> dict:
        """Парсит cron-выражение на составляющие"""
        parts = expression.strip().split()
        
        # Базовый парсинг cron (упрощенный)
        return {
            'minute': parts[0],  # минуты (0-59)
            'hour': parts[1],    # часы (0-23)
            'day': parts[2],     # день месяца (1-31)
            'month': parts[3],   # месяц (1-12)
            'weekday': parts[4]  # день недели (0-6, 0=воскресенье)
        }
    
    def _cron_matches_time(self, dt: datetime) -> bool:
        """Проверяет, соответствует ли время cron-выражению"""
        if not self.cron_parts:
            return False
        
        def match_field(value: int, field: str) -> bool:
            """Проверяет соответствие значения полю cron"""
            if field == '*':
                return True
            elif ',' in field:
                # Список значений (например, "0,15,30,45")
                return str(value) in field.split(',')
            elif '-' in field:
                # Диапазон (например, "9-18")
                start, end = map(int, field.split('-'))
                return start <= value <= end
            elif '/' in field:
                # Шаг (например, "*/15" - каждые 15 минут)
                step = int(field.split('/')[1])
                return value % step == 0
            else:
                # Конкретное значение
                return value == int(field)
        
        # Проверяем все поля
        checks = [
            match_field(dt.minute, self.cron_parts['minute']),
            match_field(dt.hour, self.cron_parts['hour']),
            match_field(dt.day, self.cron_parts['day']),
            match_field(dt.month, self.cron_parts['month']),
            match_field(dt.weekday(), self.cron_parts['weekday'])  # weekday() возвращает 0-6
        ]
        
        return all(checks)
    
    def _calculate_next_run_time(self) -> Optional[datetime]:
        """Вычисляет время следующего запуска"""
        now = datetime.now()
        
        if self.mode == "interval":
            if self.last_execution:
                return self.last_execution + timedelta(minutes=self.interval_minutes)
            else:
                return now + timedelta(minutes=self.interval_minutes)
        
        elif self.mode == "cron":
            # Ищем следующее время, соответствующее cron-выражению
            # Начинаем со следующей минуты
            next_time = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
            
            # Ищем ближайшее время, подходящее под cron
            max_iterations = 365 * 24 * 60  # Максимум на год вперед
            for _ in range(max_iterations):
                if self._cron_matches_time(next_time):
                    return next_time
                next_time += timedelta(minutes=1)
            
            logger.error("Не удалось найти следующее время выполнения по cron")
            return None
        
        elif self.mode == "time_list":
            if not self.time_list:
                return None
            
            # Преобразуем строки времени в объекты time
            times_today = []
            for time_str in self.time_list:
                try:
                    hour, minute = map(int, time_str.split(':'))
                    times_today.append(datetime.combine(now.date(), datetime.min.time()).replace(hour=hour, minute=minute))
                except (ValueError, AttributeError):
                    logger.error(f"Некорректный формат времени: {time_str}")
            
            if not times_today:
                return None
            
            # Ищем ближайшее время сегодня
            times_today.sort()
            for t in times_today:
                if t > now:
                    return t
            
            # Если все времена сегодня прошли, берем первое время завтра
            tomorrow = now.date() + timedelta(days=1)
            first_time = datetime.combine(tomorrow, datetime.min.time()).replace(
                hour=times_today[0].hour,
                minute=times_today[0].minute
            )
            return first_time
        
        return None
    
    def start(self):
        """Запуск планировщика"""
        if self.is_running:
            logger.warning("Планировщик уже запущен")
            return
        
        self.is_running = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        
        logger.info("Планировщик запущен")
        self._update_next_run_time()
    
    def stop(self):
        """Остановка планировщика"""
        if not self.is_running:
            logger.warning("Планировщик уже остановлен")
            return
        
        self.is_running = False
        self.stop_event.set()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        logger.info("Планировщик остановлен")
    
    def set_schedule(self, schedule_config: Union[str, List[str], int]):
        """Изменение расписания"""
        was_running = self.is_running
        
        if was_running:
            self.stop()
        
        self._parse_schedule_config(schedule_config)
        
        # Обновляем конфиг
        self.schedule_config = schedule_config
        logger.info(f"Расписание изменено: {schedule_config}")
        
        if was_running:
            self.start()
    
    def _run(self):
        """Основной цикл планировщика"""
        logger.info(f"Планировщик начал работу в режиме '{self.mode}'")
        
        while self.is_running and not self.stop_event.is_set():
            try:
                # Вычисляем время до следующего запуска
                wait_seconds = self._calculate_wait_time()
                
                if wait_seconds > 0:
                    # Ждем до следующего запуска с проверкой остановки
                    logger.info(f"До следующего запуска: {wait_seconds} секунд")
                    for _ in range(wait_seconds):
                        if self.stop_event.is_set():
                            return
                        time.sleep(1)
                
                # Выполняем захват
                self._execute_capture()
                
                # Обновляем время следующего запуска
                self._update_next_run_time()
                
            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")
                time.sleep(60)
    
    def _calculate_wait_time(self) -> int:
        """Вычисление времени до следующего запуска"""
        if self.next_run is None:
            self._update_next_run_time()
        
        if self.next_run is None:
            logger.warning("Не удалось определить время следующего запуска")
            return 300  # Ждем 5 минут и пробуем снова
        
        wait_seconds = max(0, int((self.next_run - datetime.now()).total_seconds()))
        return wait_seconds
    
    def _update_next_run_time(self):
        """Обновление времени следующего запуска"""
        self.next_run = self._calculate_next_run_time()
        if self.next_run:
            logger.info(f"Следующий запуск: {self.next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def _execute_capture(self):
        """Выполнение захвата изображений и отправка в чат"""
        logger.info("Планировщик: запуск автоматического захвата")
        
        try:
            # Отправляем сообщение о начале
            start_message = self.bot.send_message(
                chat_id=self.chat_id,
                text=f"<b>⏰ Автоматический захват запущен</b>\n"
                     f"Время: {datetime.now().strftime('%H:%M:%S')}",
                parse_mode='HTML'
            )
            
            # Выполняем захват со всех камер
            results = self.camera_manager.capture_all()
            
            # Подсчитываем результаты и собираем успешные файлы
            successful = []
            failed = []
            media_group = []
            
            for i, result in enumerate(results):
                if not result['error'] and os.path.exists(result.get('file_path', '')):
                    successful.append(result)
                    # Добавляем в медиа-группу
                    with open(result['file_path'], 'rb') as photo:
                        # Для python-telegram-bot используем InputMediaPhoto
                        media_group.append(
                            InputMediaPhoto(
                                media=photo,
                                caption=result.get('camera_name', f'Камера {i+1}') if i == 0 else None
                            )
                        )
                else:
                    failed.append(result)
            
            # Отправляем скриншоты одним сообщением (альбомом)
            if media_group:
                try:
                    # Разбиваем на части по 10 фото (ограничение Telegram)
                    for i in range(0, len(media_group), 10):
                        self.bot.send_media_group(
                            chat_id=self.chat_id,
                            media=media_group[i:i+10]
                        )
                    logger.info(f"Отправлен альбом из {len(media_group)} изображений")
                except Exception as e:
                    logger.error(f"Ошибка при отправке альбома: {e}")
                    # Если не удалось отправить альбом, отправляем по одному
                    for result in successful:
                        try:
                            with open(result['file_path'], 'rb') as photo:
                                self.bot.send_photo(
                                    chat_id=self.chat_id,
                                    photo=photo,
                                    caption=result.get('camera_name', ''),
                                    parse_mode='HTML'
                                )
                            time.sleep(0.5)  # Небольшая задержка между отправками
                        except Exception as single_err:
                            logger.error(f"Ошибка при отправке одного фото: {single_err}")
            
            # Отправляем итоговое сообщение
            result_text = f"<b>📊 Автозахват завершен</b>\n\n"
            
            if successful:
                result_text += f"✅ Успешно: {len(successful)} камер\n"
            if failed:
                result_text += f"❌ Ошибки: {len(failed)} камер\n"
                # Добавляем информацию об ошибках
                for i, fail in enumerate(failed[:5]):
                    result_text += f"   • {fail.get('camera_name', f'Камера {i+1}')}: {fail.get('error', 'Неизвестная ошибка')}\n"
                if len(failed) > 5:
                    result_text += f"   ... и еще {len(failed) - 5} ошибок\n"
            
            result_text += f"\n⏱️ Время: {datetime.now().strftime('%H:%M:%S')}\n"
            
            # Добавляем информацию о следующем запуске
            if self.next_run:
                next_run_str = self.next_run.strftime('%Y-%m-%d %H:%M:%S')
                result_text += f"📅 Следующий запуск: {next_run_str}"
            else:
                result_text += f"📅 Следующий запуск: не определено"
            
            self.bot.send_message(
                chat_id=self.chat_id,
                text=result_text,
                parse_mode='HTML',
                reply_to_message_id=start_message.message_id
            )
            
            # Обновляем статистику
            self.execution_count += 1
            self.last_execution = datetime.now()
            
            logger.info(f"Планировщик: захват завершен ({len(successful)} успешно, {len(failed)} ошибок)")
            
        except Exception as e:
            logger.error(f"Ошибка при автоматическом захвате: {e}")
            self.bot.send_message(
                chat_id=self.chat_id,
                text=f"❌ <b>Ошибка при автоматическом захвате:</b>\n{str(e)[:100]}",
                parse_mode='HTML'
            )
    
    def force_execute(self):
        """Принудительный запуск захвата"""
        if self.is_running:
            self._execute_capture()
        else:
            logger.warning("Планировщик не запущен, принудительный запуск невозможен")
    
    def get_schedule_info(self) -> str:
        """Возвращает информацию о текущем расписании"""
        if self.mode == "interval":
            return f"Интервальный режим: каждые {self.interval_minutes} минут"
        elif self.mode == "cron":
            return f"Cron-режим: {self.cron_expression}"
        elif self.mode == "time_list":
            return f"Режим списка времени: {', '.join(self.time_list)}"
        else:
            return "Режим не определен"
    
    def get_next_run_info(self) -> str:
        """Возвращает информацию о следующем запуске"""
        if self.next_run:
            return self.next_run.strftime('%Y-%m-%d %H:%M:%S')
        return "Не определено"


