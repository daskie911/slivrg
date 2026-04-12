from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger
from config import config
from subscription_service import SubscriptionService

router = Router()

@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    """Команда покупки подписки"""
    from database import db
    from datetime import datetime
    
    # Проверяем, есть ли уже активная подписка
    subscription = await db.get_subscription(message.from_user.id)
    
    if subscription:
        sub_until = datetime.fromisoformat(subscription['subscription_until'])
        if sub_until > datetime.utcnow():
            days_left = (sub_until - datetime.utcnow()).days
            await message.answer(
                f"✅ У вас уже есть активная подписка!\n\n"
                f"📅 Осталось дней: <b>{days_left}</b>",
                parse_mode="HTML"
            )
            return
    
    # Красивое сообщение с кнопкой оплаты
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐ Оплатить {config.STARS_PRICE} Stars", pay=True)]
    ])
    
    await message.answer_invoice(
        title="Подписка на канал",
        description=f"Доступ к приватному каналу на {config.SUBSCRIPTION_DAYS} дней",
        payload=f"subscription_{message.from_user.id}",
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice(label="Подписка", amount=config.STARS_PRICE)],
        reply_markup=keyboard
    )

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """Подтверждение платежа перед оплатой"""
    logger.info(f"💳 Pre-checkout from user {pre_checkout_query.from_user.id}")
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, bot: Bot):
    """Обработка успешного платежа"""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    logger.success(f"💰 Payment successful from user {user_id}")
    
    # Создаём подписку и invite-ссылку
    service = SubscriptionService(bot)
    
    try:
        invite_link = await service.process_successful_payment(user_id, username)
        
        await message.answer(
            f"✅ <b>Оплата прошла успешно!</b>\n\n"
            f"🔗 Ваша персональная ссылка для входа в канал:\n"
            f"<code>{invite_link}</code>\n\n"
            f"⚠️ <b>Важно:</b>\n"
            f"• Ссылка действительна 30 минут\n"
            f"• Ссылка одноразовая (только для вас)\n"
            f"• После входа ссылка автоматически удалится\n\n"
            f"📅 Подписка активна на {config.SUBSCRIPTION_DAYS} дней",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"❌ Error processing payment: {e}")
        await message.answer(
            "❌ Произошла ошибка при создании ссылки.\n"
            "Обратитесь к администратору.",
            parse_mode="HTML"
        )