"""
Vercel serverless entry point.
Telegram шлёт POST на /api/webhook — мы обрабатываем и отвечаем.
"""
import os
import json
import asyncio
from http.server import BaseHTTPRequestHandler

from telegram import Update, WebAppInfo, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler,
)

# ─── Хелпер: кнопка с цветом (Bot API 9.4, python-telegram-bot ещё не поддерживает) ──
def btn(text: str, callback_data: str = None, url: str = None,
        web_app_url: str = None, style: str = None) -> dict:
    """Возвращает сырой dict кнопки с поддержкой style."""
    b: dict = {"text": text}
    if callback_data:
        b["callback_data"] = callback_data
    if url:
        b["url"] = url
    if web_app_url:
        b["web_app"] = {"url": web_app_url}
    if style:
        b["style"] = style
    return b

def raw_keyboard(rows: list[list[dict]]) -> dict:
    """Возвращает reply_markup как dict для передачи в request_data."""
    return {"inline_keyboard": rows}

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ["BOT_TOKEN"]
SUPPORT_CHAT = os.environ.get("SUPPORT_CHAT_ID", "")  # chat_id куда слать обращения

SITE_URL    = "https://panacea.mom"
CHANNEL_URL = "https://t.me/PanaceaPlus"
YOUTUBE_URL = "https://www.youtube.com/@PanaceaChannel"

PHOTO_MAIN    = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaAvatar.png"
PHOTO_SUPPORT = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaAvatar.png"

# ConversationHandler state
WAITING_MESSAGE = 1

# ─── Тексты ───────────────────────────────────────────────────────────────────
WELCOME_TEXT = (
    "👋 Привет! Добро пожаловать в Panacea.\n\n"
    "Здесь ты найдёшь всё самое интересное — "
    "выбирай куда хочешь перейти 👇"
)

SUPPORT_TEXT = (
    "🛟 <b>Справочный центр</b>\n\n"
    "Выбери тему — и мы всё объясним:"
)

CONTACT_PROMPT = (
    "✍️ <b>Связь с командой</b>\n\n"
    "Напиши своё сообщение — мы получим его и ответим в ближайшее время."
)

