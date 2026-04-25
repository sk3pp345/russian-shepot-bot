import os
import asyncio
import json
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    LabeledPrice, 
    PreCheckoutQuery,
    ContentType
)
from aiogram.filters import Command, CommandObject
from aiohttp import web

# --- НАСТРОЙКИ ЛОГИРОВАНИЯ ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ---
TOKEN = os.getenv("BOT_TOKEN")
PUBLISH_CHANNEL = "@dnipro1777" 
ADMINS = [1252647696, 5028188335] 
DB_FILE = "database_ru.json"

# Подпись для постов (FOOTER_TEXT) — определена заранее, чтобы не было NameError
FOOTER_TEXT = (
    "\n\n<b><a href='https://t.me/Info114Pod'>ℹ️ Инфо</a> | "
    "<a href='https://t.me/+W65-IzDXhT85ZTky'>💬 Чат</a> | "
    "<a href='https://t.me/shkola_114_bot'>🤖 Предложка</a> | "
    "<a href='https://t.me/Per114Pod'>🔗 Переходник</a></b>"
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ФУНКЦИИ РАБОТЫ С БАЗОЙ ДАННЫХ ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки базы: {e}")
    return {"users": {}, "posts": [], "states": {}}

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Ошибка сохранения базы: {e}")

# --- WEB СЕРВЕР (ДЛЯ RENDER) ---
async def handle_web_request(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web_request)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Web-сервер запущен на порту {port}")

# --- КЛАВИАТУРЫ ---
def get_main_keyboard():
    keyboard = [
        [KeyboardButton(text="📝 Предложить пост")],
        [KeyboardButton(text="💎 Магазин"), KeyboardButton(text="🆘 Поддержка")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_back_keyboard():
    keyboard = [[KeyboardButton(text="⬅️ Назад")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# --- ОБРАБОТЧИКИ КОМАНД ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db = load_db()
    user_id = str(message.from_user.id)
    db["users"][user_id] = message.from_user.username or "Anonymous"
    save_db(db)
    
    welcome_text = "Привет! Это <b>Подслушано Школы 114</b> 🤫\n\nВыбери действие:"
    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="HTML")

@dp.message(Command("admins"), F.from_user.id.in_(ADMINS))
async def cmd_admins(message: types.Message):
    admin_panel = (
        "🛠 <b>Админ-панель</b>\n\n"
        "<b>/stats</b> — Статистика\n"
        "<b>/send ТЕКСТ</b> — Рассылка\n"
        "<b>/check ID</b> — Просмотр поста по номеру\n"
        "<b>/history @username</b> — Поиск ID юзера\n\n"
        "<i>Также ты можешь переслать пост из канала боту, чтобы узнать автора.</i>"
    )
    await message.answer(admin_panel, parse_mode="HTML")

# --- ИНФО О ПОСТЕ И ПЕРЕСЫЛКА ---
@dp.message(Command("check"), F.from_user.id.in_(ADMINS))
async def cmd_check(message: types.Message, command: CommandObject):
    if not command.args:
        return await message.answer("Используй: /check 5")
    
    db = load_db()
    try:
        p_idx = int(command.args) - 1
        post = db["posts"][p_idx]
        
        info = (
            f"🔍 <b>Инфо о посте №{command.args}</b>\n"
            f"👤 Автор: @{post['username']}\n"
            f"🆔 ID автора: <code>{post['user_id']}</code>\n\n"
            f"📝 Текст:\n{post['text']}"
        )
        
        if post['file_type'] == "photo":
            await bot.send_photo(message.chat.id, post['file_id'], caption=info, parse_mode="HTML")
        elif post['file_type'] == "video":
            await bot.send_video(message.chat.id, post['file_id'], caption=info, parse_mode="HTML")
        else:
            await message.answer(info, parse_mode="HTML")
    except:
        await message.answer("❌ Пост не найден.")

# Функция поиска при пересылке из канала
@dp.message(F.forward_from_chat)
async def handle_forward_from_channel(message: types.Message):
    if message.from_user.id not in ADMINS:
        return

    db = load_db()
    raw_text = message.caption or message.text or ""
    # Убираем подпись, чтобы точнее найти в базе
    search_text = raw_text.replace(FOOTER_TEXT, "").strip()
    
    found = False
    for i, p in enumerate(db["posts"]):
        # Проверяем, совпадает ли текст (хотя бы частично)
        if p["text"] and search_text and (p["text"] in search_text or search_text in p["text"]):
            info = (
                f"🎯 <b>Пост найден в базе!</b>\n\n"
                f"📮 Номер в БД: <code>{i+1}</code>\n"
                f"👤 Автор: @{p['username']}\n"
                f"🆔 ID автора: <code>{p['user_id']}</code>"
            )
            await message.reply(info, parse_mode="HTML")
            found = True
            break
    
    if not found:
        await message.reply("❌ Этого поста нет в моей базе данных.")

# --- МАГАЗИН ---
@dp.message(F.text == "💎 Магазин")
async def action_shop(message: types.Message):
    buttons = [
        [InlineKeyboardButton(text="🔓 Разбан — 50 ⭐", callback_data="buy_Разбан_50")],
        [InlineKeyboardButton(text="📢 Реклама — 100 ⭐", callback_data="buy_Реклама_100")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("💎 <b>Магазин услуг</b>", reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data.startswith("buy_"))
async def process_payment(call: types.CallbackQuery):
    data = call.data.split("_")
    item_name = data[1]
    item_price = int(data[2])
    
    await bot.send_invoice(
        call.from_user.id,
        title=item_name,
        description=f"Оплата услуги: {item_name}",
        payload=f"payment_{item_name}",
        currency="XTR",
        prices=[LabeledPrice(label=item_name, amount=item_price)]
    )
    await call.answer()

@dp.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

# --- ПРЕДЛОЖКА (ПРОЦЕСС) ---
@dp.message(F.text == "📝 Предложить пост")
async def start_suggestion(message: types.Message):
    db = load_db()
    db["states"][str(message.from_user.id)] = "waiting_for_post"
    save_db(db)
    await message.answer("📸 Пришли свой пост (текст, фото или видео):", reply_markup=get_back_keyboard())

@dp.message(F.text == "⬅️ Назад")
async def cmd_back(message: types.Message):
    db = load_db()
    db["states"].pop(str(message.from_user.id), None)
    save_db(db)
    await message.answer("🏠 Главное меню", reply_markup=get_main_keyboard())

# --- ГЛАВНЫЙ ОБРАБОТЧИК (ПРИЕМ ПОСТА И МОДЕРАЦИЯ) ---
@dp.message()
async def global_handler(message: types.Message):
    user_id = str(message.from_user.id)
    db = load_db()
    state = db["states"].get(user_id)

    # Если пользователь ничего не предлагает, просто игнорим
    if not state:
        return

    if state == "waiting_for_post":
        # Собираем данные поста
        text_content = message.caption or message.text or ""
        file_id = None
        file_type = None

        if message.photo:
            file_id = message.photo[-1].file_id
            file_type = "photo"
        elif message.video:
            file_id = message.video.file_id
            file_type = "video"

        # Сохраняем в список постов
        new_post = {
            "user_id": user_id,
            "username": message.from_user.username or "NoName",
            "text": text_content,
            "file_id": file_id,
            "file_type": file_type,
            "admin_msgs": [] # Для удаления кнопок у всех админов
        }
        db["posts"].append(new_post)
        post_number = len(db["posts"])
        
        # Сбрасываем состояние
        db["states"].pop(user_id, None)
        save_db(db)

        # Клавиатура для админов
        admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"accept_{post_number}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{post_number}")
        ]])

        # Рассылка админам на проверку
        for admin_id in ADMINS:
            caption = f"👤 От: @{message.from_user.username}\n📮 Пост №: {post_number}\n\n{text_content}"
            try:
                if file_type == "photo":
                    m = await bot.send_photo(admin_id, file_id, caption=caption, reply_markup=admin_kb)
                elif file_type == "video":
                    m = await bot.send_video(admin_id, file_id, caption=caption, reply_markup=admin_kb)
                else:
                    m = await bot.send_message(admin_id, caption, reply_markup=admin_kb)
                
                # Запоминаем сообщение у админа
                db["posts"][-1]["admin_msgs"].append({"chat_id": admin_id, "msg_id": m.message_id})
            except Exception as e:
                logger.error(f"Не удалось отправить админу {admin_id}: {e}")

        save_db(db)
        await message.answer("⏳ Твой пост отправлен на модерацию!", reply_markup=get_main_keyboard())

# --- ОБРАБОТКА РЕШЕНИЯ АДМИНА ---
@dp.callback_query(F.data.startswith("accept_") | F.data.startswith("reject_"))
async def handle_moderation(call: types.CallbackQuery):
    action, post_id = call.data.split("_")
    db = load_db()
    post_index = int(post_id) - 1
    post = db["posts"][post_index]

    if action == "accept":
        full_caption = f"{post['text']}{FOOTER_TEXT}"
        
        try:
            if post["file_type"] == "photo":
                await bot.send_photo(PUBLISH_CHANNEL, post["file_id"], caption=full_caption, parse_mode="HTML")
            elif post["file_type"] == "video":
                await bot.send_video(PUBLISH_CHANNEL, post["file_id"], caption=full_caption, parse_mode="HTML")
            else:
                await bot.send_message(PUBLISH_CHANNEL, full_caption, parse_mode="HTML", disable_web_page_preview=True)
            
            await bot.send_message(int(post["user_id"]), "🌟 Твой пост был опубликован в канале!")
            status = "✅ Одобрено"
        except Exception as e:
            await call.message.answer(f"Ошибка публикации: {e}")
            return
    else:
        await bot.send_message(int(post["user_id"]), "❌ К сожалению, твой пост отклонен модерацией.")
        status = "❌ Отклонено"

    # Убираем кнопки у всех админов
    for msg_info in post["admin_msgs"]:
        try:
            await bot.edit_message_reply_markup(
                chat_id=msg_info["chat_id"], 
                message_id=msg_info["msg_id"], 
                reply_markup=None
            )
        except:
            pass

    await call.answer(status)

# --- ЗАПУСК ---
async def main():
    # Сначала запускаем веб-сервер для Render
    asyncio.create_task(start_web_server())
    # Потом запускаем самого бота
    logger.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
