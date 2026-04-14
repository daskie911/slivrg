import aiosqlite
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
from config import config

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Подключение к БД и создание таблиц"""
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()
        logger.info(f"✅ Database connected: {self.db_path}")

    async def _create_tables(self):
        """Создание таблиц"""
        # Таблица подписок
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                subscription_until TEXT,
                invite_link TEXT,
                invite_created_at TEXT,
                payment_status TEXT DEFAULT 'pending'
            )
        """)
        
        # Таблица платежей
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                amount REAL,
                currency TEXT,
                payment_date TEXT,
                payment_method TEXT,
                telegram_payment_charge_id TEXT,
                crypto_invoice_id TEXT,
                crypto_hash TEXT
            )
        """)
        
        # Таблица ожидающих Crypto платежей
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_crypto_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                invoice_id INTEGER,
                amount REAL,
                currency TEXT,
                created_at TEXT,
                expires_at TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)
        
        await self.conn.commit()

    async def close(self):
        """Закрытие соединения"""
        if self.conn:
            await self.conn.close()
            logger.info("❌ Database connection closed")

    # ===== CRUD операции =====

    async def create_subscription(
        self,
        user_id: int,
        username: str,
        invite_link: str,
        subscription_days: int = 30
    ):
        """Создать подписку после успешной оплаты"""
        now = datetime.utcnow()
        subscription_until = now + timedelta(days=subscription_days)
        
        await self.conn.execute("""
            INSERT OR REPLACE INTO subscriptions 
            (user_id, username, subscription_until, invite_link, invite_created_at, payment_status)
            VALUES (?, ?, ?, ?, ?, 'paid')
        """, (
            user_id,
            username,
            subscription_until.isoformat(),
            invite_link,
            now.isoformat()
        ))
        await self.conn.commit()
        logger.success(f"💳 Subscription created for user {user_id} until {subscription_until}")

    async def get_subscription(self, user_id: int) -> Optional[dict]:
        """Получить подписку пользователя"""
        async with self.conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_subscription_by_invite(self, invite_link: str) -> Optional[dict]:
        """Получить подписку по invite-ссылке"""
        async with self.conn.execute(
            "SELECT * FROM subscriptions WHERE invite_link = ?", (invite_link,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def revoke_invite_link(self, user_id: int):
        """Обнулить invite_link после использования"""
        await self.conn.execute(
            "UPDATE subscriptions SET invite_link = NULL WHERE user_id = ?",
            (user_id,)
        )
        await self.conn.commit()
        logger.info(f"🔗 Invite link revoked for user {user_id}")

    async def get_active_subscriptions(self) -> list[dict]:
        """Все активные подписки"""
        now = datetime.utcnow().isoformat()
        async with self.conn.execute(
            "SELECT * FROM subscriptions WHERE subscription_until > ? AND payment_status = 'paid'",
            (now,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_expiring_soon(self, days: int = 3) -> list[dict]:
        """Подписки, истекающие через N дней"""
        now = datetime.utcnow()
        threshold = now + timedelta(days=days)
        
        async with self.conn.execute("""
            SELECT * FROM subscriptions 
            WHERE subscription_until <= ? 
            AND subscription_until > ?
            AND payment_status = 'paid'
        """, (threshold.isoformat(), now.isoformat())) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_expired_subscriptions(self, hours_ago: int = 48) -> list[dict]:
        """Подписки, истекшие более N часов назад"""
        threshold = datetime.utcnow() - timedelta(hours=hours_ago)
        
        async with self.conn.execute(
            "SELECT * FROM subscriptions WHERE subscription_until < ? AND payment_status = 'paid'",
            (threshold.isoformat(),)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def delete_subscription(self, user_id: int):
        """Удалить подписку"""
        await self.conn.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
        await self.conn.commit()
        logger.warning(f"🗑️ Subscription deleted for user {user_id}")

    async def count_active(self) -> int:
        """Количество активных подписчиков"""
        now = datetime.utcnow().isoformat()
        async with self.conn.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE subscription_until > ? AND payment_status = 'paid'",
            (now,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    # ===== Платежи =====

    async def log_payment(
        self, 
        user_id: int, 
        username: str, 
        amount: float,
        currency: str = 'XTR',
        payment_method: str = 'stars',
        telegram_charge_id: str = None,
        crypto_invoice_id: str = None,
        crypto_hash: str = None
    ):
        """Сохранить платёж в историю"""
        await self.conn.execute("""
            INSERT INTO payments 
            (user_id, username, amount, currency, payment_date, payment_method, 
             telegram_payment_charge_id, crypto_invoice_id, crypto_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            username,
            amount,
            currency,
            datetime.utcnow().isoformat(),
            payment_method,
            telegram_charge_id,
            crypto_invoice_id,
            crypto_hash
        ))
        await self.conn.commit()
        logger.info(f"💾 Payment logged: {user_id} - {amount} {currency} via {payment_method}")

    async def get_total_revenue_by_currency(self, currency: str = 'XTR') -> float:
        """Получить общую сумму дохода по валюте"""
        try:
            async with self.conn.execute(
                "SELECT SUM(amount) FROM payments WHERE currency = ?",
                (currency,)
            ) as cursor:
                row = await cursor.fetchone()
                return float(row[0]) if row and row[0] else 0.0
        except Exception as e:
            logger.warning(f"⚠️ Failed to get revenue: {e}")
            return 0.0

    async def get_total_revenue(self) -> int:
        """Получить общую сумму дохода в Stars"""
        return int(await self.get_total_revenue_by_currency('XTR'))

    # ===== Crypto платежи =====

    async def create_pending_crypto_payment(
        self,
        user_id: int,
        username: str,
        invoice_id: int,
        amount: float,
        currency: str,
        expires_at: str
    ):
        """Создать ожидающий Crypto платёж"""
        await self.conn.execute("""
            INSERT INTO pending_crypto_payments 
            (user_id, username, invoice_id, amount, currency, created_at, expires_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            user_id,
            username,
            invoice_id,
            amount,
            currency,
            datetime.utcnow().isoformat(),
            expires_at
        ))
        await self.conn.commit()
        logger.info(f"💎 Pending crypto payment created: invoice {invoice_id} for user {user_id}")

    async def get_pending_crypto_payment(self, user_id: int) -> Optional[dict]:
        """Получить ожидающий Crypto платёж"""
        async with self.conn.execute(
            "SELECT * FROM pending_crypto_payments WHERE user_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_pending_crypto_payment_by_invoice(self, invoice_id: int) -> Optional[dict]:
        """Получить платёж по invoice_id"""
        async with self.conn.execute(
            "SELECT * FROM pending_crypto_payments WHERE invoice_id = ? AND status = 'pending'",
            (invoice_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def complete_crypto_payment(self, invoice_id: int):
        """Отметить Crypto платёж как выполненный"""
        await self.conn.execute(
            "UPDATE pending_crypto_payments SET status = 'completed' WHERE invoice_id = ? AND status = 'pending'",
            (invoice_id,)
        )
        await self.conn.commit()
        logger.success(f"💎 Crypto payment completed: invoice {invoice_id}")

# Глобальный экземпляр
db = Database(config.DATABASE_PATH)
