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
FOOTER_TEXT = "\n\n<b><a href='https://t.me/shepotrussiabot'>Предложка (@shepotrussiabot)</a>\n<a href='https://t.me/shepotrussia'>Шёпот России (t.me/shepotrussia)</a>\n<a href='https://t.me/+SSbibEaewjZiMGQy'>Чат (t.me/chat)</a></b>"

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

# --- WEB СЕРВЕР (ДЛЯ RENDER) ---
async def handle(request): return web.Response(text="Shepot RU Active")
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

# --- ОБРАБОТКА /START ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db = load_db()
    db["users"][str(message.from_user.id)] = message.from_user.username or "NoUser"
    save_db(db)
    await message.answer(f"Привет! Это <b>Шёпот России</b> 🤫\n\nВыбери нужное действие в меню ниже:", 
                         reply_markup=get_main_kb(), parse_mode="HTML")

# --- МАГАЗИН ---
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
    elif cat == "serv":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎭 Префикс — 100 ⭐", callback_data="buy_prefix_100")],
            [InlineKeyboardButton(text="🔨 Бан (1д) — 200 ⭐", callback_data="buy_ban1d_200")],
            [InlineKeyboardButton(text="🔇 Мут (1д) — 100 ⭐", callback_data="buy_mute1d_100")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_shop")]
        ])
        await call.message.edit_text("🛠 <b>Категория: Услуги</b>", reply_markup=kb, parse_mode="HTML")
    elif cat == "ads":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📌 Закреп (1д) — 75 ⭐", callback_data="buy_pin_75")],
            [InlineKeyboardButton(text="📢 Рекламный пост — 50 ⭐", callback_data="buy_adpost_50")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_shop")]
        ])
        await call.message.edit_text("📢 <b>Категория: Реклама</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "back_to_shop")
async def back_to_shop(call: types.CallbackQuery): await action_shop(call.message)

@dp.callback_query(F.data == "buy_") # Логика оплаты как в прошлых версиях
async def process_buy(call: types.CallbackQuery):
    # Код оплаты Stars (XTR) здесь
    pass

# --- ПРЕДЛОЖКА И ПОДДЕРЖКА ---
@dp.message(F.text.in_(["📝 Предложить пост", "🆘 Поддержка"]))
async def set_state(message: types.Message):
    db = load_db()
    state = "waiting_for_post" if message.text == "📝 Предложить пост" else "waiting_for_support"
    db["states"][str(message.from_user.id)] = state
    save_db(db)
    text = "📸 Пришлите ваш пост (текст, фото или видео):" if state == "waiting_for_post" else "💬 Напишите ваше сообщение в поддержку (можно с фото):"
    await message.answer(text, reply_markup=get_back_kb())

@dp.message(F.text == "⬅️ Назад")
async def action_back(message: types.Message):
    db = load_db()
    db["states"].pop(str(message.from_user.id), None)
    save_db(db)
    await message.answer("🏠 Главное меню:", reply_markup=get_main_kb())

# --- ГЛАВНЫЙ ОБРАБОТЧИК ---
@dp.message()
async def main_handler(message: types.Message):
    uid = str(message.from_user.id)
    db = load_db()
    state = db["states"].get(uid)

    # 1. Распознавание пересланного поста из канала (для админа)
    if message.forward_from_chat and message.forward_from_chat.username == PUBLISH_CHANNEL.replace("@", ""):
        # Ищем в базе пост по тексту или медиа
        found = False
        for i, p in enumerate(db["posts"]):
            if p.get("text") in (message.text or message.caption or ""):
                await message.answer(f"🔍 <b>Информация о посте:</b>\n👤 Автор: @{p['username']}\n🆔 Юзер ID: <code>{p['user_id']}</code>\n📮 Пост ID: <code>{i+1}</code>", parse_mode="HTML")
                found = True; break
        if not found: await message.answer("❌ Данные об этом посте не найдены в базе.")
        return

    if not state: return

    # 2. Обработка предложки
    if state == "waiting_for_post":
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да", callback_data=f"p_acc_{uid}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"p_rej_{uid}")
        ]])
        content = message.caption or message.text or ""
        f_id = message.photo[-1].file_id if message.photo else (message.video.file_id if message.video else None)
        f_type = "photo" if message.photo else ("video" if message.video else None)
        
        post_entry = {"user_id": uid, "username": message.from_user.username, "text": content, "file_id": f_id, "file_type": f_type}
        db["posts"].append(post_entry); p_id = len(db["posts"]); save_db(db)

        for aid in ADMINS:
            info = f"👤 От: @{message.from_user.username}\n📮 Пост №: {p_id}\n\n{content}"
            if f_type == "photo": await bot.send_photo(aid, f_id, caption=info, reply_markup=kb)
            elif f_type == "video": await bot.send_video(aid, f_id, caption=info, reply_markup=kb)
            else: await bot.send_message(aid, info, reply_markup=kb)
        
        await message.answer("⏳ Отправлено админам!", reply_markup=get_main_kb())
        db["states"].pop(uid); save_db(db)

    # 3. Обработка поддержки
    elif state == "waiting_for_support":
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Ответить", callback_data=f"sup_rep_{uid}")]])
        for aid in ADMINS:
            info = f"🆘 <b>ПОДДЕРЖКА</b>\nОт: @{message.from_user.username} (<code>{uid}</code>)\n\n"
            if message.photo: await bot.send_photo(aid, message.photo[-1].file_id, caption=info + (message.caption or ""), reply_markup=kb, parse_mode="HTML")
            else: await bot.send_message(aid, info + (message.text or ""), reply_markup=kb, parse_mode="HTML")
        await message.answer("🚀 Сообщение доставлено поддержке!", reply_markup=get_main_kb())
        db["states"].pop(uid); save_db(db)

