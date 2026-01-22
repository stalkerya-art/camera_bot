# main.py
import logging
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from telegram import BotCommand
from config import load_config
from camera_manager import CameraManager
from bot_handlers import BotHandlers
from scheduler import CameraScheduler

logger = None  # Глобальная переменная для логгера

def setup_scheduler(config, camera_manager, bot):
    """Настройка планировщика с проверками"""
    global logger
    
    if not config['schedule']['enabled']:
        logger.info("Планировщик отключен в настройках")
        return None
    
    if not config['admin_chat_id']:
        logger.warning("ADMIN_CHAT_ID не указан, планировщик отключен")
        return None
    
    try:
        admin_chat_id = int(config['admin_chat_id'])
    except (ValueError, TypeError):
        logger.error(f"Неверный формат ADMIN_CHAT_ID: {config['admin_chat_id']}")
        return None
    
    # Создаем планировщик
    scheduler = CameraScheduler(
        camera_manager=camera_manager,
        bot=bot,
        chat_id=admin_chat_id,
        interval_minutes=config['schedule']['interval_minutes']
    )
    
    return scheduler

def setup_bot_commands(updater, scheduler, disabled_commands):
    """Установка меню команд бота с учетом отключенных"""
    global logger
    
    try:
        # Основные команды
        all_commands = [
            BotCommand("start", "Начало работы"),
            BotCommand("help", "Справка по боту"),
            BotCommand("cameras", "Список камер"),
            BotCommand("capture", "Сделать снимок"),
            BotCommand("stats", "Статистика работы"),
            BotCommand("chat_id", "Получить ID чата"),
        ]
        
        # Добавляем команды планировщика если он есть
        if scheduler and "schedule" not in disabled_commands:
            all_commands.extend([
                BotCommand("schedule_start", "Запустить автосбор"),
                BotCommand("schedule_stop", "Остановить автосбор"),
                BotCommand("schedule_status", "Статус расписания"),
                BotCommand("schedule_set", "Установить интервал"),
            ])
        
        # Фильтруем отключенные команды
        enabled_commands = [
            cmd for cmd in all_commands 
            if cmd.command not in disabled_commands
        ]
        
        # Устанавливаем команды бота
        updater.bot.set_my_commands(enabled_commands)
        logger.info(f"Меню команд бота установлено ({len(enabled_commands)} из {len(all_commands)})")
        
    except Exception as e:
        logger.error(f"Ошибка при установке команд меню: {e}")

def register_handlers(dp, bot_handlers, scheduler, disabled_commands):
    """Регистрация обработчиков команд с учетом отключенных"""
    global logger
    
    handlers = []
    
    # Основные команды
    if "start" not in disabled_commands:
        handlers.append(CommandHandler("start", bot_handlers.start))
    if "help" not in disabled_commands:
        handlers.append(CommandHandler("help", bot_handlers.help_command))
    if "chat_id" not in disabled_commands:
        handlers.append(CommandHandler("chat_id", bot_handlers.get_chat_id))
    if "cameras" not in disabled_commands:
        handlers.append(CommandHandler("cameras", bot_handlers.list_cameras))
    if "capture" not in disabled_commands:
        handlers.append(CommandHandler("capture", bot_handlers.capture_menu))
    if "stats" not in disabled_commands:
        handlers.append(CommandHandler("stats", bot_handlers.stats_command))
    
    # Команды расписания (только если есть планировщик и команды не отключены)
    if scheduler and "schedule" not in disabled_commands:
        if "schedule_start" not in disabled_commands:
            handlers.append(CommandHandler("schedule_start", bot_handlers.schedule_start))
        if "schedule_stop" not in disabled_commands:
            handlers.append(CommandHandler("schedule_stop", bot_handlers.schedule_stop))
        if "schedule_status" not in disabled_commands:
            handlers.append(CommandHandler("schedule_status", bot_handlers.schedule_status))
        if "schedule_set" not in disabled_commands:
            handlers.append(CommandHandler("schedule_set", bot_handlers.schedule_set))
    
    # Всегда добавляем обработчик для пароля (если не отключен start)
    if "start" not in disabled_commands:
        handlers.append(MessageHandler(Filters.text & ~Filters.command, bot_handlers.handle_password))
    
    # Всегда добавляем обработчик callback-кнопок (если не отключен capture)
    if "capture" not in disabled_commands:
        handlers.append(CallbackQueryHandler(bot_handlers.handle_capture, pattern='^capture_'))
    
    # Обработчик ошибок (всегда)
    dp.add_error_handler(bot_handlers.error_handler)
    
    # Регистрируем все обработчики
    for handler in handlers:
        dp.add_handler(handler)
    
    logger.info(f"Зарегистрировано {len(handlers)} обработчиков команд")

