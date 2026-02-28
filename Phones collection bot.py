import os
import sqlite3
import asyncio
import logging
import random
import json
from datetime import datetime, timedelta
from typing import Optional
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ТОКЕНЫ
BOT_TOKEN = os.getenv('PHONES_BOT_TOKEN', '')  # Создай нового бота через @BotFather
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x]

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# РЕДКОСТИ (как в оригинале)
RARITIES = {
    0: {'name': '📱 Шифротребность', 'color': '⬜️', 'chance': 40.0, 'upgrade_chance': 50.0},
    1: {'name': '📱 Необычный', 'color': '🟦', 'chance': 30.0, 'upgrade_chance': 40.0},
    2: {'name': '⭐ Редкий', 'color': '🟧', 'chance': 15.0, 'upgrade_chance': 30.0},
    3: {'name': '✨ Мистический', 'color': '🟪', 'chance': 8.0, 'upgrade_chance': 20.0},
    4: {'name': '💎 Хроматический', 'color': '🟥', 'chance': 5.0, 'upgrade_chance': 10.0},
    5: {'name': '🏆 Аркана', 'color': '🟨', 'chance': 1.8, 'upgrade_chance': 5.0},
    6: {'name': '🎨 Раритет', 'color': '🟩', 'chance': 0.19, 'upgrade_chance': 2.0},
    7: {'name': '🌟 Легенда', 'color': '⬛️', 'chance': 0.01, 'upgrade_chance': 0.0},
}

# БАЗА ТЕЛЕФОНОВ (из phonesDB.json)
PHONES_DB = {
    0: {
        "Apple iPhone 3G": 800, "Apple iPhone 4": 900, "Apple iPhone 5c": 1200,
        "Apple iPhone 7": 2000, "Samsung Galaxy S4": 800, "Samsung Galaxy Note 4": 1500,
        "HTC One M7": 1000, "Sony Xperia Z": 1000, "Xiaomi Redmi 1S": 850,
    },
    1: {
        "Apple iPhone 5": 3000, "Apple iPhone 6": 4000, "Apple iPhone 6s": 4900,
        "Apple iPhone 8": 4500, "Samsung Galaxy S7": 3500, "Xiaomi Redmi Note 5": 3500,
        "OnePlus 6": 4000, "Google Pixel 3a": 3500,
    },
    2: {
        "Apple iPhone X": 10000, "Apple iPhone 11": 11500, "Apple iPhone 12": 16890,
        "Apple iPhone 13": 20000, "Samsung Galaxy S9": 10000, "OnePlus 7 Pro": 10000,
        "Xiaomi Mi 11": 10000, "Google Pixel 6": 12000,
    },
    3: {
        "Apple iPhone 13 Pro": 35000, "Apple iPhone 14": 30000, "Apple iPhone 15": 53000,
        "Samsung Galaxy S22 Ultra": 55000, "Xiaomi Mi 11 Ultra": 31000,
        "OnePlus 9 Pro": 31000, "Google Pixel 7 Pro": 53000,
    },
    4: {
        "Apple iPhone 14 Pro Max": 95000, "Apple iPhone 16": 85000,
        "Samsung Galaxy S23 Ultra": 105000, "Xiaomi 13 Ultra": 110000,
        "Google Pixel 8 Pro": 85000, "OnePlus 12": 80000,
    },
    5: {
        "Apple iPhone 15 Pro Max": 200000, "Apple iPhone 16 Pro Max": 230000,
        "Samsung Galaxy S25 Ultra": 215000, "Xiaomi 15 Ultra": 220000,
        "OnePlus 13": 200000, "Google Pixel 9 Pro XL": 200000,
    },
    6: {
        "Xiaomi Mi Mix Alpha": 500000, "Samsung K Zoom": 500000,
        "Яндекс.Телефон": 500000, "Nokia 3310": 500000,
        "Apple iPhone 5s Gold Edition": 500000,
    },
    7: {
        "Apple iPhone 9": 3000000, "Nokia Lumia McLaren": 3000000,
        "Google Project Ara": 3000000, "Nokia 888 Concept": 3000000,
    }
}


class BotStates(StatesGroup):
    choosing_shop = State()
    choosing_rarity = State()
    choosing_phone = State()
    upgrading_phone = State()
    trading = State()
    admin_broadcast = State()




def init_db():
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    
    # Пользователи
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            points INTEGER DEFAULT 500,
            cards INTEGER DEFAULT 1,
            total_phones INTEGER DEFAULT 0,
            achievements INTEGER DEFAULT 0,
            farm_income INTEGER DEFAULT 0,
            last_card TIMESTAMP,
            last_daily TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
   
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_phones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            phone_name TEXT,
            rarity INTEGER,
            price INTEGER,
            obtained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
  
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            achievement_type TEXT,
            unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()


def create_user(user_id: int, username: str, first_name: str):
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)',
                   (user_id, username, first_name))
    conn.commit()
    conn.close()


def get_user(user_id: int):
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def update_points(user_id: int, amount: int):
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET points = points + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()


def get_points(user_id: int) -> int:
    user = get_user(user_id)
    return user[3] if user else 0