# ─── База знаний ──────────────────────────────────────────────────────────────
KNOWLEDGE_BASE = {
    "kb_what": {
        "title": "🔮 Что такое Panacea?",
        "text": (
            "🔮 <b>Что такое Panacea?</b>\n\n"
            "<blockquote>Panacea — это передовая разработка в области искусственного интеллекта "
            "и психологической терапии.</blockquote>\n\n"
            "Опыт всего человечества теперь доступен для улучшения ментального здоровья и качества жизни. "
            "Продвинутые языковые модели, каждая из которых является экспертом в своей области, "
            "помогут найти ответ на любой вопрос.\n\n"
            "Каждый сеанс — это не гадание и не совет. Это <b>зеркало</b>. Модели не говорят тебе что делать — "
            "они помогают увидеть то, что ты уже знаешь, но ещё не сформулировал."
        ),
    },
    "kb_models": {
        "title": "🧬 Наши модели",
        "text": (
            "🧬 <b>Наши модели</b>\n\n"
            "<blockquote>Каждая модель — отдельная система, обученная на определённой традиции знания.</blockquote>\n\n"
            "🃏 <b>Тара</b> — таролог. Работает с картами Таро, архетипами, символами. "
            "Помогает увидеть скрытое за поверхностью событий.\n\n"
            "🔗 <b>Карма</b> — кармолог. Читает кармические узлы, повторяющиеся сценарии и незакрытые циклы.\n\n"
            "⭐️ <b>Астра</b> — астролог. Натальные карты, планетарные циклы, транзиты.\n\n"
            "🌀 <b>Ева</b> — регрессолог. Работает с памятью прошлых жизней, корнями страхов и притяжений.\n\n"
            "🧠 <b>Психея</b> — юнгианский психолог и нарративный терапевт. "
            "Слушает не только слова, но и то, что за ними стоит.\n\n"
            "🔢 <b>Гера</b> — нумеролог. Числа, даты, имена — расшифровывает числовой код жизни.\n\n"
            "✨ <b>Консилиум</b> <i>(Plus)</i> — все шесть моделей отвечают одновременно. "
            "Шесть точек зрения на один вопрос."
        ),
    },
    "kb_how": {
        "title": "▶️ Как начать сеанс?",
        "text": (
            "▶️ <b>Как начать сеанс?</b>\n\n"
            "<b>1.</b> Заполни анкету — мы подберём модель под твой запрос. "
            "Заполнять необязательно, но помогает точнее.\n\n"
            "<b>2.</b> Начни разговор. В любой момент можно сменить модель прямо в ходе сеанса — "
            "история сохраняется.\n\n"
            "<b>3.</b> Получи ответ — не шаблонный, а сформированный под твой конкретный контекст.\n\n"
            "<b>4.</b> По окончании забери <b>протокол сеанса</b> — изучи самостоятельно "
            "или передай в начале следующего.\n\n"
            "<blockquote>Чем больше ты рассказываешь — тем точнее и глубже ответ.</blockquote>"
        ),
    },
    "kb_protocol": {
        "title": "📄 Протокол сеанса",
        "text": (
            "📄 <b>Протокол сеанса</b>\n\n"
            "<blockquote>После каждого сеанса ты можешь скачать его полную запись в формате PDF.</blockquote>\n\n"
            "Что в нём есть:\n"
            "• Весь диалог целиком\n"
            "• Краткое саммари: вопрос, обсуждение, вывод\n"
            "• Список использованных моделей\n\n"
            "Протокол можно передать модели в начале следующего сеанса — "
            "она учтёт весь предыдущий контекст и продолжит с того места, где вы остановились.\n\n"
            "<i>Требует Panacea Plus.</i>"
        ),
    },
    "kb_archive": {
        "title": "🗂 Архив сеансов",
        "text": (
            "🗂 <b>Архив сеансов</b>\n\n"
            "Все твои прошлые сеансы хранятся в личном архиве.\n\n"
            "<b>Как попасть в архив:</b>\n"
            "Главный экран — это двусторонняя карточка. "
            "Нажми на иконку в <b>правом верхнем углу</b> — карточка перевернётся и откроется архив.\n\n"
            "В архиве ты найдёшь:\n"
            "• Список всех сеансов с датами и моделями\n"
            "• Возможность открыть и перечитать любой сеанс\n"
            "• Кнопку скачивания протокола (PDF, требует Plus)\n\n"
            "<blockquote>Долгое нажатие на карточку сеанса — удалить. Удаление необратимо.</blockquote>"
        ),
    },
    "kb_login": {
        "title": "🔑 Вход в аккаунт",
        "text": (
            "🔑 <b>Вход в аккаунт</b>\n\n"
            "<blockquote>Регистрации как таковой нет — войти можно в один клик.</blockquote>\n\n"
            "<b>Способы входа:</b>\n"
            "• <b>Google</b> — войти через аккаунт Google\n"
            "• <b>Apple</b> — войти через Apple ID\n"
            "• <b>Гость</b> — без аккаунта, история сохраняется на 24 часа\n\n"
            "<b>Чем отличается гостевой режим:</b>\n"
            "История сеансов не сохраняется в облаке и удаляется через 24 часа. "
            "Архив и протоколы недоступны.\n\n"
            "После входа откроется анкета — заполнять необязательно, но помогает подобрать модель точнее."
        ),
    },
    "kb_plus": {
        "title": "⭐️ Panacea Plus",
        "text": (
            "⭐️ <b>Panacea Plus</b>\n\n"
            "<blockquote>Подписка, которая открывает полные возможности платформы.</blockquote>\n\n"
            "<b>Что входит в Plus:</b>\n"
            "• Оракул и Консилиум — эксклюзивные режимы\n"
            "• Скачивание протоколов сеансов в PDF\n"
            "• История не удаляется через 24 часа\n"
            "• Голосовой ввод и озвучивание ответов\n"
            "• Интерактивные тесты в ходе разговора\n"
            "• Без ограничений на количество сеансов\n\n"
            "Оформить подписку можно в разделе <b>«Подписка»</b> на сайте."
        ),
    },
    "kb_nav": {
        "title": "🗺 Навигация по сайту",
        "text": (
            "🗺 <b>Навигация по сайту</b>\n\n"
            "Сайт panacea.mom состоит из нескольких разделов:\n\n"
            "🏠 <b>Главная</b> — описание проекта и список моделей.\n\n"
            "💬 <b>Сеанс</b> — здесь начинается разговор. Заполни анкету и выбери модель.\n\n"
            "🗂 <b>Архив</b> — все прошлые сеансы и протоколы.\n\n"
            "⭐️ <b>Подписка</b> — управление Panacea Plus.\n\n"
            "👤 <b>Профиль</b> — настройки аккаунта.\n\n"
            "<blockquote>Большинство карточек двусторонние — чтобы перевернуть карточку, "
            "нажми на её правый верхний угол.</blockquote>"
        ),
    },
    "kb_privacy": {
        "title": "🔒 Конфиденциальность",
        "text": (
            "🔒 <b>Конфиденциальность</b>\n\n"
            "<blockquote>Твои данные защищены современными технологиями шифрования "
            "и полностью обезличены.</blockquote>\n\n"
            "Мы не знаем ни твоего имени, ни других личных данных — "
            "только адрес электронной почты, привязанный к аккаунту.\n\n"
            "<b>Что мы делаем:</b>\n"
            "• Данные не передаются третьим лицам\n"
            "• Сеансы хранятся только в твоём аккаунте\n"
            "• Команда проекта не читает твои сеансы\n\n"
            "Модели обучаются исключительно на обезличенных данных — "
            "без имён, контактов и любой идентифицирующей информации."
        ),
    },
    "kb_payment": {
        "title": "💳 Оплата",
        "text": (
            "💳 <b>Оплата</b>\n\n"
            "<blockquote>На данный момент оплата принимается в криптовалюте.</blockquote>\n\n"
            "<b>Принимаемые криптовалюты:</b>\n"
            "• USDT (TRC-20, ERC-20)\n"
            "• BTC\n"
            "• ETH\n"
            "• TON\n\n"
            "В будущем появится оплата банковской картой. "
            "Пока что купить подписку через карту можно при <b>личном обращении</b> к команде — "
            "напиши нам через кнопку «Связь с командой»."
        ),
    },
    "kb_tech": {
        "title": "⚙️ Технические вопросы",
        "text": (
            "⚙️ <b>Технические вопросы</b>\n\n"
            "<b>Модель не отвечает</b>\n"
            "Проверь интернет-соединение и обнови страницу.\n\n"
            "<b>История не загружается</b>\n"
            "Выйди из аккаунта и войди снова.\n\n"
            "<b>Голосовой ввод не работает</b>\n"
            "Проверь разрешение на доступ к микрофону в настройках браузера.\n\n"
            "<b>Проблемы с оплатой</b>\n"
            "Попробуй другой кошелёк или сеть. Если не помогает — обратись к команде.\n\n"
            "<blockquote>Для всех остальных проблем — используй кнопку «Связь с командой» в меню поддержки.</blockquote>"
        ),
    },
}

