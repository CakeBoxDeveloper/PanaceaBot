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

# ─── Redis ────────────────────────────────────────────────────────────────────
import redis as redislib

REDIS_URL = os.environ.get("KV_REDIS_URL", "")

def _redis():
    if not REDIS_URL:
        return None
    try:
        return redislib.from_url(REDIS_URL, decode_responses=True, socket_timeout=2)
    except Exception:
        return None

def redis_set(key: str, value: str, ex: int = 300):
    r = _redis()
    if r:
        try:
            r.set(key, value, ex=ex)
        except Exception:
            pass

def redis_get(key: str) -> str | None:
    r = _redis()
    if not r:
        return None
    try:
        return r.get(key)
    except Exception:
        return None

def redis_del(key: str):
    r = _redis()
    if r:
        try:
            r.delete(key)
        except Exception:
            pass

# ─── Firebase Admin ───────────────────────────────────────────────────────────
import firebase_admin
from firebase_admin import credentials, auth as fb_auth, firestore

_fb_app = None

def _get_fb():
    global _fb_app
    if _fb_app:
        return firestore.client()
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "")
    if not sa_json:
        return None
    try:
        sa = json.loads(sa_json)
        cred = credentials.Certificate(sa)
        _fb_app = firebase_admin.initialize_app(cred)
    except Exception:
        return None
    return firestore.client()

def activate_premium(email: str) -> tuple[bool, str]:
    try:
        db = _get_fb()
        if not db:
            return False, "Firebase не инициализирован"
        user = fb_auth.get_user_by_email(email)
        uid  = user.uid
        now     = int(__import__("time").time() * 1000)
        expires = now + 30 * 24 * 60 * 60 * 1000
        ref = db.collection("sessions").document(uid)\
                .collection("list").document("premium_status")
        ref.set({
            "active":      True,
            "activatedAt": now,
            "expiresAt":   expires,
            "updatedAt":   firestore.SERVER_TIMESTAMP,
        })
        return True, uid
    except fb_auth.UserNotFoundError:
        return False, f"email не найден: {email}"
    except Exception as e:
        return False, str(e)

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ["BOT_TOKEN"]
SUPPORT_CHAT = os.environ.get("SUPPORT_CHAT_ID", "")

SITE_URL    = "https://panacea.mom"
CHANNEL_URL = "https://t.me/PanaceaPlus"
YOUTUBE_URL = "https://www.youtube.com/@PanaceaChannel"

PHOTO_MAIN    = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaAvatar.png"
PHOTO_SUPPORT = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaQuest.png"
PHOTO_PLUS    = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaGift.png"

STARS_PRICE = 1

STATE_SUPPORT   = "support"
STATE_PLUS_SELF = "plus_self"
STATE_PLUS_GIFT = "plus_gift"
STATE_CONFIRM_SELF = "confirm_self"  # email не найден, ждём подтверждения
STATE_CONFIRM_GIFT = "confirm_gift"

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
WELCOME_TEXT = " "

SUPPORT_TEXT = "<blockquote>Справочный центр</blockquote>"

PLUS_TEXT = (
    "<blockquote>Panacea Plus</blockquote>\n\n"
    "Подписка, которая открывает полные возможности платформы.\n\n"
    "<blockquote>Оракул и Консилиум</blockquote>\n"
    "Эксклюзивные режимы для глубокой работы. Оракул сам выбирает наиболее подходящую модель под твой запрос, Консилиум даёт ответ сразу от всех шести моделей одновременно.\n\n"
    "<blockquote>Протоколы сеансов в PDF</blockquote>\n"
    "Полная запись диалога с саммари и выводами, которую можно передать модели в следующем сеансе.\n\n"
    "<blockquote>История хранится бессрочно</blockquote>\n"
    "Без подписки история удаляется через 24 часа. С Plus — все сеансы хранятся в архиве навсегда.\n\n"
    "<blockquote>Голосовой режим</blockquote>\n"
    "Говори вместо того чтобы печатать, и слушай ответы моделей вслух.\n\n"
    "<blockquote>Интерактивные тесты</blockquote>\n"
    "Модели могут присылать тесты и опросники прямо в чат для более точного анализа.\n\n"
    "<blockquote>Без ограничений</blockquote>\n"
    "Начинай новый сеанс в любое время без лимитов.\n\n"
    "Выбери вариант:"
)