def add_phone(user_id: int, phone_name: str, rarity: int, price: int):
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO user_phones (user_id, phone_name, rarity, price)
                      VALUES (?, ?, ?, ?)''', (user_id, phone_name, rarity, price))
    cursor.execute('UPDATE users SET total_phones = total_phones + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()


def get_user_phones(user_id: int, rarity: int = None):
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    if rarity is not None:
        cursor.execute('SELECT * FROM user_phones WHERE user_id = ? AND rarity = ? ORDER BY price DESC',
                       (user_id, rarity))
    else:
        cursor.execute('SELECT * FROM user_phones WHERE user_id = ? ORDER BY rarity DESC, price DESC',
                       (user_id,))
    phones = cursor.fetchall()
    conn.close()
    return phones


def delete_phone(phone_id: int):
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_phones WHERE id = ?', (phone_id,))
    conn.commit()
    conn.close()


def get_random_phone(rarity: int):
    phones = PHONES_DB.get(rarity, {})
    if not phones:
        return None, 0
    phone_name = random.choice(list(phones.keys()))
    price = phones[phone_name]
    return phone_name, price


def calculate_rarity():
    """Определяет редкость на основе шансов"""
    rand = random.uniform(0, 100)
    cumulative = 0
    for rarity in sorted(RARITIES.keys()):
        cumulative += RARITIES[rarity]['chance']
        if rand <= cumulative:
            return rarity
    return 0




def main_keyboard():
    keyboard = [
        [KeyboardButton(text="🎴 ТКарточка"), KeyboardButton(text="👤 ТАкк")],
        [KeyboardButton(text="📱 Мои телефоны"), KeyboardButton(text="🏪 Магазин телефонов")],
        [KeyboardButton(text="⬆️ Апгрейд"), KeyboardButton(text="🎁 Ежедневная награда")],
        [KeyboardButton(text="⛏️ ТМайнинг"), KeyboardButton(text="🏆 Таблица лидеров")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def shop_keyboard():
    buttons = []
    for r in range(6):  
        buttons.append([InlineKeyboardButton(
            text=f"{RARITIES[r]['name']}",
            callback_data=f"shop_{r}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def phones_list_keyboard(user_id: int, rarity: int, page: int = 0):
    phones = get_user_phones(user_id, rarity)
    buttons = []
    
    items_per_page = 5
    start = page * items_per_page
    end = start + items_per_page
    
    for phone in phones[start:end]:
        phone_id, _, phone_name, r, price, _ = phone
        buttons.append([InlineKeyboardButton(
            text=f"{phone_name} ({price:,})",
            callback_data=f"phone_{phone_id}"
        )])
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"myphones_{rarity}_{page-1}"))
    if end < len(phones):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"myphones_{rarity}_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_myphones")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def rarity_select_keyboard():
    buttons = []
    for r in range(7):
        buttons.append([InlineKeyboardButton(
            text=RARITIES[r]['name'],
            callback_data=f"myrarity_{r}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def shop_phones_keyboard(rarity: int, page: int = 0):
    phones = list(PHONES_DB.get(rarity, {}).items())
    buttons = []
    
    items_per_page = 5
    start = page * items_per_page
    end = start + items_per_page
    
    for phone_name, price in phones[start:end]:
        buttons.append([InlineKeyboardButton(
            text=f"{phone_name} - {price:,} ТОчек",
            callback_data=f"buy_{rarity}_{phone_name}"
        )])

    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"shop_{rarity}_{page-1}"))
    if end < len(phones):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"shop_{rarity}_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton(text="🔙 К редкостям", callback_data="back_shop")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def buy_confirm_keyboard(rarity: int, phone_name: str):
    buttons = [
        [InlineKeyboardButton(text="✅ Купить", callback_data=f"confirm_buy_{rarity}_{phone_name}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"shop_{rarity}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)




@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    create_user(user_id, username, first_name)
    
    # Устанавливаем команды бота в меню
    commands = [
        types.BotCommand(command="start", description="Приветственное сообщение"),
        types.BotCommand(command="tcard", description="Получить карточку"),
        types.BotCommand(command="pay", description="Передать ТОчки другому игроку"),
        types.BotCommand(command="paycoin", description="Передать T-Coins другому игроку"),
        types.BotCommand(command="trade", description="Начать обмен"),
        types.BotCommand(command="sellall", description="Продать все телефоны"),
        types.BotCommand(command="avito", description="Вторичный рынок"),
        types.BotCommand(command="tfarm", description="Майнинг ферма"),
    ]
    await bot.set_my_commands(commands)
    
    bot_info = await bot.get_me()
    
 
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Помощь 📚", callback_data="help_menu")],
        [InlineKeyboardButton(text="➕ Добавить бота в чат", url=f"https://t.me/{bot_info.username}?startgroup=true")]
    ])
    
    await message.answer_photo(
        photo="https://i.imgur.com/XKZqYwH.jpg", 
        caption=f"👋 Добро пожаловать, @{username}!\n\n"
                f"🎴 Наш бот представляет из себя инструмент для "
                f"коллекционирования различных моделей телефонов: от старого "
                f"хлама до новых ультра флагманов.\n\n"
                f"📱 Чтобы открыть вашу первую карточку напишите \"ТКарточка\".\n\n"
                f"🎯 Используйте одну из кнопок ниже для взаимодействия с функциями:",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "help_menu")
async def help_menu_callback(callback: types.CallbackQuery):
    """Меню помощи"""
    
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM user_phones')
    total_phones = cursor.fetchone()[0]
    conn.close()
    
  
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Вернуться назад", callback_data="back_start")]
    ])
    
    await callback.message.edit_caption(
        caption=f"ℹ️ <b>Наш бот представляет из себя инструмент для "
                f"коллекционирования различных моделей телефонов: от старого "
                f"хлама до новых ультра флагманов.</b>\n\n"
                f"👥 <b>Создатели бота:@usmonxadjaevv</b>\n\n"
                f"• Владелец:\n"
                f"@hyper3os\n\n"
                f"• Дизайнеры:\n"
                f"@usmonxadjaevv\n\n"
                f"🆘 <b>Нужна помощь, нашли ошибку или хотите предложить "
                f"идею? Напишите нашей оперативной поддержке:</b>\n"
                f"@hyper3os\n\n" +
                f"<b>📱 СПИСОК КОМАНД:</b>\n\n"
                f'• "ТКарточка" - позволяет забрать карточку с телефоном, доступную раз в определённый промежуток времени.\n'
                f'• "ТАкк" - выводит подробную статистику человека, написавшего команду.\n'
                f'• "Мои телефоны" - открывает список всех устройств в вашем владении.\n'
                f'• "Магазин телефонов" - магазин всех телефонов вплоть до Арканы.\n'
                f'• "Магазин улучшений" - магазин прокачки игровых условностей.\n'
                f'• "Апгрейд" - позволяет улучшить ваш телефон до следующей редкости с фиксированным шансом.\n'
                f'• "Ежедневная награда" - позволяет забрать бесплатную награду, доступную каждые 24 часа.\n'
                f'• "Таблица лидеров" - показывает топ-10 игроков по разным параметрам.\n'
                f'• "/pay @юзернейм" - команда позволяет перевести любое количество валюты другому игроку.\n'
                f'• "/event" - отображает текущий розыгрыш.\n'
                f'• "/sellall" - открывает меню продажи всех телефонов одной редкости.\n'
                f'• "/trade @юзернейм" - позволяет начать обмен с другим игроком.\n'
                f'• "/avito" или "авито" - открывает вторичный рынок.\n'
                f'• "/avito @юзернейм" - открывает объявления игрока, юзернейм которого вы указали.\n'
                f'• "/tfarm" или "тмайнинг" - открывает вашу майнинг ферму.\n'
                f'• "/achievements" или "достижения" - открывает список достижений.\n'
                f'• "/donate" или "донат" - открывает каталог доступных к покупке статусов.\n'
                f'• "/roulette" - выводит донатную рулетку.\n'
                f'• "/tconfig" - открывает конфигурацию различных параметров.\n'
                f'• "/tinfo" или "тинфо" - показывает техническую информацию сервера.\n'
                f'• "/ping" или "пинг" - пингануть бота.',
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "commands_list")
async def commands_list_callback(callback: types.CallbackQuery):
    """Список команд"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="help_menu")]
    ])
    
    await callback.message.edit_caption(
        caption="<b>📋 Команды бота:</b>\n\n"
                "<b>🎮 Основные:</b>\n"
                "• /start - Приветственное сообщение\n"
                "• /tcard - Получить карточку\n"
                "• /pay @user сумма - Перевести ТОчки другому игроку\n"
                "• /paycoin @user сумма - Перевести T-Coins другому игроку\n\n"
                "<b>📱 Коллекция:</b>\n"
                "• ТАкк - Ваш профиль\n"
                "• Мои телефоны - Ваша коллекция\n"
                "• Магазин телефонов - Купить телефон\n"
                "• Апгрейд - Улучшить телефон\n\n"
                "<b>💰 Экономика:</b>\n"
                "• Ежедневная награда - Получить бонус\n"
                "• /sellall - Продать все телефоны редкости\n\n"
                "<b>🎯 Дополнительно:</b>\n"
                "• Таблица лидеров - Топ игроков\n"
                "• /tfarm - Майнинг ферма\n"
                "• /trade @user - Обмен телефонами\n"
                "• /avito - Вторичный рынок\n"
                "• /achievements - Достижения\n"
                "• /tinfo - Информация о боте\n"
                "• /ping - Проверка связи",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "about_bot")
async def about_bot_callback(callback: types.CallbackQuery):
    """О боте"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="help_menu")]
    ])
    
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM user_phones')
    total_phones = cursor.fetchone()[0]
    conn.close()
    
    await callback.message.edit_caption(
        caption=f"ℹ️ <b>Наш бот представляет из себя инструмент для "
                f"коллекционирования различных моделей телефонов: от старого "
                f"хлама до новых ультра флагманов.</b>\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"👥 Пользователей: {total_users:,}\n"
                f"📱 Телефонов выдано: {total_phones:,}",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "creators")
async def creators_callback(callback: types.CallbackQuery):
    """Создатели"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="help_menu")]
    ])
    
    await callback.message.edit_caption(
        caption="👥 <b>Создатели бота:</b>\n\n"
                "• Владелец, главный кодер и дизайнер:\n"
                "@твой_username\n\n"
                "🆘 <b>Нужна помощь, нашли ошибку или хотите предложить "
                "идею? Напишите нашей оперативной поддержке:</b>\n"
                "@твой_support_username",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "back_start")
async def back_start_callback(callback: types.CallbackQuery):
    """Возврат к приветствию"""
    username = callback.from_user.username or ""
    bot_info = await bot.get_me()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Помощь 📚", callback_data="help_menu")],
        [InlineKeyboardButton(text="➕ Добавить бота в чат", url=f"https://t.me/{bot_info.username}?startgroup=true")]
    ])
    
    await callback.message.edit_caption(
        caption=f"👋 Добро пожаловать, @{username}!\n\n"
                f"🎴 Наш бот представляет из себя инструмент для "
                f"коллекционирования различных моделей телефонов: от старого "
                f"хлама до новых ультра флагманов.\n\n"
                f"📱 Чтобы открыть вашу первую карточку напишите \"ТКарточка\".\n\n"
                f"🎯 Используйте одну из кнопок ниже для взаимодействия с функциями:",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.message(Command("tcard"))
@dp.message(F.text.in_(["ТКарточка", "тк", "TC", "tc"]))
async def get_card_tcard(message: types.Message):
    """Алиас для /tcard"""
    await get_card(message)


@dp.message(F.text.in_(["ТКарточка", "тк", "TC", "tc"]))
async def get_card(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        await message.answer("❌ Используйте /start сначала!")
        return
    
    last_card = user[8]
    if last_card:
        last_time = datetime.fromisoformat(last_card)
        next_time = last_time + timedelta(hours=3)  # 3 часа cooldown
        now = datetime.now()
        
        if now < next_time:
            diff = next_time - now
            hours = int(diff.total_seconds() // 3600)
            minutes = int((diff.total_seconds() % 3600) // 60)
            seconds = int(diff.total_seconds() % 60)
            
            await message.answer(
                f"⏰ Следующая карточка будет доступна через:\n"
                f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            )
            return
    
    # Выдаём случайный телефон
    rarity = calculate_rarity()
    phone_name, price = get_random_phone(rarity)
    
    if not phone_name:
        await message.answer("❌ Ошибка! Попробуйте позже.")
        return
    
    add_phone(user_id, phone_name, rarity, price)
    
    # Обновляем время последней карточки
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET last_card = ?, cards = cards + 1 WHERE user_id = ?',
                   (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()
    
    rarity_name = RARITIES[rarity]['name']
    
    await message.answer(
        f"@{message.from_user.username} Вам выпал телефон!\n\n"
        f"{RARITIES[rarity]['color']} <b>{phone_name}</b>\n"
        f"{rarity_name} | Цена: <b>{price:,} ТОчек</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Действия", callback_data=f"phone_actions_{phone_id}")]
        ])
    )


@dp.message(F.text.in_(["ТАкк", "та", "TA", "ta"]))
async def show_account(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        await message.answer("❌ Используйте /start сначала!")
        return
    
    points = user[3]
    cards = user[4]
    total_phones = user[5]
    
    # Считаем общую стоимость телефонов
    phones = get_user_phones(user_id)
    total_value = sum(phone[4] for phone in phones)
    
    await message.answer(
        f"<b>@{message.from_user.username}</b>\n"
        f"<b>Место в топе:</b> #???\n"
        f"<b>ТОчек:</b> {points:,}\n"
        f"<b>Карточек:</b> {cards}\n\n"
        f"👤 <b>Профиль:</b> @{message.from_user.username}\n"
        f"📊 <b>Статус:</b> Обычный\n"
        f"💰 <b>ТОчки:</b> {points:,}\n"
        f"📱 <b>Общая стоимость телефонов:</b> {total_value:,}\n"
        f"📲 <b>Телефонов в коллекции:</b> {total_phones}\n"
        f"🏆 <b>Выполнено достижений:</b> 0"
    )


@dp.message(F.text.in_(["Мои телефоны", "мо", "mp", "МО", "MP"]))
async def my_phones(message: types.Message):
    user_id = message.from_user.id
    phones = get_user_phones(user_id)
    
    if not phones:
        await message.answer("📱 У вас пока нет телефонов! Используйте 🎴 ТКарточка")
        return
    
    await message.answer(
        "📱 <b>Мои телефоны</b>\n\nВыберите редкость:",
        reply_markup=rarity_select_keyboard()
    )


@dp.callback_query(F.data.startswith("myrarity_"))
async def show_rarity_phones(callback: types.CallbackQuery):
    rarity = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    phones = get_user_phones(user_id, rarity)
    
    if not phones:
        await callback.answer(f"У вас нет телефонов редкости {RARITIES[rarity]['name']}", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"📱 <b>{RARITIES[rarity]['name']}</b>\n\nВаши телефоны:",
        reply_markup=phones_list_keyboard(user_id, rarity, 0)
    )
    await callback.answer()


@dp.message(F.text.in_(["Магазин телефонов", "мт", "ps", "МТ", "PS"]))
async def shop(message: types.Message):
    await message.answer(
        "🏪 <b>Магазин телефонов</b>\n\nВыберите редкость:",
        reply_markup=shop_keyboard()
    )


@dp.message(F.text.in_(["Магазин улучшений", "му", "us", "МУ", "US"]))
async def upgrades_shop(message: types.Message):
    """Магазин прокачки игровых условностей"""
    user_id = message.from_user.id
    user = get_user(user_id)
    points = user[3] if user else 0
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ Уменьшить кулдаун карточки", callback_data="upgrade_card_cooldown")],
        [InlineKeyboardButton(text="💰 Увеличить награду", callback_data="upgrade_daily_reward")],
        [InlineKeyboardButton(text="⛏️ Улучшить майнинг ферму", callback_data="upgrade_farm")],
        [InlineKeyboardButton(text="🎯 Увеличить шанс апгрейда", callback_data="upgrade_chance")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await message.answer(
        "🏪 <b>Магазин улучшений</b>\n\n"
        f"💰 Ваш баланс: {points:,} ТОчек\n\n"
        "Выберите улучшение:",
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("upgrade_"))
async def process_upgrade_purchase(callback: types.CallbackQuery):
    upgrade_type = callback.data.replace("upgrade_", "")
    
    upgrades = {
        "card_cooldown": {"name": "Уменьшение кулдауна карточки", "price": 5000, "desc": "⏱ С 3 часов до 2.5 часов"},
        "daily_reward": {"name": "Увеличение ежедневной награды", "price": 3000, "desc": "💰 Со 100 до 150 ТОчек"},
        "farm": {"name": "Улучшение майнинг фермы", "price": 10000, "desc": "⛏️ Доход +50 ТОчек/сутки"},
        "chance": {"name": "Увеличение шанса апгрейда", "price": 15000, "desc": "🎯 +5% к шансу успеха"}
    }
    
    if upgrade_type not in upgrades:
        await callback.answer("❌ Неизвестное улучшение!")
        return
    
    upgrade = upgrades[upgrade_type]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Купить", callback_data=f"confirm_upgrade_{upgrade_type}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="back_upgrades")]
    ])
    
    await callback.message.edit_text(
        f"🏪 <b>{upgrade['name']}</b>\n\n"
        f"{upgrade['desc']}\n\n"
        f"💰 Цена: {upgrade['price']:,} ТОчек\n\n"
        f"⚠️ Функция в разработке!",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "back_upgrades")
async def back_upgrades(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    points = user[3] if user else 0
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ Уменьшить кулдаун карточки", callback_data="upgrade_card_cooldown")],
        [InlineKeyboardButton(text="💰 Увеличить награду", callback_data="upgrade_daily_reward")],
        [InlineKeyboardButton(text="⛏️ Улучшить майнинг ферму", callback_data="upgrade_farm")],
        [InlineKeyboardButton(text="🎯 Увеличить шанс апгрейда", callback_data="upgrade_chance")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await callback.message.edit_text(
        "🏪 <b>Магазин улучшений</b>\n\n"
        f"💰 Ваш баланс: {points:,} ТОчек\n\n"
        "Выберите улучшение:",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("shop_"))
async def show_shop_rarity(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    rarity = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0
    
    await callback.message.edit_text(
        f"🏪 <b>{RARITIES[rarity]['name']}</b>\n\nДоступные телефоны:",
        reply_markup=shop_phones_keyboard(rarity, page)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_"))
async def buy_phone_confirm(callback: types.CallbackQuery):
    parts = callback.data.split("_", 2)
    rarity = int(parts[1])
    phone_name = parts[2]
    price = PHONES_DB[rarity][phone_name]
    user_id = callback.from_user.id
    points = get_points(user_id)
    
    await callback.message.edit_text(
        f"📱 <b>{phone_name}</b>\n\n"
        f"{RARITIES[rarity]['name']}\n"
        f"💰 Цена: {price:,} ТОчек\n"
        f"💵 Ваш баланс: {points:,} ТОчек\n\n"
        f"Подтвердите покупку:",
        reply_markup=buy_confirm_keyboard(rarity, phone_name)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_buy_"))
async def confirm_buy(callback: types.CallbackQuery):
    parts = callback.data.split("_", 3)
    rarity = int(parts[2])
    phone_name = parts[3]
    price = PHONES_DB[rarity][phone_name]
    user_id = callback.from_user.id
    points = get_points(user_id)
    
    if points < price:
        await callback.answer(f"❌ Недостаточно ТОчек! Нужно: {price:,}", show_alert=True)
        return
    
    update_points(user_id, -price)
    add_phone(user_id, phone_name, rarity, price)
    
    await callback.message.edit_text(
        f"✅ <b>Покупка успешна!</b>\n\n"
        f"📱 {phone_name}\n"
        f"💰 Потрачено: {price:,} ТОчек\n"
        f"💵 Остаток: {get_points(user_id):,} ТОчек"
    )
    await callback.answer()


@dp.message(F.text.in_(["Апгрейд", "ап", "up", "АП", "UP"]))
async def upgrade_menu(message: types.Message):
    await message.answer(
        "⬆️ <b>Апгрейд телефона</b>\n\n"
        "Выберите редкость телефона который хотите улучшить:\n\n"
        "ℹ️ Шансы улучшения:\n"
        "📱 Шифротребность → Необычный: 50%\n"
        "📱 Необычный → Редкий: 40%\n"
        "⭐ Редкий → Мистический: 30%\n"
        "✨ Мистический → Хроматический: 20%\n"
        "💎 Хроматический → Аркана: 10%\n"
        "🏆 Аркана → Раритет: 5%\n"
        "🎨 Раритет → Легенда: 2%",
        reply_markup=rarity_select_keyboard()
    )


@dp.callback_query(F.data.startswith("upgrade_"))
async def perform_upgrade(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    phone_id = int(parts[1])
    
    user_id = callback.from_user.id
    
    # Получаем телефон
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM user_phones WHERE id = ? AND user_id = ?', (phone_id, user_id))
    phone = cursor.fetchone()
    
    if not phone:
        await callback.answer("❌ Телефон не найден!", show_alert=True)
        conn.close()
        return
    
    phone_id, _, phone_name, rarity, price, _ = phone
    
    if rarity >= 7:
        await callback.answer("❌ Это максимальная редкость!", show_alert=True)
        conn.close()
        return
    
    # Шанс апгрейда
    upgrade_chance = RARITIES[rarity]['upgrade_chance']
    success = random.uniform(0, 100) < upgrade_chance
    
    if success:
        # Успешный апгрейд
        new_rarity = rarity + 1
        new_phone, new_price = get_random_phone(new_rarity)
        
        # Удаляем старый телефон
        cursor.execute('DELETE FROM user_phones WHERE id = ?', (phone_id,))
        
        # Добавляем новый
        cursor.execute('''INSERT INTO user_phones (user_id, phone_name, rarity, price)
                          VALUES (?, ?, ?, ?)''', (user_id, new_phone, new_rarity, new_price))
        conn.commit()
        conn.close()
        
        await callback.message.edit_text(
            f"🎉 <b>УСПЕХ!</b>\n\n"
            f"Ваш телефон:\n"
            f"{RARITIES[rarity]['color']} {phone_name} ({price:,} ТОчек)\n\n"
            f"Улучшен до:\n"
            f"{RARITIES[new_rarity]['color']} {new_phone} ({new_price:,} ТОчек)\n\n"
            f"✨ Прибыль: +{new_price - price:,} ТОчек"
        )
    else:
        # Неудача - телефон потерян
        cursor.execute('DELETE FROM user_phones WHERE id = ?', (phone_id,))
        cursor.execute('UPDATE users SET total_phones = total_phones - 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        await callback.message.edit_text(
            f"😔 <b>НЕУДАЧА!</b>\n\n"
            f"Ваш телефон:\n"
            f"{RARITIES[rarity]['color']} {phone_name} ({price:,} ТОчек)\n\n"
            f"❌ Был утерян при улучшении...\n"
            f"💔 Потеря: -{price:,} ТОчек"
        )
    
    await callback.answer()


@dp.callback_query(F.data.startswith("phone_"))
async def show_phone_actions(callback: types.CallbackQuery):
    phone_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM user_phones WHERE id = ? AND user_id = ?', (phone_id, user_id))
    phone = cursor.fetchone()
    conn.close()
    
    if not phone:
        await callback.answer("❌ Телефон не найден!", show_alert=True)
        return
    
    _, _, phone_name, rarity, price, obtained_at = phone
    
    sell_price = int(price * 0.75)
    
    buttons = [
        [InlineKeyboardButton(text="⬆️ Улучшить", callback_data=f"upgrade_{phone_id}")],
        [InlineKeyboardButton(text="💰 Продать", callback_data=f"sell_{phone_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"myrarity_{rarity}")]
    ]
    
    await callback.message.edit_text(
        f"📱 <b>{phone_name}</b>\n\n"
        f"{RARITIES[rarity]['name']}\n"
        f"💰 Стоимость: {price:,} ТОчек\n"
        f"💸 Продать за: {sell_price:,} ТОчек\n"
        f"⬆️ Шанс улучшения: {RARITIES[rarity]['upgrade_chance']}%\n\n"
        f"Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("sell_"))
async def sell_phone(callback: types.CallbackQuery):
    phone_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM user_phones WHERE id = ? AND user_id = ?', (phone_id, user_id))
    phone = cursor.fetchone()
    
    if not phone:
        await callback.answer("❌ Телефон не найден!", show_alert=True)
        conn.close()
        return
    
    _, _, phone_name, rarity, price, _ = phone
    
    sell_price = int(price * 0.75)
    
    # Удаляем телефон и начисляем деньги
    cursor.execute('DELETE FROM user_phones WHERE id = ?', (phone_id,))
    cursor.execute('UPDATE users SET points = points + ?, total_phones = total_phones - 1 WHERE user_id = ?',
                   (sell_price, user_id))
    conn.commit()
    conn.close()
    
    await callback.message.edit_text(
        f"💰 <b>Продано!</b>\n\n"
        f"📱 {phone_name}\n"
        f"{RARITIES[rarity]['name']}\n\n"
        f"💸 Получено: {sell_price:,} ТОчек\n"
        f"💵 Ваш баланс: {get_points(user_id):,} ТОчек"
    )
    await callback.answer()


@dp.message(F.text.in_(["Ежедневная награда", "ен", "er", "ЕН", "ER"]))
async def daily_reward(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        await message.answer("❌ Используйте /start сначала!")
        return
    
    last_daily = user[9]
    if last_daily:
        last_time = datetime.fromisoformat(last_daily)
        next_time = last_time + timedelta(hours=24)
        now = datetime.now()
        
        if now < next_time:
            diff = next_time - now
            hours = int(diff.total_seconds() // 3600)
            minutes = int((diff.total_seconds() % 3600) // 60)
            
            await message.answer(
                f"⏰ Следующая награда будет доступна через:\n"
                f"{hours:02d}:{minutes:02d}:00"
            )
            return
    
    reward = 100
    update_points(user_id, reward)
    
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET last_daily = ? WHERE user_id = ?',
                   (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()
    
    await message.answer(
        f"🎁 <b>Ежедневная награда!</b>\n\n"
        f"Вы получили: <b>{reward} ТОчек</b>\n"
        f"💰 Баланс: {get_points(user_id):,} ТОчек"
    )


@dp.message(F.text.in_(["Таблица лидеров", "тл", "lb", "ТЛ", "LB"]))
async def leaderboard(message: types.Message):
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, first_name, username, points, total_phones
        FROM users
        ORDER BY points DESC
        LIMIT 10
    ''')
    leaders = cursor.fetchall()
    conn.close()
    
    if not leaders:
        await message.answer("🏆 Таблица лидеров пуста!")
        return
    
    text = "🏆 <b>ТОП-10 ИГРОКОВ</b>\n\n"
    medals = ["🥇", "🥈", "🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    
    for i, leader in enumerate(leaders):
        user_id, first_name, username, points, phones = leader
        medal = medals[i] if i < len(medals) else f"{i+1}."
        text += f"{medal} <b>{first_name}</b> @{username}\n"
        text += f"    💰 {points:,} ТОчек | 📱 {phones} телефонов\n\n"
    
    await message.answer(text)


@dp.message(F.text.in_(["/sellall", "са", "sa", "СА", "SA"]))
async def sellall_menu(message: types.Message):
    """Продажа всех телефонов одной редкости"""
    await message.answer(
        "💰 <b>Продать все телефоны</b>\n\n"
        "Выберите редкость телефонов для продажи:\n"
        "⚠️ Вы получите 75% от стоимости",
        reply_markup=rarity_select_keyboard()
    )


@dp.message(F.text.in_(["/pay", "п", "p", "П", "P"]))
async def pay_command(message: types.Message):
    """Перевод ТОчек другому игроку"""
    args = message.text.split()
    
    if len(args) < 3:
        await message.answer(
            "💸 <b>Перевод ТОчек</b>\n\n"
            "Использование:\n"
            "<code>/pay @username сумма</code>\n\n"
            "Пример:\n"
            "<code>/pay @friend 1000</code>"
        )
        return
    
    target_username = args[1].replace('@', '')
    try:
        amount = int(args[2])
    except:
        await message.answer("❌ Неверная сумма!")
        return
    
    if amount < 1:
        await message.answer("❌ Минимум 1 ТОчек!")
        return
    
    user_id = message.from_user.id
    points = get_points(user_id)
    
    if points < amount:
        await message.answer(f"❌ Недостаточно ТОчек! У вас: {points:,}")
        return
    
    # Найти получателя
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE username = ?', (target_username,))
    target = cursor.fetchone()
    conn.close()
    
    if not target:
        await message.answer(f"❌ Пользователь @{target_username} не найден!")
        return
    
    target_id = target[0]
    
    if target_id == user_id:
        await message.answer("❌ Нельзя перевести самому себе!")
        return
    
    # Переводим
    update_points(user_id, -amount)
    update_points(target_id, amount)
    
    await message.answer(
        f"✅ <b>Перевод выполнен!</b>\n\n"
        f"💸 Отправлено @{target_username}: {amount:,} ТОчек\n"
        f"💰 Ваш баланс: {get_points(user_id):,} ТОчек"
    )
    
    try:
        await bot.send_message(
            target_id,
            f"💰 <b>Вам перевели ТОчки!</b>\n\n"
            f"От: @{message.from_user.username}\n"
            f"Сумма: {amount:,} ТОчек\n"
            f"💵 Ваш баланс: {get_points(target_id):,} ТОчек"
        )
    except:
        pass


@dp.message(F.text.in_(["/paycoin", "пк", "pc", "ПК", "PC"]))
async def paycoin_command(message: types.Message):
    """Перевод T-Coins другому игроку"""
    args = message.text.split()
    
    if len(args) < 3:
        await message.answer(
            "💎 <b>Перевод T-Coins</b>\n\n"
            "Использование:\n"
            "<code>/paycoin @username сумма</code>\n\n"
            "Пример:\n"
            "<code>/paycoin @friend 50</code>\n\n"
            "ℹ️ T-Coins - это донатная валюта бота"
        )
        return
    
    target_username = args[1].replace('@', '')
    try:
        amount = int(args[2])
    except:
        await message.answer("❌ Неверная сумма!")
        return
    
    if amount < 1:
        await message.answer("❌ Минимум 1 T-Coin!")
        return
    
    # TODO: Добавить систему T-Coins в базу данных
    await message.answer(
        "⏳ <b>T-Coins система в разработке!</b>\n\n"
        "Скоро вы сможете:\n"
        "• Покупать T-Coins за Stars/Crypto\n"
        "• Переводить другим игрокам\n"
        "• Покупать эксклюзивные телефоны\n"
        "• Получать бонусы и привилегии"
    )


@dp.message(F.text.in_(["/trade", "тр", "tr", "ТР", "TR"]))
async def trade_command(message: types.Message):
    """Обмен телефонами"""
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer(
            "🤝 <b>Обмен телефонами</b>\n\n"
            "Использование:\n"
            "<code>/trade @username</code>\n\n"
            "Пример:\n"
            "<code>/trade @friend</code>"
        )
        return
    
    target_username = args[1].replace('@', '')
    
    # Найти пользователя
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE username = ?', (target_username,))
    target = cursor.fetchone()
    conn.close()
    
    if not target:
        await message.answer(f"❌ Пользователь @{target_username} не найден!")
        return
    
    await message.answer(
        f"🤝 <b>Обмен с @{target_username}</b>\n\n"
        f"⏳ Функция в разработке...\n"
        f"Скоро вы сможете обмениваться телефонами!"
    )


@dp.message(F.text.in_(["/tfarm", "тф", "tf", "ТФ", "TF", "ТМайнинг", "тмайнинг"]))
async def farm_command(message: types.Message):
    """Майнинг ферма"""
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        await message.answer("❌ Используйте /start сначала!")
        return
    
    farm_income = user[7]
    
    await message.answer(
        f"⛏️ <b>Ваша майнинг ферма</b>\n\n"
        f"💰 Доход в сутки: {farm_income:,} ТОчек\n"
        f"📊 Накоплено с фермой: {farm_income:,} ТОчек\n\n"
        f"⚠️ Улучшение фермы в разработке!"
    )


@dp.message(F.text.in_(["/event", "ев", "ev", "ЕВ", "EV"]))
async def event_command(message: types.Message):
    """Текущий розыгрыш"""
    await message.answer(
        "🎉 <b>РОЗЫГРЫШ</b>\n\n"
        "⏳ Сейчас нет активных розыгрышей\n\n"
        "Следите за объявлениями!"
    )


@dp.message(F.text.in_(["/avito", "ав", "av", "АВ", "AV", "авито"]))
async def avito_command(message: types.Message):
    """Вторичный рынок"""
    args = message.text.split()
    
    # Если указан username
    if len(args) > 1 and args[1].startswith('@'):
        username = args[1].replace('@', '')
        
        # Найти пользователя
        conn = sqlite3.connect('phones_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, first_name FROM users WHERE username = ?', (username,))
        target = cursor.fetchone()
        conn.close()
        
        if not target:
            await message.answer(f"❌ Пользователь @{username} не найден!")
            return
        
        target_id, first_name = target
        
        await message.answer(
            f"🏪 <b>Объявления @{username}</b>\n\n"
            f"⏳ Функция в разработке...\n\n"
            f"Здесь будут объявления игрока {first_name}"
        )
        return
    
    # Общий вторичный рынок
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Все объявления", callback_data="avito_all")],
        [InlineKeyboardButton(text="➕ Разместить объявление", callback_data="avito_create")],
        [InlineKeyboardButton(text="📋 Мои объявления", callback_data="avito_my")],
        [InlineKeyboardButton(text="🔍 Поиск по игроку", callback_data="avito_search")]
    ])
    
    await message.answer(
        "🏪 <b>Вторичный рынок (Авито)</b>\n\n"
        "⏳ Функция в разработке...\n\n"
        "Здесь вы сможете:\n"
        "• Выставлять телефоны на продажу\n"
        "• Покупать у других игроков\n"
        "• Торговаться о цене\n"
        "• Просматривать объявления игроков\n\n"
        "💡 Используйте: <code>/avito @username</code>\n"
        "чтобы посмотреть объявления игрока",
        reply_markup=keyboard
    )


