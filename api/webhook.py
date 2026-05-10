"""
Vercel serverless entry point.
Telegram шлёт POST на /api/webhook — мы обрабатываем и отвечаем.
"""
import os
import json
import asyncio
from http.server import BaseHTTPRequestHandler

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]

SITE_URL    = "https://panacea.mom"
CHANNEL_URL = "https://t.me/PanaceaPlus"
YOUTUBE_URL = "https://www.youtube.com/@PanaceaChannel"

PHOTO_MAIN    = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaAvatar.png"
PHOTO_SUPPORT = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaAvatar.png"

# ─── Тексты ───────────────────────────────────────────────────────────────────
WELCOME_TEXT = (
    "👋 Привет! Добро пожаловать в Panacea.\n\n"
    "Здесь ты найдёшь всё самое интересное — "
    "выбирай куда хочешь перейти 👇"
)

SUPPORT_TEXT = (
    "🛟 <b>Служба поддержки</b>\n\n"
    "Выбери тему — и мы всё объясним:"
)

# ─── База знаний ──────────────────────────────────────────────────────────────
KNOWLEDGE_BASE = {
    "kb_what": {
        "title": "🔮 Что такое Panacea?",
        "text": (
            "🔮 <b>Что такое Panacea?</b>\n\n"
            "Panacea — это пространство, где твой личный запрос встречается с коллективным знанием человечества.\n\n"
            "Миллионы текстов, традиций и историй собраны в одном месте — чтобы помочь тебе найти ответы <i>внутри себя</i>.\n\n"
            "Каждый сеанс — это не гадание и не совет. Это <b>зеркало</b>. Модели не говорят тебе что делать — "
            "они помогают увидеть то, что ты уже знаешь, но ещё не сформулировал."
        ),
    },
    "kb_models": {
        "title": "🧬 Наши модели",
        "text": (
            "🧬 <b>Наши модели</b>\n\n"
            "Каждая модель — это отдельная система, обученная на определённой традиции знания:\n\n"
            "🃏 <b>Таратаролог</b> — мастер тарологии. Помогает увидеть скрытое за поверхностью событий.\n\n"
            "🔗 <b>Кармакармолог</b> — читает кармические узлы и повторяющиеся сценарии жизни.\n\n"
            "⭐️ <b>Астраастролог</b> — эксперт по астрологии и натальным картам.\n\n"
            "🌀 <b>Еварегрессолог</b> — проводник в память прошлых жизней.\n\n"
            "🧠 <b>Психеяпсихолог</b> — юнгианский психолог и нарративный терапевт.\n\n"
            "🔢 <b>Геранумеролог</b> — видит скрытый порядок в числах и датах.\n\n"
            "✨ <b>Оракул</b> — анализирует запрос и сам выбирает подходящую модель. Идеально если не знаешь с чего начать."
        ),
    },
    "kb_how": {
        "title": "▶️ Как начать сеанс?",
        "text": (
            "▶️ <b>Как начать сеанс?</b>\n\n"
            "<b>Шаг 1.</b> Заполни анкету — мы подберём модель под твой запрос.\n\n"
            "<b>Шаг 2.</b> Начни разговор. В любой момент можно сменить модель прямо в ходе сеанса.\n\n"
            "<b>Шаг 3.</b> Получи ответ — не шаблонный, а сформированный под твой конкретный контекст.\n\n"
            "<b>Шаг 4.</b> По окончании забери <b>протокол сеанса</b> — изучи самостоятельно или передай в начале следующего.\n\n"
            "💡 <i>Чем больше ты рассказываешь — тем точнее и глубже ответ.</i>"
        ),
    },
    "kb_protocol": {
        "title": "📄 Протокол сеанса",
        "text": (
            "📄 <b>Протокол сеанса</b>\n\n"
            "После каждого сеанса ты можешь скачать его полную запись — это и есть протокол.\n\n"
            "Что в нём есть:\n"
            "• Весь диалог целиком\n"
            "• Ключевые выводы и наблюдения модели\n"
            "• Рекомендации для следующего сеанса\n\n"
            "Протокол можно передать модели в начале следующего сеанса — она учтёт весь предыдущий контекст и продолжит работу с того места, где вы остановились."
        ),
    },
    "kb_archive": {
        "title": "🗂 Архив сеансов",
        "text": (
            "🗂 <b>Архив сеансов</b>\n\n"
            "Все твои прошлые сеансы хранятся в личном архиве.\n\n"
            "Как попасть в архив:\n"
            "Открой сайт → войди в аккаунт → раздел <b>«Архив»</b> в меню.\n\n"
            "Там ты найдёшь:\n"
            "• Список всех сеансов с датами\n"
            "• Возможность открыть и перечитать любой сеанс\n"
            "• Кнопку скачивания протокола\n\n"
            "💡 <i>Архив доступен только авторизованным пользователям.</i>"
        ),
    },
    "kb_login": {
        "title": "🔑 Вход и регистрация",
        "text": (
            "🔑 <b>Вход и регистрация</b>\n\n"
            "Для начала работы нужен аккаунт на panacea.mom.\n\n"
            "<b>Регистрация:</b>\n"
            "Нажми «Войти» → «Создать аккаунт» → введи email и придумай пароль.\n\n"
            "<b>Вход:</b>\n"
            "Нажми «Войти» → введи email и пароль.\n\n"
            "<b>Забыл пароль?</b>\n"
            "На странице входа нажми «Забыли пароль?» — на email придёт ссылка для сброса.\n\n"
            "💡 <i>Без аккаунта сеансы не сохраняются и архив недоступен.</i>"
        ),
    },
    "kb_plus": {
        "title": "⭐️ Panacea Plus",
        "text": (
            "⭐️ <b>Panacea Plus</b>\n\n"
            "Panacea Plus — это подписка, которая открывает расширенные возможности.\n\n"
            "<b>Что входит в Plus:</b>\n"
            "• Неограниченное количество сеансов\n"
            "• Доступ ко всем моделям без ограничений\n"
            "• Приоритетная обработка запросов\n"
            "• Расширенные протоколы сеансов\n\n"
            "<b>Как оформить:</b>\n"
            "Войди в аккаунт → раздел «Подписка» → выбери план и способ оплаты.\n\n"
            "💡 <i>Донаты и Panacea Plus — единственный способ поддержать проект и помочь ему развиваться.</i>"
        ),
    },
    "kb_nav": {
        "title": "🗺 Навигация по сайту",
        "text": (
            "🗺 <b>Навигация по сайту</b>\n\n"
            "Сайт panacea.mom состоит из нескольких разделов:\n\n"
            "🏠 <b>Главная</b> — описание проекта и список моделей.\n\n"
            "💬 <b>Сеанс</b> — здесь начинается разговор с моделью. Заполни анкету и выбери модель.\n\n"
            "🗂 <b>Архив</b> — все твои прошлые сеансы и протоколы.\n\n"
            "⭐️ <b>Подписка</b> — управление Panacea Plus.\n\n"
            "👤 <b>Профиль</b> — настройки аккаунта, смена пароля и email.\n\n"
            "💡 <i>Все разделы доступны через меню в верхней части сайта.</i>"
        ),
    },
    "kb_privacy": {
        "title": "🔒 Конфиденциальность",
        "text": (
            "🔒 <b>Конфиденциальность</b>\n\n"
            "Мы понимаем, что сеансы могут быть очень личными.\n\n"
            "<b>Что мы делаем:</b>\n"
            "• Твои данные не передаются третьим лицам\n"
            "• Сеансы хранятся только в твоём аккаунте\n"
            "• Команда проекта не читает твои сеансы\n\n"
            "<b>Что делают модели:</b>\n"
            "Модели обучаются на обезличенных данных — без имён, контактов и личной информации.\n\n"
            "💡 <i>Мы не контролируем то, что говорят модели, и не претендуем на истину в последней инстанции.</i>"
        ),
    },
    "kb_payment": {
        "title": "💳 Оплата и возврат",
        "text": (
            "💳 <b>Оплата и возврат</b>\n\n"
            "<b>Способы оплаты:</b>\n"
            "• Банковская карта (Visa, Mastercard, МИР)\n"
            "• Другие способы — в разделе «Подписка» на сайте\n\n"
            "<b>Возврат средств:</b>\n"
            "Если что-то пошло не так — напиши нам. Каждый случай рассматривается индивидуально.\n\n"
            "<b>Проблемы с оплатой?</b>\n"
            "Попробуй другой браузер или другую карту. Если не помогает — обратись в поддержку через канал @PanaceaPlus."
        ),
    },
    "kb_contact": {
        "title": "📬 Связь с командой",
        "text": (
            "📬 <b>Связь с командой</b>\n\n"
            "Если у тебя остались вопросы или что-то не работает:\n\n"
            "📢 Telegram-канал: @PanaceaPlus\n"
            "▶️ YouTube: @PanaceaChannel\n"
            "🌐 Сайт: panacea.mom\n\n"
            "Мы небольшая команда и стараемся отвечать как можно быстрее.\n\n"
            "💡 <i>Перед обращением проверь — возможно ответ уже есть в этом справочном центре.</i>"
        ),
    },
}