# --- АДМИН КОМАНДЫ ---
@dp.message(Command("stats"), F.from_user.id.in_(ADMINS))
async def cmd_stats(message: types.Message):
    db = load_db()
    await message.answer(f"📊 Статистика:\nЮзеров: {len(db['users'])}\nПостов в базе: {len(db['posts'])}")

@dp.message(Command("check"), F.from_user.id.in_(ADMINS))
async def cmd_check(message: types.Message, command: CommandObject):
    if not command.args: return
    db = load_db()
    try:
        p = db["posts"][int(command.args)-1]
        info = f"📦 Пост №{command.args}\nАвтор: @{p['username']}\n\nТекст: {p['text']}"
        if p["file_id"]:
            if p["file_type"] == "photo": await bot.send_photo(message.chat.id, p["file_id"], caption=info)
            else: await bot.send_video(message.chat.id, p["file_id"], caption=info)
        else: await message.answer(info)
    except: await message.answer("❌ Не найдено")

@dp.message(Command("history"), F.from_user.id.in_(ADMINS))
async def cmd_history(message: types.Message, command: CommandObject):
    if not command.args: return
    db = load_db()
    uname = command.args.replace("@", "")
    ids = [str(i+1) for i, p in enumerate(db["posts"]) if p["username"] == uname]
    await message.answer(f"📝 Посты @{uname}: {', '.join(ids) if ids else 'нет'}")

# --- ОБРАБОТКА CALLBACKS (ОТВЕТЫ И ПУБЛИКАЦИЯ) ---
@dp.callback_query(F.data.startswith("sup_rep_"))
async def support_reply(call: types.CallbackQuery):
    uid = call.data.split("_")[2]
    db = load_db()
    db["states"][str(call.from_user.id)] = f"rep_to_{uid}"
    save_db(db)
    await call.message.answer(f"✍️ Пишите ответ для юзера {uid}:")
    await call.answer()

@dp.callback_query(F.data.startswith("p_"))
async def process_post(call: types.CallbackQuery):
    _, act, t_uid = call.data.split("_")
    if act == "acc":
        # Логика публикации в канал с синим текстом
        content = call.message.caption or call.message.text or ""
        if "От:" in content: content = content.split("\n\n")[-1] # Убираем инфо админа
        
        if call.message.photo: await bot.send_photo(PUBLISH_CHANNEL, call.message.photo[-1].file_id, caption=f"{content}{FOOTER_TEXT}", parse_mode="HTML")
        elif call.message.video: await bot.send_video(PUBLISH_CHANNEL, call.message.video.file_id, caption=f"{content}{FOOTER_TEXT}", parse_mode="HTML")
        else: await bot.send_message(PUBLISH_CHANNEL, f"{content}{FOOTER_TEXT}", parse_mode="HTML", disable_web_page_preview=True)
        await bot.send_message(int(t_uid), "🌟 Ваш пост опубликован!")
    await call.message.delete_reply_markup()
    await call.answer()

async def main():
    asyncio.create_task(start_server())
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