@dp.message(F.text.in_(["/achievements", "достижения", "Достижения"]))
async def achievements_command(message: types.Message):
    """Достижения"""
    user_id = message.from_user.id
    
    await message.answer(
        "🏆 <b>ДОСТИЖЕНИЯ</b>\n\n"
        "⏳ Функция в разработке...\n\n"
        "Скоро вы сможете получать:\n"
        "• 🎯 За количество телефонов\n"
        "• 💰 За накопленные ТОчки\n"
        "• 🎴 За собранные карточки\n"
        "• ⬆️ За успешные апгрейды"
    )


@dp.message(F.text.in_(["/donate", "донат", "Донат"]))
async def donate_command(message: types.Message):
    """Донат - покупка статусов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ VIP статус - 100₽", callback_data="donate_vip")],
        [InlineKeyboardButton(text="💎 Premium статус - 300₽", callback_data="donate_premium")],
        [InlineKeyboardButton(text="👑 Legendary статус - 500₽", callback_data="donate_legendary")],
        [InlineKeyboardButton(text="💰 Пакет ТОчек - от 50₽", callback_data="donate_points")],
        [InlineKeyboardButton(text="🎴 Эксклюзивный телефон - 200₽", callback_data="donate_phone")]
    ])
    
    await message.answer(
        "💎 <b>КАТАЛОГ ДОНАТА</b>\n\n"
        "<b>⭐ VIP статус (100₽):</b>\n"
        "• Уменьшение кулдауна карточки\n"
        "• +50% к ежедневной награде\n"
        "• Особый значок в профиле\n\n"
        "<b>💎 Premium (300₽):</b>\n"
        "• Все преимущества VIP\n"
        "• +10% к шансу апгрейда\n"
        "• Доступ к эксклюзивным телефонам\n\n"
        "<b>👑 Legendary (500₽):</b>\n"
        "• Все преимущества Premium\n"
        "• Гарантированный легендарный телефон\n"
        "• Приоритетная поддержка\n\n"
        "💳 <b>Способы оплаты:</b>\n"
        "• Telegram Stars ⭐\n"
        "• Криптовалюта (USDT) 💎\n\n"
        "⚠️ Система доната в разработке!",
        reply_markup=keyboard
    )


@dp.message(F.text.in_(["/roulette", "рулетка", "Рулетка"]))
async def roulette_command(message: types.Message):
    """Донатная рулетка"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Крутить (10 ТОчек)", callback_data="spin_roulette_10")],
        [InlineKeyboardButton(text="🎰 Крутить (100 ТОчек)", callback_data="spin_roulette_100")],
        [InlineKeyboardButton(text="🎰 Крутить (1000 ТОчек)", callback_data="spin_roulette_1000")],
        [InlineKeyboardButton(text="💎 Крутить за T-Coins", callback_data="spin_roulette_coins")]
    ])
    
    await message.answer(
        "🎰 <b>ДОНАТНАЯ РУЛЕТКА</b>\n\n"
        "Выиграйте:\n"
        "• 📱 Редкие телефоны\n"
        "• 💰 Кучу ТОчек\n"
        "• 💎 T-Coins\n"
        "• 🏆 Эксклюзивные награды\n\n"
        "⚠️ Функция в разработке!",
        reply_markup=keyboard
    )


