import os
import asyncio
import json
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (InlineKeyboardMarkup, InlineKeyboardButton, 
                            ReplyKeyboardMarkup, KeyboardButton, LabeledPrice, PreCheckoutQuery,
                            ContentType)
from aiogram.filters import Command, CommandObject
from aiohttp import web

# --- НАСТРОЙКИ ---
logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")
PUBLISH_CHANNEL = "@shepotrussia" 
ADMINS = [1252647696, 5028188335] 

bot = Bot(token=TOKEN)
dp = Dispatcher()
DB_FILE = "database_ru.json"

# Синий текст под постами
FOOTER_TEXT = "\n\n<b><a href='https://t.me/shepotrussiabot'>Предложка (@shepotrussiabot)</a>\n<a href='https://t.me/shepotrussia'>Шёпот России (t.me/shepotrussia)</a>\n<a href='https://t.me/+SSbibEaewjZiMGQy'>Чат</a></b>"

# --- РАБОТА С БД ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"users": {}, "posts": [], "states": {}}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- RUNTIME (WEB СЕРВЕР) ---
async def handle(request): 
    return web.Response(text="Shepot Russia Runtime Active")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000)))
    await site.start()

# --- КЛАВИАТУРЫ ---
def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Предложить пост")],
        [KeyboardButton(text="💎 Магазин"), KeyboardButton(text="🆘 Поддержка")]
    ], resize_keyboard=True)

def get_back_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)

# --- ГЛАВНЫЕ ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db = load_db()
    db["users"][str(message.from_user.id)] = message.from_user.username or "NoUser"
    save_db(db)
    await message.answer("Привет! Это <b>Шёпот России</b> 🤫\nВыбери действие в меню:", reply_markup=get_main_kb(), parse_mode="HTML")

# Магазин с категориями
@dp.message(F.text == "💎 Магазин")
async def action_shop(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 Разбан / Размут", callback_data="cat_ban")],
        [InlineKeyboardButton(text="🛠 Услуги", callback_data="cat_serv")],
        [InlineKeyboardButton(text="📢 Реклама", callback_data="cat_ads")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])
    await message.answer("💎 <b>Категории магазина:</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("cat_"))
async def shop_categories(call: types.CallbackQuery):
    cat = call.data.split("_")[1]
    if cat == "ban":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔓 Разбан — 50 ⭐", callback_data="buy_unban_50")],
            [InlineKeyboardButton(text="🔇 Размут — 25 ⭐", callback_data="buy_unmute_25")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_shop")]
        ])
        await call.message.edit_text("🔓 <b>Категория: Разбан</b>", reply_markup=kb, parse_mode="HTML")
    # Добавь другие категории по желанию сюда

@dp.message(F.text.in_(["📝 Предложить пост", "🆘 Поддержка"]))
async def set_state(message: types.Message):
    db = load_db()
    state = "waiting_for_post" if message.text == "📝 Предложить пост" else "waiting_for_support"
    db["states"][str(message.from_user.id)] = state
    save_db(db)
    await message.answer("📸 Пришлите ваш контент (текст/фото/видео):", reply_markup=get_back_kb())

@dp.message(F.text == "⬅️ Назад")
async def action_back(message: types.Message):
    db = load_db()
    db["states"].pop(str(message.from_user.id), None)
    save_db(db)
    await message.answer("🏠 Главное меню:", reply_markup=get_main_kb())

@dp.message()
async def main_handler(message: types.Message):
    uid = str(message.from_user.id)
    db = load_db()
    state = db["states"].get(uid)

    # Детектив: проверка пересланного поста
    if message.forward_from_chat and message.forward_from_chat.username == PUBLISH_CHANNEL.replace("@", ""):
        found = False
        for i, p in enumerate(db["posts"]):
            if p.get("text") in (message.text or message.caption or ""):
                await message.answer(f"🔍 <b>Инфо о посте:</b>\n👤 Автор: @{p['username']}\n🆔 ID: <code>{p['user_id']}</code>\n📮 №: <code>{i+1}</code>", parse_mode="HTML")
                found = True; break
        if not found: await message.answer("❌ Данные не найдены.")
        return

    if not state: return

    # Предложка
    if state == "waiting_for_post":
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да", callback_data=f"p_acc_{uid}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"p_rej_{uid}")
        ]])
        content = message.caption or message.text or ""
        f_id = message.photo[-1].file_id if message.photo else (message.video.file_id if message.video else None)
        f_type = "photo" if message.photo else ("video" if message.video else None)
        
        db["posts"].append({"user_id": uid, "username": message.from_user.username, "text": content, "file_id": f_id, "file_type": f_type})
        save_db(db)

        for aid in ADMINS:
            if f_type == "photo": await bot.send_photo(aid, f_id, caption=f"👤 @{message.from_user.username}\n\n{content}", reply_markup=kb)
            elif f_type == "video": await bot.send_video(aid, f_id, caption=f"👤 @{message.from_user.username}\n\n{content}", reply_markup=kb)
            else: await bot.send_message(aid, f"👤 @{message.from_user.username}\n\n{content}", reply_markup=kb)
        
        await message.answer("⏳ Отправлено админам!", reply_markup=get_main_kb())
        db["states"].pop(uid); save_db(db)

# --- МОДЕРАЦИЯ ---
@dp.callback_query(F.data.startswith("p_acc_"))
async def accept_post(call: types.CallbackQuery):
    t_uid = call.data.split("_")[2]
    raw = call.message.caption or call.message.text or ""
    final = raw.split("@")[1].split("\n\n")[-1] if "@" in raw else raw
    
    try:
        if call.message.photo: await bot.send_photo(PUBLISH_CHANNEL, call.message.photo[-1].file_id, caption=f"{final}{FOOTER_TEXT}", parse_mode="HTML")
        elif call.message.video: await bot.send_video(PUBLISH_CHANNEL, call.message.video.file_id, caption=f"{final}{FOOTER_TEXT}", parse_mode="HTML")
        else: await bot.send_message(PUBLISH_CHANNEL, f"{final}{FOOTER_TEXT}", parse_mode="HTML", disable_web_page_preview=True)
        await bot.send_message(int(t_uid), "🌟 Ваш пост опубликован!")
    except: pass
    await call.message.edit_reply_markup(None)

async def main():
    asyncio.create_task(start_server())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())