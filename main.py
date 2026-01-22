# main.py
import logging
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
from config import load_config
from camera_manager import CameraManager
from bot_handlers import BotHandlers
from scheduler import CameraScheduler

def setup_scheduler(config, camera_manager, bot):
    """Настройка планировщика с проверками"""
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
    
    # Проверяем, есть ли доступ к чату
    if not scheduler.chat_id:
        logger.error("Не удалось инициализировать планировщик: неверный chat_id")
        return None
    
    # Запускаем автоматически, если включено в настройках
    if config['schedule']['enabled']:
        try:
            scheduler.start()
        except Exception as e:
            logger.error(f"Ошибка при запуске планировщика: {e}")
            logger.info("Планировщик будет работать в ручном режиме")
    
    return scheduler

def main():
    """Точка входа"""
    # Загрузка конфигурации
    config = load_config()
    
    if not config['token']:
        print("❌ ОШИБКА: Токен бота не указан!")
        print("\n1. Получите токен у @BotFather")
        print("2. Создайте файл .env в папке проекта")
        print("3. Добавьте строку: TELEGRAM_BOT_TOKEN=ваш_токен")
        return
    
    # Настройка логирования
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=config['log_level']
    )
    logger = logging.getLogger(__name__)
    
    # Инициализация менеджера камер
    camera_manager = CameraManager(config)
    
    # Инициализация бота
    updater = Updater(config['token'], use_context=True)
    dp = updater.dispatcher
    
    # Инициализация планировщика
    scheduler = setup_scheduler(config, camera_manager, updater.bot)
    
    # Инициализация обработчиков бота
    bot_handlers = BotHandlers(camera_manager, config, scheduler)
    
    # Регистрация обработчиков команд
    dp.add_handler(CommandHandler("start", bot_handlers.start))
    dp.add_handler(CommandHandler("help", bot_handlers.help_command))
    dp.add_handler(CommandHandler("chat_id", bot_handlers.get_chat_id))  # ← ДОБАВЬТЕ ЭТУ СТРОЧКУ!
    dp.add_handler(CommandHandler("cameras", bot_handlers.list_cameras))
    dp.add_handler(CommandHandler("capture", bot_handlers.capture_menu))
    dp.add_handler(CommandHandler("stats", bot_handlers.stats_command))
    
    # Обработчики расписания
    if scheduler:
        dp.add_handler(CommandHandler("schedule_start", bot_handlers.schedule_start))
        dp.add_handler(CommandHandler("schedule_stop", bot_handlers.schedule_stop))
        dp.add_handler(CommandHandler("schedule_status", bot_handlers.schedule_status))
        dp.add_handler(CommandHandler("schedule_set", bot_handlers.schedule_set))
    
    # Обработчик callback-кнопок
    dp.add_handler(CallbackQueryHandler(bot_handlers.handle_capture, pattern='^capture_'))
    
    # Обработчик ошибок
    dp.add_error_handler(bot_handlers.error_handler)
    
    # Запуск бота
    logger.info("🤖 Бот запускается...")
    print("=" * 60)
    print("🤖 IP Camera Bot с расписанием")
    print("=" * 60)
    print(f"Камер настроено: {len(camera_manager.cameras)}")
    
    # Вывод информации о планировщике
    if scheduler and scheduler.is_running:
        print(f"Планировщик: 🟢 Активен (интервал: {scheduler.interval_minutes} мин)")
        print(f"             Чат ID: {scheduler.chat_id}")
    elif scheduler:
        print("Планировщик: 🔴 Остановлен (используйте /schedule_start)")
    else:
        print("Планировщик: ⚪ Отключен")
    
    print("\n📋 Основные команды:")
    print("  /start - Запустить бота")
    print("  /help - Справка")
    print("  /chat_id - Получить ID чата")
    print("  /cameras - Список камер")
    print("  /capture - Сделать снимок")
    print("  /stats - Статистика")
    
    if scheduler:
        print("\n⏰ Команды расписания:")
        print("  /schedule_start - Запустить автосбор")
        print("  /schedule_stop - Остановить автосбор")
        print("  /schedule_status - Статус расписания")
        print("  /schedule_set <минуты> - Изменить интервал")
    
    print("=" * 60)
    
    # Запускаем polling
    updater.start_polling()
    updater.idle()
    
    # При остановке бота останавливаем планировщик
    if scheduler:
        scheduler.stop()

if __name__ == '__main__':
    main()