import os
import asyncio
import json
import logging
import sys
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
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiohttp import web

# ==========================================
# 1. КОНФИГУРАЦИЯ И ЛОГИРОВАНИЕ
# ==========================================

# Настройка вывода логов в консоль Render
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("Bot114")

# Константы (Определяем в самом начале, чтобы избежать NameError)
TOKEN = os.getenv("BOT_TOKEN")
PUBLISH_CHANNEL = "@dnipro1777" 
ADMINS = [1252647696, 5028188335] 
DB_FILE = "database_ru.json"

# Подпись для постов
FOOTER_TEXT = (
    "\n\n<b><a href='https://t.me/Info114Pod'>ℹ️ Инфо</a> | "
    "<a href='https://t.me/+W65-IzDXhT85ZTky'>💬 Чат</a> | "
    "<a href='https://t.me/shkola_114_bot'>🤖 Предложка</a> | "
    "<a href='https://t.me/Per114Pod'>🔗 Переходник</a></b>"
)

# Инициализация бота
if not TOKEN:
    logger.error("КРИТИЧЕСКАЯ ОШИБКА: Токен бота не найден в переменных окружения!")
    sys.exit(1)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ==========================================
# 2. РАБОТА С БАЗОЙ ДАННЫХ (JSON)
# ==========================================

def load_database():
    """Загрузка данных из файла JSON"""
    if not os.path.exists(DB_FILE):
        logger.info("Файл базы данных не найден, создаем новый.")
        return {"users": {}, "posts": [], "states": {}}
    
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при чтении базы данных: {e}")
        return {"users": {}, "posts": [], "states": {}}

def save_database(data):
    """Сохранение данных в файл JSON"""
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Ошибка при сохранении базы данных: {e}")

# ==========================================
# 3. КЛАВИАТУРЫ
# ==========================================