@dp.message(F.text.in_(["/tconfig", "тконфиг", "ТКонфиг"]))
async def tconfig_command(message: types.Message):
    """Конфигурация параметров"""
    user_id = message.from_user.id
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="config_notifications")],
        [InlineKeyboardButton(text="🎨 Тема оформления", callback_data="config_theme")],
        [InlineKeyboardButton(text="🌐 Язык", callback_data="config_language")],
        [InlineKeyboardButton(text="🔒 Приватность", callback_data="config_privacy")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await message.answer(
        "⚙️ <b>КОНФИГУРАЦИЯ</b>\n\n"
        "Настройте бота под себя:",
        reply_markup=keyboard
    )


@dp.message(F.text.in_(["/tinfo", "тинфо", "ТИнфо"]))
async def tinfo_command(message: types.Message):
    """Техническая информация"""
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM user_phones')
    total_phones = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(points) FROM users')
    total_points = cursor.fetchone()[0] or 0
    
    conn.close()
    
    await message.answer(
        f"ℹ️ <b>Техническая информация</b>\n\n"
        f"👥 Пользователей: {total_users:,}\n"
        f"📱 Телефонов выдано: {total_phones:,}\n"
        f"💰 Всего ТОчек: {total_points:,}\n\n"
        f"🤖 Версия: 1.0.0\n"
        f"📅 Дата запуска: {datetime.now().strftime('%d.%m.%Y')}"
    )


@dp.message(F.text.in_(["/ping", "пинг", "Пинг"]))
async def ping_command(message: types.Message):
    """Пинг бота"""
    start = datetime.now()
    msg = await message.answer("🏓 Понг!")
    end = datetime.now()
    diff = (end - start).total_seconds() * 1000
    
    await msg.edit_text(f"🏓 Понг!\n⏱ {diff:.0f}ms")


@dp.message(F.text.in_(["Помощь", "помощь", "/help", "км", "h", "КМ", "H"]))
async def help_command(message: types.Message):
    """Помощь по командам"""
    await message.answer(
        "<b>📖 СПИСОК КОМАНД</b>\n\n"
        "<b>🎮 Игровые:</b>\n"
        "• <code>ТКарточка</code> (тк) - Получить случайный телефон\n"
        "• <code>ТАкк</code> (та) - Профиль и статистика\n"
        "• <code>Мои телефоны</code> (мо) - Ваша коллекция\n"
        "• <code>Магазин телефонов</code> (мт) - Купить телефон\n"
        "• <code>Апгрейд</code> (ап) - Улучшить телефон\n"
        "• <code>Ежедневная награда</code> (ен) - Получить награду\n\n"
        "<b>💰 Экономика:</b>\n"
        "• <code>/pay @user сумма</code> - Перевести ТОчки\n"
        "• <code>/sellall</code> (са) - Продать все телефоны редкости\n\n"
        "<b>👥 Социальное:</b>\n"
        "• <code>/trade @user</code> - Обмен телефонами\n"
        "• <code>Таблица лидеров</code> (тл) - Топ игроков\n\n"
        "<b>🎁 Дополнительно:</b>\n"
        "• <code>/tfarm</code> - Майнинг ферма\n"
        "• <code>/event</code> - Текущий розыгрыш\n"
        "• <code>/avito</code> - Вторичный рынок\n"
        "• <code>/achievements</code> - Достижения\n"
        "• <code>/tinfo</code> - Информация о боте\n"
        "• <code>/ping</code> - Проверка связи\n\n"
        "💡 Команды можно писать на русском или английском!"
    )


@dp.callback_query(F.data == "back_main")
async def back_main(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()


@dp.callback_query(F.data == "back_shop")
async def back_shop(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🏪 <b>Магазин телефонов</b>\n\nВыберите редкость:",
        reply_markup=shop_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "back_myphones")
async def back_myphones(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📱 <b>Мои телефоны</b>\n\nВыберите редкость:",
        reply_markup=rarity_select_keyboard()
    )
    await callback.answer()


# ==================== ВСЕ ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ====================

@dp.message(F.text.in_(["/sellall", "са", "sa", "СА", "SA"]))
async def sellall_menu(message: types.Message):
    """Продажа всех телефонов одной редкости"""
    buttons = [[InlineKeyboardButton(text=f"{RARITIES[i]['name']}", callback_data=f"sellall_{i}")] for i in range(7)]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        "💰 <b>Продать все телефоны</b>\n\n"
        "Выберите редкость телефонов для продажи:\n"
        "⚠️ Вы получите 75% от стоимости",
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("sellall_"))
async def process_sellall(callback: types.CallbackQuery):
    rarity = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    phones = get_user_phones(user_id, rarity)
    
    if not phones:
        await callback.answer(f"❌ У вас нет телефонов редкости {RARITIES[rarity]['name']}", show_alert=True)
        return
    
    total_price = sum(phone[4] for phone in phones)
    sell_price = int(total_price * 0.75)
    count = len(phones)
    
    conn = sqlite3.connect('phones_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_phones WHERE user_id = ? AND rarity = ?', (user_id, rarity))
    cursor.execute('UPDATE users SET points = points + ?, total_phones = total_phones - ? WHERE user_id = ?',
                   (sell_price, count, user_id))
    conn.commit()
    conn.close()
    
    await callback.message.edit_text(
        f"✅ <b>Продано!</b>\n\n"
        f"📱 Телефонов продано: {count}\n"
        f"{RARITIES[rarity]['name']}\n\n"
        f"💸 Получено: {sell_price:,} ТОчек\n"
        f"💵 Ваш баланс: {get_points(user_id):,} ТОчек"
    )
    await callback.answer()


@dp.message(F.text.in_(["/event", "ев", "ev", "ЕВ", "EV"]))
async def event_command(message: types.Message):
    """Текущий розыгрыш"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Участвовать", callback_data="event_join")],
        [InlineKeyboardButton(text="📊 Участники", callback_data="event_list")]
    ])
    
    await message.answer(
        "🎉 <b>ТЕКУЩИЙ РОЗЫГРЫШ</b>\n\n"
        "🎁 <b>Призы:</b>\n"
        "🥇 1 место: 50,000 ТОчек + Легендарный телефон\n"
        "🥈 2 место: 25,000 ТОчек + Хроматический телефон\n"
        "🥉 3 место: 10,000 ТОчек\n\n"
        "⏰ <b>Розыгрыш через:</b> 7 дней\n"
        "👥 <b>Участников:</b> 156\n\n"
        "💡 Нажмите кнопку для участия!",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "event_join")
async def event_join(callback: types.CallbackQuery):
    await callback.answer("✅ Вы участвуете в розыгрыше!", show_alert=True)


@dp.callback_query(F.data == "event_list")
async def event_list(callback: types.CallbackQuery):
    await callback.answer("📊 Список участников в разработке", show_alert=True)


@dp.message(F.text.in_(["/tfarm", "тф", "tf", "ТФ", "TF", "ТМайнинг", "тмайнинг"]))
async def farm_command(message: types.Message):
    """Майнинг ферма"""
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        await message.answer("❌ Используйте /start сначала!")
        return
    
    farm_income = user[7] if user[7] > 0 else 100
    accumulated = farm_income * 24
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Снять деньги с фермы", callback_data="farm_collect")],
        [InlineKeyboardButton(text="⬆️ Улучшить ферму", callback_data="farm_upgrade")]
    ])
    
    await message.answer(
        f"⛏️ <b>Ваша майнинг ферма</b>\n\n"
        f"💰 <b>Доход в сутки:</b> {farm_income:,} ТОчек\n"
        f"📊 <b>Накоплено с фермой:</b> {accumulated:,} ТОчек\n"
        f"⬆️ <b>Уровень фермы:</b> 1\n\n"
        f"💡 Улучшите ферму для увеличения дохода!",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "farm_collect")
async def farm_collect_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    farm_income = user[7] if user[7] > 0 else 100
    collected = farm_income * 24
    update_points(user_id, collected)
    
    await callback.message.edit_text(
        f"✅ <b>Деньги сняты с фермы!</b>\n\n"
        f"💰 Получено: {collected:,} ТОчек\n"
        f"💵 Ваш баланс: {get_points(user_id):,} ТОчек"
    )
    await callback.answer()


@dp.callback_query(F.data == "farm_upgrade")
async def farm_upgrade_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "⬆️ <b>Улучшение фермы</b>\n\n"
        "💰 Цена: 5,000 ТОчек\n"
        "📈 Доход увеличится на +50 ТОчек/сутки\n\n"
        "⚠️ Функция в разработке!"
    )
    await callback.answer()


@dp.message(F.text.in_(["/achievements", "достижения", "Достижения"]))
async def achievements_command(message: types.Message):
    """Достижения"""
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        await message.answer("❌ Используйте /start сначала!")
        return
    
    phones_count = user[5]
    points = user[3]
    achievements = []
    
    if phones_count >= 1:
        achievements.append("🎯 Первый телефон")
    if phones_count >= 10:
        achievements.append("🏆 Коллекционер I (10 телефонов)")
    if phones_count >= 50:
        achievements.append("🏆 Коллекционер II (50 телефонов)")
    if phones_count >= 100:
        achievements.append("🏆 Коллекционер III (100 телефонов)")
    if points >= 1000:
        achievements.append("💰 Богач I (1,000 ТОчек)")
    if points >= 10000:
        achievements.append("💰 Богач II (10,000 ТОчек)")
    if points >= 100000:
        achievements.append("💰 Богач III (100,000 ТОчек)")
    
    text = "🏆 <b>ВАШИ ДОСТИЖЕНИЯ</b>\n\n"
    text += f"📊 <b>Выполнено:</b> {len(achievements)}/20\n\n"
    
    if achievements:
        for ach in achievements:
            text += f"✅ {ach}\n"
        text += "\n<b>Продолжайте играть для новых достижений!</b>"
    else:
        text += "⚠️ У вас пока нет достижений\n\n"
        text += "<b>Доступные достижения:</b>\n"
        text += "🎯 Первый телефон - получите первый телефон\n"
        text += "🏆 Коллекционер I - соберите 10 телефонов\n"
        text += "💰 Богач I - накопите 1,000 ТОчек"
    
    await message.answer(text)


@dp.message(F.text.in_(["/donate", "донат", "Донат"]))
async def donate_command(message: types.Message):
    """Донат - покупка статусов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ VIP статус - 100₽", callback_data="donate_vip")],
        [InlineKeyboardButton(text="💎 Premium статус - 300₽", callback_data="donate_premium")],
        [InlineKeyboardButton(text="👑 Legendary статус - 500₽", callback_data="donate_legendary")],
        [InlineKeyboardButton(text="💰 Пакет ТОчек - от 50₽", callback_data="donate_points")],
        [InlineKeyboardButton(text="🎴 Эксклюзивный телефон - 200₽", callback_data="donate_phone")]
    ])
    
    await message.answer(
        "💎 <b>КАТАЛОГ ДОНАТА</b>\n\n"
        "<b>⭐ VIP статус (100₽):</b>\n"
        "• Уменьшение кулдауна карточки на 30%\n"
        "• +50% к ежедневной награде\n"
        "• Особый значок в профиле\n\n"
        "<b>💎 Premium (300₽):</b>\n"
        "• Все преимущества VIP\n"
        "• +10% к шансу апгрейда\n"
        "• Доступ к эксклюзивным телефонам\n\n"
        "<b>👑 Legendary (500₽):</b>\n"
        "• Все преимущества Premium\n"
        "• Гарантированный легендарный телефон\n"
        "• Приоритетная поддержка\n\n"
        "💳 <b>Способы оплаты:</b>\n"
        "• Telegram Stars ⭐\n"
        "• Криптовалюта (USDT) 💎",
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("donate_"))
async def process_donate(callback: types.CallbackQuery):
    donate_type = callback.data.replace("donate_", "")
    prices = {"vip": "100₽", "premium": "300₽", "legendary": "500₽", "points": "от 50₽", "phone": "200₽"}
    
    await callback.message.edit_text(
        f"💎 <b>Покупка: {donate_type.upper()}</b>\n\n"
        f"💰 Цена: {prices.get(donate_type, 'Неизвестно')}\n\n"
        f"📞 Для оплаты обратитесь: @support\n\n"
        f"⚠️ После оплаты отправьте чек в поддержку!"
    )
    await callback.answer()


