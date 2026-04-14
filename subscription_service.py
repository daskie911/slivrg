from datetime import datetime, timedelta, timezone
from aiogram import Bot
from aiogram.types import ChatInviteLink
from loguru import logger
from database import db
from config import config

class SubscriptionService:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def create_invite_link(self, user_id: int, username: str) -> str:
        """Создать уникальную invite-ссылку для пользователя"""
        expire_date = datetime.now(timezone.utc) + timedelta(minutes=config.INVITE_LINK_EXPIRE_MINUTES)
        
        try:
            invite: ChatInviteLink = await self.bot.create_chat_invite_link(
                chat_id=config.CHANNEL_ID,
                member_limit=1,
                expire_date=expire_date,
                name=f"User {user_id} - {username or 'NoUsername'}"[:32]
            )
            
            logger.success(f"🔗 Invite link created: {invite.invite_link}")
            return invite.invite_link
        
        except Exception as e:
            logger.error(f"❌ Failed to create invite link: {e}")
            raise

    async def revoke_invite_link(self, invite_link: str):
        """Отозвать invite-ссылку"""
        try:
            await self.bot.revoke_chat_invite_link(
                chat_id=config.CHANNEL_ID,
                invite_link=invite_link
            )
            logger.info(f"✅ Invite link revoked: {invite_link}")
        except Exception as e:
            logger.error(f"❌ Failed to revoke invite link: {e}")

    async def process_successful_payment(self, user_id: int, username: str):
        """Обработка успешной оплаты"""
        invite_link = await self.create_invite_link(user_id, username)
        
        await db.create_subscription(
            user_id=user_id,
            username=username,
            invite_link=invite_link,
            subscription_days=config.SUBSCRIPTION_DAYS
        )
        
        return invite_link

    async def handle_user_joined(self, user_id: int, invite_link: str | None):
        """Обработка присоединения пользователя к каналу"""
        if not invite_link:
            logger.warning(f"⚠️ User {user_id} joined without invite link")
            return False
        
        subscription = await db.get_subscription_by_invite(invite_link)
        
        if not subscription:
            logger.warning(f"⚠️ No subscription found for invite: {invite_link}")
            return False
        
        if subscription['user_id'] != user_id:
            logger.warning(
                f"🚨 User {user_id} tried to join with link for user {subscription['user_id']}"
            )
            return False
        
        await self.revoke_invite_link(invite_link)
        await db.revoke_invite_link(user_id)
        logger.success(f"✅ User {user_id} successfully joined, invite revoked")
        return True

    async def kick_user(self, user_id: int):
        """Кикнуть пользователя из канала"""
        try:
            await self.bot.ban_chat_member(
                chat_id=config.CHANNEL_ID,
                user_id=user_id
            )
            await self.bot.unban_chat_member(
                chat_id=config.CHANNEL_ID,
                user_id=user_id
            )
            logger.warning(f"⚠️ User {user_id} kicked from channel")
        except Exception as e:
            logger.error(f"❌ Failed to kick user {user_id}: {e}")

    async def is_user_in_channel(self, user_id: int) -> bool:
        """Проверить, состоит ли пользователь в канале"""
        try:
            member = await self.bot.get_chat_member(
                chat_id=config.CHANNEL_ID,
                user_id=user_id
            )
            return member.status in ['member', 'administrator', 'creator']
        except Exception:
            return False
