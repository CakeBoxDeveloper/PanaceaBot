"""
Vercel serverless entry point.
Telegram шлёт POST на /api/webhook — мы обрабатываем и отвечаем.
"""
import os
import json
import asyncio
from http.server import BaseHTTPRequestHandler

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ─── Настройки (берутся из Environment Variables на Vercel) ───────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]

WELCOME_TEXT = (
    "👋 Привет! Добро пожаловать.\n\n"
    "Здесь ты найдёшь всё самое интересное — "
    "выбирай куда хочешь перейти 👇"
)

PHOTO_URL   = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaAvatar.png"
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

# ─── Vercel handler ───────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        async def process():
            app = ApplicationBuilder().token(BOT_TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            await app.initialize()
            update = Update.de_json(json.loads(body), app.bot)
            await app.process_update(update)
            await app.shutdown()

        asyncio.run(process())

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")