# ─── База знаний ──────────────────────────────────────────────────────────────
KNOWLEDGE_BASE = {
    "kb_what": {
        "title": "Что такое Panacea?",
        "text": (
            "<blockquote>Что такое Panacea?</blockquote>\n\n"
            "Panacea — это передовая разработка в области искусственного интеллекта и психологической терапии. Опыт всего человечества теперь доступен для улучшения ментального здоровья и качества жизни.\n\n"
            "Продвинутые языковые модели, каждая из которых является экспертом в своей области, помогут найти ответ на любой вопрос. Каждый сеанс — это не гадание и не совет. Это зеркало. Модели не говорят тебе что делать — они помогают увидеть то, что ты уже знаешь, но ещё не сформулировал.\n\n"
            "Мы небольшая команда инженеров и энтузиастов. Мы не контролируем то, что говорят модели, и не претендуем на истину в последней инстанции. Наша задача — обеспечить работу системы и продолжать её развивать."
        ),
    },
    "kb_models": {
        "title": "Наши модели",
        "text": (
            "<blockquote>Наши модели</blockquote>\n\n"
            "Каждая модель — отдельная система, обученная на определённой традиции знания. Все модели удерживают весь разговор целиком в рамках одного сеанса и могут рассматривать твой вопрос одновременно с десятков точек зрения.\n\n"
            "Тара — таролог. Мастер традиционной школы тарологии. Каждый расклад — это разговор с символами, которые уже знают ответ.\n\n"
            "Карма — кармолог. Читает кармические узлы и незакрытые циклы. Специализируется на повторяющихся ситуациях и скрытых уроках судьбы.\n\n"
            "Астра — астролог. Эксперт в области астрологии и натальных карт. Читает планетарные циклы как язык, на котором Вселенная говорит с каждым из нас.\n\n"
            "Ева — регрессолог. Проводник в глубинную память прошлых жизней. Помогает найти корень страхов, притяжений и повторяющихся сценариев.\n\n"
            "Психея — юнгианский психолог и нарративный терапевт. Слушает не только слова, но и то, что стоит за ними.\n\n"
            "Гера — нумеролог. Видит скрытый порядок в числах. Даты, имена, повторяющиеся цифры — всё это части одного послания.\n\n"
            "Консилиум (Plus) — все шесть моделей отвечают одновременно. Шесть точек зрения на один вопрос."
        ),
    },
    "kb_how": {
        "title": "Как начать сеанс?",
        "text": (
            "<blockquote>Как начать сеанс?</blockquote>\n\n"
            "I. Заполни анкету — укажи свой запрос, текущее состояние и другие параметры. Заполнять необязательно, но чем больше контекста — тем точнее подбор модели.\n\n"
            "II. Начни разговор. В любой момент можно сменить модель прямо в ходе сеанса — нажми на имя модели в левом верхнем углу чата. История при этом сохраняется.\n\n"
            "III. Получи ответ — не шаблонный, а сформированный под твой конкретный контекст. Чем больше ты рассказываешь — тем точнее и глубже ответ.\n\n"
            "IV. По окончании забери протокол сеанса через меню в правом верхнем углу чата. Изучи самостоятельно или передай в начале следующего сеанса.\n\n"
            "Если не знаешь с чего начать — выбери Оракул. Он сам проанализирует запрос и выберет наиболее подходящую модель."
        ),
    },
    "kb_protocol": {
        "title": "Протокол сеанса",
        "text": (
            "<blockquote>Протокол сеанса</blockquote>\n\n"
            "После каждого сеанса можно скачать его полную запись в формате PDF. Протокол генерируется на основе диалога — AI составляет краткое саммари с ключевыми выводами.\n\n"
            "Что содержит протокол:\n"
            "· Весь диалог целиком\n"
            "· Краткое саммари: вопрос, обсуждение, вывод\n"
            "· Список использованных моделей\n\n"
            "Как скачать: нажми кнопку меню в правом верхнем углу чата — Сохранить историю сеанса.\n\n"
            "Протокол можно передать модели в начале следующего сеанса — она продолжит работу с того места, где вы остановились. Требует Panacea Plus."
        ),
    },
    "kb_archive": {
        "title": "Архив сеансов",
        "text": (
            "<blockquote>Архив сеансов</blockquote>\n\n"
            "Все твои прошлые сеансы хранятся в личном архиве. Главный экран приложения — это двусторонняя карточка. Лицевая сторона — анкета для нового сеанса. Обратная — архив.\n\n"
            "Как открыть архив: нажми иконку в правом верхнем углу карточки — она перевернётся.\n\n"
            "В архиве ты найдёшь список всех сеансов с датами, количеством сообщений и использованными моделями. Нажми на сеанс — откроется чат с восстановленной историей. Кнопка со свитком справа от каждого сеанса — скачать протокол PDF.\n\n"
            "Долгое нажатие на карточку сеанса — удалить. Удаление необратимо.\n\n"
            "Без Panacea Plus история удаляется через 24 часа. С подпиской — хранится бессрочно."
        ),
    },
    "kb_login": {
        "title": "Вход в аккаунт",
        "text": (
            "<blockquote>Вход в аккаунт</blockquote>\n\n"
            "Регистрации как таковой нет — войти можно в один клик на экране входа.\n\n"
            "Способы входа:\n"
            "· Google — войти через аккаунт Google\n"
            "· Apple — войти через Apple ID\n"
            "· Гость — без аккаунта, история сохраняется на 24 часа\n\n"
            "В гостевом режиме архив, протоколы и синхронизация между устройствами недоступны. История удаляется через 24 часа автоматически.\n\n"
            "После входа откроется анкета — заполнять необязательно, но помогает подобрать модель точнее. Если возникли проблемы со входом — попробуй другой браузер или очисти кэш."
        ),
    },
    "kb_plus": {
        "title": "Panacea Plus",
        "text": (
            "<blockquote>Panacea Plus</blockquote>\n\n"
            "Подписка, которая открывает полные возможности платформы.\n\n"
            "<blockquote>Оракул и Консилиум</blockquote>\n"
            "Эксклюзивные режимы. Оракул сам выбирает модель под запрос, Консилиум даёт ответ от всех шести моделей одновременно.\n\n"
            "<blockquote>Протоколы сеансов в PDF</blockquote>\n"
            "Полная запись диалога с саммари и выводами. Можно передать модели в начале следующего сеанса.\n\n"
            "<blockquote>История хранится бессрочно</blockquote>\n"
            "Без подписки история удаляется через 24 часа. С Plus — все сеансы хранятся в архиве навсегда.\n\n"
            "<blockquote>Голосовой режим</blockquote>\n"
            "Говори вместо того чтобы печатать, и слушай ответы моделей вслух.\n\n"
            "<blockquote>Интерактивные тесты</blockquote>\n"
            "Модели могут присылать тесты и опросники прямо в чат для более точного анализа.\n\n"
            "<blockquote>Без ограничений</blockquote>\n"
            "Начинай новый сеанс в любое время без лимитов.\n\n"
            "Оформить подписку можно прямо здесь или в разделе Подписка на сайте."
        ),
    },
    "kb_nav": {
        "title": "Навигация по сайту",
        "text": (
            "<blockquote>Навигация по сайту</blockquote>\n\n"
            "Сайт panacea.mom состоит из нескольких разделов, доступных через меню.\n\n"
            "Главная — описание проекта и список моделей.\n"
            "Сеанс — здесь начинается разговор. Заполни анкету и выбери модель.\n"
            "Архив — все прошлые сеансы и протоколы.\n"
            "Подписка — управление Panacea Plus.\n"
            "Профиль — настройки аккаунта.\n\n"
            "Большинство карточек в приложении двусторонние — чтобы перевернуть карточку, нажми на её правый верхний угол."
        ),
    },
    "kb_privacy": {
        "title": "Конфиденциальность",
        "text": (
            "<blockquote>Конфиденциальность</blockquote>\n\n"
            "Твои данные защищены современными технологиями шифрования и полностью обезличены. Мы не знаем ни твоего имени, ни других личных данных — только адрес электронной почты, привязанный к аккаунту.\n\n"
            "· Данные не передаются третьим лицам\n"
            "· Сеансы хранятся только в твоём аккаунте\n"
            "· Команда проекта не читает твои сеансы\n\n"
            "Модели обучаются исключительно на обезличенных данных — без имён, контактов и любой идентифицирующей информации."
        ),
    },
    "kb_payment": {
        "title": "Оплата",
        "text": (
            "<blockquote>Оплата</blockquote>\n\n"
            "На данный момент оплата принимается в криптовалюте и через Telegram Stars прямо в этом боте.\n\n"
            "Принимаемые криптовалюты:\n"
            "· USDT (TRC-20, ERC-20)\n"
            "· BTC · ETH · TON\n\n"
            "В будущем появится оплата банковской картой. Пока что купить подписку через карту можно при личном обращении к команде.\n\n"
            "Если возникли проблемы с оплатой — попробуй другой кошелёк или сеть. Если не помогает — обратись к команде."
        ),
    },
}

