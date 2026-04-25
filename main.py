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

# --- ОБРАБОТКА /START ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db = load_db()
    db["users"][str(message.from_user.id)] = message.from_user.username or "NoUser"
    save_db(db)
    await message.answer(f"Привет! Это <b>Шёпот России</b> 🤫\n\nВыбери нужное действие в меню ниже:", 
                         reply_markup=get_main_kb(), parse_mode="HTML")

@dp.message(Command("admins"))
async def cmd_admins(message: types.Message):
    await message.answer("🛠 <b>Администрация проекта:</b>\n\n• @sk3pp345\n• @ada_dev\n\nПо вопросам сотрудничества пишите в поддержку!", parse_mode="HTML")

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
            [InlineKeyboardButton(text="🔓 Разбан — 50 ⭐", callback_data="buy_Разбан_50")],
            [InlineKeyboardButton(text="🔇 Размут — 25 ⭐", callback_data="buy_Размут_25")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_shop")]
        ])
        await call.message.edit_text("🔓 <b>Категория: Разбан</b>", reply_markup=kb, parse_mode="HTML")
    elif cat == "serv":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎭 Префикс — 100 ⭐", callback_data="buy_Префикс_100")],
            [InlineKeyboardButton(text="🔨 Бан (1д) — 200 ⭐", callback_data="buy_Бан-1д_200")],
            [InlineKeyboardButton(text="🔇 Мут (1д) — 100 ⭐", callback_data="buy_Мут-1д_100")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_shop")]
        ])
        await call.message.edit_text("🛠 <b>Категория: Услуги</b>", reply_markup=kb, parse_mode="HTML")
    elif cat == "ads":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📌 Закреп (1д) — 75 ⭐", callback_data="buy_Закреп_75")],
            [InlineKeyboardButton(text="📢 Рекламный пост — 50 ⭐", callback_data="buy_Реклама_50")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_shop")]
        ])
        await call.message.edit_text("📢 <b>Категория: Реклама</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "back_to_shop")
async def back_to_shop(call: types.CallbackQuery): await action_shop(call.message)

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(call: types.CallbackQuery):
    _, item_name, price = call.data.split("_")
    prices = [LabeledPrice(label=item_name, amount=int(price))]
    await bot.send_invoice(
        call.from_user.id, title=f"Покупка: {item_name}", 
        description=f"Оплата товара '{item_name}' через Telegram Stars",
        payload=f"pay_{item_name}", currency="XTR", prices=prices
    )
    await call.answer()

@dp.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def success_payment(message: types.Message):
    await message.answer("✅ Оплата прошла успешно! Администраторы свяжутся с вами для активации услуги.")
    for aid in ADMINS:
        await bot.send_message(aid, f"💰 <b>НОВАЯ ОПЛАТА</b>\nЮзер: @{message.from_user.username}\nТовар: {message.successful_payment.invoice_payload}")

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

    # 1. Ответ админа юзеру (логика поддержки)
    if state and state.startswith("rep_to_"):
        target_id = state.split("_")[2]
        try:
            if message.photo: await bot.send_photo(target_id, message.photo[-1].file_id, caption=f"✉️ <b>Ответ от поддержки:</b>\n\n{message.caption or ''}", parse_mode="HTML")
            else: await bot.send_message(target_id, f"✉️ <b>Ответ от поддержки:</b>\n\n{message.text}", parse_mode="HTML")
            await message.answer("✅ Сообщение доставлено пользователю!")
        except: await message.answer("❌ Не удалось отправить (юзер заблокировал бота)")
        db["states"].pop(uid); save_db(db)
        return

    # 2. Распознавание пересланного поста (для админа)
    if message.forward_from_chat and message.forward_from_chat.username == PUBLISH_CHANNEL.replace("@", ""):
        found = False
        for i, p in enumerate(db["posts"]):
            if p.get("text") in (message.text or message.caption or ""):
                await message.answer(f"🔍 <b>Инфо:</b>\n👤 Автор: @{p['username']}\n🆔 ID: <code>{p['user_id']}</code>\n📮 №: <code>{i+1}</code>", parse_mode="HTML")
                found = True; break
        if not found: await message.answer("❌ Пост не найден в базе.")
        return

    if not state: return

    # 3. Обработка предложки
    if state == "waiting_for_post":
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да", callback_data=f"p_acc_{uid}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"p_rej_{uid}")
        ]])
        content = message.caption or message.text or ""
        f_id = message.photo[-1].file_id if message.photo else (message.video.file_id if message.video else None)
        f_type = "photo" if message.photo else ("video" if message.video else None)
        
        db["posts"].append({"user_id": uid, "username": message.from_user.username, "text": content, "file_id": f_id, "file_type": f_type})
        p_id = len(db["posts"]); save_db(db)

        for aid in ADMINS:
            info = f"👤 От: @{message.from_user.username}\n📮 Пост №: {p_id}\n\n{content}"
            if f_type == "photo": await bot.send_photo(aid, f_id, caption=info, reply_markup=kb)
            elif f_type == "video": await bot.send_video(aid, f_id, caption=info, reply_markup=kb)
            else: await bot.send_message(aid, info, reply_markup=kb)
        
        await message.answer("⏳ Отправлено админам!", reply_markup=get_main_kb())
        db["states"].pop(uid); save_db(db)

    # 4. Обработка поддержки
    elif state == "waiting_for_support":
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Ответить", callback_data=f"sup_rep_{uid}")]])
        for aid in ADMINS:
            info = f"🆘 <b>ПОДДЕРЖКА</b>\nОт: @{message.from_user.username} (<code>{uid}</code>)\n\n"
            if message.photo: await bot.send_photo(aid, message.photo[-1].file_id, caption=info + (message.caption or ""), reply_markup=kb, parse_mode="HTML")
            else: await bot.send_message(aid, info + (message.text or ""), reply_markup=kb, parse_mode="HTML")
        await message.answer("🚀 Сообщение доставлено поддержке!", reply_markup=get_main_kb())
        db["states"].pop(uid); save_db(db)

