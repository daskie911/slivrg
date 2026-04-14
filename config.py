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
    
    # Цены
    STARS_PRICE: int = int(os.getenv('STARS_PRICE', '100'))
    CRYPTO_PRICE_TON: float = float(os.getenv('CRYPTO_PRICE_TON', '1.5'))
    CRYPTO_PRICE_USDT: float = float(os.getenv('CRYPTO_PRICE_USDT', '2.0'))
    
    # Crypto Bot настройки
    CRYPTO_BOT_TOKEN: str = os.getenv('CRYPTO_BOT_TOKEN', '')
    
    SUBSCRIPTION_DAYS: int = 30
    INVITE_LINK_EXPIRE_MINUTES: int = 30
    REMINDER_DAYS_BEFORE: int = 3
    KICK_AFTER_EXPIRE_HOURS: int = 48
    
    # Доступные криптовалюты
    AVAILABLE_CURRENCIES = ['TON', 'USDT', 'BTC', 'ETH']

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
        
        if cls.CRYPTO_BOT_TOKEN:
            logger.info(f'💎 Crypto Bot enabled')
        else:
            logger.warning('⚠️ Crypto Bot token not set')

    @classmethod
    def update_price(cls, new_price: float, currency: str = 'stars'):
        """Обновить цену подписки"""
        if currency == 'stars':
            cls.STARS_PRICE = int(new_price)
            key = 'STARS_PRICE'
            value = str(int(new_price))
        elif currency == 'ton':
            cls.CRYPTO_PRICE_TON = float(new_price)
            key = 'CRYPTO_PRICE_TON'
            value = str(new_price)
        elif currency == 'usdt':
            cls.CRYPTO_PRICE_USDT = float(new_price)
            key = 'CRYPTO_PRICE_USDT'
            value = str(new_price)
        else:
            return
        
        env_path = Path('.env')
        if env_path.exists():
            set_key(str(env_path), key, value)
            logger.success(f'💰 {currency.upper()} price updated to {new_price}')
        else:
            logger.warning('⚠️ .env file not found, price updated only in memory')

    @classmethod
    def update_subscription_days(cls, new_days: int):
        """Обновить срок подписки"""
        cls.SUBSCRIPTION_DAYS = new_days
        logger.success(f'📅 Subscription days updated to {new_days}')
    
    @classmethod
    def get_crypto_price(cls, currency: str) -> float:
        """Получить цену для криптовалюты"""
        prices = {
            'TON': cls.CRYPTO_PRICE_TON,
            'USDT': cls.CRYPTO_PRICE_USDT,
            'BTC': cls.CRYPTO_PRICE_USDT / 50000,  # Примерный курс
            'ETH': cls.CRYPTO_PRICE_USDT / 3000,   # Примерный курс
        }
        return prices.get(currency, cls.CRYPTO_PRICE_TON)

config = Config()
