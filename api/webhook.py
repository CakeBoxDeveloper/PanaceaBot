"""
Vercel serverless entry point.
Telegram шлёт POST на /api/webhook — мы обрабатываем и отвечаем.

Состояние не хранится между запросами (serverless).
Для оплаты используем need_email=True — Telegram сам спрашивает email.
Для поддержки используем ForceReply — ловим reply_to_message_id.
"""
import os
import json
import asyncio
import urllib.request as urlreq
from http.server import BaseHTTPRequestHandler

from telegram import Update, ForceReply
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, PreCheckoutQueryHandler, filters, ContextTypes,
)

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

# ─── Хелпер: кнопка с цветом (Bot API 9.4) ───────────────────────────────────
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

SUPPORT_TEXT = (
    "◈ <b>Справочный центр</b>\n\n"
    "Выбери тему — и мы всё объясним:"
)

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
    f"<b>Стоимость:</b> {STARS_PRICE} ★\n\n"
    "Выбери вариант:"
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
            "Каждый сеанс — это не гадание и не совет. Это <b>зеркало</b>. Модели не говорят тебе что делать — "
            "они помогают увидеть то, что ты уже знаешь, но ещё не сформулировал."
        ),
    },
    "kb_models": {
        "title": "⬡ Наши модели",
        "text": (
            "⬡ <b>Наши модели</b>\n\n"
            "<blockquote>Каждая модель — отдельная система, обученная на определённой традиции знания.</blockquote>\n\n"
            "⟁ <b>Тара</b> — таролог. Работает с картами Таро, архетипами, символами.\n\n"
            "⟁ <b>Карма</b> — кармолог. Читает кармические узлы, повторяющиеся сценарии и незакрытые циклы.\n\n"
            "⟁ <b>Астра</b> — астролог. Натальные карты, планетарные циклы, транзиты.\n\n"
            "⟁ <b>Ева</b> — регрессолог. Работает с памятью прошлых жизней, корнями страхов и притяжений.\n\n"
            "⟁ <b>Психея</b> — юнгианский психолог и нарративный терапевт.\n\n"
            "⟁ <b>Гера</b> — нумеролог. Числа, даты, имена — расшифровывает числовой код жизни.\n\n"
            "◇ <b>Консилиум</b> <i>(Plus)</i> — все шесть моделей отвечают одновременно."
        ),
    },
    "kb_how": {
        "title": "▷ Как начать сеанс?",
        "text": (
            "▷ <b>Как начать сеанс?</b>\n\n"
            "<b>I.</b> Заполни анкету — мы подберём модель под твой запрос.\n\n"
            "<b>II.</b> Начни разговор. В любой момент можно сменить модель прямо в ходе сеанса.\n\n"
            "<b>III.</b> Получи ответ — не шаблонный, а сформированный под твой конкретный контекст.\n\n"
            "<b>IV.</b> По окончании забери <b>протокол сеанса</b> — изучи самостоятельно "
            "или передай в начале следующего.\n\n"
            "<blockquote>Чем больше ты рассказываешь — тем точнее и глубже ответ.</blockquote>"
        ),
    },
    "kb_protocol": {
        "title": "▤ Протокол сеанса",
        "text": (
            "▤ <b>Протокол сеанса</b>\n\n"
            "<blockquote>После каждого сеанса ты можешь скачать его полную запись в формате PDF.</blockquote>\n\n"
            "Что в нём есть:\n"
            "· Весь диалог целиком\n"
            "· Краткое саммари: вопрос, обсуждение, вывод\n"
            "· Список использованных моделей\n\n"
            "Протокол можно передать модели в начале следующего сеанса.\n\n"
            "<i>Требует Panacea Plus.</i>"
        ),
    },
    "kb_archive": {
        "title": "▦ Архив сеансов",
        "text": (
            "▦ <b>Архив сеансов</b>\n\n"
            "Все твои прошлые сеансы хранятся в личном архиве.\n\n"
            "<b>Как попасть в архив:</b>\n"
            "Главный экран — это двусторонняя карточка. "
            "Нажми на иконку в <b>правом верхнем углу</b> — карточка перевернётся и откроется архив.\n\n"
            "В архиве ты найдёшь:\n"
            "· Список всех сеансов с датами и моделями\n"
            "· Возможность открыть и перечитать любой сеанс\n"
            "· Кнопку скачивания протокола (PDF, требует Plus)\n\n"
            "<blockquote>Долгое нажатие на карточку сеанса — удалить. Удаление необратимо.</blockquote>"
        ),
    },
    "kb_login": {
        "title": "◎ Вход в аккаунт",
        "text": (
            "◎ <b>Вход в аккаунт</b>\n\n"
            "<blockquote>Регистрации как таковой нет — войти можно в один клик.</blockquote>\n\n"
            "<b>Способы входа:</b>\n"
            "· <b>Google</b> — войти через аккаунт Google\n"
            "· <b>Apple</b> — войти через Apple ID\n"
            "· <b>Гость</b> — без аккаунта, история сохраняется на 24 часа\n\n"
            "<b>Чем отличается гостевой режим:</b>\n"
            "История сеансов не сохраняется в облаке и удаляется через 24 часа. "
            "Архив и протоколы недоступны."
        ),
    },
    "kb_plus": {
        "title": "◈ Panacea Plus",
        "text": (
            "◈ <b>Panacea Plus</b>\n\n"
            "<blockquote>Подписка, которая открывает полные возможности платформы.</blockquote>\n\n"
            "<b>Что входит в Plus:</b>\n"
            "· Оракул и Консилиум — эксклюзивные режимы\n"
            "· Скачивание протоколов сеансов в PDF\n"
            "· История не удаляется через 24 часа\n"
            "· Голосовой ввод и озвучивание ответов\n"
            "· Интерактивные тесты в ходе разговора\n"
            "· Без ограничений на количество сеансов\n\n"
            "Оформить подписку можно в разделе <b>«Подписка»</b> на сайте или прямо здесь."
        ),
    },
    "kb_nav": {
        "title": "⊹ Навигация по сайту",
        "text": (
            "⊹ <b>Навигация по сайту</b>\n\n"
            "· <b>Главная</b> — описание проекта и список моделей.\n"
            "· <b>Сеанс</b> — здесь начинается разговор.\n"
            "· <b>Архив</b> — все прошлые сеансы и протоколы.\n"
            "· <b>Подписка</b> — управление Panacea Plus.\n"
            "· <b>Профиль</b> — настройки аккаунта.\n\n"
            "<blockquote>Большинство карточек двусторонние — чтобы перевернуть карточку, "
            "нажми на её правый верхний угол.</blockquote>"
        ),
    },
    "kb_privacy": {
        "title": "⊘ Конфиденциальность",
        "text": (
            "⊘ <b>Конфиденциальность</b>\n\n"
            "<blockquote>Твои данные защищены современными технологиями шифрования "
            "и полностью обезличены.</blockquote>\n\n"
            "Мы не знаем ни твоего имени, ни других личных данных — "
            "только адрес электронной почты, привязанный к аккаунту.\n\n"
            "· Данные не передаются третьим лицам\n"
            "· Сеансы хранятся только в твоём аккаунте\n"
            "· Команда проекта не читает твои сеансы"
        ),
    },
    "kb_payment": {
        "title": "◻ Оплата",
        "text": (
            "◻ <b>Оплата</b>\n\n"
            "<blockquote>На данный момент оплата принимается в криптовалюте.</blockquote>\n\n"
            "<b>Принимаемые криптовалюты:</b>\n"
            "· USDT (TRC-20, ERC-20)\n"
            "· BTC · ETH · TON\n\n"
            "В будущем появится оплата банковской картой. "
            "Пока что купить подписку через карту можно при <b>личном обращении</b> к команде."
        ),
    },
    "kb_tech": {
        "title": "⚙ Технические вопросы",
        "text": (
            "⚙ <b>Технические вопросы</b>\n\n"
            "<b>Модель не отвечает</b> — проверь интернет и обнови страницу.\n\n"
            "<b>История не загружается</b> — выйди из аккаунта и войди снова.\n\n"
            "<b>Голосовой ввод не работает</b> — проверь разрешение микрофона в браузере.\n\n"
            "<b>Проблемы с оплатой</b> — попробуй другой кошелёк или сеть.\n\n"
            "<blockquote>Для всех остальных проблем — используй кнопку «Связь с командой».</blockquote>"
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
    items = list(KNOWLEDGE_BASE.items())
    main_items = [(k, v) for k, v in items if k != "kb_tech"]
    for i in range(0, len(main_items), 2):
        row = [btn(main_items[i][1]["title"], callback_data=main_items[i][0])]
        if i + 1 < len(main_items):
            row.append(btn(main_items[i + 1][1]["title"], callback_data=main_items[i + 1][0]))
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

# ─── Сырые запросы к Bot API ──────────────────────────────────────────────────
def _post(method: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urlreq.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urlreq.urlopen(req) as r:
        return json.loads(r.read())

async def send_photo_raw(chat_id: int, photo: str, caption: str, keyboard: dict) -> dict:
    return _post("sendPhoto", {
        "chat_id": chat_id, "photo": photo,
        "caption": caption, "parse_mode": "HTML",
        "reply_markup": keyboard,
    })

async def edit_photo_raw(chat_id: int, message_id: int,
                         photo: str, caption: str, keyboard: dict):
    _post("editMessageMedia", {
        "chat_id": chat_id, "message_id": message_id,
        "media": {"type": "photo", "media": photo,
                  "caption": caption, "parse_mode": "HTML"},
        "reply_markup": keyboard,
    })

# ─── Хендлеры ─────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_photo_raw(update.effective_chat.id, PHOTO_MAIN, WELCOME_TEXT, main_keyboard())

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data    = query.data
    chat_id = query.message.chat_id
    msg_id  = query.message.message_id

    if data == "back_main":
        await edit_photo_raw(chat_id, msg_id, PHOTO_MAIN, WELCOME_TEXT, main_keyboard())

    elif data == "support":
        await edit_photo_raw(chat_id, msg_id, PHOTO_SUPPORT, SUPPORT_TEXT, support_keyboard())

    elif data == "plus":
        await edit_photo_raw(chat_id, msg_id, PHOTO_PLUS, PLUS_TEXT, plus_keyboard())

    elif data in ("plus_self", "plus_gift"):
        # Telegram сам спрашивает email через need_email=True
        for_self = data == "plus_self"
        label    = "Panacea Plus — для себя" if for_self else "Panacea Plus — подарок другу"
        _post("sendInvoice", {
            "chat_id":    chat_id,
            "title":      "Panacea Plus",
            "description": label,
            "payload":    json.dumps({"for_self": for_self}),
            "currency":   "XTR",
            "prices":     [{"label": "Panacea Plus", "amount": STARS_PRICE}],
            "need_email": True,
            "send_email_to_provider": False,
        })

    elif data == "contact":
        # Отправляем сообщение с ForceReply — бот ждёт ответа именно на него
        result = _post("sendMessage", {
            "chat_id":    chat_id,
            "text":       "◎ <b>Связь с командой</b>\n\nНапиши своё сообщение — ответь на это сообщение:",
            "parse_mode": "HTML",
            "reply_markup": {"force_reply": True, "selective": True},
        })
        # Сохраняем id этого сообщения в тексте (через edit) чтобы потом удалить
        context.bot_data[f"support_prompt_{chat_id}"] = result.get("result", {}).get("message_id")

    elif data in KNOWLEDGE_BASE:
        await edit_photo_raw(chat_id, msg_id, PHOTO_SUPPORT,
                             KNOWLEDGE_BASE[data]["text"], article_keyboard())

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ловим ответы на ForceReply (сообщения в поддержку)."""
    msg = update.message
    if not msg or not msg.reply_to_message:
        return

    # Проверяем что это ответ на наш ForceReply-промпт
    prompt_id = context.bot_data.get(f"support_prompt_{msg.chat_id}")
    if msg.reply_to_message.message_id != prompt_id:
        return

    user = update.effective_user
    text = msg.text

    # Удаляем оба сообщения — промпт и ответ пользователя
    try:
        await context.bot.delete_message(msg.chat_id, msg.reply_to_message.message_id)
    except Exception:
        pass
    try:
        await msg.delete()
    except Exception:
        pass

    # Чистим сохранённый id
    context.bot_data.pop(f"support_prompt_{msg.chat_id}", None)

    # Шлём команде
    if SUPPORT_CHAT:
        try:
            _post("sendMessage", {
                "chat_id":    SUPPORT_CHAT,
                "text": (
                    f"◎ <b>Новое обращение</b>\n\n"
                    f"От: {user.full_name} (@{user.username or '—'})\n"
                    f"ID: <code>{user.id}</code>\n\n{text}"
                ),
                "parse_mode": "HTML",
            })
        except Exception:
            pass

    # Подтверждение пользователю
    await send_photo_raw(
        msg.chat_id, PHOTO_MAIN,
        "✦ Сообщение отправлено. Мы ответим в ближайшее время.",
        confirm_keyboard(),
    )

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payment = update.message.successful_payment
    payload = json.loads(payment.invoice_payload)
    email   = payment.order_info.email if payment.order_info else "—"
    user    = update.effective_user

    _post("sendMessage", {
        "chat_id":    update.effective_chat.id,
        "text": (
            "✦ <b>Оплата прошла успешно!</b>\n\n"
            f"Подписка Panacea Plus будет активирована на аккаунт <code>{email}</code> "
            "в течение нескольких минут."
        ),
        "parse_mode": "HTML",
        "reply_markup": raw_keyboard([[btn("← В главное меню", callback_data="back_main", style="primary")]]),
    })

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
            app.add_handler(MessageHandler(filters.REPLY & filters.TEXT, handle_reply))
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
import os
import json
import asyncio
import urllib.request as urlreq
from http.server import BaseHTTPRequestHandler

from telegram import Update, LabeledPrice
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, PreCheckoutQueryHandler, filters,
    ContextTypes, ConversationHandler,
)

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ["BOT_TOKEN"]
SUPPORT_CHAT = os.environ.get("SUPPORT_CHAT_ID", "")

SITE_URL    = "https://panacea.mom"
CHANNEL_URL = "https://t.me/PanaceaPlus"
YOUTUBE_URL = "https://www.youtube.com/@PanaceaChannel"

PHOTO_MAIN    = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaAvatar.png"
PHOTO_SUPPORT = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaAvatar.png"
PHOTO_PLUS    = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaAvatar.png"

STARS_PRICE = 100  # тестовая цена в звёздах

# ─── Состояния ConversationHandler ────────────────────────────────────────────
WAITING_MESSAGE  = 1
WAITING_EMAIL    = 2   # ввод email для себя
WAITING_GIFT_EMAIL = 3 # ввод email друга

# ─── Хелпер: кнопка с цветом (Bot API 9.4) ───────────────────────────────────
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

SUPPORT_TEXT = (
    "◈ <b>Справочный центр</b>\n\n"
    "Выбери тему — и мы всё объясним:"
)

CONTACT_PROMPT = (
    "◎ <b>Связь с командой</b>\n\n"
    "Напиши своё сообщение — мы получим его и ответим в ближайшее время."
)

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
    f"<b>Стоимость:</b> {STARS_PRICE} ★\n\n"
    "Выбери вариант:"
)

EMAIL_PROMPT_SELF = (
    "◎ <b>Подписка для себя</b>\n\n"
    "Укажи email, который ты используешь для входа на panacea.mom — "
    "на него будет активирована подписка."
)

EMAIL_PROMPT_GIFT = (
    "◎ <b>Подписка в подарок</b>\n\n"
    "Укажи email друга, который он использует для входа на panacea.mom — "
    "подписка будет активирована на его аккаунт."
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
            "Каждый сеанс — это не гадание и не совет. Это <b>зеркало</b>. Модели не говорят тебе что делать — "
            "они помогают увидеть то, что ты уже знаешь, но ещё не сформулировал."
        ),
    },
    "kb_models": {
        "title": "⬡ Наши модели",
        "text": (
            "⬡ <b>Наши модели</b>\n\n"
            "<blockquote>Каждая модель — отдельная система, обученная на определённой традиции знания.</blockquote>\n\n"
            "⟁ <b>Тара</b> — таролог. Работает с картами Таро, архетипами, символами.\n\n"
            "⟁ <b>Карма</b> — кармолог. Читает кармические узлы, повторяющиеся сценарии и незакрытые циклы.\n\n"
            "⟁ <b>Астра</b> — астролог. Натальные карты, планетарные циклы, транзиты.\n\n"
            "⟁ <b>Ева</b> — регрессолог. Работает с памятью прошлых жизней, корнями страхов и притяжений.\n\n"
            "⟁ <b>Психея</b> — юнгианский психолог и нарративный терапевт.\n\n"
            "⟁ <b>Гера</b> — нумеролог. Числа, даты, имена — расшифровывает числовой код жизни.\n\n"
            "◇ <b>Консилиум</b> <i>(Plus)</i> — все шесть моделей отвечают одновременно."
        ),
    },
    "kb_how": {
        "title": "▷ Как начать сеанс?",
        "text": (
            "▷ <b>Как начать сеанс?</b>\n\n"
            "<b>I.</b> Заполни анкету — мы подберём модель под твой запрос.\n\n"
            "<b>II.</b> Начни разговор. В любой момент можно сменить модель прямо в ходе сеанса.\n\n"
            "<b>III.</b> Получи ответ — не шаблонный, а сформированный под твой конкретный контекст.\n\n"
            "<b>IV.</b> По окончании забери <b>протокол сеанса</b> — изучи самостоятельно "
            "или передай в начале следующего.\n\n"
            "<blockquote>Чем больше ты рассказываешь — тем точнее и глубже ответ.</blockquote>"
        ),
    },
    "kb_protocol": {
        "title": "▤ Протокол сеанса",
        "text": (
            "▤ <b>Протокол сеанса</b>\n\n"
            "<blockquote>После каждого сеанса ты можешь скачать его полную запись в формате PDF.</blockquote>\n\n"
            "Что в нём есть:\n"
            "· Весь диалог целиком\n"
            "· Краткое саммари: вопрос, обсуждение, вывод\n"
            "· Список использованных моделей\n\n"
            "Протокол можно передать модели в начале следующего сеанса.\n\n"
            "<i>Требует Panacea Plus.</i>"
        ),
    },
    "kb_archive": {
        "title": "▦ Архив сеансов",
        "text": (
            "▦ <b>Архив сеансов</b>\n\n"
            "Все твои прошлые сеансы хранятся в личном архиве.\n\n"
            "<b>Как попасть в архив:</b>\n"
            "Главный экран — это двусторонняя карточка. "
            "Нажми на иконку в <b>правом верхнем углу</b> — карточка перевернётся и откроется архив.\n\n"
            "В архиве ты найдёшь:\n"
            "· Список всех сеансов с датами и моделями\n"
            "· Возможность открыть и перечитать любой сеанс\n"
            "· Кнопку скачивания протокола (PDF, требует Plus)\n\n"
            "<blockquote>Долгое нажатие на карточку сеанса — удалить. Удаление необратимо.</blockquote>"
        ),
    },
    "kb_login": {
        "title": "◎ Вход в аккаунт",
        "text": (
            "◎ <b>Вход в аккаунт</b>\n\n"
            "<blockquote>Регистрации как таковой нет — войти можно в один клик.</blockquote>\n\n"
            "<b>Способы входа:</b>\n"
            "· <b>Google</b> — войти через аккаунт Google\n"
            "· <b>Apple</b> — войти через Apple ID\n"
            "· <b>Гость</b> — без аккаунта, история сохраняется на 24 часа\n\n"
            "<b>Чем отличается гостевой режим:</b>\n"
            "История сеансов не сохраняется в облаке и удаляется через 24 часа. "
            "Архив и протоколы недоступны."
        ),
    },
    "kb_plus": {
        "title": "◈ Panacea Plus",
        "text": (
            "◈ <b>Panacea Plus</b>\n\n"
            "<blockquote>Подписка, которая открывает полные возможности платформы.</blockquote>\n\n"
            "<b>Что входит в Plus:</b>\n"
            "· Оракул и Консилиум — эксклюзивные режимы\n"
            "· Скачивание протоколов сеансов в PDF\n"
            "· История не удаляется через 24 часа\n"
            "· Голосовой ввод и озвучивание ответов\n"
            "· Интерактивные тесты в ходе разговора\n"
            "· Без ограничений на количество сеансов\n\n"
            "Оформить подписку можно в разделе <b>«Подписка»</b> на сайте или прямо здесь."
        ),
    },
    "kb_nav": {
        "title": "⊹ Навигация по сайту",
        "text": (
            "⊹ <b>Навигация по сайту</b>\n\n"
            "· <b>Главная</b> — описание проекта и список моделей.\n"
            "· <b>Сеанс</b> — здесь начинается разговор.\n"
            "· <b>Архив</b> — все прошлые сеансы и протоколы.\n"
            "· <b>Подписка</b> — управление Panacea Plus.\n"
            "· <b>Профиль</b> — настройки аккаунта.\n\n"
            "<blockquote>Большинство карточек двусторонние — чтобы перевернуть карточку, "
            "нажми на её правый верхний угол.</blockquote>"
        ),
    },
    "kb_privacy": {
        "title": "⊘ Конфиденциальность",
        "text": (
            "⊘ <b>Конфиденциальность</b>\n\n"
            "<blockquote>Твои данные защищены современными технологиями шифрования "
            "и полностью обезличены.</blockquote>\n\n"
            "Мы не знаем ни твоего имени, ни других личных данных — "
            "только адрес электронной почты, привязанный к аккаунту.\n\n"
            "· Данные не передаются третьим лицам\n"
            "· Сеансы хранятся только в твоём аккаунте\n"
            "· Команда проекта не читает твои сеансы"
        ),
    },
    "kb_payment": {
        "title": "◻ Оплата",
        "text": (
            "◻ <b>Оплата</b>\n\n"
            "<blockquote>На данный момент оплата принимается в криптовалюте.</blockquote>\n\n"
            "<b>Принимаемые криптовалюты:</b>\n"
            "· USDT (TRC-20, ERC-20)\n"
            "· BTC · ETH · TON\n\n"
            "В будущем появится оплата банковской картой. "
            "Пока что купить подписку через карту можно при <b>личном обращении</b> к команде."
        ),
    },
    "kb_tech": {
        "title": "⚙ Технические вопросы",
        "text": (
            "⚙ <b>Технические вопросы</b>\n\n"
            "<b>Модель не отвечает</b> — проверь интернет и обнови страницу.\n\n"
            "<b>История не загружается</b> — выйди из аккаунта и войди снова.\n\n"
            "<b>Голосовой ввод не работает</b> — проверь разрешение микрофона в браузере.\n\n"
            "<b>Проблемы с оплатой</b> — попробуй другой кошелёк или сеть.\n\n"
            "<blockquote>Для всех остальных проблем — используй кнопку «Связь с командой».</blockquote>"
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
    items = list(KNOWLEDGE_BASE.items())
    main_items = [(k, v) for k, v in items if k != "kb_tech"]
    for i in range(0, len(main_items), 2):
        row = [btn(main_items[i][1]["title"], callback_data=main_items[i][0])]
        if i + 1 < len(main_items):
            row.append(btn(main_items[i + 1][1]["title"], callback_data=main_items[i + 1][0]))
        rows.append(row)
    rows.append([
        btn("⚙ Технические вопросы", callback_data="kb_tech"),
        btn("◎ Связь с командой", callback_data="contact"),
    ])
    rows.append([btn("← Назад", callback_data="back_main", style="primary")])
    return raw_keyboard(rows)

def article_keyboard() -> dict:
    return raw_keyboard([[btn("← Назад", callback_data="support", style="primary")]])

def contact_keyboard() -> dict:
    return raw_keyboard([[btn("← Отмена", callback_data="support", style="primary")]])

def confirm_keyboard() -> dict:
    return raw_keyboard([[btn("← В главное меню", callback_data="back_main", style="primary")]])

def email_keyboard(cancel_target: str = "plus") -> dict:
    return raw_keyboard([[btn("← Отмена", callback_data=cancel_target, style="primary")]])

# ─── Сырые запросы к Bot API (для поддержки style) ───────────────────────────
def _post(method: str, payload: dict):
    data = json.dumps(payload).encode()
    req = urlreq.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urlreq.urlopen(req) as r:
        return json.loads(r.read())

async def send_photo_raw(chat_id: int, photo: str, caption: str, keyboard: dict):
    _post("sendPhoto", {
        "chat_id": chat_id, "photo": photo,
        "caption": caption, "parse_mode": "HTML",
        "reply_markup": keyboard,
    })

async def edit_photo_raw(chat_id: int, message_id: int,
                         photo: str, caption: str, keyboard: dict):
    _post("editMessageMedia", {
        "chat_id": chat_id, "message_id": message_id,
        "media": {"type": "photo", "media": photo,
                  "caption": caption, "parse_mode": "HTML"},
        "reply_markup": keyboard,
    })

async def edit_text_raw(chat_id: int, message_id: int, text: str, keyboard: dict):
    _post("editMessageText", {
        "chat_id": chat_id, "message_id": message_id,
        "text": text, "parse_mode": "HTML",
        "reply_markup": keyboard,
    })

# ─── Хендлеры ─────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_photo_raw(update.effective_chat.id, PHOTO_MAIN, WELCOME_TEXT, main_keyboard())

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id
    msg_id  = query.message.message_id

    if data == "back_main":
        await edit_photo_raw(chat_id, msg_id, PHOTO_MAIN, WELCOME_TEXT, main_keyboard())
        return ConversationHandler.END

    if data == "support":
        await edit_photo_raw(chat_id, msg_id, PHOTO_SUPPORT, SUPPORT_TEXT, support_keyboard())
        return ConversationHandler.END

    if data == "plus":
        await edit_photo_raw(chat_id, msg_id, PHOTO_PLUS, PLUS_TEXT, plus_keyboard())
        return ConversationHandler.END

    if data == "plus_self":
        await edit_photo_raw(chat_id, msg_id, PHOTO_PLUS, EMAIL_PROMPT_SELF, email_keyboard("plus"))
        context.user_data["plus_msg_id"]   = msg_id
        context.user_data["plus_chat_id"]  = chat_id
        context.user_data["plus_for_self"] = True
        return WAITING_EMAIL

    if data == "plus_gift":
        await edit_photo_raw(chat_id, msg_id, PHOTO_PLUS, EMAIL_PROMPT_GIFT, email_keyboard("plus"))
        context.user_data["plus_msg_id"]   = msg_id
        context.user_data["plus_chat_id"]  = chat_id
        context.user_data["plus_for_self"] = False
        return WAITING_GIFT_EMAIL

    if data == "contact":
        await edit_photo_raw(chat_id, msg_id, PHOTO_SUPPORT, CONTACT_PROMPT, contact_keyboard())
        context.user_data["contact_msg_id"]  = msg_id
        context.user_data["contact_chat_id"] = chat_id
        return WAITING_MESSAGE

    if data in KNOWLEDGE_BASE:
        await edit_photo_raw(chat_id, msg_id, PHOTO_SUPPORT,
                             KNOWLEDGE_BASE[data]["text"], article_keyboard())
        return ConversationHandler.END

    return ConversationHandler.END

async def receive_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получаем email и выставляем счёт в Stars."""
    email    = update.message.text.strip()
    chat_id  = update.effective_chat.id
    for_self = context.user_data.get("plus_for_self", True)

    try:
        await update.message.delete()
    except Exception:
        pass

    label = "Panacea Plus — для себя" if for_self else f"Panacea Plus — подарок для {email}"

    # Отправляем invoice через стандартный метод (Stars = currency XTR)
    _post("sendInvoice", {
        "chat_id": chat_id,
        "title": "Panacea Plus",
        "description": label,
        "payload": json.dumps({"email": email, "for_self": for_self}),
        "currency": "XTR",
        "prices": [{"label": "Panacea Plus", "amount": STARS_PRICE}],
    })

    # Редактируем старое сообщение
    msg_id = context.user_data.get("plus_msg_id")
    if msg_id:
        await edit_photo_raw(
            chat_id, msg_id, PHOTO_PLUS,
            f"◎ <b>Счёт выставлен</b>\n\nEmail: <code>{email}</code>\n\n"
            "Оплати счёт выше — подписка активируется автоматически.",
            confirm_keyboard(),
        )

    return ConversationHandler.END

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Подтверждаем платёж."""
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Платёж прошёл — уведомляем пользователя и команду."""
    payment = update.message.successful_payment
    payload = json.loads(payment.invoice_payload)
    email   = payload.get("email", "—")
    chat_id = update.effective_chat.id
    user    = update.effective_user

    # Уведомление пользователю
    _post("sendMessage", {
        "chat_id": chat_id,
        "text": (
            "✦ <b>Оплата прошла успешно!</b>\n\n"
            f"Подписка Panacea Plus будет активирована на аккаунт <code>{email}</code> "
            "в течение нескольких минут."
        ),
        "parse_mode": "HTML",
        "reply_markup": raw_keyboard([[btn("← В главное меню", callback_data="back_main", style="primary")]]),
    })

    # Уведомление команде
    if SUPPORT_CHAT:
        try:
            _post("sendMessage", {
                "chat_id": SUPPORT_CHAT,
                "text": (
                    f"★ <b>Новая оплата</b>\n\n"
                    f"От: {user.full_name} (@{user.username or '—'})\n"
                    f"ID: <code>{user.id}</code>\n"
                    f"Email: <code>{email}</code>\n"
                    f"Сумма: {payment.total_amount} XTR"
                ),
                "parse_mode": "HTML",
            })
        except Exception:
            pass

async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получаем сообщение для команды."""
    user    = update.effective_user
    text    = update.message.text
    chat_id = context.user_data.get("contact_chat_id")
    msg_id  = context.user_data.get("contact_msg_id")

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

    try:
        await update.message.delete()
    except Exception:
        pass

    if msg_id and chat_id:
        await edit_photo_raw(
            chat_id, msg_id, PHOTO_MAIN,
            "✦ Сообщение отправлено. Мы ответим в ближайшее время.",
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
                    WAITING_MESSAGE:    [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message),
                        CallbackQueryHandler(button),
                    ],
                    WAITING_EMAIL:      [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_email),
                        CallbackQueryHandler(button),
                    ],
                    WAITING_GIFT_EMAIL: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_email),
                        CallbackQueryHandler(button),
                    ],
                },
                fallbacks=[CommandHandler("cancel", cancel)],
                per_message=False,
            )

            app.add_handler(CommandHandler("start", start))
            app.add_handler(conv)
            app.add_handler(PreCheckoutQueryHandler(pre_checkout))
            app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

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