# --- МОДЕРАЦИЯ ---
@dp.callback_query(F.data.startswith("p_"))
async def process_post(call: types.CallbackQuery):
    _, act, t_uid = call.data.split("_")
    if act == "acc":
        content = call.message.caption or call.message.text or ""
        if "От:" in content: content = content.split("\n\n")[-1]
        
        if call.message.photo: await bot.send_photo(PUBLISH_CHANNEL, call.message.photo[-1].file_id, caption=f"{content}{FOOTER_TEXT}", parse_mode="HTML")
        elif call.message.video: await bot.send_video(PUBLISH_CHANNEL, call.message.video.file_id, caption=f"{content}{FOOTER_TEXT}", parse_mode="HTML")
        else: await bot.send_message(PUBLISH_CHANNEL, f"{content}{FOOTER_TEXT}", parse_mode="HTML", disable_web_page_preview=True)
        await bot.send_message(int(t_uid), "🌟 <b>Твой пост опубликован в канале!</b>", parse_mode="HTML")
    else:
        await bot.send_message(int(t_uid), "❌ <b>Твой пост был отклонен модерацией.</b>", parse_mode="HTML")
    
    await call.message.delete_reply_markup()
    await call.answer()

@dp.callback_query(F.data.startswith("sup_rep_"))
async def support_reply_call(call: types.CallbackQuery):
    uid = call.data.split("_")[2]
    db = load_db()
    db["states"][str(call.from_user.id)] = f"rep_to_{uid}"
    save_db(db)
    await call.message.answer(f"✍️ Напиши сообщение для пользователя {uid}. Оно будет отправлено следующим сообщением:")
    await call.answer()

async def main():
    asyncio.create_task(start_server())
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
