import os
import json
import subprocess
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://your-project.vercel.app")
ADMIN_PASSWORD = "12345"  # ← Замени на свой пароль

# Хранилище состояний пользователей
user_states = {}  # {user_id: {"state": "waiting_password" | "admin_panel" | "waiting_url"}}

# ─── Контент ──────────────────────────────────────────────────────────────────
WELCOME_TEXT = (
    "👋 Привет! Добро пожаловать.\n\n"
    "Здесь ты найдёшь всё самое интересное — "
    "выбирай куда хочешь перейти 👇"
)

PHOTO_URL   = "https://example.com/your-image.jpg"  # ← загрузи картинку и замени ссылку

SITE_URL    = "https://panacea.mom"
CHANNEL_URL = "https://t.me/PanaceaPlus"
YOUTUBE_URL = "https://www.youtube.com/@PanaceaChannel"

# ─── Клавиатура ───────────────────────────────────────────────────────────────
def build_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🌐 Сайт", url=SITE_URL)],
        [
            InlineKeyboardButton("📢 Канал", url=CHANNEL_URL),
            InlineKeyboardButton("▶️ YouTube", url=YOUTUBE_URL),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

# ─── Хендлер /start ───────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_photo(
        photo=PHOTO_URL,
        caption=WELCOME_TEXT,
        reply_markup=build_keyboard(),
    )

# ─── Хендлер /admin ───────────────────────────────────────────────────────────
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_states[user_id] = {"state": "waiting_password"}
    await update.message.reply_text("🔐 Введи пароль для доступа к админ-панели:")

# ─── Админ-панель с фото ──────────────────────────────────────────────────────
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    text = (
        "<b>🔧 Админ-панель</b>\n\n"
        "Загрузи видео на канал"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📹 Загрузить видео", callback_data="post_video")],
        [InlineKeyboardButton("🚪 Выход", callback_data="logout")],
    ])
    
    photo_url = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaGift.png"
    
    user_states[user_id] = {"state": "admin_panel"}
    await update.message.reply_photo(
        photo=photo_url,
        caption=text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# ─── Обработка текстовых сообщений ────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id].get("state")
    
    # Ожидаем пароль
    if state == "waiting_password":
        if text == ADMIN_PASSWORD:
            await update.message.reply_text("✓ Пароль верный!")
            await show_admin_panel(update, context)
        else:
            await update.message.reply_text("❌ Неверный пароль. Попробуй ещё раз:")
    
    # Ожидаем ссылку на видео
    elif state == "waiting_url":
        if "youtube.com" in text or "youtu.be" in text:
            await update.message.reply_text("⏳ Выкладываю видео...")
            
            # Запускаем скрипт
            try:
                result = subprocess.run(
                    [sys.executable, "post_youtube.py", text],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
                
                if result.returncode == 0:
                    output = f"✓ Успешно!\n\n{result.stdout}"
                else:
                    output = f"✗ Ошибка:\n\n{result.stderr}"
            except subprocess.TimeoutExpired:
                output = "✗ Скрипт выполнялся слишком долго (>60 сек)"
            except Exception as e:
                output = f"✗ Ошибка: {str(e)}"
            
            await update.message.reply_text(f"<b>Результат:</b>\n\n<code>{output}</code>", parse_mode="HTML")
            
            # Возвращаемся в админ-панель
            await show_admin_panel(update, context)
        else:
            await update.message.reply_text("❌ Это не похоже на YouTube ссылку. Попробуй ещё раз:")

# ─── Обработка callback'ов ────────────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await query.answer()
    
    if user_id not in user_states or user_states[user_id].get("state") != "admin_panel":
        await query.edit_message_text("❌ Сначала введи пароль")
        return
    
    if data == "post_video":
        user_states[user_id] = {"state": "waiting_url"}
        await query.edit_message_text("📹 Отправь ссылку на YouTube видео:\n\nПример: https://www.youtube.com/watch?v=UKUOGqeRWjk")
    
    elif data == "logout":
        if user_id in user_states:
            del user_states[user_id]
        await query.edit_message_text("👋 Вышел из админ-панели")

# ─── Запуск (локально) ────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is running (polling)...")
    app.run_polling()
