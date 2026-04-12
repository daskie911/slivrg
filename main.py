import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage  # ← ДОБАВЬТЕ ЭТУ СТРОКУ
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from config import config
from database import db
from schedulers.subscription_checker import SubscriptionChecker

# Импорт роутеров
from handlers import start_handler
from handlers import payment_handler
from handlers import chat_member_handler
from handlers import admin_handler

# Настройка логирования
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO"
)
logger.add(
    "logs/bot.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG"
)

async def main():
    # Валидация конфига
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"❌ Config error: {e}")
        return

    # Инициализация бота
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # ✅ ДОБАВЬТЕ MemoryStorage:
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Подключение к БД
    await db.connect()

    # Регистрация роутеров
    dp.include_router(start_handler.router)
    dp.include_router(payment_handler.router)
    dp.include_router(chat_member_handler.router)
    dp.include_router(admin_handler.router)

    # Настройка планировщика задач
    scheduler = AsyncIOScheduler(timezone="UTC")
    checker = SubscriptionChecker(bot)
    
    # Запуск проверки каждые 30 минут
    scheduler.add_job(
        checker.run_all_checks,
        'interval',
        minutes=30,
        id='subscription_checker'
    )
    scheduler.start()
    logger.success("✅ Scheduler started (checking every 30 minutes)")

    # Callback для кнопки "Продлить"
    @dp.callback_query(lambda c: c.data == "renew_subscription")
    async def renew_callback(callback):
        await callback.message.answer(
            "💳 Для продления подписки используйте команду /subscribe"
        )
        await callback.answer()

    # Запуск бота
    logger.success("✅ Bot started successfully")
    
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await db.close()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("⚠️ Bot stopped by user")