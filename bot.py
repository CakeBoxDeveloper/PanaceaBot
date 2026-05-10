import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://your-project.vercel.app")

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

# ─── Запуск (локально) ────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("Bot is running (polling)...")
    app.run_polling()
