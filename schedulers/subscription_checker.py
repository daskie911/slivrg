from datetime import datetime
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger
from database import db
from subscription_service import SubscriptionService
from config import config

class SubscriptionChecker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.service = SubscriptionService(bot)

    async def check_expired_subscriptions(self):
        """Кикать пользователей с истёкшей подпиской (> 48 часов)"""
        logger.info("🔍 Checking expired subscriptions...")
        
        expired = await db.get_expired_subscriptions(hours_ago=config.KICK_AFTER_EXPIRE_HOURS)
        
        for sub in expired:
            user_id = sub['user_id']
            
            if await self.service.is_user_in_channel(user_id):
                logger.warning(f"⚠️ Kicking expired user {user_id}")
                await self.service.kick_user(user_id)
                
                try:
                    await self.bot.send_message(
                        user_id,
                        "⏰ <b>Ваша подписка истекла</b>\n\n"
                        "Вы были удалены из канала.\n\n"
                        "Чтобы продолжить доступ, продлите подписку: /subscribe",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {user_id}: {e}")
            
            await db.delete_subscription(user_id)

    async def send_renewal_reminders(self):
        """Отправка напоминаний о продлении (за 3 дня)"""
        logger.info("🔔 Checking subscriptions expiring soon...")
        
        expiring = await db.get_expiring_soon(days=config.REMINDER_DAYS_BEFORE)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Продлить подписку", callback_data="renew_subscription")]
        ])
        
        for sub in expiring:
            user_id = sub['user_id']
            sub_until = datetime.fromisoformat(sub['subscription_until'])
            days_left = (sub_until - datetime.utcnow()).days
            
            try:
                await self.bot.send_message(
                    user_id,
                    f"⏰ <b>Подписка скоро истечёт!</b>\n\n"
                    f"📅 Осталось дней: <b>{days_left}</b>\n\n"
                    f"Не забудьте продлить доступ к каналу.",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                logger.info(f"🔔 Reminder sent to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send reminder to {user_id}: {e}")

    async def run_all_checks(self):
        """Запуск всех проверок"""
        await self.check_expired_subscriptions()
        await self.send_renewal_reminders()