# ─── Клавиатуры ───────────────────────────────────────────────────────────────
def main_keyboard() -> dict:
    return raw_keyboard([
        [btn("Открыть сайт Panacea", web_app_url=SITE_URL, style="primary")],
        [btn("Подписка Panacea Plus", callback_data="plus")],
        [
            btn("Канал Panacea", url=CHANNEL_URL),
            btn("Panacea Youtube", url=YOUTUBE_URL),
        ],
        [btn("Справочный центр", callback_data="support")],
    ])
    return raw_keyboard([
        [btn("Открыть сайт Panacea", web_app_url=SITE_URL, style="primary")],
        [btn("Подписка Panacea Plus", callback_data="plus")],
        [
            btn("Канал Panacea", url=CHANNEL_URL),
            btn("Panacea Youtube", url=YOUTUBE_URL),
        ],
        [btn("Справочный центр", callback_data="support")],
    ])

def plus_keyboard() -> dict:
    return raw_keyboard([
        [
            btn("Купить себе", callback_data="plus_self"),
            btn("Подарить другу", callback_data="plus_gift"),
        ],
        [btn("← Назад", callback_data="back_main", style="primary")],
    ])

def support_keyboard() -> dict:
    rows = []
    items = list(KNOWLEDGE_BASE.items())
    for i in range(0, len(items), 2):
        row = [btn(items[i][1]["title"], callback_data=items[i][0])]
        if i + 1 < len(items):
            row.append(btn(items[i+1][1]["title"], callback_data=items[i+1][0]))
        rows.append(row)
    rows.append([btn("Связь с командой", callback_data="contact", style="success")])
    rows.append([btn("← Назад", callback_data="back_main", style="primary")])
    return raw_keyboard(rows)