def main():
    """Точка входа"""
    global logger
    
    # Загрузка конфигурации
    config = load_config()
    
    if not config['token']:
        print("❌ ОШИБКА: Токен бота не указан!")
        return
    
    # Настройка логирования
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=config['log_level']
    )
    logger = logging.getLogger(__name__)
    
    # Логируем отключенные команды после настройки логирования
    if config.get('disabled_commands'):
        logger.info(f"Отключенные команды: {config['disabled_commands']}")
    
    # Инициализация менеджера камер
    camera_manager = CameraManager(config)
    
    # Инициализация бота
    updater = Updater(config['token'], use_context=True)
    dp = updater.dispatcher
    
    # Инициализация планировщика
    scheduler = None
    if not config.get('disabled_commands') or "schedule" not in config['disabled_commands']:
        scheduler = setup_scheduler(config, camera_manager, updater.bot)
    
    # Инициализация обработчиков бота
    bot_handlers = BotHandlers(camera_manager, config, scheduler)
    
    # Регистрация обработчиков с учетом отключенных команд
    disabled_commands = config.get('disabled_commands', [])
    register_handlers(dp, bot_handlers, scheduler, disabled_commands)
    
    # Запуск бота
    logger.info("🤖 Бот запускается...")
    print("=" * 60)
    print("🤖 IP Camera Bot с настройкой команд")
    print("=" * 60)
    print(f"Камер настроено: {len(camera_manager.cameras)}")
    
    if config['bot_password']:
        print(f"🔒 Авторизация: ВКЛЮЧЕНА (пароль: {config['bot_password']})")
    else:
        print("🔓 Авторизация: ОТКЛЮЧЕНА (доступ для всех)")
    
    # Устанавливаем меню команд
    setup_bot_commands(updater, scheduler, disabled_commands)
    
    # Показываем статус отключенных команд
    if disabled_commands:
        print(f"🚫 Отключенные команды: {', '.join(disabled_commands)}")
    
    # Вывод информации о планировщике
    if scheduler and scheduler.is_running:
        print(f"Планировщик: 🟢 Активен (интервал: {scheduler.interval_minutes} мин)")
    elif scheduler:
        print("Планировщик: 🔴 Остановлен (используйте /schedule_start)")
    elif "schedule" in disabled_commands:
        print("Планировщик: ⚫ Отключен (команда отключена в настройках)")
    else:
        print("Планировщик: ⚪ Не настроен")
    
    # Вывод доступных команд
    print("\n📋 Доступные команды:")
    available_commands = ["start", "help", "chat_id", "cameras", "capture", "stats"]
    if scheduler and "schedule" not in disabled_commands:
        available_commands.extend(["schedule_start", "schedule_stop", "schedule_status", "schedule_set"])
    
    for cmd in available_commands:
        if cmd not in disabled_commands:
            print(f"  /{cmd}")
    
    print("=" * 60)
    print("ℹ️  Для отключения команд добавьте в .env:")
    print('   DISABLED_COMMANDS="capture,schedule"')
    print("=" * 60)
    
    # Запускаем polling
    updater.start_polling()
    updater.idle()
    
    # При остановке бота останавливаем планировщик
    if scheduler:
        scheduler.stop()

if __name__ == '__main__':
    main()