@dp.message(F.text.in_(["/roulette", "рулетка", "Рулетка"]))
async def roulette_command(message: types.Message):
    """Донатная рулетка"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Крутить (100 ТОчек)", callback_data="spin_roulette_100")],
        [InlineKeyboardButton(text="🎰 Крутить (500 ТОчек)", callback_data="spin_roulette_500")],
        [InlineKeyboardButton(text="🎰 Крутить (1000 ТОчек)", callback_data="spin_roulette_1000")],
        [InlineKeyboardButton(text="💎 Крутить за T-Coins", callback_data="spin_roulette_coins")]
    ])
    
    await message.answer(
        "🎰 <b>ДОНАТНАЯ РУЛЕТКА</b>\n\n"
        "Выиграйте:\n"
        "• 📱 Редкие телефоны\n"
        "• 💰 До x5 ТОчек\n"
        "• 💎 T-Coins\n"
        "• 🏆 Эксклюзивные награды\n\n"
        "🎯 Шанс выигрыша: 40%",
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("spin_roulette_"))
async def spin_roulette(callback: types.CallbackQuery):
    bet = callback.data.split("_")[-1]
    user_id = callback.from_user.id
    
    if bet == "coins":
        await callback.answer("⚠️ T-Coins система в разработке!", show_alert=True)
        return
    
    bet_amount = int(bet)
    points = get_points(user_id)
    
    if points < bet_amount:
        await callback.answer(f"❌ Недостаточно ТОчек! У вас: {points:,}", show_alert=True)
        return
    
    win = random.choice([True, True, False, False, False])
    
    if win:
        multiplier = random.randint(2, 5)
        prize = bet_amount * multiplier
        update_points(user_id, prize - bet_amount)
        await callback.message.edit_text(
            f"🎉 <b>ВЫИГРЫШ!</b>\n\n"
            f"🎰 Множитель: x{multiplier}\n"
            f"💰 Вы выиграли: {prize:,} ТОчек\n"
            f"📈 Прибыль: +{prize - bet_amount:,} ТОчек\n\n"
            f"💵 Ваш баланс: {get_points(user_id):,} ТОчек"
        )
    else:
        update_points(user_id, -bet_amount)
        await callback.message.edit_text(
            f"😔 <b>Проигрыш...</b>\n\n"
            f"💸 Потеряно: {bet_amount:,} ТОчек\n"
            f"💰 Ваш баланс: {get_points(user_id):,} ТОчек\n\n"
            f"💡 Попробуйте ещё раз!"
        )
    await callback.answer()


@dp.message(F.text.in_(["/tconfig", "тконфиг", "ТКонфиг"]))
async def tconfig_command(message: types.Message):
    """Конфигурация параметров"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="config_notifications")],
        [InlineKeyboardButton(text="🎨 Тема оформления", callback_data="config_theme")],
        [InlineKeyboardButton(text="🌐 Язык", callback_data="config_language")],
        [InlineKeyboardButton(text="🔒 Приватность", callback_data="config_privacy")]
    ])
    
    await message.answer("⚙️ <b>КОНФИГУРАЦИЯ</b>\n\nНастройте бота под себя:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("config_"))
async def process_config(callback: types.CallbackQuery):
    config_type = callback.data.replace("config_", "")
    settings = {
        "notifications": "🔔 <b>Уведомления</b>\n\nСтатус: Включены ✅\n\n⚠️ Изменение в разработке",
        "theme": "🎨 <b>Тема оформления</b>\n\nТекущая: Стандартная\n\n⚠️ Изменение в разработке",
        "language": "🌐 <b>Язык</b>\n\nТекущий: Русский 🇷🇺\n\n⚠️ Изменение в разработке",
        "privacy": "🔒 <b>Приватность</b>\n\nУровень: Стандартный\n\n⚠️ Изменение в разработке"
    }
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_tconfig")]])
    await callback.message.edit_text(settings.get(config_type, 'Неизвестная настройка'), reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "back_tconfig")
async def back_tconfig(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="config_notifications")],
        [InlineKeyboardButton(text="🎨 Тема оформления", callback_data="config_theme")],
        [InlineKeyboardButton(text="🌐 Язык", callback_data="config_language")],
        [InlineKeyboardButton(text="🔒 Приватность", callback_data="config_privacy")]
    ])
    await callback.message.edit_text("⚙️ <b>КОНФИГУРАЦИЯ</b>\n\nНастройте бота под себя:", reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_upgrade_"))
async def confirm_upgrade_purchase(callback: types.CallbackQuery):
    upgrade_type = callback.data.replace("confirm_upgrade_", "")
    user_id = callback.from_user.id
    
    upgrades = {
        "card_cooldown": {"name": "Уменьшение кулдауна карточки", "price": 5000},
        "daily_reward": {"name": "Увеличение ежедневной награды", "price": 3000},
        "farm": {"name": "Улучшение майнинг фермы", "price": 10000},
        "chance": {"name": "Увеличение шанса апгрейда", "price": 15000}
    }
    
    upgrade = upgrades[upgrade_type]
    points = get_points(user_id)
    
    if points < upgrade['price']:
        await callback.answer(f"❌ Недостаточно ТОчек! Нужно: {upgrade['price']:,}", show_alert=True)
        return
    
    update_points(user_id, -upgrade['price'])
    await callback.message.edit_text(
        f"✅ <b>Улучшение куплено!</b>\n\n"
        f"🏪 {upgrade['name']}\n"
        f"💰 Потрачено: {upgrade['price']:,} ТОчек\n"
        f"💵 Остаток: {get_points(user_id):,} ТОчек\n\n"
        f"⚠️ Эффект будет применён после перезапуска!"
    )
    await callback.answer()


# ==================== ЗАПУСК ====================

async def main():
    init_db()
    logger.info("🚀 Phones Collection Bot запущен!")
    await dp.start_polling(bot)


if __name__ == '__main__':
    import sys
    import subprocess
    import time
    
    if len(sys.argv) == 1:
        try:
            import watchfiles
            print("🔥 Hot Reload активирован!")
            
            def run_bot():
                return subprocess.Popen([sys.executable, __file__, '--running'])
            
            process = run_bot()
            last_mtime = os.path.getmtime(__file__)
            
            try:
                while True:
                    time.sleep(1)
                    current_mtime = os.path.getmtime(__file__)
                    
                    if current_mtime != last_mtime:
                        print("🔄 Изменения обнаружены! Перезапуск...")
                        process.terminate()
                        process.wait()
                        last_mtime = current_mtime
                        process = run_bot()
            except KeyboardInterrupt:
                print("\n🛑 Остановка...")
                process.terminate()
                process.wait()
        except ImportError:
            print("📦 Устанавливаю watchfiles...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "watchfiles", "-q"])
            print("✅ Установлено! Перезапускаю...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
    else:
        asyncio.run(main())
