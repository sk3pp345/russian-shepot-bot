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

FOOTER_TEXT = "\n\n<b><a href='https://t.me/shepotrussiabot'>Предложка (@shepotrussiabot)</a>\n<a href='https://t.me/shepotrussia'>Шёпот России (t.me/shepotrussia)</a>\n<a href='https://t.me/shepotrussiachat'>Чат</a></b>"

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

# --- ОБРАБОТКА /START И /ADMINS ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db = load_db()
    db["users"][str(message.from_user.id)] = message.from_user.username or "NoUser"
    save_db(db)
    await message.answer(f"Привет! Это <b>Шёпот России</b> 🤫\n\nВыбери действие в меню ниже:", reply_markup=get_main_kb(), parse_mode="HTML")

@dp.message(Command("admins"))
async def cmd_admins(message: types.Message):
    # Обновленный текст админ-панели
    admin_text = (
        "🛠 <b>Админ-панель</b>\n\n"
        "<b>/stats</b> — Статистика (юзеры и посты)\n"
        "<b>/send текст</b> — Рассылка сообщения всем юзерам\n"
        "<b>/history @user</b> — Все ID постов и ID самого юзера\n"
        "<b>/check ID</b> — Посмотреть пост (текст + медиа)\n\n"
        "<i>Администраторы: @sk3pp345, @ada_dev</i>"
    )
    await message.answer(admin_text, parse_mode="HTML")

# --- КОМАНДЫ УПРАВЛЕНИЯ ---
@dp.message(Command("stats"), F.from_user.id.in_(ADMINS))
async def cmd_stats(message: types.Message):
    db = load_db()
    await message.answer(f"📊 <b>Статистика:</b>\n\nЮзеров в базе: {len(db['users'])}\nВсего предложки: {len(db['posts'])}", parse_mode="HTML")

@dp.message(Command("check"), F.from_user.id.in_(ADMINS))
async def cmd_check(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Введите ID: /check 5")
    db = load_db()
    try:
        p_idx = int(command.args)-1
        p = db["posts"][p_idx]
        info = f"🔍 <b>Инфо о посте №{command.args}</b>\n👤 Автор: @{p['username']}\n🆔 ID автора: <code>{p['user_id']}</code>\n\n📝 Текст:\n{p['text']}"
        
        if p['file_type'] == "photo": await bot.send_photo(message.chat.id, p['file_id'], caption=info, parse_mode="HTML")
        elif p['file_type'] == "video": await bot.send_video(message.chat.id, p['file_id'], caption=info, parse_mode="HTML")
        else: await message.answer(info, parse_mode="HTML")
    except: await message.answer("❌ Пост с таким номером не найден.")

@dp.message(Command("history"), F.from_user.id.in_(ADMINS))
async def cmd_history(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Введите юзернейм: /history @user")
    db = load_db()
    uname = command.args.replace("@", "")
    user_posts = [str(i+1) for i, p in enumerate(db["posts"]) if p["username"] == uname]
    user_id = next((uid for uid, un in db["users"].items() if un == uname), "Не найден в базе")
    await message.answer(f"📝 <b>История @{uname}:</b>\n🆔 ID: <code>{user_id}</code>\n📮 Номера постов: {', '.join(user_posts) if user_posts else 'еще не предлагал'}", parse_mode="HTML")

@dp.message(Command("send"), F.from_user.id.in_(ADMINS))
async def cmd_send(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Использование: /send Текст рассылки")
    db = load_db()
    users = db["users"].keys()
    count = 0
    await message.answer(f"🚀 Начинаю рассылку на {len(users)} чел...")
    for uid in users:
        try:
            await bot.send_message(uid, command.args)
            count += 1
            await asyncio.sleep(0.05) 
        except: pass
    await message.answer(f"✅ Рассылка завершена!\nПолучили: {count} пользователей.")

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
    items = {
        "ban": [("🔓 Разбан", 50), ("🔇 Размут", 25)],
        "serv": [("🎭 Префикс", 100), ("🔨 Бан (1д)", 200), ("🔇 Мут (1д)", 100)],
        "ads": [("📌 Закреп (1д)", 75), ("📢 Рекламный пост", 50)]
    }
    kb_list = [[InlineKeyboardButton(text=f"{n} — {p} ⭐", callback_data=f"buy_{n}_{p}")] for n, p in items[cat]]
    kb_list.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_shop")])
    await call.message.edit_text(f"🛍 <b>Категория: {cat.upper()}</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list), parse_mode="HTML")

@dp.callback_query(F.data == "back_to_shop")
async def back_to_shop(call: types.CallbackQuery): await action_shop(call.message)

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(call: types.CallbackQuery):
    _, item, price = call.data.split("_")
    await bot.send_invoice(call.from_user.id, title=item, description=f"Оплата товара '{item}'", payload=f"pay_{item}", currency="XTR", prices=[LabeledPrice(label=item, amount=int(price))])
    await call.answer()

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery): await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def success_pay(m: types.Message):
    await m.answer("✅ Оплата прошла успешно! Админы свяжутся с тобой.")
    for aid in ADMINS: await bot.send_message(aid, f"💰 <b>НОВАЯ ОПЛАТА</b>\nЮзер: @{m.from_user.username}\nТовар: {m.successful_payment.invoice_payload}")

# --- ПРЕДЛОЖКА И ПОДДЕРЖКА ---
@dp.message(F.text.in_(["📝 Предложить пост", "🆘 Поддержка"]))
async def set_state(message: types.Message):
    db = load_db()
    state = "waiting_for_post" if message.text == "📝 Предложить пост" else "waiting_for_support"
    db["states"][str(message.from_user.id)] = state
    save_db(db)
    text = "📸 Пришлите ваш пост:" if state == "waiting_for_post" else "💬 Опишите вашу проблему:"
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

    if state and state.startswith("rep_to_"):
        target_id = state.split("_")[2]
        try:
            await bot.send_message(target_id, f"✉️ <b>Ответ поддержки:</b>\n\n{message.text}", parse_mode="HTML")
            await message.answer("✅ Сообщение доставлено!")
        except: await message.answer("❌ Юзер заблокировал бота.")
        db["states"].pop(uid); save_db(db)
        return

    if not state: return

    if state == "waiting_for_post":
        content = message.caption or message.text or ""
        f_id = message.photo[-1].file_id if message.photo else (message.video.file_id if message.video else None)
        f_type = "photo" if message.photo else ("video" if message.video else None)
        db["posts"].append({"user_id": uid, "username": message.from_user.username, "text": content, "file_id": f_id, "file_type": f_type, "admin_msgs": []})
        p_id = len(db["posts"]); save_db(db)

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да", callback_data=f"p_acc_{p_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"p_rej_{p_id}")
        ]])
        
        for aid in ADMINS:
            info = f"👤 От: @{message.from_user.username}\n📮 Пост №: {p_id}\n\n{content}"
            msg = None
            if f_type == "photo": msg = await bot.send_photo(aid, f_id, caption=info, reply_markup=kb)
            elif f_type == "video": msg = await bot.send_video(aid, f_id, caption=info, reply_markup=kb)
            else: msg = await bot.send_message(aid, info, reply_markup=kb)
            db["posts"][-1]["admin_msgs"].append({"chat_id": aid, "msg_id": msg.message_id})
        
        save_db(db)
        await message.answer("⏳ Отправлено на модерацию!", reply_markup=get_main_kb())
        db["states"].pop(uid); save_db(db)

    elif state == "waiting_for_support":
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Ответить", callback_data=f"sup_rep_{uid}")]])
        for aid in ADMINS:
            await bot.send_message(aid, f"🆘 <b>ПОДДЕРЖКА</b>\nОт: @{message.from_user.username}\n\n{message.text}", reply_markup=kb, parse_mode="HTML")
        await message.answer("🚀 Доставлено поддержке!", reply_markup=get_main_kb())
        db["states"].pop(uid); save_db(db)