def get_main_menu_kb():
    """Главное меню бота"""
    buttons = [
        [KeyboardButton(text="📝 Предложить пост")],
        [KeyboardButton(text="💎 Магазин"), KeyboardButton(text="🆘 Поддержка")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_cancel_kb():
    """Кнопка отмены/назад"""
    buttons = [[KeyboardButton(text="⬅️ Назад")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ==========================================
# 4. АДМИНСКИЕ ФУНКЦИИ И ИНФО О ПОСТАХ
# ==========================================

@dp.message(Command("admins"), F.from_user.id.in_(ADMINS))
async def admin_help(message: types.Message):
    """Список команд для администратора"""
    text = (
        "🛠 <b>Панель администратора</b>\n\n"
        "• <code>/stats</code> — Посмотреть количество юзеров и постов\n"
        "• <code>/check [ID]</code> — Найти пост по его номеру в базе\n"
        "• <code>/send [Текст]</code> — Сделать рассылку всем пользователям\n\n"
        "💡 <b>Подсказка:</b> Перешли пост из канала в этот чат, чтобы узнать, кто его автор."
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("stats"), F.from_user.id.in_(ADMINS))
async def admin_stats(message: types.Message):
    """Статистика бота"""
    db = load_database()
    u_count = len(db.get("users", {}))
    p_count = len(db.get("posts", []))
    await message.answer(f"📊 <b>Статистика:</b>\n\nЮзеров: {u_count}\nПостов в базе: {p_count}", parse_mode="HTML")

@dp.message(Command("check"), F.from_user.id.in_(ADMINS))
async def admin_check_post(message: types.Message, command: CommandObject):
    """Просмотр конкретного поста по его индексу"""
    if not command.args:
        return await message.answer("Укажите номер поста. Пример: <code>/check 10</code>", parse_mode="HTML")
    
    db = load_database()
    try:
        index = int(command.args) - 1
        posts = db.get("posts", [])
        
        if index < 0 or index >= len(posts):
            return await message.answer("❌ Пост с таким номером не найден.")
        
        p = posts[index]
        info = (
            f"🔍 <b>Информация о посте №{command.args}</b>\n"
            f"👤 Автор: @{p.get('username', 'Hidden')}\n"
            f"🆔 ID автора: <code>{p.get('user_id')}</code>\n\n"
            f"📝 Текст:\n{p.get('text', '[Нет текста]')}"
        )
        
        if p.get('file_type') == "photo":
            await bot.send_photo(message.chat.id, p['file_id'], caption=info, parse_mode="HTML")
        elif p.get('file_type') == "video":
            await bot.send_video(message.chat.id, p['file_id'], caption=info, parse_mode="HTML")
        else:
            await message.answer(info, parse_mode="HTML")
            
    except ValueError:
        await message.answer("❌ Номер поста должен быть числом.")

# ФУНКЦИЯ ПОЛУЧЕНИЯ ИНФО О ПОСТЕ ЧЕРЕЗ ПЕРЕСЫЛКУ
@dp.message(F.forward_from_chat)
async def info_from_forward(message: types.Message):
    """Определение автора при пересылке сообщения из канала админом"""
    if message.from_user.id not in ADMINS:
        return

    db = load_database()
    # Получаем чистый текст поста без тегов, чтобы сравнить с базой
    msg_text = message.caption or message.text or ""
    clean_search = msg_text.replace(FOOTER_TEXT, "").strip()
    
    found_post = None
    post_index = 0
    
    for i, p in enumerate(db.get("posts", [])):
        db_text = p.get("text", "").strip()
        if db_text and clean_search and (db_text in clean_search or clean_search in db_text):
            found_post = p
            post_index = i + 1
            break
            
    if found_post:
        response = (
            f"✅ <b>Автор найден!</b>\n\n"
            f"👤 Юзер: @{found_post.get('username')}\n"
            f"🆔 ID: <code>{found_post.get('user_id')}</code>\n"
            f"📮 Номер поста в БД: {post_index}"
        )
        await message.reply(response, parse_mode="HTML")
    else:
        await message.reply("❌ Не удалось найти этот пост в базе данных предложки.")

# ==========================================
# 5. МАГАЗИН И ПЛАТЕЖИ
# ==========================================

@dp.message(F.text == "💎 Магазин")
async def show_shop(message: types.Message):
    """Интерфейс магазина"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 Разбан — 50 ⭐", callback_data="buy_unban_50")],
        [InlineKeyboardButton(text="📢 Реклама — 100 ⭐", callback_data="buy_ads_100")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="to_main")]
    ])
    await message.answer("🛒 <b>Магазин услуг</b>\n\nВыбери нужный товар:", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("buy_"))
async def create_invoice(call: types.CallbackQuery):
    """Создание счета на оплату через Telegram Stars"""
    _, item, price = call.data.split("_")
    
    label = "Разбан" if item == "unban" else "Реклама"
    
    try:
        await bot.send_invoice(
            chat_id=call.from_user.id,
            title=f"Покупка: {label}",
            description=f"Оплата услуги {label} в боте Предложка 114",
            payload=f"stars_pay_{item}",
            currency="XTR",
            prices=[LabeledPrice(label=label, amount=int(price))]
        )
        await call.answer()
    except Exception as e:
        logger.error(f"Ошибка при создании счета: {e}")
        await call.answer("❌ Ошибка при создании счета.", show_alert=True)

@dp.pre_checkout_query()
async def check_payment_valid(query: PreCheckoutQuery):
    """Подтверждение готовности к оплате"""
    await bot.answer_pre_checkout_query(query.id, ok=True)

# ==========================================
# 6. ЛОГИКА ПРЕДЛОЖКИ (СОСТОЯНИЯ)
# ==========================================

@dp.message(F.text == "📝 Предложить пост")
async def start_suggest(message: types.Message):
    """Начало процесса предложения поста"""
    db = load_database()
    db["states"][str(message.from_user.id)] = "waiting_for_content"
    save_database(db)
    
    await message.answer(
        "📝 <b>Напиши текст своего поста или отправь фото/видео.</b>\n\n"
        "Если ты хочешь отменить отправку, нажми кнопку ниже.",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )

@dp.message(F.text == "⬅️ Назад")
async def cancel_action(message: types.Message):
    """Отмена действий и возврат в меню"""
    db = load_database()
    db["states"].pop(str(message.from_user.id), None)
    save_database(db)
    await message.answer("🏠 Возвращаемся в главное меню.", reply_markup=get_main_menu_kb())

@dp.message()
async def process_user_messages(message: types.Message):
    """Основной обработчик сообщений (прием постов)"""
    user_id = str(message.from_user.id)
    db = load_database()
    user_state = db.get("states", {}).get(user_id)

    # Если пользователь просто пишет боту без активного состояния
    if not user_state:
        if message.from_user.id not in ADMINS:
            await message.answer("Воспользуйся кнопками меню 👇", reply_markup=get_main_menu_kb())
        return

    # Логика приема контента поста
    if user_state == "waiting_for_content":
        content_text = message.caption or message.text or ""
        f_id = None
        f_type = None

        if message.photo:
            f_id = message.photo[-1].file_id
            f_type = "photo"
        elif message.video:
            f_id = message.video.file_id
            f_type = "video"

        # Сохраняем пост в базу
        new_post = {
            "user_id": user_id,
            "username": message.from_user.username or "NoUsername",
            "text": content_text,
            "file_id": f_id,
            "file_type": f_type,
            "admin_msgs": []
        }
        db["posts"].append(new_post)
        p_id = len(db["posts"])
        
        # Сбрасываем состояние
        db["states"].pop(user_id, None)
        save_database(db)

        # Клавиатура для модерации
        mod_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"adm_acc_{p_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_rej_{p_id}")
        ]])

        # Уведомляем админов
        for admin_id in ADMINS:
            try:
                caption = f"🆕 <b>Новая предложка №{p_id}</b>\n👤 От: @{message.from_user.username}\n\n{content_text}"
                
                if f_type == "photo":
                    sent = await bot.send_photo(admin_id, f_id, caption=caption, reply_markup=mod_kb, parse_mode="HTML")
                elif f_type == "video":
                    sent = await bot.send_video(admin_id, f_id, caption=caption, reply_markup=mod_kb, parse_mode="HTML")
                else:
                    sent = await bot.send_message(admin_id, caption, reply_markup=mod_kb, parse_mode="HTML")
                
                # Сохраняем ID сообщений у админов для последующего удаления кнопок
                db["posts"][-1]["admin_msgs"].append({"chat": admin_id, "id": sent.message_id})
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

        save_database(db)
        await message.answer("✅ Твой пост успешно отправлен модераторам!", reply_markup=get_main_menu_kb())

# ==========================================
# 7. МОДЕРАЦИЯ (ОБРАБОТКА КНОПОК)
# ==========================================

@dp.callback_query(F.data.startswith("adm_"))
async def handle_moderation_callback(call: types.CallbackQuery):
    """Обработка кнопок 'Опубликовать' и 'Отклонить'"""
    parts = call.data.split("_")
    action = parts[1]
    post_id = int(parts[2])
    
    db = load_database()
    post = db["posts"][post_id - 1]

    if action == "acc":
        # Формируем итоговое сообщение для канала
        final_text = f"{post['text']}{FOOTER_TEXT}"
        
        try:
            if post["file_type"] == "photo":
                await bot.send_photo(PUBLISH_CHANNEL, post["file_id"], caption=final_text, parse_mode="HTML")
            elif post["file_type"] == "video":
                await bot.send_video(PUBLISH_CHANNEL, post["file_id"], caption=final_text, parse_mode="HTML")
            else:
                await bot.send_message(PUBLISH_CHANNEL, final_text, parse_mode="HTML", disable_web_page_preview=True)
            
            await bot.send_message(int(post["user_id"]), "🎉 Твой пост был опубликован в канале!")
            msg_status = "✅ Опубликовано"
        except Exception as e:
            logger.error(f"Ошибка при публикации в канал: {e}")
            return await call.answer("❌ Ошибка при отправке в канал.", show_alert=True)
    else:
        try:
            await bot.send_message(int(post["user_id"]), "❌ Извини, но твой пост был отклонен модерацией.")
        except: pass
        msg_status = "❌ Отклонено"

    # Удаляем инлайновые кнопки у всех админов
    for m_info in post.get("admin_msgs", []):
        try:
            await bot.edit_message_reply_markup(chat_id=m_info["chat"], message_id=m_info["id"], reply_markup=None)
        except: pass

    await call.answer(msg_status)

# ==========================================
# 8. ЗАПУСК WEB-СЕРВЕРА И БОТА
# ==========================================

async def web_healthcheck(request):
    return web.Response(text="Bot Active")

async def start_app():
    # Настройка Web-сервера для Render
    app = web.Application()
    app.router.add_get('/', web_healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Healthcheck сервер запущен на порту {port}")

async def main_loop():
    # Запускаем фоновые задачи
    asyncio.create_task(start_app())
    
    # Запускаем опрос сервера Telegram
    logger.info("Запуск Polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот выключен.")
