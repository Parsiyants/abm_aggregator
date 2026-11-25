# services/telegram_notifier.py
import os
from aiogram import Bot
from repositories.telegram_repo import TelegramSubscriberRepository

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8864470107:AAFlsEXiMTOafvnij4yusZ60FvpebrKsf3g")
repo = TelegramSubscriberRepository()

# Создаём бота только если есть токен
bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None


async def send_notification_to_all(order_data: dict) -> dict:
    """
    Отправляет уведомление о новом заказе всем подписчикам
    """
    if not bot:
        print("Telegram bot not configured, skipping notification")
        return {"total": 0, "success": 0, "failed": 0, "error": "bot not configured"}
    
    subscribers = await repo.get_all_active_subscribers()
    
    if not subscribers:
        print("Нет активных подписчиков")
        return {"total": 0, "success": 0, "failed": 0}
    
    # Форматируем сообщение
    message = (
        f"🆕 <b>Новый заказ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <code>{order_data.get('order_id')}</code>\n"
        f"🏪 {order_data.get('cabinet_name')}\n"
        f"💰 Сумма: {order_data.get('price')} ₽\n"
        f"📦 Товаров: {order_data.get('order_count')}\n"
        f"🕒 Создан: {order_data.get('order_date')}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📋 Для обработки перейдите в систему"
    )
    
    success_count = 0
    failed_count = 0
    
    for chat_id in subscribers:
        try:
            await bot.send_message(chat_id, message, parse_mode="HTML")
            success_count += 1
        except Exception as e:
            print(f"Ошибка отправки chat_id {chat_id}: {e}")
            failed_count += 1
    
    return {
        "total": len(subscribers),
        "success": success_count,
        "failed": failed_count
    }


async def send_test_notification(chat_id: int = None) -> bool:
    """Отправляет тестовое уведомление"""
    if not bot:
        print("Telegram bot not configured")
        return False
    
    if chat_id:
        subscribers = [chat_id]
    else:
        subscribers = await repo.get_all_active_subscribers()
    
    if not subscribers:
        print("Нет подписчиков для тестового уведомления")
        return False
    
    message = "🔔 <b>Тестовое уведомление</b>\nЕсли вы видите это сообщение, бот работает корректно!"
    
    for chat_id in subscribers:
        try:
            await bot.send_message(chat_id, message, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка: {e}")
            return False
    
    return True