# ─── Клавиатуры ───────────────────────────────────────────────────────────────
def main_keyboard() -> dict:
    return raw_keyboard([
        [btn("🌐 Сайт", web_app_url=SITE_URL, style="primary")],
        [
            btn("📢 Канал", url=CHANNEL_URL),
            btn("▶️ YouTube", url=YOUTUBE_URL),
        ],
        [btn("🛟 Служба поддержки", callback_data="support")],
    ])

def support_keyboard() -> dict:
    rows = []
    items = list(KNOWLEDGE_BASE.items())
    for i in range(0, len(items), 2):
        row = [btn(items[i][1]["title"], callback_data=items[i][0])]
        if i + 1 < len(items):
            row.append(btn(items[i + 1][1]["title"], callback_data=items[i + 1][0]))
        rows.append(row)
    rows.append([
        btn("✉️ Связь с командой", callback_data="contact", style="primary"),
        btn("◀️ Назад", callback_data="back_main"),
    ])
    return raw_keyboard(rows)

def article_keyboard() -> dict:
    return raw_keyboard([
        [btn("◀️ Назад", callback_data="support")],
    ])

def contact_keyboard() -> dict:
    return raw_keyboard([
        [btn("◀️ Отмена", callback_data="support", style="danger")],
    ])

def confirm_keyboard() -> dict:
    return raw_keyboard([
        [btn("◀️ В главное меню", callback_data="back_main", style="success")],
    ])

