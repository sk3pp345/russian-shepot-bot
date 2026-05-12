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

# --- БАЗА ДАННЫХ ---
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

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    db = load_db()
    db["users"][str(m.from_user.id)] = m.from_user.username or "User"
    db["states"].pop(str(m.from_user.id), None) 
    save_db(db)
    await m.answer("Привіт! Выбери действие:", reply_markup=get_main_kb())

@dp.message(Command("reply"), F.from_user.id.in_(ADMINS))
async def cmd_reply(m: types.Message, command: CommandObject):
    if not command.args or " " not in command.args:
        return await m.answer("Используй: /reply ID Текст")
    uid, text = command.args.split(" ", 1)
    try:
        await bot.send_message(uid, f"🔔 <b>Ответ поддержки:</b>\n\n{text}", parse_mode="HTML")
        await m.answer("✅ Ответ отправлен!")
    except: await m.answer("❌ Ошибка отправки.")

# РАССЫЛКА ВСЕМ ПОЛЬЗОВАТЕЛЯМ
@dp.message(Command("send"), F.from_user.id.in_(ADMINS))
async def cmd_mass_send(m: types.Message, command: CommandObject):
    if not command.args:
        return await m.answer("Используй: /send Текст рассылки")
    
    db = load_db()
    users = db.get("users", {})
    count = 0
    for uid in users:
        try:
            await bot.send_message(uid, command.args)
            count += 1
            await asyncio.sleep(0.05) # Защита от спам-фильтра ТГ
        except: pass
    await m.answer(f"✅ Рассылка завершена! Получили {count} чел.")

# КТО АВТОР (через пересылку)
@dp.message(Command("who"), F.from_user.id.in_(ADMINS))
async def cmd_who(m: types.Message):
    if not m.reply_to_message:
        return await m.answer("Перешли пост из канала и ответь на него этой командой.")
    
    db = load_db()
    s_text = (m.reply_to_message.caption or m.reply_to_message.text or "").replace(FOOTER_TEXT, "").strip()
    
    found = False
    for p in db["posts"]:
        if p.get("text") == s_text:
            await m.answer(f"👤 <b>Автор:</b> @{p.get('username')}\nID: <code>{p.get('user_id')}</code>", parse_mode="HTML")
            found = True
            break
    if not found: await m.answer("❌ Автор не найден.")

# --- ОБРАБОТКА ПРЕДЛОЖКИ И ПОДДЕРЖКИ ---
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
            info = f"🆘 <b>Поддержка от: @{m.from_user.username or 'скрыт'}</b>\n\n"
            await m.copy_to(aid, caption=info + (m.caption or ""), reply_markup=kb, parse_mode="HTML") if not m.text else await bot.send_message(aid, info + m.text, reply_markup=kb, parse_mode="HTML")
        await m.answer("✅ Отправлено!", reply_markup=get_main_kb())
        db["states"].pop(uid, None)
        save_db(db)

    # ПРЕДЛОЖКА
    elif state == "post":
        p_id = len(db["posts"]) + 1
        txt = m.caption or m.text or ""
        db["posts"].append({"user_id": uid, "username": m.from_user.username, "text": txt, "admin_msgs": []})
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"acc_{p_id}"), 
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej_{p_id}")
        ]])
        
        for aid in ADMINS:
            info = f"👤 <b>Предложка от: @{m.from_user.username or 'скрыт'}</b> | №{p_id}\n\n"
            res = await m.copy_to(aid, caption=info + txt, reply_markup=kb, parse_mode="HTML")
            db["posts"][-1]["admin_msgs"].append({"chat": aid, "id": res.message_id})
            
        save_db(db)
        await m.answer("📩 Пост на модерации!", reply_markup=get_main_kb())
        db["states"].pop(uid, None)
        save_db(db)

# --- МОДЕРАЦИЯ ---
@dp.callback_query(F.data.startswith("acc_") | F.data.startswith("rej_"))
async def moderation_handler(c: types.CallbackQuery):
    act, p_id = c.data.split("_")[0], int(c.data.split("_")[1])
    db = load_db()
    if p_id > len(db["posts"]): return await c.answer("❌ Ошибка: Пост не найден.")

    p_data = db["posts"][p_id-1]
    u_id = p_data["user_id"]

    if act == "acc":
        final_text = p_data["text"] + FOOTER_TEXT
        if c.message.photo: await bot.send_photo(PUBLISH_CHANNEL, c.message.photo[-1].file_id, caption=final_text, parse_mode="HTML")
        elif c.message.video: await bot.send_video(PUBLISH_CHANNEL, c.message.video.file_id, caption=final_text, parse_mode="HTML")
        else: await bot.send_message(PUBLISH_CHANNEL, final_text, parse_mode="HTML")
        try: await bot.send_message(u_id, "🌟 Твой пост опубликован!")
        except: pass
    else:
        try: await bot.send_message(u_id, "🚫 Твой пост отклонен.")
        except: pass

    # Удаляем кнопки у ВСЕХ админов (синхронизация)
    for amsg in p_data.get("admin_msgs", []):
        try: await bot.edit_message_reply_markup(chat_id=amsg["chat"], message_id=amsg["id"], reply_markup=None)
        except: pass
    await c.answer("Готово")

@dp.callback_query(F.data.startswith("ans_"))
async def setup_reply(c: types.CallbackQuery):
    uid = c.data.split("_")[1]
    await c.message.answer(f"Ответ для {uid}:\n<code>/reply {uid} Текст</code>", parse_mode="HTML")
    await c.answer()

# --- СЕРВЕР ---
async def start_web():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000))).start()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(start_web())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
