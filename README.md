# 🤖 Slivrg — Telegram Subscription Bot

> Telegram-бот для управления платными подписками на приватный канал с поддержкой оплаты через **Telegram Stars** и **криптовалюту (Crypto Bot)**.

---

## 📋 Оглавление

- [Описание](#-описание)
- [Архитектура](#-архитектура)
- [Стек технологий](#-стек-технологий)
- [Структура проекта](#-структура-проекта)
- [Функциональность](#-функциональность)
- [Установка и запуск](#-установка-и-запуск)
- [Переменные окружения](#-переменные-окружения)
- [Команды бота](#-команды-бота)
- [Админ-панель](#-админ-панель)
- [Деплой](#-деплой)

---

## 📖 Описание

**Slivrg** — полнофункциональный Telegram-бот, реализующий систему платного доступа к приватному каналу/чату. Бот автоматизирует весь цикл подписки:

1. Пользователь выбирает способ оплаты (Stars или крипта)
2. После оплаты получает уникальную одноразовую invite-ссылку
3. При входе в канал ссылка автоматически отзывается
4. Планировщик следит за истечением подписок: отправляет напоминания и удаляет неоплативших пользователей

---

## 🏗 Архитектура

Проект построен на **модульной архитектуре** с чётким разделением ответственности:

```
┌──────────────────────────────────────────────────┐
│                   main.py                        │
│         (точка входа, инициализация)             │
├──────────┬──────────┬──────────┬─────────────────┤
│  start   │ payment  │  chat    │     admin       │
│ handler  │ handler  │ member   │    handler      │
│          │          │ handler  │                 │
├──────────┴──────────┴──────────┴─────────────────┤
│          subscription_service.py                 │
│          (бизнес-логика подписок)                │
├──────────────────────┬───────────────────────────┤
│    database.py       │   crypto_service.py       │
│   (SQLite + CRUD)    │  (Crypto Bot API)         │
├──────────────────────┴───────────────────────────┤
│               config.py                          │
│      (конфигурация из .env)                      │
├──────────────────────────────────────────────────┤
│     schedulers/subscription_checker.py           │
│   (периодические проверки каждые 30 мин)         │
└──────────────────────────────────────────────────┘
```

---

## 🛠 Стек технологий

| Компонент | Технология | Версия |
|---|---|---|
| Фреймворк бота | [aiogram](https://github.com/aiogram/aiogram) | 3.7.0 |
| База данных | [aiosqlite](https://github.com/omnilib/aiosqlite) (SQLite) | 0.20.0 |
| Планировщик задач | [APScheduler](https://github.com/agronholm/apscheduler) | 3.10.4 |
| Крипто-платежи | [aiocryptopay](https://github.com/LulzLoL231/aiocryptopay) | 0.4.8 |
| HTTP-клиент | [aiohttp](https://github.com/aio-libs/aiohttp) | 3.9.5 |
| Конфигурация | [python-dotenv](https://github.com/theskumar/python-dotenv) | 1.0.1 |
| Логирование | [loguru](https://github.com/Delgan/loguru) | 0.7.2 |
| Язык | Python | 3.11.12 |

---

## 📂 Структура проекта

```
slivrg/
├── handlers/                        # Обработчики команд и событий
│   ├── __init__.py                  # Пакетный файл
│   ├── start_handler.py             # /start, /status
│   ├── payment_handler.py           # /subscribe, оплата Stars & Crypto
│   ├── chat_member_handler.py       # Отслеживание входа/выхода из канала
│   └── admin_handler.py             # /admin — полная админ-панель
│
├── schedulers/
│   └── subscription_checker.py      # Автопроверка подписок (каждые 30 мин)
│
├── config.py                        # Конфигурация (из .env + runtime-обновления)
├── database.py                      # Работа с БД (SQLite, 3 таблицы)
├── crypto_service.py                # Интеграция с Crypto Bot (@CryptoBot)
├── subscription_service.py          # Бизнес-логика подписок
├── main.py                          # Точка входа
│
├── Dockerfile                       # Docker-образ (python:3.11-slim)
├── Procfile                         # Heroku / Railway deploy
├── runtime.txt                      # Python runtime версия
└── requirements.txt                 # Зависимости
```

---

## ⚡ Функциональность

### 👤 Пользовательские функции

| Функция | Описание |
|---|---|
| `/start` | Приветствие и список команд |
| `/subscribe` | Покупка подписки (выбор способа оплаты) |
| `/status` | Проверка статуса подписки (дней осталось, дата истечения) |

### 💳 Способы оплаты

- **Telegram Stars (XTR)** — нативная оплата через Telegram
  - Используется `answer_invoice` с валютой `XTR`
  - Поддержка `pre_checkout_query` для подтверждения
- **Криптовалюта через @CryptoBot** — TON, USDT, BTC, ETH
  - Создание инвойса через Crypto Bot API
  - Автоматическая проверка оплаты (polling каждые 5 сек, до 10 минут)
  - Ручная кнопка «Проверить оплату»

### 🔗 Система invite-ссылок

- Уникальная одноразовая ссылка (`member_limit=1`)
- Срок действия — 30 минут (настраивается)
- Автоматический отзыв после входа в канал
- Защита от использования чужой ссылки (проверка `user_id`)
- Несанкционированные пользователи автоматически кикаются

### ⏰ Планировщик (каждые 30 мин)

- **Напоминания** — за 3 дня до истечения подписки
- **Удаление** — кик из канала через 48 часов после истечения
- Уведомление пользователя о кике с предложением продлить

### 🛡 Админ-панель (`/admin`)

| Раздел | Возможности |
|---|---|
| 📊 Статистика | Активные подписчики, истекающие, просроченные, доход по валютам |
| 👥 Подписчики | Список активных пользователей (до 10 с пагинацией) |
| 💰 Доход | Детальная финансовая сводка (Stars с комиссией 30%, крипта) |
| 💎 Crypto баланс | Реалтайм-баланс кошелька Crypto Bot |
| 🔍 Поиск | Поиск пользователя по Telegram ID |
| 📢 Рассылка | Отправка сообщения всем активным подписчикам |
| ⚙️ Настройки | Изменение цен (Stars/TON/USDT), срока подписки |
| 🗑️ Удаление | Удаление подписки + кик пользователя |

---

## 🚀 Установка и запуск

### Предварительные требования

- Python 3.11+
- Telegram Bot Token (от [@BotFather](https://t.me/BotFather))
- ID приватного канала/чата
- *(Опционально)* Crypto Bot Token (от [@CryptoBot](https://t.me/CryptoBot))

### Локальный запуск

```bash
# 1. Клонировать репозиторий
git clone https://github.com/daskie911/slivrg.git
cd slivrg

# 2. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Создать файл .env (см. раздел «Переменные окружения»)
cp .env.example .env
# Отредактировать .env

# 5. Запустить бота
python main.py
```

### Запуск через Docker

```bash
# Сборка образа
docker build -t slivrg-bot .

# Запуск контейнера
docker run -d \
  --name slivrg \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  slivrg-bot
```

---

## 🔐 Переменные окружения

Создайте файл `.env` в корне проекта:

```env
# === Обязательные ===
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
ADMIN_IDS=123456789,987654321
CHANNEL_ID=-1001234567890

# === База данных ===
DATABASE_PATH=./data/subscriptions.db

# === Цены ===
STARS_PRICE=100
CRYPTO_PRICE_TON=1.5
CRYPTO_PRICE_USDT=2.0

# === Crypto Bot (опционально) ===
CRYPTO_BOT_TOKEN=your_crypto_bot_token
```

| Переменная | Тип | По умолчанию | Описание |
|---|---|---|---|
| `BOT_TOKEN` | `str` | — | Токен Telegram-бота |
| `ADMIN_IDS` | `str` | — | ID администраторов через запятую |
| `CHANNEL_ID` | `int` | — | ID приватного канала |
| `DATABASE_PATH` | `str` | `./data/subscriptions.db` | Путь к файлу SQLite |
| `STARS_PRICE` | `int` | `100` | Цена в Telegram Stars |
| `CRYPTO_PRICE_TON` | `float` | `1.5` | Цена в TON |
| `CRYPTO_PRICE_USDT` | `float` | `2.0` | Цена в USDT |
| `CRYPTO_BOT_TOKEN` | `str` | `""` | Токен Crypto Bot (пусто = отключено) |

> **Примечание:** Цены BTC и ETH рассчитываются приблизительно от `CRYPTO_PRICE_USDT`.

---

## 💬 Команды бота

### Пользовательские команды

| Команда | Описание |
|---|---|
| `/start` | Приветствие и список доступных команд |
| `/subscribe` | Открыть меню покупки подписки |
| `/status` | Проверить статус текущей подписки |

### Администраторские команды

| Команда | Описание |
|---|---|
| `/admin` | Открыть полную админ-панель (Inline-клавиатура) |
| `/stats` | Быстрая статистика (количество активных подписчиков) |

---

## 🗄 База данных

SQLite с тремя таблицами:

### `subscriptions`
Хранит данные подписок пользователей.

| Поле | Тип | Описание |
|---|---|---|
| `user_id` | INTEGER PK | Telegram ID пользователя |
| `username` | TEXT | Username или имя |
| `subscription_until` | TEXT (ISO 8601) | Дата окончания подписки |
| `invite_link` | TEXT | Текущая invite-ссылка (NULL после использования) |
| `invite_created_at` | TEXT | Дата создания ссылки |
| `payment_status` | TEXT | Статус (`pending` / `paid`) |

### `payments`
Лог всех платежей.

| Поле | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | Автоинкремент |
| `user_id` | INTEGER | Telegram ID |
| `amount` | REAL | Сумма |
| `currency` | TEXT | Валюта (XTR, TON, USDT, BTC, ETH) |
| `payment_method` | TEXT | Метод (`stars` / `crypto`) |
| `telegram_payment_charge_id` | TEXT | ID платежа Stars |
| `crypto_invoice_id` | TEXT | ID инвойса Crypto Bot |

### `pending_crypto_payments`
Ожидающие крипто-платежи.

| Поле | Тип | Описание |
|---|---|---|
| `invoice_id` | INTEGER | ID инвойса в Crypto Bot |
| `status` | TEXT | `pending` / `completed` |
| `expires_at` | TEXT | Срок действия (10 минут) |

---

## 🚢 Деплой

### Railway / Heroku

Проект содержит `Procfile` и `runtime.txt`, готов к деплою:

```
worker: python main.py
```

Добавьте переменные окружения в настройках платформы.

### Docker

```bash
docker build -t slivrg-bot .
docker run -d --env-file .env -v ./data:/app/data slivrg-bot
```

### VPS

```bash
# Через systemd
sudo nano /etc/systemd/system/slivrg.service
```

```ini
[Unit]
Description=Slivrg Telegram Bot
After=network.target

[Service]
User=your_user
WorkingDirectory=/path/to/slivrg
ExecStart=/path/to/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable slivrg
sudo systemctl start slivrg
```

---

## ⚠️ Важные замечания

- **Бот должен быть администратором** приватного канала с правами на приглашение пользователей и управление участниками.
- **Telegram Stars** — комиссия Telegram составляет ~30% (учтено в админ-панели).
- **Crypto Bot** — если токен не указан, крипто-платежи автоматически отключаются.
- **FSM (MemoryStorage)** — состояния хранятся в памяти; при перезапуске бота незавершённые диалоги сбрасываются.
- **Логирование** — stdout (INFO) + файл `logs/bot.log` (DEBUG, ротация 10 МБ, хранение 7 дней).

---

## 📄 Лицензия

Проект распространяется без указанной лицензии. Свяжитесь с автором для уточнения условий использования.

---

<p align="center">
  Разработано <a href="https://github.com/daskie911">@daskie911</a>
</p>