# ─── Клавиатуры ───────────────────────────────────────────────────────────────
def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Сайт", web_app=WebAppInfo(url=SITE_URL))],
        [
            InlineKeyboardButton("📢 Канал", url=CHANNEL_URL),
            InlineKeyboardButton("▶️ YouTube", url=YOUTUBE_URL),
        ],
        [InlineKeyboardButton("🛟 Служба поддержки", callback_data="support")],
    ])

def support_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    items = list(KNOWLEDGE_BASE.items())
    # По две кнопки в ряд
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(items[i][1]["title"], callback_data=items[i][0])]
        if i + 1 < len(items):
            row.append(InlineKeyboardButton(items[i+1][1]["title"], callback_data=items[i+1][0]))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)

def article_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад", callback_data="support")],
    ])

# ─── Хендлеры ─────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_photo(
        photo=PHOTO_MAIN,
        caption=WELCOME_TEXT,
        reply_markup=main_keyboard(),
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "support":
        await query.edit_message_media(
            media=__import__("telegram").InputMediaPhoto(
                media=PHOTO_SUPPORT,
                caption=SUPPORT_TEXT,
                parse_mode="HTML",
            ),
            reply_markup=support_keyboard(),
        )

    elif data == "back_main":
        await query.edit_message_media(
            media=__import__("telegram").InputMediaPhoto(
                media=PHOTO_MAIN,
                caption=WELCOME_TEXT,
                parse_mode="HTML",
            ),
            reply_markup=main_keyboard(),
        )

    elif data in KNOWLEDGE_BASE:
        article = KNOWLEDGE_BASE[data]
        await query.edit_message_media(
            media=__import__("telegram").InputMediaPhoto(
                media=PHOTO_SUPPORT,
                caption=article["text"],
                parse_mode="HTML",
            ),
            reply_markup=article_keyboard(),
        )

# ─── Vercel handler ───────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        async def process():
            app = ApplicationBuilder().token(BOT_TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CallbackQueryHandler(button))
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
