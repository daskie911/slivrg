from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Стартовое сообщение"""
    await message.answer(
        "👋 <b>Добро пожаловать в Subscription Bot!</b>\n\n"
        "Этот бот управляет доступом к приватному каналу.\n\n"
        "📌 <b>Команды:</b>\n"
        "/subscribe — купить подписку на 30 дней\n"
        "/status — проверить статус подписки",
        parse_mode="HTML"
    )

@router.message(Command("status"))
async def cmd_status(message: Message):
    """Проверка статуса подписки"""
    from database import db
    from datetime import datetime
    
    subscription = await db.get_subscription(message.from_user.id)
    
    if not subscription:
        await message.answer(
            "❌ У вас нет активной подписки.\n\n"
            "Используйте /subscribe для покупки.",
            parse_mode="HTML"
        )
        return
    
    sub_until = datetime.fromisoformat(subscription['subscription_until'])
    now = datetime.utcnow()
    
    if sub_until > now:
        days_left = (sub_until - now).days
        await message.answer(
            f"✅ <b>Подписка активна</b>\n\n"
            f"📅 Осталось дней: <b>{days_left}</b>\n"
            f"⏰ Истекает: <code>{sub_until.strftime('%Y-%m-%d %H:%M')}</code>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "⚠️ <b>Подписка истекла</b>\n\n"
            "Используйте /subscribe для продления.",
            parse_mode="HTML"
        )
