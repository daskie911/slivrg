from aiogram import Router, Bot, F
from aiogram.types import ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter, KICKED, MEMBER
from loguru import logger
from subscription_service import SubscriptionService
from config import config

router = Router()

@router.chat_member(
    ChatMemberUpdatedFilter(member_status_changed=KICKED >> MEMBER)
)
async def user_joined_channel(event: ChatMemberUpdated, bot: Bot):
    """Обработка присоединения пользователя к каналу"""
    if event.chat.id != config.CHANNEL_ID:
        return
    
    user_id = event.from_user.id
    username = event.from_user.username or event.from_user.first_name
    
    logger.info(f"👤 User {user_id} ({username}) joined channel")
    
    service = SubscriptionService(bot)
    
    invite_link = event.invite_link.invite_link if event.invite_link else None
    
    is_valid = await service.handle_user_joined(user_id, invite_link)
    
    if not is_valid:
        logger.warning(f"🚨 Kicking unauthorized user {user_id}")
        await service.kick_user(user_id)
        
        try:
            await bot.send_message(
                user_id,
                "❌ <b>Доступ запрещён!</b>\n\n"
                "Вы попытались войти по чужой ссылке.\n"
                "Купите собственную подписку: /subscribe",
                parse_mode="HTML"
            )
        except Exception:
            pass

@router.chat_member(
    ChatMemberUpdatedFilter(member_status_changed=MEMBER >> KICKED)
)
async def user_left_channel(event: ChatMemberUpdated):
    """Обработка выхода из канала"""
    if event.chat.id != config.CHANNEL_ID:
        return
    
    user_id = event.from_user.id
    logger.info(f"👋 User {user_id} left channel")