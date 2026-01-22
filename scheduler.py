# scheduler.py
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional
import os
from telegram import InputMediaPhoto

logger = logging.getLogger(__name__)

class CameraScheduler:
    """Планировщик для автоматического захвата изображений"""
    
    def __init__(self, camera_manager, bot, chat_id, interval_minutes=60):
        self.camera_manager = camera_manager
        self.bot = bot
        self.chat_id = chat_id
        self.interval_minutes = interval_minutes
        
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        self.execution_count = 0
        self.last_execution: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        
        logger.info(f"Планировщик инициализирован с интервалом {interval_minutes} минут")
    
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
        self._calculate_next_run()
    
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
    
    def set_interval(self, interval_minutes: int):
        """Изменение интервала"""
        was_running = self.is_running
        
        if was_running:
            self.stop()
        
        self.interval_minutes = interval_minutes
        logger.info(f"Интервал изменен на {interval_minutes} минут")
        
        if was_running:
            self.start()
    
    def _run(self):
        """Основной цикл планировщика"""
        logger.info(f"Планировщик начал работу с интервалом {self.interval_minutes} минут")
        
        while self.is_running and not self.stop_event.is_set():
            try:
                # Вычисляем время до следующего запуска
                wait_seconds = self._calculate_wait_time()
                
                if wait_seconds > 0:
                    # Ждем до следующего запуска с проверкой остановки
                    for _ in range(wait_seconds):
                        if self.stop_event.is_set():
                            return
                        time.sleep(1)
                
                # Выполняем захват
                self._execute_capture()
                
                # Пересчитываем время следующего запуска
                self._calculate_next_run()
                
            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")
                time.sleep(60)  # Ждем минуту при ошибке
    
    def _calculate_wait_time(self) -> int:
        """Вычисление времени до следующего запуска"""
        if self.last_execution is None:
            return 0  # Запускаем сразу
        
        next_run_time = self.last_execution + timedelta(minutes=self.interval_minutes)
        wait_seconds = max(0, int((next_run_time - datetime.now()).total_seconds()))
        
        return wait_seconds
    
    def _calculate_next_run(self):
        """Вычисление времени следующего запуска"""
        if self.last_execution:
            self.next_run = self.last_execution + timedelta(minutes=self.interval_minutes)
        else:
            self.next_run = datetime.now() + timedelta(minutes=self.interval_minutes)
    
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
                for i, fail in enumerate(failed[:5]):  # Показываем первые 5 ошибок
                    result_text += f"   • {fail.get('camera_name', f'Камера {i+1}')}: {fail.get('error', 'Неизвестная ошибка')}\n"
                if len(failed) > 5:
                    result_text += f"   ... и еще {len(failed) - 5} ошибок\n"
            
            result_text += f"\n⏱️ Время: {datetime.now().strftime('%H:%M:%S')}\n"
            result_text += f"📅 Следующий запуск через {self.interval_minutes} минут"
            
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