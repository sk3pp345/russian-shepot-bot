import os
import asyncio
import json
import logging
import sys

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton
)
from aiogram.filters import Command, CommandObject
from aiohttp import web

# --- ЛОГИ ---
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("Bot114")

TOKEN = os.getenv("BOT_TOKEN")
PUBLISH_CHANNEL = "@dnipro1777" 
ADMINS = [1252647696, 5028188335] 
DB_FILE = "database_ru.json"

FOOTER_TEXT = (
    "\n\n<b><a href='https://t.me/Info114Pod'>ℹ️ Инфо</a> | "
    "<a href='https://t.me/+W65-IzDXhT85ZTky'>💬 Чат</a> | "
    "<a href='https://t.me/shkola_114_bot'>🤖 Предложка</a> | "
    "<a href='https://t.me/Per114Pod'>🔗 Переходник</a></b>"
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БД ---
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

# --- КЛАВИАТУРЫ ---
def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Предложить пост")],
        [KeyboardButton(text="🆘 Поддержка")]
    ], resize_keyboard=True)

def get_back_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)

# --- WEB ---
async def start_web():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000))).start()

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    db = load_db()
    db["users"][str(m.from_user.id)] = m.from_user.username or "User"
    save_db(db)
    await m.answer("Привет! Это Предложка 114 🤫\nВыбери действие ниже:", reply_markup=get_main_kb())

@dp.message(Command("reply"), F.from_user.id.in_(ADMINS))
async def cmd_reply(m: types.Message, command: CommandObject):
    if not command.args or " " not in command.args:
        return await m.answer("Используй: /reply ID Текст")
    uid, text = command.args.split(" ", 1)
    try:
        await bot.send_message(uid, f"🔔 <b>Ответ поддержки:</b>\n\n{text}", parse_mode="HTML")
        await m.answer("✅ Отправлено!")
    except: await m.answer("❌ Ошибка")

# --- ОБРАБОТКА ---
@dp.message(F.text == "⬅️ Назад")
async def go_back(m: types.Message):
    db = load_db()
    db["states"].pop(str(m.from_user.id), None)
    save_db(db)
    await m.answer("Возвращаю в меню:", reply_markup=get_main_kb())

@dp.message(F.text == "🆘 Поддержка")
async def support_start(m: types.Message):
    db = load_db()
    db["states"][str(m.from_user.id)] = "support"
    save_db(db)
    await m.answer("Напиши свой вопрос админам:", reply_markup=get_back_kb())

@dp.message(F.text == "📝 Предложить пост")
async def post_start(m: types.Message):
    db = load_db()
    db["states"][str(m.from_user.id)] = "post"
    save_db(db)
    await m.answer("Пришли текст или фото/видео:", reply_markup=get_back_kb())

@dp.message()
async def main_handler(m: types.Message):
    uid = str(m.from_user.id)
    db = load_db()
    state = db["states"].get(uid)

    if state == "support":
        content = m.text or m.caption or "[Медиа]"
        await m.answer("🚀 <b>Твой вопрос отправлен админам!</b>", reply_markup=get_main_kb(), parse_mode="HTML")
        for aid in ADMINS:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Ответить", callback_data=f"ans_{uid}")]])
            await bot.send_message(aid, f"🆘 <b>Вопрос от @{m.from_user.username}:</b>\n\n{content}", reply_markup=kb, parse_mode="HTML")
        db["states"].pop(uid, None)
        save_db(db)
        return

    if state == "post":
        txt = m.caption or m.text or ""
        f_id = m.photo[-1].file_id if m.photo else (m.video.file_id if m.video else None)
        f_type = "photo" if m.photo else ("video" if m.video else None)
        
        db["posts"].append({"user_id": uid, "username": m.from_user.username, "text": txt, "file_id": f_id, "file_type": f_type, "admin_msgs": []})
        p_id = len(db["posts"])
        
        await m.answer("📩 <b>Пост отправлен на модерацию!</b>", reply_markup=get_main_kb(), parse_mode="HTML")
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"acc_{p_id}"), 
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej_{p_id}")
        ]])
        
        for aid in ADMINS:
            cap = f"👤 @{m.from_user.username}\n📮 Пост №{p_id}\n\n{txt}"
            if f_type == "photo": res = await bot.send_photo(aid, f_id, caption=cap, reply_markup=kb)
            elif f_type == "video": res = await bot.send_video(aid, f_id, caption=cap, reply_markup=kb)
            else: res = await bot.send_message(aid, cap, reply_markup=kb)
            db["posts"][-1]["admin_msgs"].append({"chat": aid, "id": res.message_id})
        
        db["states"].pop(uid, None)
        save_db(db)
        return

# --- CALLBACK ---
@dp.callback_query(F.data.startswith("acc_") | F.data.startswith("rej_"))
async def moderation_handler(c: types.CallbackQuery):
    act, p_id = c.data.split("_")[0], int(c.data.split("_")[1])
    db = load_db()
    p = db["posts"][p_id-1]
    
    if act == "acc":
        cap = f"{p['text']}{FOOTER_TEXT}"
        if p["file_type"] == "photo": await bot.send_photo(PUBLISH_CHANNEL, p["file_id"], caption=cap, parse_mode="HTML")
        elif p["file_type"] == "video": await bot.send_video(PUBLISH_CHANNEL, p["file_id"], caption=cap, parse_mode="HTML")
        else: await bot.send_message(PUBLISH_CHANNEL, cap, parse_mode="HTML")
        await bot.send_message(p["user_id"], "🌟 <b>Твой пост опубликован!</b>", parse_mode="HTML")
    else:
        await bot.send_message(p["user_id"], "🚫 <b>Твой пост отклонен.</b>", parse_mode="HTML")

    for m in p.get("admin_msgs", []):
        try: await bot.edit_message_reply_markup(chat_id=m["chat"], message_id=m["id"], reply_markup=None)
        except: pass
    await c.answer("Готово")

@dp.callback_query(F.data.startswith("ans_"))
async def setup_reply(c: types.CallbackQuery):
    uid = c.data.split("_")[1]
    await c.message.answer(f"Команда:\n<code>/reply {uid} Текст</code>", parse_mode="HTML")
    await c.answer()

async def main():
    await bot.session.close() # Закрываем старые сессии
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(start_web())
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.error("Бот остановлен!")