def article_keyboard() -> dict:
    return raw_keyboard([[btn("← Назад", callback_data="support", style="primary")]])

def plus_article_keyboard() -> dict:
    return raw_keyboard([
        [
            btn("Купить себе", callback_data="plus_self"),
            btn("Подарить другу", callback_data="plus_gift"),
        ],
        [btn("← Назад", callback_data="support", style="primary")],
    ])

def confirm_keyboard() -> dict:
    return raw_keyboard([[btn("← В главное меню", callback_data="back_main", style="primary")]])

def email_confirm_keyboard() -> dict:
    """Промежуточный экран когда email не найден."""
    return raw_keyboard([
        [
            btn("← Назад", callback_data="email_confirm_back", style="danger"),
            btn("Продолжить", callback_data="email_confirm_proceed", style="success"),
        ],
    ])

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
        "caption": caption or " ", "parse_mode": "HTML",
        "reply_markup": keyboard,
    })

def edit_photo(chat_id: int, message_id: int, photo: str, caption: str, keyboard: dict):
    _post("editMessageMedia", {
        "chat_id": chat_id, "message_id": message_id,
        "media": {"type": "photo", "media": photo,
                  "caption": caption or " ", "parse_mode": "HTML"},
        "reply_markup": keyboard,
    })

def delete_msg(chat_id: int, message_id: int):
    try:
        _post("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
    except Exception:
        pass

def _post_file_with_keyboard(chat_id: int, file_bytes: bytes,
                              filename: str, caption: str, keyboard: dict) -> dict:
    """Отправка документа с caption и inline-клавиатурой через multipart."""
    import urllib.request
    boundary = "----PanaceaBoundary"
    kb_json = json.dumps(keyboard)

    parts = [
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n"),
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n"),
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"parse_mode\"\r\n\r\nHTML\r\n"),
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"reply_markup\"\r\n\r\n{kb_json}\r\n"),
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{filename}\"\r\nContent-Type: application/pdf\r\n\r\n"),
    ]
    body = b"".join(p.encode() for p in parts) + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urlreq.urlopen(req) as r:
        return json.loads(r.read())


def _post_file(method: str, chat_id: int, file_bytes: bytes,
               filename: str, mime: str, caption: str = "") -> dict:
    """Отправка файла через multipart/form-data."""
    import urllib.request
    boundary = "----PanaceaBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
        f"{chat_id}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="caption"\r\n\r\n'
        f"{caption}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urlreq.urlopen(req) as r:
        return json.loads(r.read())