# ─── Хелпер: отправка/редактирование через сырой API (для поддержки style) ───
async def send_photo_raw(bot, chat_id: int, photo: str, caption: str, keyboard: dict):
    import urllib.request as urlreq
    payload = json.dumps({
        "chat_id": chat_id,
        "photo": photo,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": keyboard,
    }).encode()
    req = urlreq.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urlreq.urlopen(req) as r:
        return json.loads(r.read())

async def edit_photo_raw(bot, chat_id: int, message_id: int,
                         photo: str, caption: str, keyboard: dict):
    import urllib.request as urlreq
    payload = json.dumps({
        "chat_id": chat_id,
        "message_id": message_id,
        "media": {
            "type": "photo",
            "media": photo,
            "caption": caption,
            "parse_mode": "HTML",
        },
        "reply_markup": keyboard,
    }).encode()
    req = urlreq.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageMedia",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urlreq.urlopen(req) as r:
        return json.loads(r.read())
# ─── Хендлеры ─────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import urllib.request as urlreq
    chat_id = update.effective_chat.id
    payload = json.dumps({
        "chat_id": chat_id,
        "photo": PHOTO_MAIN,
        "caption": WELCOME_TEXT,
        "parse_mode": "HTML",
        "reply_markup": main_keyboard(),
    }).encode()
    req = urlreq.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urlreq.urlopen(req):
        pass

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    if data == "support":
        await edit_photo_raw(query.get_bot(), chat_id, message_id,
                             PHOTO_SUPPORT, SUPPORT_TEXT, support_keyboard())
        return ConversationHandler.END

    elif data == "back_main":
        await edit_photo_raw(query.get_bot(), chat_id, message_id,
                             PHOTO_MAIN, WELCOME_TEXT, main_keyboard())
        return ConversationHandler.END

    elif data == "contact":
        await edit_photo_raw(query.get_bot(), chat_id, message_id,
                             PHOTO_SUPPORT, CONTACT_PROMPT, contact_keyboard())
        context.user_data["contact_message_id"] = message_id
        context.user_data["contact_chat_id"] = chat_id
        return WAITING_MESSAGE

    elif data in KNOWLEDGE_BASE:
        article = KNOWLEDGE_BASE[data]
        await edit_photo_raw(query.get_bot(), chat_id, message_id,
                             PHOTO_SUPPORT, article["text"], article_keyboard())
        return ConversationHandler.END

    return ConversationHandler.END

async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    text = update.message.text

    if SUPPORT_CHAT:
        try:
            await context.bot.send_message(
                chat_id=SUPPORT_CHAT,
                text=(
                    f"📬 <b>Новое обращение</b>\n\n"
                    f"От: {user.full_name} (@{user.username or '—'})\n"
                    f"ID: <code>{user.id}</code>\n\n"
                    f"{text}"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

    try:
        await update.message.delete()
    except Exception:
        pass

    msg_id = context.user_data.get("contact_message_id")
    chat_id = context.user_data.get("contact_chat_id")
    if msg_id and chat_id:
        await edit_photo_raw(
            context.bot, chat_id, msg_id,
            PHOTO_MAIN,
            "✅ Сообщение отправлено! Мы ответим в ближайшее время.",
            confirm_keyboard(),
        )

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return ConversationHandler.END

# ─── Vercel handler ───────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        async def process():
            app = ApplicationBuilder().token(BOT_TOKEN).build()

            conv = ConversationHandler(
                entry_points=[CallbackQueryHandler(button)],
                states={
                    WAITING_MESSAGE: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message),
                        CallbackQueryHandler(button),
                    ],
                },
                fallbacks=[CommandHandler("cancel", cancel)],
                per_message=False,
            )

            app.add_handler(CommandHandler("start", start))
            app.add_handler(conv)

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
