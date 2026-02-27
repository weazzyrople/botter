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


# ==================== БАЗА ДАННЫХ ====================

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
    
    # Телефоны пользователей
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
    
    # Достижения
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


# ==================== КЛАВИАТУРЫ ====================

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
    for r in range(6):  # До Арканы
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
    
    # Навигация
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


# ==================== ОБРАБОТЧИКИ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    create_user(user_id, username, first_name)
    
    await message.answer_photo(
        photo="https://i.imgur.com/placeholder.jpg",  # Замени на свою картинку
        caption=f"👋 Добро пожаловать, @{username}!\n\n"
                f"🎴 Наш бот предлагает вам погрузиться в мир смартфонов и "
                f"доказать другим, что вы лучше понимаете новые технологии!\n\n"
                f"📱 Чтобы открыть вашу первую карточку напишите \"ТКарточка\".\n\n"
                f"💡 Используйте одну из кнопок ниже для взаимодействия с функциями:",
        reply_markup=main_keyboard()
    )


@dp.message(F.text == "🎴 ТКарточка")
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
    
    await message.answer_photo(
        photo="https://i.imgur.com/phone_placeholder.jpg",  # Замени на картинку телефона
        caption=f"@{message.from_user.username} Вам выпал телефон!\n\n"
                f"{RARITIES[rarity]['color']} {phone_name}\n"
                f"{RARITIES[rarity]['name']} | Цена: {price:,} ТОчек"
    )


@dp.message(F.text == "👤 ТАкк")
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


@dp.message(F.text == "📱 Мои телефоны")
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


@dp.message(F.text == "🏪 Магазин телефонов")
async def shop(message: types.Message):
    await message.answer(
        "🏪 <b>Магазин телефонов</b>\n\nВыберите редкость:",
        reply_markup=shop_keyboard()
    )


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


@dp.message(F.text == "⬆️ Апгрейд")
async def upgrade_menu(message: types.Message):
    await message.answer(
        "⬆️ <b>Апгрейд телефона</b>\n\n"
        "Выберите редкость телефона который хотите улучшить:",
        reply_markup=rarity_select_keyboard()
    )


@dp.message(F.text == "🎁 Ежедневная награда")
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


@dp.message(F.text == "🏆 Таблица лидеров")
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
