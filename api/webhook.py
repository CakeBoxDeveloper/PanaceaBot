"""
Vercel serverless entry point — с Redis для хранения состояния.
"""
import os
import json
import asyncio
import urllib.request as urlreq
from http.server import BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, PreCheckoutQueryHandler, filters, ContextTypes,
)

# ─── Redis (Upstash через Vercel KV) ─────────────────────────────────────────
REDIS_URL   = os.environ.get("KV_REDIS_URL", "")          # redis://default:pass@host:port
KV_API_URL  = os.environ.get("KV_REST_API_URL", "")       # https://...upstash.io
KV_API_TOKEN = os.environ.get("KV_REST_API_TOKEN", "")    # token

def redis_set(key: str, value: str, ex: int = 300):
    """Сохраняем состояние через Upstash REST API."""
    if not KV_API_URL or not KV_API_TOKEN:
        return
    data = json.dumps(["SET", key, value, "EX", str(ex)]).encode()
    req = urlreq.Request(
        f"{KV_API_URL}/pipeline",
        data=data,
        headers={"Authorization": f"Bearer {KV_API_TOKEN}",
                 "Content-Type": "application/json"},
    )
    try:
        with urlreq.urlopen(req):
            pass
    except Exception:
        pass

def redis_get(key: str) -> str | None:
    """Читаем состояние через Upstash REST API."""
    if not KV_API_URL or not KV_API_TOKEN:
        return None
    req = urlreq.Request(
        f"{KV_API_URL}/get/{key}",
        headers={"Authorization": f"Bearer {KV_API_TOKEN}"},
    )
    try:
        with urlreq.urlopen(req) as r:
            result = json.loads(r.read())
            return result.get("result")
    except Exception:
        return None

def redis_del(key: str):
    if not KV_API_URL or not KV_API_TOKEN:
        return
    req = urlreq.Request(
        f"{KV_API_URL}/del/{key}",
        headers={"Authorization": f"Bearer {KV_API_TOKEN}"},
        method="GET",
    )
    try:
        with urlreq.urlopen(req):
            pass
    except Exception:
        pass

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ["BOT_TOKEN"]
SUPPORT_CHAT = os.environ.get("SUPPORT_CHAT_ID", "")

SITE_URL    = "https://panacea.mom"
CHANNEL_URL = "https://t.me/PanaceaPlus"
YOUTUBE_URL = "https://www.youtube.com/@PanaceaChannel"

PHOTO_MAIN    = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaAvatar.png"
PHOTO_SUPPORT = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaAvatar.png"
PHOTO_PLUS    = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaAvatar.png"

STARS_PRICE = 100

# Состояния
STATE_SUPPORT = "support"
STATE_PLUS_SELF = "plus_self"
STATE_PLUS_GIFT = "plus_gift"

# ─── Хелперы кнопок ───────────────────────────────────────────────────────────
def btn(text: str, callback_data: str = None, url: str = None,
        web_app_url: str = None, style: str = None) -> dict:
    b: dict = {"text": text}
    if callback_data: b["callback_data"] = callback_data
    if url:           b["url"] = url
    if web_app_url:   b["web_app"] = {"url": web_app_url}
    if style:         b["style"] = style
    return b

def raw_keyboard(rows: list[list[dict]]) -> dict:
    return {"inline_keyboard": rows}

# ─── Тексты ───────────────────────────────────────────────────────────────────
WELCOME_TEXT = (
    "✦ Привет! Добро пожаловать в Panacea.\n\n"
    "Здесь ты найдёшь всё самое интересное — "
    "выбирай куда хочешь перейти ↓"
)
SUPPORT_TEXT = "◈ <b>Справочный центр</b>\n\nВыбери тему — и мы всё объясним:"
PLUS_TEXT = (
    "◈ <b>Panacea Plus</b>\n\n"
    "<blockquote>Подписка, которая открывает полные возможности платформы.</blockquote>\n\n"
    "<b>Что входит в Plus:</b>\n"
    "· Оракул и Консилиум — эксклюзивные режимы\n"
    "· Скачивание протоколов сеансов в PDF\n"
    "· История не удаляется через 24 часа\n"
    "· Голосовой ввод и озвучивание ответов\n"
    "· Интерактивные тесты в ходе разговора\n"
    "· Без ограничений на количество сеансов\n\n"
    f"<b>Стоимость:</b> {STARS_PRICE} ★\n\nВыбери вариант:"
)

