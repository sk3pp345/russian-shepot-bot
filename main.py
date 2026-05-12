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

# --- НАСТРОЙКИ ---
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
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

# --- БАЗА ДАННЫХ (С ПРИНУДИТЕЛЬНЫМ СОХРАНЕНИЕМ) ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "users" not in data: data["users"] = {}
                if "posts" not in data: data["posts"] = []
                if "states" not in data: data["states"] = {}
                return data
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

# --- КОМАНДЫ АДМИНА ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    db = load_db()
    uid = str(m.from_user.id)
    db["users"][uid] = m.from_user.username or "User"
    db["states"].pop(uid, None) 
    save_db(db)
    await m.answer("Привіт! Выбери действие:", reply_markup=get_main_kb())

@dp.message(Command("send"), F.from_user.id.in_(ADMINS))
async def cmd_mass_send(m: types.Message, command: CommandObject):
    if not command.args:
        return await m.answer("Пиши: /send Текст")
    db = load_db()
    u_list = list(db["users"].keys())
    count = 0
    for u in u_list:
        try:
            await bot.send_message(u, command.args)
            count += 1
            await asyncio.sleep(0.1)
        except: pass
    await m.answer(f"✅ Рассылка: {count} чел.")

@dp.message(Command("who"), F.from_user.id.in_(ADMINS))
async def cmd_who(m: types.Message):
    if not m.reply_to_message:
        return await m.answer("Ответь на пересланный пост этой командой.")
    db = load_db()
    txt = (m.reply_to_message.caption or m.reply_to_message.text or "").replace(FOOTER_TEXT, "").strip()
    for p in db["posts"]:
        if p.get("text") == txt:
            return await m.answer(f"👤 Автор: @{p.get('username')}\nID: {p.get('user_id')}")
    await m.answer("❌ Не найдено.")

@dp.message(Command("reply"), F.from_user.id.in_(ADMINS))
async def cmd_reply(m: types.Message, command: CommandObject):
    if not command.args or " " not in command.args:
        return await m.answer("Пиши: /reply ID Текст")
    uid, text = command.args.split(" ", 1)
    try:
        await bot.send_message(uid, f"🔔 <b>Ответ поддержки:</b>\n\n{text}", parse_mode="HTML")
        await m.answer("✅ Отправлено!")
    except: await m.answer("❌ Ошибка.")

# --- ЛОГИКА КНОПОК ---
@dp.message(F.text == "⬅️ Назад")
async def go_back(m: types.Message):
    db = load_db()
    db["states"].pop(str(m.from_user.id), None)
    save_db(db)
    await m.answer("Главное меню:", reply_markup=get_main_kb())

@dp.message(F.text == "🆘 Поддержка")
async def support_start(m: types.Message):
    db = load_db()
    db["states"][str(m.from_user.id)] = "support"
    save_db(db)
    await m.answer("Напиши свой вопрос:", reply_markup=get_back_kb())

@dp.message(F.text == "📝 Предложить пост")
async def post_start(m: types.Message):
    db = load_db()
    db["states"][str(m.from_user.id)] = "post"
    save_db(db)
    await m.answer("Пришли контент поста:", reply_markup=get_back_kb())

# --- ОБРАБОТКА ТЕКСТА И МЕДИА ---
@dp.message()
async def main_handler(m: types.Message):
    uid = str(m.from_user.id)
    db = load_db()
    state = db["states"].get(uid)
    if not state: return

    # ПОДДЕРЖКА
    if state == "support":
        for aid in ADMINS:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Ответить", callback_data=f"ans_{uid}")]])
            user_info = f"🆘 <b>Вопрос от: @{m.from_user.username or 'скрыт'}</b>\n\n"
            if m.text: await bot.send_message(aid, user_info + m.text, reply_markup=kb, parse_mode="HTML")
            else: await m.copy_to(aid, caption=user_info + (m.caption or ""), reply_markup=kb, parse_mode="HTML")
        await m.answer("✅ Отправлено админам!", reply_markup=get_main_kb())
        db["states"].pop(uid, None)
        save_db(db)

    # ПРЕДЛОЖКА
    elif state == "post":
        txt = m.caption or m.text or ""
        db["posts"].append({"user_id": uid, "username": m.from_user.username, "text": txt, "admin_msgs": []})
        p_idx = len(db["posts"])
        save_db(db) # Сразу сохраняем индекс

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"acc_{p_idx}"), 
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej_{p_idx}")
        ]])
        
        for aid in ADMINS:
            admin_cap = f"👤 <b>От: @{m.from_user.username or 'скрыт'}</b> | №{p_idx}\n\n{txt}"
            res = await m.copy_to(aid, caption=admin_cap, reply_markup=kb, parse_mode="HTML")
            db["posts"][-1]["admin_msgs"].append({"chat": aid, "id": res.message_id})
        
        save_db(db)
        await m.answer("📩 Пост на модерации!", reply_markup=get_main_kb())
        db["states"].pop(uid, None)
        save_db(db)

# --- CALLBACK ---
@dp.callback_query(F.data.startswith("acc_") | F.data.startswith("rej_"))
async def moderation_handler(c: types.CallbackQuery):
    act, p_idx = c.data.split("_")[0], int(c.data.split("_")[1])
    db = load_db()
    if p_idx > len(db["posts"]): return await c.answer("❌ Ошибка: пост не найден в БД", show_alert=True)

    post = db["posts"][p_idx-1]
    if act == "acc":
        final_text = post["text"] + FOOTER_TEXT
        if c.message.photo: await bot.send_photo(PUBLISH_CHANNEL, c.message.photo[-1].file_id, caption=final_text, parse_mode="HTML")
        elif c.message.video: await bot.send_video(PUBLISH_CHANNEL, c.message.video.file_id, caption=final_text, parse_mode="HTML")
        else: await bot.send_message(PUBLISH_CHANNEL, final_text, parse_mode="HTML")
        try: await bot.send_message(post["user_id"], "🌟 Твой пост опубликован!")
        except: pass
    else:
        try: await bot.send_message(post["user_id"], "🚫 Твой пост отклонен.")
        except: pass

    for amsg in post.get("admin_msgs", []):
        try: await bot.edit_message_reply_markup(chat_id=amsg["chat"], message_id=amsg["id"], reply_markup=None)
        except: pass
    await c.answer("Готово")

@dp.callback_query(F.data.startswith("ans_"))
async def setup_reply(c: types.CallbackQuery):
    await c.message.answer(f"Команда для ответа:\n<code>/reply {c.data.split('_')[1]} Текст</code>", parse_mode="HTML")
    await c.answer()

# --- RUN ---
async def start_web():
    app = web.Application(); app.router.add_get('/', lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000))).start()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(start_web())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