# --- МОДЕРАЦИЯ (СИНХРОНИЗАЦИЯ АДМИНОВ) ---
@dp.callback_query(F.data.startswith("p_"))
async def process_post(call: types.CallbackQuery):
    _, act, p_id = call.data.split("_")
    db = load_db()
    p_idx = int(p_id)-1
    post = db["posts"][p_idx]
    
    if act == "acc":
        if post["file_type"] == "photo": await bot.send_photo(PUBLISH_CHANNEL, post["file_id"], caption=f"{post['text']}{FOOTER_TEXT}", parse_mode="HTML")
        elif post["file_type"] == "video": await bot.send_video(PUBLISH_CHANNEL, post["file_id"], caption=f"{post['text']}{FOOTER_TEXT}", parse_mode="HTML")
        else: await bot.send_message(PUBLISH_CHANNEL, f"{post['text']}{FOOTER_TEXT}", parse_mode="HTML", disable_web_page_preview=True)
        await bot.send_message(int(post["user_id"]), "🌟 Твой пост опубликован!")
        res_text = "✅ Одобрено"
    else:
        await bot.send_message(int(post["user_id"]), "❌ Пост отклонен модерацией.")
        res_text = "❌ Отклонено"

    # Удаление кнопок у всех админов сразу
    for m in post["admin_msgs"]:
        try: await bot.edit_message_reply_markup(chat_id=m["chat_id"], message_id=m["msg_id"], reply_markup=None)
        except: pass
    
    await call.answer(res_text)

@dp.callback_query(F.data.startswith("sup_rep_"))
async def support_reply_call(call: types.CallbackQuery):
    uid = call.data.split("_")[2]
    db = load_db()
    db["states"][str(call.from_user.id)] = f"rep_to_{uid}"
    save_db(db)
    await call.message.answer(f"✍️ Пиши ответ для пользователя {uid}:")
    await call.answer()

async def main():
    asyncio.create_task(start_server())
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