# ─── База знаний ──────────────────────────────────────────────────────────────
KNOWLEDGE_BASE = {
    "kb_what": {
        "title": "◈ Что такое Panacea?",
        "text": (
            "◈ <b>Что такое Panacea?</b>\n\n"
            "<blockquote>Panacea — это передовая разработка в области искусственного интеллекта "
            "и психологической терапии.</blockquote>\n\n"
            "Опыт всего человечества теперь доступен для улучшения ментального здоровья и качества жизни. "
            "Продвинутые языковые модели, каждая из которых является экспертом в своей области, "
            "помогут найти ответ на любой вопрос.\n\n"
            "Каждый сеанс — это не гадание и не совет. Это <b>зеркало</b>. "
            "Модели не говорят тебе что делать — они помогают увидеть то, что ты уже знаешь."
        ),
    },
    "kb_models": {
        "title": "⬡ Наши модели",
        "text": (
            "⬡ <b>Наши модели</b>\n\n"
            "<blockquote>Каждая модель — отдельная система, обученная на определённой традиции знания.</blockquote>\n\n"
            "⟁ <b>Тара</b> — таролог. Работает с картами Таро, архетипами, символами.\n\n"
            "⟁ <b>Карма</b> — кармолог. Читает кармические узлы и повторяющиеся сценарии.\n\n"
            "⟁ <b>Астра</b> — астролог. Натальные карты, планетарные циклы, транзиты.\n\n"
            "⟁ <b>Ева</b> — регрессолог. Работает с памятью прошлых жизней.\n\n"
            "⟁ <b>Психея</b> — юнгианский психолог и нарративный терапевт.\n\n"
            "⟁ <b>Гера</b> — нумеролог. Числа, даты, имена — числовой код жизни.\n\n"
            "◇ <b>Консилиум</b> <i>(Plus)</i> — все шесть моделей отвечают одновременно."
        ),
    },
    "kb_how": {
        "title": "▷ Как начать сеанс?",
        "text": (
            "▷ <b>Как начать сеанс?</b>\n\n"
            "<b>I.</b> Заполни анкету — подберём модель под твой запрос.\n\n"
            "<b>II.</b> Начни разговор. Модель можно сменить прямо в ходе сеанса.\n\n"
            "<b>III.</b> Получи ответ — сформированный под твой конкретный контекст.\n\n"
            "<b>IV.</b> Забери <b>протокол сеанса</b> — изучи или передай в начале следующего.\n\n"
            "<blockquote>Чем больше ты рассказываешь — тем точнее и глубже ответ.</blockquote>"
        ),
    },
    "kb_protocol": {
        "title": "▤ Протокол сеанса",
        "text": (
            "▤ <b>Протокол сеанса</b>\n\n"
            "<blockquote>После каждого сеанса можно скачать полную запись в PDF.</blockquote>\n\n"
            "· Весь диалог целиком\n"
            "· Краткое саммари: вопрос, обсуждение, вывод\n"
            "· Список использованных моделей\n\n"
            "<i>Требует Panacea Plus.</i>"
        ),
    },
    "kb_archive": {
        "title": "▦ Архив сеансов",
        "text": (
            "▦ <b>Архив сеансов</b>\n\n"
            "Главный экран — двусторонняя карточка. "
            "Нажми иконку в <b>правом верхнем углу</b> — откроется архив.\n\n"
            "· Список всех сеансов с датами и моделями\n"
            "· Открыть и перечитать любой сеанс\n"
            "· Скачать протокол PDF (требует Plus)\n\n"
            "<blockquote>Долгое нажатие на карточку сеанса — удалить. Необратимо.</blockquote>"
        ),
    },
    "kb_login": {
        "title": "◎ Вход в аккаунт",
        "text": (
            "◎ <b>Вход в аккаунт</b>\n\n"
            "<blockquote>Регистрации нет — войти можно в один клик.</blockquote>\n\n"
            "· <b>Google</b> — через аккаунт Google\n"
            "· <b>Apple</b> — через Apple ID\n"
            "· <b>Гость</b> — без аккаунта, история на 24 часа\n\n"
            "В гостевом режиме архив и протоколы недоступны."
        ),
    },
    "kb_plus": {
        "title": "◈ Panacea Plus",
        "text": (
            "◈ <b>Panacea Plus</b>\n\n"
            "<blockquote>Подписка, которая открывает полные возможности платформы.</blockquote>\n\n"
            "· Оракул и Консилиум — эксклюзивные режимы\n"
            "· Протоколы сеансов в PDF\n"
            "· История не удаляется через 24 часа\n"
            "· Голосовой ввод и озвучивание ответов\n"
            "· Интерактивные тесты\n"
            "· Без ограничений на количество сеансов"
        ),
    },
    "kb_nav": {
        "title": "⊹ Навигация по сайту",
        "text": (
            "⊹ <b>Навигация по сайту</b>\n\n"
            "· <b>Главная</b> — описание проекта и модели\n"
            "· <b>Сеанс</b> — начать разговор\n"
            "· <b>Архив</b> — прошлые сеансы и протоколы\n"
            "· <b>Подписка</b> — управление Plus\n"
            "· <b>Профиль</b> — настройки аккаунта\n\n"
            "<blockquote>Большинство карточек двусторонние — перевернуть можно нажав правый верхний угол.</blockquote>"
        ),
    },
    "kb_privacy": {
        "title": "⊘ Конфиденциальность",
        "text": (
            "⊘ <b>Конфиденциальность</b>\n\n"
            "<blockquote>Данные защищены шифрованием и полностью обезличены.</blockquote>\n\n"
            "Мы не знаем ни имени, ни других личных данных — только email аккаунта.\n\n"
            "· Данные не передаются третьим лицам\n"
            "· Сеансы хранятся только в твоём аккаунте\n"
            "· Команда не читает твои сеансы"
        ),
    },
    "kb_payment": {
        "title": "◻ Оплата",
        "text": (
            "◻ <b>Оплата</b>\n\n"
            "<blockquote>Оплата принимается в криптовалюте.</blockquote>\n\n"
            "· USDT (TRC-20, ERC-20)\n"
            "· BTC · ETH · TON\n\n"
            "Оплата картой — при личном обращении к команде."
        ),
    },
    "kb_tech": {
        "title": "⚙ Технические вопросы",
        "text": (
            "⚙ <b>Технические вопросы</b>\n\n"
            "<b>Модель не отвечает</b> — проверь интернет, обнови страницу.\n\n"
            "<b>История не загружается</b> — выйди и войди снова.\n\n"
            "<b>Голосовой ввод не работает</b> — проверь разрешение микрофона.\n\n"
            "<b>Проблемы с оплатой</b> — попробуй другой кошелёк или сеть.\n\n"
            "<blockquote>Остальное — кнопка «Связь с командой».</blockquote>"
        ),
    },
}

