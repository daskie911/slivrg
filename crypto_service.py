from aiocryptopay import AioCryptoPay, Networks
from loguru import logger
from config import config

class CryptoService:
    def __init__(self):
        self.crypto = None
        self.enabled = False
        
        if config.CRYPTO_BOT_TOKEN:
            try:
                # Не инициализируем сразу, только проверяем токен
                self.enabled = True
                logger.info("💎 Crypto Bot token found, service will initialize on first use")
            except Exception as e:
                logger.error(f"❌ Crypto Bot init error: {e}")
                self.enabled = False
        else:
            logger.warning("⚠️ Crypto Bot token not set, crypto payments disabled")

    async def _get_crypto(self):
        """Получить экземпляр AioCryptoPay (ленивая инициализация)"""
        if not self.crypto and self.enabled:
            try:
                self.crypto = AioCryptoPay(
                    token=config.CRYPTO_BOT_TOKEN,
                    network=Networks.MAIN_NET
                )
                logger.info("💎 Crypto Bot service initialized")
            except Exception as e:
                logger.error(f"❌ Failed to init Crypto Bot: {e}")
                self.enabled = False
        return self.crypto

    async def create_invoice(
        self,
        user_id: int,
        amount: float,
        currency: str = 'TON',
        description: str = None
    ):
        """Создать инвойс для оплаты"""
        crypto = await self._get_crypto()
        if not crypto:
            logger.error("❌ Crypto Bot not available")
            return None

        try:
            invoice = await crypto.create_invoice(
                asset=currency,
                amount=amount,
                description=description or f"Подписка на {config.SUBSCRIPTION_DAYS} дней",
                payload=f"subscription_{user_id}",
                expires_in=600,
                allow_comments=False,
                allow_anonymous=False
            )
            
            logger.success(f"💎 Invoice created: {invoice.invoice_id} for user {user_id}")
            return invoice
            
        except Exception as e:
            logger.error(f"❌ Failed to create invoice: {e}")
            return None

    async def get_invoice(self, invoice_id: int):
        """Получить информацию об инвойсе"""
        crypto = await self._get_crypto()
        if not crypto:
            return None

        try:
            invoices = await crypto.get_invoices(invoice_ids=[invoice_id])
            return invoices[0] if invoices else None
        except Exception as e:
            logger.error(f"❌ Failed to get invoice: {e}")
            return None

    async def check_invoice_paid(self, invoice_id: int) -> bool:
        """Проверить, оплачен ли инвойс"""
        invoice = await self.get_invoice(invoice_id)
        if invoice:
            return invoice.status == 'paid'
        return False

    async def get_balance(self) -> dict | None:
        """Получить баланс Crypto Bot"""
        crypto = await self._get_crypto()
        if not crypto:
            return None

        try:
            balances = await crypto.get_balance()
            return {
                balance.currency_code: float(balance.available)
                for balance in balances
            }
        except Exception as e:
            logger.error(f"❌ Failed to get balance: {e}")
            return None

    async def close(self):
        """Закрыть сессию"""
        if self.crypto:
            await self.crypto.close()
            logger.info("💎 Crypto Bot session closed")

# Глобальный экземпляр (без инициализации)
crypto_service = CryptoService()