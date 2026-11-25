# telegram_bot.py
import asyncio
from dotenv import load_dotenv
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from repositories.telegram_repo import TelegramSubscriberRepository

# Загружаем .env
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN not set!")

bot = None
dp = None
repo = TelegramSubscriberRepository()

# Клавиатура для удобства
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Статус"), KeyboardButton(text="🔕 Отписаться")]
    ],
    resize_keyboard=True
)


def init_bot():
    """Инициализирует бота"""
    global bot, dp
    if not BOT_TOKEN:
        print("Telegram bot not initialized: missing token")
        return False
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Регистрируем обработчики
    register_handlers()
    
    print("🤖 Telegram bot initialized")
    return True


def register_handlers():
    """Регистрирует все обработчики команд"""
    
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        """Обработчик команды /start"""
        chat_id = message.chat.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        
        await repo.add_subscriber(chat_id, username, first_name, last_name)
        count = await repo.get_subscriber_count()
        
        await message.answer(
            f"🤖 *Добро пожаловать!*\n\n"
            f"✅ Вы подписаны на уведомления о новых заказах.\n"
            f"👥 Всего подписчиков: {count}\n\n"
            f"📦 Каждый новый заказ будет приходить сюда.\n\n"
            f"📋 *Доступные команды:*\n"
            f"/status - проверить статус\n"
            f"/unsubscribe - отписаться\n"
            f"/help - помощь",
            parse_mode="Markdown",
            reply_markup=main_keyboard
        )
        print(f"✅ New subscriber: {chat_id} (@{username})")
    
    @dp.message(Command("unsubscribe"))
    async def cmd_unsubscribe(message: types.Message):
        """Обработчик команды /unsubscribe"""
        chat_id = message.chat.id
        await repo.remove_subscriber(chat_id)
        
        await message.answer(
            "❌ Вы отписаны от уведомлений.\n\n"
            "Чтобы подписаться снова, отправьте /start",
            reply_markup=ReplyKeyboardRemove()
        )
        print(f"🔕 Unsubscribed: {chat_id}")
    
    @dp.message(Command("status"))
    async def cmd_status(message: types.Message):
        """Обработчик команды /status"""
        chat_id = message.chat.id
        is_subscribed = await repo.is_subscribed(chat_id)
        count = await repo.get_subscriber_count()
        
        if is_subscribed:
            await message.answer(
                f"✅ *Вы подписаны на уведомления!*\n"
                f"👥 Всего подписчиков: {count}",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                "❌ *Вы не подписаны на уведомления*\n"
                "Отправьте /start, чтобы подписаться",
                parse_mode="Markdown"
            )
    
    @dp.message(Command("myid"))
    async def cmd_myid(message: types.Message):
        """Обработчик команды /myid"""
        await message.answer(f"🆔 Your chat_id: `{message.chat.id}`", parse_mode="Markdown")
        print(f"🆔 ID requested: {message.chat.id}")
    
    @dp.message(Command("help"))
    async def cmd_help(message: types.Message):
        """Обработчик команды /help"""
        await message.answer(
            "📋 *Доступные команды:*\n\n"
            "/start - Подписаться на уведомления\n"
            "/status - Проверить статус подписки\n"
            "/unsubscribe - Отписаться\n"
            "/myid - Показать ваш chat_id\n"
            "/help - Помощь",
            parse_mode="Markdown"
        )
    
    # Обработка кнопок клавиатуры
    @dp.message(lambda message: message.text == "📊 Статус")
    async def handle_status_button(message: types.Message):
        await cmd_status(message)
    
    @dp.message(lambda message: message.text == "🔕 Отписаться")
    async def handle_unsubscribe_button(message: types.Message):
        await cmd_unsubscribe(message)
    
    # Отладочный обработчик (для всех сообщений, которые не подошли под команды)
    @dp.message()
    async def catch_all(message: types.Message):
        print(f"🔍 DEBUG: Unhandled message: '{message.text}' from {message.chat.id}")
        await message.answer(
            f"❓ Неизвестная команда.\n\n"
            f"Отправьте /help для списка доступных команд."
        )


async def start_bot():
    """Запускает бота (вызывается из startup_event)"""
    if not init_bot():
        return
    
    print("🚀 Telegram bot polling started...")
    
    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        print("📴 Telegram bot polling cancelled")
    except Exception as e:
        print(f"❌ Polling error: {e}")
    finally:
        await stop_bot()


async def stop_bot():
    """Останавливает бота"""
    global bot
    if bot:
        print("🛑 Closing Telegram bot session...")
        try:
            await bot.session.close()
        except Exception as e:
            print(f"Error closing session: {e}")
        print("✅ Telegram bot stopped")