# ─── Клавиатуры ───────────────────────────────────────────────────────────────
def main_keyboard() -> dict:
    return raw_keyboard([
        [btn("Открыть сайт Panacea", web_app_url=SITE_URL, style="primary")],
        [btn(f"Подписка Panacea Plus  ·  {STARS_PRICE} ★", callback_data="plus")],
        [
            btn("Канал Panacea", url=CHANNEL_URL, style="success"),
            btn("Panacea Youtube", url=YOUTUBE_URL, style="danger"),
        ],
        [btn("Справочный центр", callback_data="support", style="primary")],
    ])

def plus_keyboard() -> dict:
    return raw_keyboard([
        [btn("Купить себе", callback_data="plus_self", style="primary")],
        [btn("Подарить другу", callback_data="plus_gift", style="success")],
        [btn("← Назад", callback_data="back_main", style="primary")],
    ])

def support_keyboard() -> dict:
    rows = []
    main_items = [(k, v) for k, v in KNOWLEDGE_BASE.items() if k != "kb_tech"]
    for i in range(0, len(main_items), 2):
        row = [btn(main_items[i][1]["title"], callback_data=main_items[i][0])]
        if i + 1 < len(main_items):
            row.append(btn(main_items[i+1][1]["title"], callback_data=main_items[i+1][0]))
        rows.append(row)
    rows.append([
        btn("⚙ Технические вопросы", callback_data="kb_tech"),
        btn("◎ Связь с командой", callback_data="contact"),
    ])
    rows.append([btn("← Назад", callback_data="back_main", style="primary")])
    return raw_keyboard(rows)

