import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from config import config
from database import db
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
    waiting_for_price = State()  # ← НОВОЕ
    waiting_for_subscription_days = State()  # ← НОВОЕ

# ============= Главное меню админ-панели =============

def get_admin_keyboard():
    """Клавиатура админ-панели"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Список подписчиков", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 Доход", callback_data="admin_revenue")],
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
    total_revenue = await db.get_total_revenue()
    expiring_soon = await db.get_expiring_soon(days=3)
    expired = await db.get_expired_subscriptions(hours_ago=48)
    
    stats_text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Активных подписчиков: <b>{active_count}</b>\n"
        f"⏰ Истекают скоро (3 дня): <b>{len(expiring_soon)}</b>\n"
        f"⚠️ Просроченные (>48ч): <b>{len(expired)}</b>\n\n"
        f"💰 <b>Финансы</b>\n"
        f"⭐ Всего получено: <b>{total_revenue} Stars</b>\n"
        f"💵 Чистый доход (~70%): <b>{int(total_revenue * 0.7)} Stars</b>\n\n"
        f"📈 Средний чек: <b>{total_revenue // max(active_count, 1)} Stars</b>"
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
    
    total = await db.get_total_revenue()
    active_subs = await db.count_active()
    
    gross = total
    commission = int(total * 0.3)
    net = total - commission
    
    revenue_text = (
        f"💰 <b>Финансовая сводка</b>\n\n"
        f"📊 <b>Общие показатели</b>\n"
        f"⭐ Валовый доход: <b>{gross} Stars</b>\n"
        f"💸 Комиссия Telegram (30%): <b>{commission} Stars</b>\n"
        f"💵 Чистый доход: <b>{net} Stars</b>\n\n"
        f"👥 <b>Подписчики</b>\n"
        f"Активных: <b>{active_subs}</b>\n"
        f"Средний чек: <b>{gross // max(active_subs, 1)} Stars</b>\n\n"
        f"💡 <b>Для вывода средств:</b>\n"
        f"@BotFather → /mybots → Ваш бот\n"
        f"→ Bot Settings → Payments → Balance"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(revenue_text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

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
    
    settings_text = (
        f"⚙️ <b>Настройки бота</b>\n\n"
        f"💰 Цена подписки: <b>{config.STARS_PRICE} Stars</b>\n"
        f"📅 Срок подписки: <b>{config.SUBSCRIPTION_DAYS} дней</b>\n"
        f"⏰ Срок invite-ссылки: <b>{config.INVITE_LINK_EXPIRE_MINUTES} минут</b>\n"
        f"🔔 Напоминание за: <b>{config.REMINDER_DAYS_BEFORE} дня</b>\n"
        f"⚠️ Кик после истечения: <b>{config.KICK_AFTER_EXPIRE_HOURS} часов</b>\n\n"
        f"🆔 Channel ID: <code>{config.CHANNEL_ID}</code>\n"
        f"👤 Админы: <code>{', '.join(map(str, config.ADMIN_IDS))}</code>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Изменить цену", callback_data="admin_change_price")],
        [InlineKeyboardButton(text="📅 Изменить срок подписки", callback_data="admin_change_days")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(settings_text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

# ============= Изменение цены =============

@router.callback_query(F.data == "admin_change_price")
async def change_price_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение цены"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        f"💰 <b>Изменение цены подписки</b>\n\n"
        f"Текущая цена: <b>{config.STARS_PRICE} Stars</b>\n\n"
        f"Отправьте новую цену в Stars (целое число):\n\n"
        f"Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_price)
    await callback.answer()

@router.message(AdminStates.waiting_for_price, Command("cancel"))
async def change_price_cancel(message: Message, state: FSMContext):
    """Отмена изменения цены"""
    await state.clear()
    await message.answer(
        "❌ Изменение цены отменено",
        reply_markup=get_admin_keyboard()
    )

@router.message(AdminStates.waiting_for_price)
async def change_price_process(message: Message, state: FSMContext):
    """Обработка изменения цены"""
    try:
        new_price = int(message.text.strip())
        
        if new_price < 1:
            await message.answer("❌ Цена должна быть больше 0. Попробуйте снова или /cancel для отмены.")
            return
        
        if new_price > 2500:
            await message.answer("❌ Максимальная цена 2500 Stars. Попробуйте снова или /cancel для отмены.")
            return
        
        old_price = config.STARS_PRICE
        config.update_price(new_price)
        
        await message.answer(
            f"✅ <b>Цена успешно изменена!</b>\n\n"
            f"Было: <b>{old_price} Stars</b>\n"
            f"Стало: <b>{new_price} Stars</b>\n\n"
            f"💡 Изменения вступили в силу немедленно.",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        
        logger.success(f"💰 Admin {message.from_user.id} changed price: {old_price} → {new_price}")
        
    except ValueError:
        await message.answer("❌ Неверный формат. Введите целое число или /cancel для отмены.")
        return
    
    await state.clear()

# ============= Изменение срока подписки =============

@router.callback_query(F.data == "admin_change_days")
async def change_days_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение срока подписки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        f"📅 <b>Изменение срока подписки</b>\n\n"
        f"Текущий срок: <b>{config.SUBSCRIPTION_DAYS} дней</b>\n\n"
        f"Отправьте новый срок в днях (целое число):\n\n"
        f"Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_subscription_days)
    await callback.answer()

@router.message(AdminStates.waiting_for_subscription_days, Command("cancel"))
async def change_days_cancel(message: Message, state: FSMContext):
    """Отмена изменения срока"""
    await state.clear()
    await message.answer(
        "❌ Изменение срока отменено",
        reply_markup=get_admin_keyboard()
    )

@router.message(AdminStates.waiting_for_subscription_days)
async def change_days_process(message: Message, state: FSMContext):
    """Обработка изменения срока подписки"""
    try:
        new_days = int(message.text.strip())
        
        if new_days < 1:
            await message.answer("❌ Срок должен быть больше 0. Попробуйте снова или /cancel для отмены.")
            return
        
        if new_days > 365:
            await message.answer("❌ Максимальный срок 365 дней. Попробуйте снова или /cancel для отмены.")
            return
        
        old_days = config.SUBSCRIPTION_DAYS
        config.update_subscription_days(new_days)
        
        await message.answer(
            f"✅ <b>Срок подписки успешно изменён!</b>\n\n"
            f"Было: <b>{old_days} дней</b>\n"
            f"Стало: <b>{new_days} дней</b>\n\n"
            f"💡 Изменения применятся к новым подпискам.",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        
        logger.success(f"📅 Admin {message.from_user.id} changed subscription days: {old_days} → {new_days}")
        
    except ValueError:
        await message.answer("❌ Неверный формат. Введите целое число или /cancel для отмены.")
        return
    
    await state.clear()

# ============= Удаление подписки =============

@router.callback_query(F.data.startswith("admin_delete_"))
async def delete_subscription(callback: CallbackQuery, bot: Bot):
    """Удалить подписку пользователя"""
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
    """Вернуться в главное меню"""
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
    """Закрыть админ-панель"""
    await state.clear()
    await callback.message.delete()
    await callback.answer("❌ Панель закрыта")

# ============= Дополнительные команды =============

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Быстрая статистика"""
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