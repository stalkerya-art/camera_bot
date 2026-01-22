# bot_handlers.py
import logging
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from utils import escape_html, format_timestamp, humanize_size

logger = logging.getLogger(__name__)

class BotHandlers:
    """Класс с обработчиками команд бота"""
    
    def __init__(self, camera_manager, config, scheduler=None):
        self.camera_manager = camera_manager
        self.scheduler = scheduler
        self.bot_password = config.get('bot_password')
        self.authorized_users = set()  # Для хранения авторизованных пользователей
        
        # Если пароль не установлен, добавляем всех пользователей
        if not self.bot_password:
            logger.warning("Пароль бота не установлен! Доступ открыт для всех.")
            self.authorized_users.add('all')  # Специальный маркер для всех
    
    def is_authorized(self, user_id):
        """Проверка авторизации пользователя"""
        if not self.bot_password:
            return True  # Если пароль не установлен, все авторизованы
        
        # Проверяем, есть ли пользователь в списке авторизованных
        return user_id in self.authorized_users
    
    def check_auth_and_reply(self, update: Update):
        """Проверка авторизации и отправка сообщения, если не авторизован"""
        if update.message:
            user = update.message.from_user
        elif update.callback_query:
            user = update.callback_query.from_user
        else:
            return False
            
        if not self.is_authorized(user.id):
            if update.message:
                update.message.reply_text(
                    "🔒 <b>Требуется авторизация</b>\n\n"
                    "Для доступа к боту введите пароль:\n"
                    "<code>/start ПАРОЛЬ</code>",
                    parse_mode='HTML'
                )
            elif update.callback_query:
                update.callback_query.answer(
                    "❌ Не авторизован. Введите /start для авторизации",
                    show_alert=True
                )
            return False
        return True
    
    def start(self, update: Update, context: CallbackContext):
        """Команда /start с поддержкой пароля"""
        user = update.message.from_user
        user_id = user.id
        
        # Если пользователь уже авторизован
        if self.is_authorized(user_id):
            self._send_welcome(update, user)
            return
        
        # Проверяем, передан ли пароль с командой
        if context.args and len(context.args) > 0:
            password_attempt = context.args[0]
            
            if password_attempt == self.bot_password:
                # Авторизуем пользователя
                self.authorized_users.add(user_id)
                logger.info(f"Пользователь {user_id} ({user.username}) авторизован")
                
                update.message.reply_text(
                    "✅ <b>Авторизация успешна!</b>\n\n"
                    f"Добро пожаловать, {escape_html(user.first_name)}!",
                    parse_mode='HTML'
                )
                
                # Показываем приветствие
                self._send_welcome(update, user)
                return
            else:
                update.message.reply_text(
                    "❌ <b>Неверный пароль</b>\n\n"
                    "Попробуйте еще раз:\n"
                    "<code>/start ПАРОЛЬ</code>",
                    parse_mode='HTML'
                )
                return
        
        # Если пароль не передан, просим его ввести
        update.message.reply_text(
            "🔒 <b>Требуется авторизация</b>\n\n"
            "Введите пароль для доступа к боту:\n"
            "<code>/start ПАРОЛЬ</code>\n\n"
            "Или просто отправьте пароль сообщением",
            parse_mode='HTML'
        )
    
    def handle_password(self, update: Update, context: CallbackContext):
        """Обработчик ввода пароля в отдельном сообщении"""
        user = update.message.from_user
        user_id = user.id
        
        # Если пользователь уже авторизован, игнорируем
        if self.is_authorized(user_id):
            return
        
        # Проверяем пароль
        password_attempt = update.message.text
        
        if password_attempt == self.bot_password:
            # Авторизуем пользователя
            self.authorized_users.add(user_id)
            logger.info(f"Пользователь {user_id} ({user.username}) авторизован")
            
            update.message.reply_text(
                "✅ <b>Авторизация успешна!</b>\n\n"
                f"Добро пожаловать, {escape_html(user.first_name)}!",
                parse_mode='HTML'
            )
            
            # Показываем приветствие
            self._send_welcome(update, user)
        else:
            update.message.reply_text(
                "❌ <b>Неверный пароль</b>\n\n"
                "Попробуйте еще раз",
                parse_mode='HTML'
            )
    
    def _send_welcome(self, update: Update, user):
        """Отправка приветственного сообщения"""
        welcome_text = f"""
<b>👋 Привет, {escape_html(user.first_name)}!</b>

🤖 <b>IP Camera Bot</b>
Бот для захвата изображений с IP-камер

📋 <b>Доступные команды:</b>
/start - Начало работы
/help - Справка
/cameras - Список камер
/capture - Сделать снимок
/stats - Статистика
/chat_id - Получить ID чата
"""
        if self.scheduler:
            welcome_text += """
/schedule_start - Запустить автосбор
/schedule_stop - Остановить автосбор
/schedule_status - Статус расписания
/schedule_set - Установить интервал
"""

        welcome_text += f"""
🖼️ <b>Настроено камер:</b> {len(self.camera_manager.cameras)}
🕒 <b>Время сервера:</b> {format_timestamp()}
"""
        update.message.reply_text(welcome_text, parse_mode='HTML')
    
    def help_command(self, update: Update, context: CallbackContext):
        """Команда /help"""
        if not self.check_auth_and_reply(update):
            return
            
        help_text = """
<b>📚 Справка по боту</b>

<b>Основные команды:</b>
/start - Запустить бота
/help - Показать эту справку
/cameras - Список настроенных камер
/capture - Выбрать камеру для снимка
/stats - Статистика работы
/chat_id - Получить ID текущего чата
"""
        if self.scheduler:
            help_text += """
<b>Расписание автосбора:</b>
/schedule_start - Запустить автосбор
/schedule_stop - Остановить автосбор
/schedule_status - Статус расписания
/schedule_set 60 - Установить интервал (в минутах)
"""

        help_text += """
<b>Поддерживаемые типы камер:</b>
• HTTP/HTTPS (JPEG snapshot)
• ISAPI (Hikvision, Dahua)
"""
        update.message.reply_text(help_text, parse_mode='HTML')
    
    def get_chat_id(self, update: Update, context: CallbackContext):
        """Команда для получения chat_id текущего чата"""
        if not self.check_auth_and_reply(update):
            return
            
        chat = update.message.chat
        chat_info = f"""
<b>📋 Информация о чате:</b>

👤 <b>Имя:</b> {escape_html(chat.first_name or chat.title)}
🆔 <b>ID:</b> <code>{chat.id}</code>
📁 <b>Тип:</b> {chat.type}
🔗 <b>Username:</b> @{chat.username or 'нет'}

💡 <b>Для настройки расписания:</b>
Добавьте в файл .env:
<code>ADMIN_CHAT_ID={chat.id}</code>
"""
        update.message.reply_text(chat_info, parse_mode='HTML')
    
    def list_cameras(self, update: Update, context: CallbackContext):
        """Команда /cameras - список камер"""
        if not self.check_auth_and_reply(update):
            return
            
        cameras = self.camera_manager.cameras
        
        if not cameras:
            update.message.reply_text(
                "<b>❌ Камеры не настроены</b>\n\n"
                "Добавьте камеры в файл .env\n"
                "Пример:\n"
                "<code>CAMERA_1_NAME=Входная дверь\n"
                "CAMERA_1_TYPE=http\n"
                "CAMERA_1_URL=http://192.168.1.100/snapshot.jpg</code>",
                parse_mode='HTML'
            )
            return
        
        camera_list = "<b>📹 Настроенные камеры:</b>\n\n"
        for cam_id, camera in cameras.items():
            status = "🟢" if camera['url'] else "🔴"
            camera_list += f"{status} <b>Камера {cam_id}:</b> {escape_html(camera['name'])}\n"
            camera_list += f"   Тип: {camera['type'].upper()}\n"
            if camera['url']:
                camera_list += f"   URL: <code>{escape_html(camera['url'][:50])}...</code>\n\n"
            else:
                camera_list += f"   URL: ❌ не указан\n\n"
        
        update.message.reply_text(camera_list, parse_mode='HTML')
    
    def capture_menu(self, update: Update, context: CallbackContext):
        """Меню выбора камеры для захвата"""
        if not self.check_auth_and_reply(update):
            return
            
        cameras = self.camera_manager.cameras
        
        if not cameras:
            update.message.reply_text("❌ Нет настроенных камер", parse_mode='HTML')
            return
        
        keyboard = []
        row = []
        
        for i, (cam_id, camera) in enumerate(cameras.items()):
            button = InlineKeyboardButton(
                f"📷 {cam_id}: {camera['name'][:10]}",
                callback_data=f'capture_{cam_id}'
            )
            row.append(button)
            
            if len(row) == 2 or i == len(cameras) - 1:
                keyboard.append(row)
                row = []
        
        if len(cameras) > 1:
            keyboard.append([
                InlineKeyboardButton("📸 Все камеры", callback_data='capture_all')
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            "<b>📸 Выберите камеру для захвата:</b>\n\n"
            "Нажмите на кнопку с номером камеры\n"
            "или 'Все камеры' для последовательного захвата",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    def handle_capture(self, update: Update, context: CallbackContext):
        """Обработчик выбора камеры"""
        if not self.check_auth_and_reply(update):
            return
            
        query = update.callback_query
        query.answer()
        
        if query.data == 'capture_all':
            self.capture_all_cameras(query, context)
        else:
            camera_id = int(query.data.split('_')[1])
            self.capture_single_camera(query, context, camera_id)
    
    def capture_single_camera(self, query, context, camera_id):
        """Захват с одной камеры"""
        camera = self.camera_manager.cameras.get(camera_id)
        
        if not camera:
            query.edit_message_text(f"❌ Камера {camera_id} не найдена", parse_mode='HTML')
            return
        
        query.edit_message_text(
            f"<b>📡 Захватываю изображение...</b>\n\n"
            f"Камера: {escape_html(camera['name'])}\n"
            f"Тип: {camera['type'].upper()}\n"
            f"Время: {format_timestamp()}",
            parse_mode='HTML'
        )
        
        result = self.camera_manager.capture_image(camera_id)
        error = result.get('error')
        image_data = result.get('image_data')
        
        if error:
            query.edit_message_text(
                f"<b>❌ Ошибка захвата</b>\n\n"
                f"Камера: {escape_html(camera['name'])}\n"
                f"Ошибка: {error}\n\n"
                f"Проверьте:\n"
                f"1. Доступность камеры\n"
                f"2. Настройки в .env\n"
                f"3. Логин и пароль",
                parse_mode='HTML'
            )
            return
        
        if image_data:
            # Сбрасываем указатель в начало файла
            image_data.seek(0)
            
            # Получаем размер изображения
            file_size = len(image_data.getvalue()) // 1024
            
            caption = (
                f"<b>📸 {escape_html(camera['name'])}</b>\n"
                f"🕒 {format_timestamp()}\n"
                f"📊 Размер: {file_size} КБ\n"
                f"✅ Успешно захвачено"
            )
            
            try:
                context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=image_data,
                    caption=caption,
                    parse_mode='HTML'
                )
                query.edit_message_text(f"✅ Изображение с камеры {camera_id} отправлено", parse_mode='HTML')
            except Exception as e:
                logger.error(f"Ошибка отправки фото: {e}")
                query.edit_message_text(f"❌ Ошибка отправки: {escape_html(str(e))}", parse_mode='HTML')
        else:
            query.edit_message_text(
                f"<b>❌ Ошибка захвата</b>\n\n"
                f"Камера: {escape_html(camera['name'])}\n"
                f"Ошибка: Изображение не получено\n\n"
                f"Проверьте настройки камеры",
                parse_mode='HTML'
            )
    
    def capture_all_cameras(self, query, context):
        """Последовательный захват со всех камер"""
        cameras = self.camera_manager.cameras
        
        if not cameras:
            query.edit_message_text("❌ Нет настроенных камер", parse_mode='HTML')
            return
        
        query.edit_message_text(
            f"<b>📡 Запуск последовательного захвата...</b>\n\n"
            f"Количество камер: {len(cameras)}\n"
            f"Время начала: {format_timestamp()}",
            parse_mode='HTML'
        )
        
        successful = 0
        failed = 0
        
        for cam_id, camera in cameras.items():
            time.sleep(1)  # Пауза между камерами
            
            result = self.camera_manager.capture_image(cam_id)
            error = result.get('error')
            image_data = result.get('image_data')
            
            if error:
                context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"❌ <b>{escape_html(camera['name'])}:</b> {error}",
                    parse_mode='HTML'
                )
                failed += 1
                continue
            
            if image_data:
                # Сбрасываем указатель в начало файла
                image_data.seek(0)
                
                caption = f"📸 {escape_html(camera['name'])} ({format_timestamp()})"
                
                try:
                    context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=image_data,
                        caption=caption,
                        parse_mode='HTML'
                    )
                    successful += 1
                except Exception as e:
                    context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=f"❌ Ошибка отправки с {escape_html(camera['name'])}: {escape_html(str(e)[:100])}",
                        parse_mode='HTML'
                    )
                    failed += 1
            else:
                context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"❌ <b>{escape_html(camera['name'])}:</b> Изображение не получено",
                    parse_mode='HTML'
                )
                failed += 1
        
        query.edit_message_text(
            f"<b>📊 Завершено!</b>\n\n"
            f"✅ Успешно: {successful} камер\n"
            f"❌ Ошибки: {failed} камер\n"
            f"⏱️ Время: {format_timestamp()}\n\n"
            f"Используйте /capture для повторного захвата",
            parse_mode='HTML'
        )
    
    def stats_command(self, update: Update, context: CallbackContext):
        """Команда /stats - статистика"""
        if not self.check_auth_and_reply(update):
            return
            
        stats = self.camera_manager.get_stats()
        storage_info = self.camera_manager.get_storage_info()
        
        stats_text = f"""
<b>📊 Статистика бота</b>

<b>🤖 Информация о боте:</b>
• Запущен: {format_timestamp()}
• Камер настроено: {len(self.camera_manager.cameras)}

<b>📈 Статистика захвата:</b>
• Всего попыток: {stats['total_captures']}
• Успешно: {stats['successful_captures']}
• Ошибок: {stats['failed_captures']}
• Последний захват: {format_timestamp(stats['last_capture_time']) if stats['last_capture_time'] else 'никогда'}

<b>💾 Хранилище:</b>
• Файлов скриншотов: {storage_info['file_count']}
• Общий размер: {humanize_size(storage_info['total_size'])}
• Путь: <code>{self.camera_manager.screenshots_dir.absolute()}</code>
"""
        
        if self.scheduler:
            schedule_status = "🟢 Активно" if self.scheduler.is_running else "🔴 Остановлено"
            stats_text += f"\n<b>⏰ Расписание:</b>\n• Статус: {schedule_status}"
            if self.scheduler.is_running:
                stats_text += f"\n• Интервал: {self.scheduler.interval_minutes} минут"
                if self.scheduler.next_run:
                    stats_text += f"\n• Следующий запуск: {format_timestamp(self.scheduler.next_run)}"
        
        update.message.reply_text(stats_text, parse_mode='HTML')
    
    def schedule_start(self, update: Update, context: CallbackContext):
        """Запуск расписания"""
        if not self.check_auth_and_reply(update):
            return
            
        if not self.scheduler:
            update.message.reply_text("❌ Планировщик не инициализирован", parse_mode='HTML')
            return
        
        self.scheduler.start()
        update.message.reply_text(
            "✅ <b>Расписание запущено!</b>\n\n"
            f"Интервал: {self.scheduler.interval_minutes} минут\n"
            f"Следующий запуск: через {self.scheduler.interval_minutes} минут",
            parse_mode='HTML'
        )
    
    def schedule_stop(self, update: Update, context: CallbackContext):
        """Остановка расписания"""
        if not self.check_auth_and_reply(update):
            return
            
        if not self.scheduler:
            update.message.reply_text("❌ Планировщик не инициализирован", parse_mode='HTML')
            return
        
        self.scheduler.stop()
        update.message.reply_text("✅ Расписание остановлено", parse_mode='HTML')
    
    def schedule_status(self, update: Update, context: CallbackContext):
        """Статус расписания"""
        if not self.check_auth_and_reply(update):
            return
            
        if not self.scheduler:
            update.message.reply_text("❌ Планировщик не инициализирован", parse_mode='HTML')
            return
        
        status = "🟢 Активно" if self.scheduler.is_running else "🔴 Остановлено"
        next_run = format_timestamp(self.scheduler.next_run) if self.scheduler.next_run else "не запланировано"
        last_execution = format_timestamp(self.scheduler.last_execution) if self.scheduler.last_execution else "никогда"
        
        status_text = f"""
<b>⏰ Статус расписания:</b>

• Статус: {status}
• Интервал: {self.scheduler.interval_minutes} минут
• Следующий запуск: {next_run}
• Всего выполнено: {self.scheduler.execution_count} раз
• Последний запуск: {last_execution}
"""
        update.message.reply_text(status_text, parse_mode='HTML')
    
    def schedule_set(self, update: Update, context: CallbackContext):
        """Установка интервала расписания"""
        if not self.check_auth_and_reply(update):
            return
            
        if not self.scheduler:
            update.message.reply_text("❌ Планировщик не инициализирован", parse_mode='HTML')
            return
        
        if not context.args:
            update.message.reply_text(
                "❌ Укажите интервал в минутах\n"
                "Пример: /schedule_set 30",
                parse_mode='HTML'
            )
            return
        
        try:
            interval = int(context.args[0])
            if interval < 1:
                raise ValueError
                
            was_running = self.scheduler.is_running
            self.scheduler.set_interval(interval)
            
            if was_running:
                message = f"✅ Интервал изменен на {interval} минут\n\nРасписание продолжает работать"
            else:
                message = f"✅ Интервал изменен на {interval} минут\n\nИспользуйте /schedule_start для запуска"
            
            update.message.reply_text(message, parse_mode='HTML')
        except ValueError:
            update.message.reply_text("❌ Укажите число больше 0", parse_mode='HTML')
    
    def error_handler(self, update: Update, context: CallbackContext):
        """Обработчик ошибок"""
        logger.error(f"Ошибка: {context.error}")
        
        try:
            if update and update.message:
                update.message.reply_text(
                    "<b>❌ Произошла ошибка!</b>\n\n"
                    "Попробуйте еще раз или проверьте:\n"
                    "1. Доступность камер\n"
                    "2. Настройки в .env\n"
                    "3. Интернет-соединение",
                    parse_mode='HTML'
                )
        except:
            pass  # Игнорируем ошибки при отправке сообщения об ошибке