def article_keyboard() -> dict:
    return raw_keyboard([[btn("← Назад", callback_data="support", style="primary")]])

def confirm_keyboard() -> dict:
    return raw_keyboard([[btn("← В главное меню", callback_data="back_main", style="primary")]])

def cancel_keyboard(target: str = "support") -> dict:
    return raw_keyboard([[btn("← Отмена", callback_data=target, style="primary")]])

# ─── Bot API helpers ──────────────────────────────────────────────────────────
def _post(method: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urlreq.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urlreq.urlopen(req) as r:
        return json.loads(r.read())

def send_photo(chat_id: int, photo: str, caption: str, keyboard: dict) -> dict:
    return _post("sendPhoto", {
        "chat_id": chat_id, "photo": photo,
        "caption": caption, "parse_mode": "HTML",
        "reply_markup": keyboard,
    })

def edit_photo(chat_id: int, message_id: int, photo: str, caption: str, keyboard: dict):
    _post("editMessageMedia", {
        "chat_id": chat_id, "message_id": message_id,
        "media": {"type": "photo", "media": photo,
                  "caption": caption, "parse_mode": "HTML"},
        "reply_markup": keyboard,
    })

def send_text(chat_id: int, text: str, keyboard: dict = None) -> dict:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if keyboard:
        payload["reply_markup"] = keyboard
    return _post("sendMessage", payload)

def delete_msg(chat_id: int, message_id: int):
    try:
        _post("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
    except Exception:
        pass

# ─── Хендлеры ─────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    redis_del(f"state:{chat_id}")
    send_photo(chat_id, PHOTO_MAIN, WELCOME_TEXT, main_keyboard())

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data    = query.data
    chat_id = query.message.chat_id
    msg_id  = query.message.message_id

    if data == "back_main":
        redis_del(f"state:{chat_id}")
        edit_photo(chat_id, msg_id, PHOTO_MAIN, WELCOME_TEXT, main_keyboard())

    elif data == "support":
        redis_del(f"state:{chat_id}")
        edit_photo(chat_id, msg_id, PHOTO_SUPPORT, SUPPORT_TEXT, support_keyboard())

    elif data == "plus":
        redis_del(f"state:{chat_id}")
        edit_photo(chat_id, msg_id, PHOTO_PLUS, PLUS_TEXT, plus_keyboard())

    elif data == "plus_self":
        redis_set(f"state:{chat_id}", STATE_PLUS_SELF)
        edit_photo(chat_id, msg_id, PHOTO_PLUS,
            "◎ <b>Подписка для себя</b>\n\n"
            "Укажи email, который используешь для входа на panacea.mom:",
            cancel_keyboard("plus"))

    elif data == "plus_gift":
        redis_set(f"state:{chat_id}", STATE_PLUS_GIFT)
        edit_photo(chat_id, msg_id, PHOTO_PLUS,
            "◎ <b>Подписка в подарок</b>\n\n"
            "Укажи email друга, который он использует для входа на panacea.mom:",
            cancel_keyboard("plus"))

    elif data == "contact":
        redis_set(f"state:{chat_id}", STATE_SUPPORT)
        edit_photo(chat_id, msg_id, PHOTO_SUPPORT,
            "◎ <b>Связь с командой</b>\n\n"
            "Напиши своё сообщение:",
            cancel_keyboard("support"))

    elif data in KNOWLEDGE_BASE:
        edit_photo(chat_id, msg_id, PHOTO_SUPPORT,
                   KNOWLEDGE_BASE[data]["text"], article_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатываем любой текст от пользователя согласно состоянию в Redis."""
    msg     = update.message
    chat_id = msg.chat_id
    text    = msg.text.strip()
    user    = update.effective_user

    state = redis_get(f"state:{chat_id}")

    # Удаляем сообщение пользователя
    delete_msg(chat_id, msg.message_id)

    if state == STATE_SUPPORT:
        redis_del(f"state:{chat_id}")
        # Пересылаем команде
        if SUPPORT_CHAT:
            try:
                _post("sendMessage", {
                    "chat_id": SUPPORT_CHAT,
                    "text": (
                        f"◎ <b>Новое обращение</b>\n\n"
                        f"От: {user.full_name} (@{user.username or '—'})\n"
                        f"ID: <code>{user.id}</code>\n\n{text}"
                    ),
                    "parse_mode": "HTML",
                })
            except Exception:
                pass
        send_photo(chat_id, PHOTO_MAIN,
                   "✦ Сообщение отправлено. Мы ответим в ближайшее время.",
                   confirm_keyboard())

    elif state in (STATE_PLUS_SELF, STATE_PLUS_GIFT):
        redis_del(f"state:{chat_id}")
        for_self = state == STATE_PLUS_SELF
        label    = f"Для аккаунта: {text}" if for_self else f"Подарок для: {text}"
        _post("sendInvoice", {
            "chat_id":     chat_id,
            "title":       "Panacea Plus",
            "description": label,
            "payload":     json.dumps({"for_self": for_self, "email": text}),
            "currency":    "XTR",
            "prices":      [{"label": "Panacea Plus", "amount": STARS_PRICE}],
        })

    # Если состояния нет — игнорируем

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payment = update.message.successful_payment
    payload = json.loads(payment.invoice_payload)
    email   = payload.get("email", "—")
    user    = update.effective_user
    chat_id = update.effective_chat.id

    send_photo(chat_id, PHOTO_MAIN,
        f"✦ <b>Оплата прошла!</b>\n\n"
        f"Подписка Panacea Plus будет активирована на аккаунт "
        f"<code>{email}</code> в течение нескольких минут.",
        confirm_keyboard())

    if SUPPORT_CHAT:
        try:
            _post("sendMessage", {
                "chat_id": SUPPORT_CHAT,
                "text": (
                    f"★ <b>Новая оплата</b>\n\n"
                    f"От: {user.full_name} (@{user.username or '—'})\n"
                    f"ID: <code>{user.id}</code>\n"
                    f"Email: <code>{email}</code>\n"
                    f"Для себя: {'да' if payload.get('for_self') else 'нет'}\n"
                    f"Сумма: {payment.total_amount} XTR"
                ),
                "parse_mode": "HTML",
            })
        except Exception:
            pass

# ─── Vercel handler ───────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        async def process():
            app = ApplicationBuilder().token(BOT_TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CallbackQueryHandler(button))
            app.add_handler(PreCheckoutQueryHandler(pre_checkout))
            app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
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
