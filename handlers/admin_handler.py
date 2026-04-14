import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from config import config
from database import db
from crypto_service import crypto_service
from datetime import datetime

router = Router()

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом"""
    return user_id in config.ADMIN_IDS

# ============= FSM для админских действий =============

class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_channel_id = State()
    waiting_for_broadcast_message = State()
    waiting_for_price_stars = State()
    waiting_for_price_ton = State()
    waiting_for_price_usdt = State()
    waiting_for_subscription_days = State()

# ============= Главное меню админ-панели =============

def get_admin_keyboard():
    """Клавиатура админ-панели"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Список подписчиков", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 Доход", callback_data="admin_revenue")],
        [InlineKeyboardButton(text="💎 Crypto баланс", callback_data="admin_crypto_balance")],
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin_find_user")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close")]
    ])
    return keyboard

@router.message(Command("admin"))
async def cmd_admin_panel(message: Message):
    """Открыть админ-панель"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для этой команды.")
        return
    
    await message.answer(
        "🎛️ <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

# ============= Статистика =============

@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: CallbackQuery):
    """Показать статистику"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    active_count = await db.count_active()
    
    # Получаем доход по всем валютам
    revenue_stars = await db.get_total_revenue_by_currency('XTR')
    revenue_ton = await db.get_total_revenue_by_currency('TON')
    revenue_usdt = await db.get_total_revenue_by_currency('USDT')
    revenue_btc = await db.get_total_revenue_by_currency('BTC')
    revenue_eth = await db.get_total_revenue_by_currency('ETH')
    
    expiring_soon = await db.get_expiring_soon(days=3)
    expired = await db.get_expired_subscriptions(hours_ago=48)
    
    stats_text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Активных подписчиков: <b>{active_count}</b>\n"
        f"⏰ Истекают скоро (3 дня): <b>{len(expiring_soon)}</b>\n"
        f"⚠️ Просроченные (>48ч): <b>{len(expired)}</b>\n\n"
        f"💰 <b>Финансы</b>\n"
        f"⭐ Stars: <b>{int(revenue_stars)}</b>\n"
        f"💎 TON: <b>{revenue_ton:.2f}</b>\n"
        f"💵 USDT: <b>{revenue_usdt:.2f}</b>\n"
        f"₿ BTC: <b>{revenue_btc:.6f}</b>\n"
        f"Ξ ETH: <b>{revenue_eth:.4f}</b>\n\n"
        f"💵 Чистый доход Stars (~70%): <b>{int(revenue_stars * 0.7)}</b>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(stats_text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

# ============= Список подписчиков =============

