# get_chat_id.py
import os
from dotenv import load_dotenv
from telegram.ext import Updater

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

def main():
    updater = Updater(TOKEN, use_context=True)
    
    # Получаем информацию о боте
    bot = updater.bot
    print(f"🤖 Бот: {bot.first_name} (@{bot.username})")
    
    # Получаем обновления
    updates = bot.get_updates()
    
    if updates:
        print("\n📋 Последние чаты:")
        for update in updates[-5:]:  # Последние 5 обновлений
            if update.message:
                chat = update.message.chat
                print(f"  👤 {chat.first_name} {chat.last_name or ''} (ID: {chat.id})")
                print(f"     Тип: {chat.type}, Юзернейм: @{chat.username or 'нет'}")
                print()
    else:
        print("❌ Нет обновлений. Отправьте боту любое сообщение и попробуйте снова.")

if __name__ == '__main__':
    main()