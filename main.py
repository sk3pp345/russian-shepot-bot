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

# --- WEB СЕРВЕР (ДЛЯ RENDER) ---
async def start_web():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000))).start()

# --- АДМИНСКИЕ КОМАНДЫ ---
@dp.message(Command("admins"), F.from_user.id.in_(ADMINS))
async def cmd_admins(m: types.Message):
    text = (
        "🛠 <b>Админ-панель</b>\n\n"
        "• <code>/stats</code> — Статистика\n"
        "• <code>/check [ID]</code> — Инфо о посте\n"
        "• <code>/send [Текст]</code> — Рассылка\n"
        "• <code>/reply [ID] [Текст]</code> — Ответ в поддержку"
    )
    await m.answer(text, parse_mode="HTML")

@dp.message(Command("stats"), F.from_user.id.in_(ADMINS))
async def cmd_stats(m: types.Message):
    db = load_db()
    await m.answer(f"📊 Юзеров: {len(db['users'])}\n📮 Постов: {len(db['posts'])}")

@dp.message(Command("send"), F.from_user.id.in_(ADMINS))
async def cmd_send(m: types.Message, command: CommandObject):
    if not command.args: return await m.answer("Введите текст рассылки")
    db = load_db()
    count = 0
    for uid in db["users"]:
        try:
            await bot.send_message(uid, command.args)
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await m.answer(f"✅ Рассылка завершена. Получили: {count}")

@dp.message(Command("check"), F.from_user.id.in_(ADMINS))
async def cmd_check(m: types.Message, command: CommandObject):
    if not command.args: return await m.answer("Укажите номер поста")
    db = load_db()
    try:
        p = db["posts"][int(command.args)-1]
        await m.answer(f"👤 Автор: @{p['username']}\n🆔 ID: {p['user_id']}\n📝 Текст: {p['text']}")
    except: await m.answer("Пост не найден")

# Поиск автора по пересылке
@dp.message(F.forward_from_chat)
async def handle_forward(m: types.Message):
    if m.from_user.id not in ADMINS: return
    db = load_db()
    txt = (m.caption or m.text or "").replace(FOOTER_TEXT, "").strip()
    found = next(((i+1, p) for i, p in enumerate(db["posts"]) if txt and (p["text"] in txt or txt in p["text"])), None)
    if found:
        await m.reply(f"🎯 Пост №{found[0]}\n👤 Автор: @{found[1]['username']}\n🆔 ID: <code>{found[1]['user_id']}</code>", parse_mode="HTML")
    else:
        await m.reply("❌ В базе предложки не найдено")

# --- ЛОГИКА БОТА ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    db = load_db()
    db["users"][str(m.from_user.id)] = m.from_user.username or "User"
    save_db(db)
    await m.answer("Привет! Это Предложка 114 🤫", reply_markup=get_main_kb())

@dp.message(F.text == "🆘 Поддержка")
async def support_btn(m: types.Message):
    db = load_db()
    db["states"][str(m.from_user.id)] = "waiting_support"
    save_db(db)
    await m.answer("Напиши свой вопрос, и админы ответят тебе здесь:", reply_markup=get_back_kb())

@dp.message(F.text == "📝 Предложить пост")
async def post_btn(m: types.Message):
    db = load_db()
    db["states"][str(m.from_user.id)] = "waiting_post"
    save_db(db)
    await m.answer("Пришли текст, фото или видео для канала:", reply_markup=get_back_kb())

@dp.message(F.text == "⬅️ Назад")
async def back_btn(m: types.Message):
    db = load_db()
    db["states"].pop(str(m.from_user.id), None)
    save_db(db)
    await m.answer("Главное меню:", reply_markup=get_main_kb())

@dp.message()
async def global_handler(m: types.Message):
    uid = str(m.from_user.id)
    db = load_db()
    state = db["states"].get(uid)

    if not state: return

    # ИСПРАВЛЕНИЕ "NONE" В ПОДДЕРЖКЕ
    if state == "waiting_support":
        msg_text = m.text or m.caption or "[Медиа без текста]"
        for aid in ADMINS:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Ответить", callback_data=f"ans_{uid}")]])
            await bot.send_message(aid, f"🆘 <b>Вопрос от @{m.from_user.username}:</b>\n\n{msg_text}", reply_markup=kb, parse_mode="HTML")
        db["states"].pop(uid, None)
        save_db(db)
        return await m.answer("✅ Твой вопрос отправлен админам!", reply_markup=get_main_kb())

    if state == "waiting_post":
        f_id = m.photo[-1].file_id if m.photo else (m.video.file_id if m.video else None)
        f_type = "photo" if m.photo else ("video" if m.video else None)
        txt = m.caption or m.text or ""
        
        db["posts"].append({"user_id": uid, "username": m.from_user.username, "text": txt, "file_id": f_id, "file_type": f_type, "admin_msgs": []})
        p_id = len(db["posts"])
        db["states"].pop(uid, None)
        save_db(db)

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
        
        save_db(db)
        await m.answer("🚀 Пост отправлен на модерацию!", reply_markup=get_main_kb())

# --- ОБРАБОТКА CALLBACK ---
@dp.callback_query(F.data.startswith("acc_") | F.data.startswith("rej_"))
async def handle_mod(c: types.CallbackQuery):
    act, p_id = c.data.split("_")[0], int(c.data.split("_")[1])
    db = load_db()
    p = db["posts"][p_id-1]
    
    if act == "acc":
        final_cap = f"{p['text']}{FOOTER_TEXT}"
        if p["file_type"] == "photo": await bot.send_photo(PUBLISH_CHANNEL, p["file_id"], caption=final_cap, parse_mode="HTML")
        elif p["file_type"] == "video": await bot.send_video(PUBLISH_CHANNEL, p["file_id"], caption=final_cap, parse_mode="HTML")
        else: await bot.send_message(PUBLISH_CHANNEL, final_cap, parse_mode="HTML")
        await bot.send_message(p["user_id"], "🎉 Твой пост опубликован!")
    
    for am in p["admin_msgs"]:
        try: await bot.edit_message_reply_markup(chat_id=am["chat"], message_id=am["id"], reply_markup=None)
        except: pass
    await c.answer("Выполнено")

@dp.callback_query(F.data.startswith("ans_"))
async def handle_ans(c: types.CallbackQuery):
    uid = c.data.split("_")[1]
    await c.message.answer(f"Скопируй и ответь:\n<code>/reply {uid} ТЕКСТ</code>", parse_mode="HTML")
    await c.answer()

@dp.message(Command("reply"), F.from_user.id.in_(ADMINS))
async def cmd_reply(m: types.Message, command: CommandObject):
    if not command.args or " " not in command.args: 
        return await m.answer("Формат: /reply ID Текст")
    uid, text = command.args.split(" ", 1)
    try:
        await bot.send_message(uid, f"🆘 <b>Ответ поддержки:</b>\n\n{text}", parse_mode="HTML")
        await m.answer("✅ Ответ отправлен пользователю!")
    except: await m.answer("❌ Ошибка отправки")

# --- ЗАПУСК ---
async def main():
    asyncio.create_task(start_web())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
