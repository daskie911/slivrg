from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from config import config
from subscription_service import SubscriptionService
from crypto_service import crypto_service
from database import db
from datetime import datetime, timedelta
import asyncio

router = Router()

class PaymentStates(StatesGroup):
    waiting_crypto_payment = State()

# ============= Выбор способа оплаты =============

@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    """Команда покупки подписки"""
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
    
    keyboard_buttons = [
        [InlineKeyboardButton(
            text=f"⭐ Telegram Stars — {config.STARS_PRICE} Stars",
            callback_data="pay_stars"
        )]
    ]
    
    if crypto_service.enabled:
        keyboard_buttons.append([InlineKeyboardButton(
            text=f"💎 Криптовалюта — от {config.CRYPTO_PRICE_TON} TON",
            callback_data="pay_crypto"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(
        f"💳 <b>Подписка на канал</b>\n\n"
        f"📅 Срок: <b>{config.SUBSCRIPTION_DAYS} дней</b>\n\n"
        f"Выберите способ оплаты:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

# ============= Оплата Stars =============

@router.callback_query(F.data == "pay_stars")
async def pay_with_stars(callback: CallbackQuery):
    """Оплата через Telegram Stars"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐ Оплатить {config.STARS_PRICE} Stars", pay=True)]
    ])
    
    await callback.message.answer_invoice(
        title="Подписка на канал",
        description=f"Доступ к приватному каналу на {config.SUBSCRIPTION_DAYS} дней",
        payload=f"subscription_{callback.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label="Подписка", amount=config.STARS_PRICE)],
        reply_markup=keyboard
    )
    await callback.answer()

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """Подтверждение платежа Stars"""
    logger.info(f"💳 Pre-checkout from user {pre_checkout_query.from_user.id}")
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, bot: Bot):
    """Обработка успешного платежа Stars"""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    payment = message.successful_payment
    amount = payment.total_amount
    
    logger.success(f"💰 Stars payment successful: {user_id} paid {amount} Stars")
    
    await db.log_payment(
        user_id=user_id,
        username=username,
        amount=amount,
        currency='XTR',
        payment_method='stars',
        telegram_charge_id=payment.telegram_payment_charge_id
    )
    
    service = SubscriptionService(bot)
    
    try:
        invite_link = await service.process_successful_payment(user_id, username)
        
        await message.answer(
            f"✅ <b>Оплата прошла успешно!</b>\n\n"
            f"💰 Оплачено: <b>{amount} Stars</b>\n"
            f"🔗 Ваша персональная ссылка:\n"
            f"<code>{invite_link}</code>\n\n"
            f"⚠️ <b>Важно:</b>\n"
            f"• Ссылка действительна 30 минут\n"
            f"• Ссылка одноразовая\n"
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

# ============= Оплата Crypto =============

@router.callback_query(F.data == "pay_crypto")
async def choose_crypto_currency(callback: CallbackQuery):
    """Выбор криптовалюты"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💎 TON — {config.CRYPTO_PRICE_TON} TON",
            callback_data="pay_crypto_TON"
        )],
        [InlineKeyboardButton(
            text=f"💵 USDT — {config.CRYPTO_PRICE_USDT} USDT",
            callback_data="pay_crypto_USDT"
        )],
        [InlineKeyboardButton(
            text=f"₿ Bitcoin",
            callback_data="pay_crypto_BTC"
        )],
        [InlineKeyboardButton(
            text=f"Ξ Ethereum",
            callback_data="pay_crypto_ETH"
        )],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_payment_methods")]
    ])
    
    await callback.message.edit_text(
        "💎 <b>Выберите криптовалюту</b>\n\n"
        "Оплата через @CryptoBot\n"
        "Без комиссии, мгновенное зачисление",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_with_crypto(callback: CallbackQuery, state: FSMContext):
    """Создание Crypto инвойса"""
    currency = callback.data.split("_")[2]
    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name
    
    if not crypto_service.enabled:
        await callback.answer("❌ Crypto payments temporarily unavailable", show_alert=True)
        return
    
    amount = config.get_crypto_price(currency)
    
    # Создаём инвойс
    invoice = await crypto_service.create_invoice(
        user_id=user_id,
        amount=amount,
        currency=currency,
        description=f"Подписка на {config.SUBSCRIPTION_DAYS} дней"
    )
    
    if not invoice:
        await callback.answer("❌ Ошибка создания платежа", show_alert=True)
        return
    
    # Сохраняем в БД
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    await db.create_pending_crypto_payment(
        user_id=user_id,
        username=username,
        invoice_id=invoice.invoice_id,
        amount=amount,
        currency=currency,
        expires_at=expires_at
    )
    
    # Отправляем пользователю
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=invoice.bot_invoice_url)],
        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_crypto_{invoice.invoice_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_crypto")]
    ])
    
    await callback.message.edit_text(
        f"💎 <b>Оплата через Crypto Bot</b>\n\n"
        f"💰 Сумма: <b>{amount} {currency}</b>\n"
        f"⏰ Действителен: 10 минут\n\n"
        f"1️⃣ Нажмите \"Оплатить\"\n"
        f"2️⃣ Оплатите в @CryptoBot\n"
        f"3️⃣ Вернитесь и нажмите \"Проверить оплату\"\n\n"
        f"💡 Платёж проверяется автоматически",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    await state.set_state(PaymentStates.waiting_crypto_payment)
    await callback.answer()
    
    # Автоматическая проверка каждые 5 секунд
    asyncio.create_task(auto_check_payment(callback.message, invoice.invoice_id, user_id, username, amount, currency, callback.bot))

async def auto_check_payment(
    message: Message,
    invoice_id: int,
    user_id: int,
    username: str,
    amount: float,
    currency: str,
    bot: Bot
):
    """Автоматическая проверка оплаты"""
    for _ in range(120):  # 10 минут (120 * 5 секунд)
        await asyncio.sleep(5)
        
        is_paid = await crypto_service.check_invoice_paid(invoice_id)
        
        if is_paid:
            await process_crypto_payment(invoice_id, user_id, username, amount, currency, bot)
            try:
                await message.delete()
            except:
                pass
            break

@router.callback_query(F.data.startswith("check_crypto_"))
async def check_crypto_payment_manual(callback: CallbackQuery, bot: Bot):
    """Ручная проверка Crypto платежа"""
    invoice_id = int(callback.data.split("_")[2])
    
    await callback.answer("🔍 Проверяю оплату...")
    
    is_paid = await crypto_service.check_invoice_paid(invoice_id)
    
    if is_paid:
        # Получаем данные платежа
        pending = await db.get_pending_crypto_payment_by_invoice(invoice_id)
        
        if pending:
            await process_crypto_payment(
                invoice_id,
                pending['user_id'],
                pending['username'],
                pending['amount'],
                pending['currency'],
                bot
            )
            await callback.message.delete()
        else:
            await callback.answer("❌ Платёж не найден в базе", show_alert=True)
    else:
        await callback.answer("⏳ Платёж ещё не получен", show_alert=True)

async def process_crypto_payment(
    invoice_id: int,
    user_id: int,
    username: str,
    amount: float,
    currency: str,
    bot: Bot
):
    """Обработка успешного Crypto платежа"""
    # Помечаем платёж как выполненный
    await db.complete_crypto_payment(invoice_id)
    
    # Логируем платёж
    await db.log_payment(
        user_id=user_id,
        username=username,
        amount=amount,
        currency=currency,
        payment_method='crypto',
        crypto_invoice_id=str(invoice_id)
    )
    
    # Создаём подписку
    service = SubscriptionService(bot)
    invite_link = await service.process_successful_payment(user_id, username)
    
    # Отправляем пользователю
    await bot.send_message(
        user_id,
        f"✅ <b>Оплата подтверждена!</b>\n\n"
        f"💎 Получено: <b>{amount} {currency}</b>\n"
        f"🔗 Ваша персональная ссылка:\n"
        f"<code>{invite_link}</code>\n\n"
        f"⚠️ <b>Важно:</b>\n"
        f"• Ссылка действительна 30 минут\n"
        f"• Ссылка одноразовая\n"
        f"• После входа ссылка автоматически удалится\n\n"
        f"📅 Подписка активна на {config.SUBSCRIPTION_DAYS} дней",
        parse_mode="HTML"
    )
    
    logger.success(f"💎 Crypto payment processed: {user_id} paid {amount} {currency}")

@router.callback_query(F.data == "cancel_crypto")
async def cancel_crypto_payment(callback: CallbackQuery, state: FSMContext):
    """Отмена Crypto платежа"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Оплата отменена\n\n"
        "Для новой попытки используйте /subscribe",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_payment_methods")
async def back_to_payment_methods(callback: CallbackQuery):
    """Вернуться к выбору способа оплаты"""
    keyboard_buttons = [
        [InlineKeyboardButton(
            text=f"⭐ Telegram Stars — {config.STARS_PRICE} Stars",
            callback_data="pay_stars"
        )]
    ]
    
    if crypto_service.enabled:
        keyboard_buttons.append([InlineKeyboardButton(
            text=f"💎 Криптовалюта — от {config.CRYPTO_PRICE_TON} TON",
            callback_data="pay_crypto"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(
        f"💳 <b>Подписка на канал</b>\n\n"
        f"📅 Срок: <b>{config.SUBSCRIPTION_DAYS} дней</b>\n\n"
        f"Выберите способ оплаты:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()