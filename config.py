import os
from pathlib import Path
from dotenv import load_dotenv, set_key
from loguru import logger

load_dotenv()

class Config:
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
    ADMIN_IDS: list[int] = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
    CHANNEL_ID: int = int(os.getenv('CHANNEL_ID', '0'))
    DATABASE_PATH: str = os.getenv('DATABASE_PATH', './data/subscriptions.db')
    STARS_PRICE: int = int(os.getenv('STARS_PRICE', '100'))
    
    SUBSCRIPTION_DAYS: int = 30
    INVITE_LINK_EXPIRE_MINUTES: int = 30
    REMINDER_DAYS_BEFORE: int = 3
    KICK_AFTER_EXPIRE_HOURS: int = 48

    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise ValueError('BOT_TOKEN not set in .env')
        if not cls.ADMIN_IDS:
            raise ValueError('ADMIN_IDS not set in .env')
        if cls.CHANNEL_ID == 0:
            raise ValueError('CHANNEL_ID not set in .env')
        
        db_path = Path(cls.DATABASE_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f'✅ Config loaded: Channel={cls.CHANNEL_ID}, Admins={cls.ADMIN_IDS}')

    @classmethod
    def update_price(cls, new_price: int):
        """Обновить цену подписки"""
        cls.STARS_PRICE = new_price
        
        # Обновляем .env файл
        env_path = Path('.env')
        if env_path.exists():
            set_key(str(env_path), 'STARS_PRICE', str(new_price))
            logger.success(f'💰 Price updated to {new_price} Stars')
        else:
            logger.warning('⚠️ .env file not found, price updated only in memory')

    @classmethod
    def update_subscription_days(cls, new_days: int):
        """Обновить срок подписки"""
        cls.SUBSCRIPTION_DAYS = new_days
        logger.success(f'📅 Subscription days updated to {new_days}')

config = Config()