# ─── Логирование в канал ──────────────────────────────────────────────────────
PHOTO_LOG_MESSAGE = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/Message.png"
PHOTO_LOG_PAYMENT = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/Payment.png"
PHOTO_LOG_OTHER   = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/Other.png"

def log_to_channel(photo: str, text: str):
    if not SUPPORT_CHAT:
        return
    try:
        _post("sendPhoto", {
            "chat_id":    SUPPORT_CHAT,
            "photo":      photo,
            "caption":    text,
            "parse_mode": "HTML",
        })
    except Exception:
        pass

def generate_receipt_pdf(email: str, for_self: bool, amount: int,
                         paid_at: str, tg_user: str) -> bytes:
    """Генерирует PDF-квитанцию и возвращает байты."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import io, os

    base = os.path.dirname(__file__)

    fn, fn_bold, fn_title = "Helvetica", "Helvetica-Bold", "Helvetica-Bold"
    try:
        pdfmetrics.registerFont(TTFont("Roboto",      os.path.join(base, "RobotoRegular.ttf")))
        pdfmetrics.registerFont(TTFont("Roboto-Bold", os.path.join(base, "RobotoBold.ttf")))
        fn, fn_bold = "Roboto", "Roboto-Bold"
    except Exception:
        pass
    try:
        pdfmetrics.registerFont(TTFont("Tiempos", os.path.join(base, "TiemposHeadline-Black.ttf")))
        fn_title = "Tiempos"
    except Exception:
        pass

    BG   = colors.HexColor("#d2bea5")
    TEXT = colors.HexColor("#201a16")
    GREY = colors.HexColor("#5a4e46")
    ROW1 = colors.HexColor("#d2bea5")
    ROW2 = colors.HexColor("#c8ae96")
    LINE = colors.HexColor("#b8a090")

    buf = io.BytesIO()
    page_w = A4[0] - 4*cm

    def bg_canvas(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BG)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    title_style  = ParagraphStyle('title',  fontName=fn_title, fontSize=28,
                                  textColor=TEXT, alignment=TA_LEFT, spaceAfter=8)
    footer_style = ParagraphStyle('footer', fontSize=18, alignment=TA_CENTER,
                                  fontName=fn, textColor=GREY)

    rows = [
        ("Продукт",     "Panacea Plus — 1 месяц"),
        ("Сумма",       f"{amount} Telegram Stars"),
        ("Email",       email),
        ("Тип",         "Для себя" if for_self else "Подарок"),
        ("Дата оплаты", paid_at),
        ("Покупатель",  tg_user),
        ("Статус",      "Оплачено"),
    ]

    table = Table(rows, colWidths=[5*cm, page_w - 5*cm])
    table.setStyle(TableStyle([
        ('FONTNAME',       (0,0), (-1,-1), fn),
        ('FONTNAME',       (0,0), (0,-1),  fn_bold),
        ('FONTSIZE',       (0,0), (-1,-1), 11),
        ('TEXTCOLOR',      (0,0), (-1,-1), TEXT),
        ('TEXTCOLOR',      (0,0), (0,-1),  GREY),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [ROW1, ROW2]),
        ('TOPPADDING',     (0,0), (-1,-1), 9),
        ('BOTTOMPADDING',  (0,0), (-1,-1), 9),
        ('LEFTPADDING',    (0,0), (-1,-1), 12),
        ('BOX',            (0,0), (-1,-1), 0.5, LINE),
        ('INNERGRID',      (0,0), (-1,-1), 0.5, LINE),
    ]))

    story = [
        Paragraph("Panacea Plus", title_style),
        Spacer(1, 0.8*cm),
        table,
        Spacer(1, 1*cm),
        Paragraph("panacea.mom", ParagraphStyle('footer2', fontSize=11, alignment=TA_CENTER,
                                                fontName=fn_title, textColor=GREY)),
    ]

    doc.build(story, onFirstPage=bg_canvas, onLaterPages=bg_canvas)
    return buf.getvalue()


def _send_invoice(chat_id: int, email: str, for_self: bool):
    result = _post("sendInvoice", {
        "chat_id":      chat_id,
        "title":        "🔑 Подписка Panacea Plus на 1 месяц для:",
        "description":  email,
        "payload":      json.dumps({"for_self": for_self, "email": email}),
        "currency":     "XTR",
        "prices":       [{"label": "Panacea Plus · 1 месяц", "amount": STARS_PRICE}],
        "photo_url":    "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaGift.png",
        "photo_width":  800,
        "photo_height": 800,
    })
    invoice_msg_id = result.get("result", {}).get("message_id")
    if invoice_msg_id:
        redis_set(f"main_msg:{chat_id}", str(invoice_msg_id), ex=86400)

# ─── Хендлеры ─────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    redis_del(f"state:{chat_id}")
    # Удаляем команду /start
    try:
        delete_msg(chat_id, update.message.message_id)
    except Exception:
        pass
    # Удаляем предыдущее главное сообщение если есть
    old_msg_id = redis_get(f"main_msg:{chat_id}")
    if old_msg_id:
        try:
            delete_msg(chat_id, int(old_msg_id))
        except Exception:
            pass
    # Отправляем новое главное сообщение
    try:
        result = send_photo(chat_id, PHOTO_MAIN, " ", main_keyboard())
        new_msg_id = result.get("result", {}).get("message_id")
        if new_msg_id:
            redis_set(f"main_msg:{chat_id}", str(new_msg_id), ex=86400)
    except Exception as e:
        # Fallback — отправляем без картинки
        try:
            result = _post("sendMessage", {
                "chat_id": chat_id,
                "text": "Panacea",
                "reply_markup": main_keyboard(),
            })
            new_msg_id = result.get("result", {}).get("message_id")
            if new_msg_id:
                redis_set(f"main_msg:{chat_id}", str(new_msg_id), ex=86400)
        except Exception:
            pass

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data    = query.data
    chat_id = query.message.chat_id
    msg_id  = query.message.message_id

    if data == "back_main":
        redis_del(f"state:{chat_id}")
        # Удаляем текущее сообщение, отправляем новое главное
        delete_msg(chat_id, msg_id)
        old_main = redis_get(f"main_msg:{chat_id}")
        if old_main and int(old_main) != msg_id:
            delete_msg(chat_id, int(old_main))
        result = send_photo(chat_id, PHOTO_MAIN, WELCOME_TEXT, main_keyboard())
        new_msg_id = result.get("result", {}).get("message_id")
        if new_msg_id:
            redis_set(f"main_msg:{chat_id}", str(new_msg_id), ex=86400)

    elif data == "support":
        redis_del(f"state:{chat_id}")
        edit_photo(chat_id, msg_id, PHOTO_SUPPORT, SUPPORT_TEXT, support_keyboard())

    elif data == "plus":
        redis_del(f"state:{chat_id}")
        edit_photo(chat_id, msg_id, PHOTO_PLUS, PLUS_TEXT, plus_keyboard())

    elif data == "plus_self":
        redis_set(f"state:{chat_id}", STATE_PLUS_SELF)
        edit_photo(chat_id, msg_id, PHOTO_PLUS,
            "<blockquote>Подписка для себя</blockquote>\n\nУкажи email, который используешь для входа на panacea.mom:",
            cancel_keyboard("plus"))

    elif data == "plus_gift":
        redis_set(f"state:{chat_id}", STATE_PLUS_GIFT)
        edit_photo(chat_id, msg_id, PHOTO_PLUS,
            "<blockquote>Подписка в подарок</blockquote>\n\nУкажи email друга, который он использует для входа на panacea.mom:",
            cancel_keyboard("plus"))

    elif data == "contact":
        redis_set(f"state:{chat_id}", STATE_SUPPORT)
        edit_photo(chat_id, msg_id, PHOTO_SUPPORT,
            "<blockquote>Связь с командой</blockquote>\n\n"
            "Напиши своё сообщение — мы отвечаем всем в порядке очереди.\n\n"
            "Если ты уже писал нам ранее, не нужно отправлять повторное сообщение — мы обязательно ответим.",
            cancel_keyboard("support"))

    elif data == "save_receipt_self" or data.startswith("save_receipt:"):
        # Пересылаем квитанцию в Saved Messages
        r_msg_id = redis_get(f"receipt_msg:{chat_id}")
        if not r_msg_id and data.startswith("save_receipt:"):
            r_msg_id = data.split(":", 1)[1]
        if r_msg_id:
            try:
                _post("forwardMessage", {
                    "chat_id":      chat_id,
                    "from_chat_id": chat_id,
                    "message_id":   int(r_msg_id),
                })
                await query.answer("Квитанция сохранена в Избранное", show_alert=False)
            except Exception:
                await query.answer("Не удалось сохранить", show_alert=False)
        else:
            await query.answer("Квитанция недоступна", show_alert=False)

    elif data == "email_confirm_proceed":
        state = redis_get(f"state:{chat_id}")
        email = redis_get(f"pending_email:{chat_id}")
        for_self = state == STATE_CONFIRM_SELF
        redis_del(f"state:{chat_id}")
        redis_del(f"pending_email:{chat_id}")
        delete_msg(chat_id, msg_id)
        if email:
            _send_invoice(chat_id, email, for_self)
        else:
            # email пропал из Redis — просим ввести снова
            new_state = STATE_PLUS_SELF if for_self else STATE_PLUS_GIFT
            redis_set(f"state:{chat_id}", new_state)
            result = send_photo(chat_id, PHOTO_PLUS,
                "<blockquote>Сессия истекла</blockquote>\n\nПожалуйста, введи email ещё раз:",
                cancel_keyboard("plus"))
            new_msg_id = result.get("result", {}).get("message_id")
            if new_msg_id:
                redis_set(f"main_msg:{chat_id}", str(new_msg_id), ex=86400)

    elif data == "email_confirm_back":
        state = redis_get(f"state:{chat_id}")
        for_self = state == STATE_CONFIRM_SELF
        redis_del(f"state:{chat_id}")
        redis_del(f"pending_email:{chat_id}")
        new_state = STATE_PLUS_SELF if for_self else STATE_PLUS_GIFT
        redis_set(f"state:{chat_id}", new_state)
        edit_photo(chat_id, msg_id, PHOTO_PLUS,
            "<blockquote>Подписка для себя</blockquote>\n\nУкажи email, который используешь для входа на panacea.mom:"
            if for_self else
            "<blockquote>Подписка в подарок</blockquote>\n\nУкажи email друга, который он использует для входа на panacea.mom:",
            cancel_keyboard("plus"))

    elif data in KNOWLEDGE_BASE:
        kb = plus_article_keyboard() if data == "kb_plus" else article_keyboard()
        edit_photo(chat_id, msg_id, PHOTO_SUPPORT, KNOWLEDGE_BASE[data]["text"], kb)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg     = update.message
    chat_id = msg.chat_id
    text    = msg.text.strip()
    user    = update.effective_user
    state   = redis_get(f"state:{chat_id}")

    delete_msg(chat_id, msg.message_id)

    if state == STATE_SUPPORT:
        redis_del(f"state:{chat_id}")
        log_to_channel(PHOTO_LOG_MESSAGE,
            f"<blockquote>@{user.username or '—'} · {user.full_name} · ID {user.id}</blockquote>\n"
            f"{text}"
        )
        # Редактируем текущее сообщение на подтверждение
        main_msg_id = redis_get(f"main_msg:{chat_id}")
        if main_msg_id:
            edit_photo(chat_id, int(main_msg_id), PHOTO_SUPPORT,
                "Сообщение отправлено. Мы ответим в ближайшее время.",
                confirm_keyboard())
        else:
            send_photo(chat_id, PHOTO_SUPPORT,
                "Сообщение отправлено. Мы ответим в ближайшее время.",
                confirm_keyboard())

    elif state in (STATE_PLUS_SELF, STATE_PLUS_GIFT):
        redis_del(f"state:{chat_id}")
        for_self = state == STATE_PLUS_SELF

        # Проверяем email в Firebase
        email_ok = False
        try:
            db = _get_fb()
            if db:
                fb_user = fb_auth.get_user_by_email(text)
                email_ok = fb_user is not None
        except Exception:
            email_ok = False

        # Удаляем сообщение с запросом email
        main_msg_id = redis_get(f"main_msg:{chat_id}")
        if main_msg_id:
            delete_msg(chat_id, int(main_msg_id))

        if not email_ok:
            # Промежуточный экран — email не найден
            new_state = STATE_CONFIRM_SELF if for_self else STATE_CONFIRM_GIFT
            redis_set(f"state:{chat_id}", new_state)
            redis_set(f"pending_email:{chat_id}", text, ex=600)
            result = send_photo(chat_id, PHOTO_PLUS,
                f"<blockquote>Аккаунт с адресом {text} пока не найден на сайте.\n\n"
                f"Подписку можно купить сейчас — аккаунт активируется автоматически когда пользователь с этой почтой войдёт на panacea.mom.</blockquote>",
                email_confirm_keyboard())
            new_msg_id = result.get("result", {}).get("message_id")
            if new_msg_id:
                redis_set(f"main_msg:{chat_id}", str(new_msg_id), ex=86400)
            return

        # Email найден — сразу инвойс
        _send_invoice(chat_id, text, for_self)

async def stars_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    _post("sendInvoice", {
        "chat_id":     chat_id,
        "title":       "Тест Stars",
        "description": "Тестовый платёж — 1 звезда",
        "payload":     json.dumps({"test": True}),
        "currency":    "XTR",
        "prices":      [{"label": "Тест", "amount": 1}],
    })

async def state_debug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    state   = redis_get(f"state:{chat_id}")
    await update.message.reply_text(
        f"KV_REDIS_URL: <code>{'задан' if REDIS_URL else 'НЕТ'}</code>\n"
        f"state: <code>{state or 'нет'}</code>",
        parse_mode="HTML"
    )

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payment = update.message.successful_payment
    payload = json.loads(payment.invoice_payload)
    email   = payload.get("email", "")
    user    = update.effective_user
    chat_id = update.effective_chat.id

    ok, detail = activate_premium(email) if email else (False, "email не передан")

    # Удаляем инвойс
    main_msg_id = redis_get(f"main_msg:{chat_id}")
    if main_msg_id:
        delete_msg(chat_id, int(main_msg_id))

    if ok:
        text = (
            f"<blockquote>Оплата прошла!</blockquote>\n\n"
            f"Подписка Panacea Plus активирована на аккаунт {email}.\n\n"
            "Обнови страницу сайта — изменения уже применены."
        )
    else:
        text = (
            f"<blockquote>Оплата прошла!</blockquote>\n\n"
            f"Аккаунт с адресом {email} пока не зарегистрирован на сайте. "
            "Подписка активируется автоматически как только ты войдёшь под этим аккаунтом на panacea.mom."
        )

    # Генерируем PDF и отправляем как единственное сообщение с текстом и кнопками
    receipt_msg_id = None
    try:
        import datetime
        paid_at = datetime.datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC")
        tg_user = f"{user.full_name} (@{user.username or '—'})"
        pdf_bytes = generate_receipt_pdf(email, payload.get("for_self", True),
                                         payment.total_amount, paid_at, tg_user)

        # Клавиатура
        receipt_keyboard = raw_keyboard([
            [btn("← В главное меню", callback_data="back_main", style="primary")],
        ])

        # Отправляем документ с caption = текст об оплате + кнопки
        doc_result = _post_file_with_keyboard(
            chat_id, pdf_bytes,
            f"receipt_{chat_id}.pdf",
            text,
            receipt_keyboard
        )
        receipt_msg_id = doc_result.get("result", {}).get("message_id")
        if receipt_msg_id:
            redis_set(f"receipt_msg:{chat_id}", str(receipt_msg_id), ex=86400)
            redis_set(f"main_msg:{chat_id}", str(receipt_msg_id), ex=86400)
    except Exception:
        # Fallback — фото без квитанции
        result = send_photo(chat_id, PHOTO_MAIN, text, confirm_keyboard())
        new_msg_id = result.get("result", {}).get("message_id")
        if new_msg_id:
            redis_set(f"main_msg:{chat_id}", str(new_msg_id), ex=86400)

    # Лог оплаты в канал
    for_self = payload.get("for_self", True)
    firebase_ok = ok
    # Не логируем ошибку неправильной почты — только реальные ошибки Firebase
    firebase_error = None if (ok or "не найден" in detail or "Malformed" in detail or "email" in detail.lower()) else detail

    log_caption = (
        f"Имя: {user.full_name}\n"
        f"@{user.username or '—'} · ID {user.id}\n"
        f"<blockquote>{email} ({'для себя' if for_self else 'в подарок'})</blockquote>\n"
        f"{payment.total_amount} ★"
    )
    if firebase_error:
        log_caption += f"\n<blockquote>Почта не найдена в базе</blockquote>"

    log_to_channel(PHOTO_LOG_PAYMENT, log_caption)

# ─── Vercel handler ───────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        async def process():
            app = ApplicationBuilder().token(BOT_TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("stars", stars_test))
            app.add_handler(CommandHandler("state", state_debug))
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
