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

FOOTER_TEXT = "\n\n<b><a href='https://t.me/shkola_114_bot'>🤖 Предложка 114</a></b>"

bot = Bot(token=TOKEN)
dp = Dispatcher()

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
    db["states"].pop(str(m.from_user.id), None) # Сброс состояния при старте
    save_db(db)
    await m.answer("Привіт! Выбери действие на кнопках ниже:", reply_markup=get_main_kb())

@dp.message(Command("reply"), F.from_user.id.in_(ADMINS))
async def cmd_reply(m: types.Message, command: CommandObject):
    if not command.args or " " not in command.args:
        return await m.answer("Ошибка! Пиши так: /reply ID Текст (или ответь на медиа этой командой)")
    
    uid, text = command.args.split(" ", 1)
    try:
        # Если админ отвечает на фото/видео командой /reply
        if m.reply_to_message:
            await m.reply_to_message.copy_to(uid, caption=f"🔔 <b>Ответ поддержки:</b>\n\n{text}", parse_mode="HTML")
        else:
            await bot.send_message(uid, f"🔔 <b>Ответ поддержки:</b>\n\n{text}", parse_mode="HTML")
        await m.answer("✅ Ответ отправлен!")
    except:
        await m.answer("❌ Не удалось отправить. Возможно, юзер заблокировал бота.")

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
    await m.answer("Режим поддержки включен. Пришли текст, фото или видео — админы их получат.", reply_markup=get_back_kb())

@dp.message(F.text == "📝 Предложить пост")
async def post_start(m: types.Message):
    db = load_db()
    db["states"][str(m.from_user.id)] = "post"
    save_db(db)
    await m.answer("Режим предложки. Пришли свой пост (текст, фото или видео):", reply_markup=get_back_kb())

# --- ЕДИНЫЙ ОБРАБОТЧИК МЕДИА И ТЕКСТА ---
@dp.message()
async def universal_handler(m: types.Message):
    uid = str(m.from_user.id)
    db = load_db()
    state = db["states"].get(uid)

    # 1. Если человек НЕ выбрал действие — ничего не пересылаем
    if not state:
        if m.chat.type == "private":
            await m.answer("⚠️ Пожалуйста, сначала выбери действие на кнопках ниже!", reply_markup=get_main_kb())
        return

    # 2. Логика ПОДДЕРЖКИ (текст + медиа)
    if state == "support":
        for aid in ADMINS:
            try:
                # Пересылаем сообщение админам с кнопкой ответа
                kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Ответить", callback_data=f"ans_{uid}")]])
                await m.send_copy(aid, reply_markup=kb)
            except: pass
        await m.answer("✅ Сообщение в поддержу отправлено!", reply_markup=get_main_kb())
        db["states"].pop(uid, None)
        save_db(db)

    # 3. Логика ПРЕДЛОЖКИ (текст + медиа)
    elif state == "post":
        p_id = len(db["posts"]) + 1
        db["posts"].append({"user_id": uid, "username": m.from_user.username, "admin_msgs": []})
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"acc_{p_id}"), 
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej_{p_id}")
        ]])
        
        for aid in ADMINS:
            try:
                # Админ получает копию поста с кнопками
                cap = f"👤 @{m.from_user.username} | Пост №{p_id}\n\n{m.caption or m.text or ''}"
                res = await m.send_copy(aid, caption=cap, reply_markup=kb)
                db["posts"][-1]["admin_msgs"].append({"chat": aid, "id": res.message_id})
            except: pass
            
        save_db(db)
        await m.answer("📩 Пост отправлен на модерацию!", reply_markup=get_main_kb())
        db["states"].pop(uid, None)
        save_db(db)

# --- ОБРАБОТКА CALLBACK ---
@dp.callback_query(F.data.startswith("acc_") | F.data.startswith("rej_"))
async def moderation_handler(c: types.CallbackQuery):
    act, p_id = c.data.split("_")[0], int(c.data.split("_")[1])
    db = load_db()
    
    # Ищем пост в базе
    try:
        p_data = db["posts"][p_id-1]
        user_id = p_data["user_id"]
    except:
        return await c.answer("Ошибка: пост не найден")

    if act == "acc":
        # Публикация (копируем сообщение из оригинала или пересылаем)
        await c.message.copy_to(PUBLISH_CHANNEL, caption=(c.message.caption or "") + FOOTER_TEXT, reply_markup=None)
        await bot.send_message(user_id, "🌟 Твой пост опубликован в канале!")
    else:
        await bot.send_message(user_id, "🚫 Твой пост отклонен модератором.")

    # Убираем кнопки у всех админов
    for m in p_data.get("admin_msgs", []):
        try: await bot.edit_message_reply_markup(chat_id=m["chat"], message_id=m["id"], reply_markup=None)
        except: pass
    
    await c.answer("Выполнено")

@dp.callback_query(F.data.startswith("ans_"))
async def setup_reply(c: types.CallbackQuery):
    uid = c.data.split("_")[1]
    await c.message.answer(f"Чтобы ответить юзеру, напиши:\n<code>/reply {uid} Текст</code>", parse_mode="HTML")
    await c.answer()

# --- ЗАПУСК ---
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
