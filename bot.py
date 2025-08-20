import asyncio
import logging
import random
import sqlite3
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from openai import AsyncOpenAI

# =============== НАСТРОЙКИ ===============
API_TOKEN = "ВАШ_ТОКЕН_ОТ_BOTFATHER"
OPENAI_API_KEY = "ВАШ_ТОКЕН_OPENAI"
WEATHER_API_KEY = "ВАШ_ТОКЕН_ОТ_OPENWEATHER"
DB_PATH = "bot.db"
ADMIN_ID = 123456789  # твой Telegram ID (узнать через @userinfobot)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
gpt = AsyncOpenAI(api_key=OPENAI_API_KEY)

# =============== БАЗА ДАННЫХ ===============
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_message(user_id: int, text: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO logs (user_id, message) VALUES (?, ?)", (user_id, text))
    conn.commit()
    conn.close()

def get_logs(limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, user_id, message FROM logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def clear_logs():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM logs")
    conn.commit()
    conn.close()

# =============== СТАРТ ===============
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🌍 Факт", callback_data="fact")
    kb.button(text="🎮 Игра", callback_data="game")
    kb.button(text="⛅ Погода", callback_data="weather")
    kb.button(text="🤖 GPT", callback_data="gpt")
    kb.adjust(2)

    await message.answer(
        f"Привет, {message.from_user.first_name}! 🚀\n"
        "Я супер-бот с фактами, играми, погодой и GPT.\n\n"
        "Выбирай, что делаем:",
        reply_markup=kb.as_markup()
    )
    log_message(message.from_user.id, "/start")

# =============== ФАКТЫ ===============
@dp.callback_query(F.data == "fact")
async def send_fact(callback: types.CallbackQuery):
    facts = [
        "🐧 Пингвины — отличные пловцы, но не умеют летать.",
        "🚀 Первый человек в космосе — Юрий Гагарин (1961).",
        "💡 Электрическая лампочка запатентована Эдисоном в 1879 году.",
        "🌊 Океаны покрывают 71% поверхности Земли."
    ]
    fact = random.choice(facts)
    await callback.message.answer(fact)
    await callback.answer()
    log_message(callback.from_user.id, f"Факт: {fact}")

# =============== ИГРА ===============
@dp.callback_query(F.data == "game")
async def start_game(callback: types.CallbackQuery):
    number = random.randint(1, 5)
    await callback.message.answer("Я загадал число от 1 до 5. Угадай!")

    @dp.message(F.text.regexp(r"^[1-5]$"))
    async def guess_number(message: types.Message):
        if int(message.text) == number:
            await message.answer("🎉 Правильно! Ты угадал!")
        else:
            await message.answer(f"😅 Нет, я загадал {number}.")
        log_message(message.from_user.id, f"Игра: {message.text}")

    await callback.answer()

# =============== ПОГОДА ===============
@dp.callback_query(F.data == "weather")
async def get_weather(callback: types.CallbackQuery):
    await callback.message.answer("Введи название города:")

    @dp.message()
    async def city_weather(message: types.Message):
        city = message.text
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                if resp.status == 200:
                    temp = data['main']['temp']
                    desc = data['weather'][0]['description']
                    await message.answer(f"⛅ В {city} сейчас {temp}°C, {desc}.")
                else:
                    await message.answer("😢 Не нашёл город.")
        log_message(message.from_user.id, f"Погода: {city}")

    await callback.answer()

# =============== GPT ===============
@dp.callback_query(F.data == "gpt")
async def ask_gpt(callback: types.CallbackQuery):
    await callback.message.answer("Задай вопрос 🤖:")

    @dp.message()
    async def gpt_reply(message: types.Message):
        response = await gpt.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": message.text}]
        )
        answer = response.choices[0].message.content
        await message.answer(answer)
        log_message(message.from_user.id, f"GPT: {message.text}")

    await callback.answer()

# =============== АДМИНКА ===============
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ У тебя нет доступа.")

    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Логи", callback_data="admin_logs")
    kb.button(text="🗑️ Очистить логи", callback_data="admin_clear")
    kb.adjust(1)

    await message.answer("⚙️ Админ-панель", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "admin_logs")
async def admin_logs(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    logs = get_logs()
    text = "\n".join([f"{row[0]}. {row[1]}: {row[2]}" for row in logs]) or "Логи пусты."
    await callback.message.answer(f"📂 Последние логи:\n\n{text}")
    await callback.answer()

@dp.callback_query(F.data == "admin_clear")
async def admin_clear(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    clear_logs()
    await callback.message.answer("🗑️ Логи очищены!")
    await callback.answer()

# =============== ЗАПУСК ===============
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())