@router.callback_query(F.data == "admin_users")
async def show_users(callback: CallbackQuery):
    """Показать список активных подписчиков"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    active_subs = await db.get_active_subscriptions()
    
    if not active_subs:
        await callback.answer("📭 Нет активных подписчиков", show_alert=True)
        return
    
    users_text = "👥 <b>Активные подписчики</b>\n\n"
    
    for i, sub in enumerate(active_subs[:10], 1):
        username = sub['username'] or 'Без username'
        sub_until = datetime.fromisoformat(sub['subscription_until'])
        days_left = (sub_until - datetime.utcnow()).days
        
        users_text += (
            f"{i}. <code>{sub['user_id']}</code> | @{username}\n"
            f"   📅 Осталось: {days_left} дней\n\n"
        )
    
    if len(active_subs) > 10:
        users_text += f"\n... и ещё {len(active_subs) - 10} подписчиков"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(users_text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

# ============= Доход =============

@router.callback_query(F.data == "admin_revenue")
async def show_revenue(callback: CallbackQuery):
    """Показать детальную информацию о доходе"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    revenue_stars = await db.get_total_revenue_by_currency('XTR')
    revenue_ton = await db.get_total_revenue_by_currency('TON')
    revenue_usdt = await db.get_total_revenue_by_currency('USDT')
    revenue_btc = await db.get_total_revenue_by_currency('BTC')
    revenue_eth = await db.get_total_revenue_by_currency('ETH')
    
    active_subs = await db.count_active()
    
    stars_commission = int(revenue_stars * 0.3)
    stars_net = int(revenue_stars - stars_commission)
    
    revenue_text = (
        f"💰 <b>Финансовая сводка</b>\n\n"
        f"📊 <b>Telegram Stars</b>\n"
        f"⭐ Валовый доход: <b>{int(revenue_stars)} Stars</b>\n"
        f"💸 Комиссия (30%): <b>{stars_commission} Stars</b>\n"
        f"💵 Чистый доход: <b>{stars_net} Stars</b>\n\n"
        f"💎 <b>Криптовалюта</b>\n"
        f"TON: <b>{revenue_ton:.2f}</b>\n"
        f"USDT: <b>{revenue_usdt:.2f}</b>\n"
        f"BTC: <b>{revenue_btc:.6f}</b>\n"
        f"ETH: <b>{revenue_eth:.4f}</b>\n\n"
        f"👥 <b>Подписчики</b>\n"
        f"Активных: <b>{active_subs}</b>\n\n"
        f"💡 <b>Для вывода:</b>\n"
        f"Stars: @BotFather → Payments\n"
        f"Crypto: @CryptoBot → My Apps"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(revenue_text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

# ============= Crypto баланс =============

@router.callback_query(F.data == "admin_crypto_balance")
async def show_crypto_balance(callback: CallbackQuery):
    """Показать баланс Crypto Bot"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    if not crypto_service.enabled:
        await callback.answer("❌ Crypto Bot не настроен", show_alert=True)
        return
    
    await callback.answer("🔍 Получаю баланс...")
    
    balance = await crypto_service.get_balance()
    
    if not balance:
        await callback.answer("❌ Ошибка получения баланса", show_alert=True)
        return
    
    balance_text = "💎 <b>Баланс Crypto Bot</b>\n\n"
    
    for currency, amount in balance.items():
        if amount > 0:
            balance_text += f"{currency}: <b>{amount:.6f}</b>\n"
    
    if len(balance_text.split('\n')) == 2:
        balance_text += "\n<i>Баланс пуст</i>"
    
    balance_text += "\n\n💡 Вывести можно через @CryptoBot"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_crypto_balance")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(balance_text, parse_mode="HTML", reply_markup=keyboard)

# ============= Поиск пользователя =============

@router.callback_query(F.data == "admin_find_user")
async def find_user_start(callback: CallbackQuery, state: FSMContext):
    """Начать поиск пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Отправьте Telegram ID пользователя:\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await callback.answer()

@router.message(AdminStates.waiting_for_user_id, Command("cancel"))
async def find_user_cancel(message: Message, state: FSMContext):
    """Отмена поиска"""
    await state.clear()
    await message.answer(
        "❌ Поиск отменён",
        reply_markup=get_admin_keyboard()
    )

@router.message(AdminStates.waiting_for_user_id)
async def find_user_process(message: Message, state: FSMContext):
    """Обработка поиска пользователя"""
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат. Введите числовой ID или /cancel для отмены.")
        return
    
    subscription = await db.get_subscription(user_id)
    
    if not subscription:
        await message.answer(
            f"❌ Пользователь <code>{user_id}</code> не найден в базе",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        await state.clear()
        return
    
    sub_until = datetime.fromisoformat(subscription['subscription_until'])
    now = datetime.utcnow()
    is_active = sub_until > now
    days_left = (sub_until - now).days if is_active else 0
    
    status_emoji = "✅" if is_active else "❌"
    status_text = "Активна" if is_active else "Истекла"
    
    user_info = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Username: @{subscription['username'] or 'Нет'}\n\n"
        f"{status_emoji} Статус: <b>{status_text}</b>\n"
        f"📅 Подписка до: <code>{sub_until.strftime('%Y-%m-%d %H:%M')}</code>\n"
        f"⏳ Осталось дней: <b>{days_left}</b>\n\n"
        f"🔗 Invite-ссылка: {'Активна' if subscription.get('invite_link') else 'Использована'}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Удалить подписку", callback_data=f"admin_delete_{user_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
    ])
    
    await message.answer(user_info, parse_mode="HTML", reply_markup=keyboard)
    await state.clear()

# ============= Рассылка =============

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    """Начать рассылку"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "📢 <b>Рассылка сообщения</b>\n\n"
        "Отправьте текст сообщения для рассылки всем подписчикам.\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast_message, Command("cancel"))
async def broadcast_cancel(message: Message, state: FSMContext):
    """Отмена рассылки"""
    await state.clear()
    await message.answer(
        "❌ Рассылка отменена",
        reply_markup=get_admin_keyboard()
    )

@router.message(AdminStates.waiting_for_broadcast_message)
async def broadcast_process(message: Message, state: FSMContext, bot: Bot):
    """Обработка рассылки"""
    broadcast_text = message.html_text
    
    active_subs = await db.get_active_subscriptions()
    
    if not active_subs:
        await message.answer(
            "❌ Нет активных подписчиков для рассылки",
            reply_markup=get_admin_keyboard()
        )
        await state.clear()
        return
    
    status_msg = await message.answer(f"📤 Начинаю рассылку {len(active_subs)} пользователям...")
    
    success = 0
    failed = 0
    
    for sub in active_subs:
        try:
            await bot.send_message(sub['user_id'], broadcast_text, parse_mode="HTML")
            success += 1
            logger.info(f"✅ Broadcast sent to {sub['user_id']}")
        except Exception as e:
            logger.error(f"❌ Failed to send broadcast to {sub['user_id']}: {e}")
            failed += 1
        
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"✅ Успешно: {success}\n"
        f"❌ Ошибок: {failed}",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()

# ============= Настройки =============

@router.callback_query(F.data == "admin_settings")
async def show_settings(callback: CallbackQuery):
    """Показать настройки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    crypto_status = "✅ Подключен" if crypto_service.enabled else "❌ Не настроен"
    
    settings_text = (
        f"⚙️ <b>Настройки бота</b>\n\n"
        f"<b>Цены:</b>\n"
        f"⭐ Stars: <b>{config.STARS_PRICE} Stars</b>\n"
        f"💎 TON: <b>{config.CRYPTO_PRICE_TON} TON</b>\n"
        f"💵 USDT: <b>{config.CRYPTO_PRICE_USDT} USDT</b>\n\n"
        f"📅 Срок подписки: <b>{config.SUBSCRIPTION_DAYS} дней</b>\n"
        f"⏰ Срок invite-ссылки: <b>{config.INVITE_LINK_EXPIRE_MINUTES} минут</b>\n\n"
        f"🆔 Channel ID: <code>{config.CHANNEL_ID}</code>\n"
        f"💎 Crypto Bot: {crypto_status}"
    )
    
    keyboard_buttons = [
        [InlineKeyboardButton(text="⭐ Изменить цену Stars", callback_data="admin_change_price_stars")],
    ]
    
    if crypto_service.enabled:
        keyboard_buttons.append([InlineKeyboardButton(text="💎 Изменить цену TON", callback_data="admin_change_price_ton")])
        keyboard_buttons.append([InlineKeyboardButton(text="💵 Изменить цену USDT", callback_data="admin_change_price_usdt")])
    
    keyboard_buttons.append([InlineKeyboardButton(text="📅 Изменить срок", callback_data="admin_change_days")])
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(settings_text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

# ============= Изменение цен =============

@router.callback_query(F.data == "admin_change_price_stars")
async def change_price_stars_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение цены Stars"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        f"💰 <b>Изменение цены Stars</b>\n\n"
        f"Текущая цена: <b>{config.STARS_PRICE} Stars</b>\n\n"
        f"Отправьте новую цену (целое число):\n\n"
        f"Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_price_stars)
    await callback.answer()

@router.message(AdminStates.waiting_for_price_stars, Command("cancel"))
async def change_price_stars_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Изменение отменено", reply_markup=get_admin_keyboard())

@router.message(AdminStates.waiting_for_price_stars)
async def change_price_stars_process(message: Message, state: FSMContext):
    try:
        new_price = int(message.text.strip())
        if new_price < 1 or new_price > 2500:
            await message.answer("❌ Цена должна быть от 1 до 2500 Stars")
            return
        
        old_price = config.STARS_PRICE
        config.update_price(new_price, currency='stars')
        
        await message.answer(
            f"✅ <b>Цена Stars изменена!</b>\n\n"
            f"Было: {old_price} Stars\n"
            f"Стало: {new_price} Stars",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        logger.success(f"Admin {message.from_user.id} changed Stars price: {old_price} → {new_price}")
    except ValueError:
        await message.answer("❌ Неверный формат. Введите целое число")
        return
    
    await state.clear()

@router.callback_query(F.data == "admin_change_price_ton")
async def change_price_ton_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        f"💎 <b>Изменение цены TON</b>\n\n"
        f"Текущая цена: <b>{config.CRYPTO_PRICE_TON} TON</b>\n\n"
        f"Отправьте новую цену (например: 1.5):\n\n"
        f"Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_price_ton)
    await callback.answer()

@router.message(AdminStates.waiting_for_price_ton, Command("cancel"))
async def change_price_ton_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Изменение отменено", reply_markup=get_admin_keyboard())

@router.message(AdminStates.waiting_for_price_ton)
async def change_price_ton_process(message: Message, state: FSMContext):
    try:
        new_price = float(message.text.strip().replace(',', '.'))
        if new_price <= 0 or new_price > 1000:
            await message.answer("❌ Цена должна быть от 0.01 до 1000 TON")
            return
        
        old_price = config.CRYPTO_PRICE_TON
        config.update_price(new_price, currency='ton')
        
        await message.answer(
            f"✅ <b>Цена TON изменена!</b>\n\n"
            f"Было: {old_price} TON\n"
            f"Стало: {new_price} TON",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        logger.success(f"Admin {message.from_user.id} changed TON price: {old_price} → {new_price}")
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число")
        return
    
    await state.clear()

@router.callback_query(F.data == "admin_change_price_usdt")
async def change_price_usdt_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        f"💵 <b>Изменение цены USDT</b>\n\n"
        f"Текущая цена: <b>{config.CRYPTO_PRICE_USDT} USDT</b>\n\n"
        f"Отправьте новую цену (например: 2.0):\n\n"
        f"Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_price_usdt)
    await callback.answer()

@router.message(AdminStates.waiting_for_price_usdt, Command("cancel"))
async def change_price_usdt_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Изменение отменено", reply_markup=get_admin_keyboard())

@router.message(AdminStates.waiting_for_price_usdt)
async def change_price_usdt_process(message: Message, state: FSMContext):
    try:
        new_price = float(message.text.strip().replace(',', '.'))
        if new_price <= 0 or new_price > 10000:
            await message.answer("❌ Цена должна быть от 0.01 до 10000 USDT")
            return
        
        old_price = config.CRYPTO_PRICE_USDT
        config.update_price(new_price, currency='usdt')
        
        await message.answer(
            f"✅ <b>Цена USDT изменена!</b>\n\n"
            f"Было: {old_price} USDT\n"
            f"Стало: {new_price} USDT",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        logger.success(f"Admin {message.from_user.id} changed USDT price: {old_price} → {new_price}")
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число")
        return
    
    await state.clear()

# ============= Изменение срока =============

@router.callback_query(F.data == "admin_change_days")
async def change_days_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        f"📅 <b>Изменение срока подписки</b>\n\n"
        f"Текущий срок: <b>{config.SUBSCRIPTION_DAYS} дней</b>\n\n"
        f"Отправьте новый срок (целое число):\n\n"
        f"Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_subscription_days)
    await callback.answer()

@router.message(AdminStates.waiting_for_subscription_days, Command("cancel"))
async def change_days_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Изменение отменено", reply_markup=get_admin_keyboard())

@router.message(AdminStates.waiting_for_subscription_days)
async def change_days_process(message: Message, state: FSMContext):
    try:
        new_days = int(message.text.strip())
        if new_days < 1 or new_days > 365:
            await message.answer("❌ Срок должен быть от 1 до 365 дней")
            return
        
        old_days = config.SUBSCRIPTION_DAYS
        config.update_subscription_days(new_days)
        
        await message.answer(
            f"✅ <b>Срок подписки изменён!</b>\n\n"
            f"Было: {old_days} дней\n"
            f"Стало: {new_days} дней",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        logger.success(f"Admin {message.from_user.id} changed subscription days: {old_days} → {new_days}")
    except ValueError:
        await message.answer("❌ Неверный формат. Введите целое число")
        return
    
    await state.clear()

# ============= Удаление подписки =============

@router.callback_query(F.data.startswith("admin_delete_"))
async def delete_subscription(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    from subscription_service import SubscriptionService
    service = SubscriptionService(bot)
    await service.kick_user(user_id)
    await db.delete_subscription(user_id)
    
    await callback.answer("🗑️ Подписка удалена, пользователь кикнут", show_alert=True)
    await callback.message.edit_text(
        f"✅ Подписка пользователя <code>{user_id}</code> удалена\n"
        f"⚠️ Пользователь кикнут из канала",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

# ============= Навигация =============

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🎛️ <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_close")
async def admin_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer("❌ Панель закрыта")

# ============= Дополнительные команды =============

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для этой команды.")
        return
    
    active_count = await db.count_active()
    
    await message.answer(
        f"📊 <b>Быстрая статистика</b>\n\n"
        f"👥 Активных подписчиков: <b>{active_count}</b>\n\n"
        f"💡 Для подробной информации: /admin",
        parse_mode="HTML"
    )