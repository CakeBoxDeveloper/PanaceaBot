"""
Публикует пост с кнопкой в канал.
Запуск: python post_to_channel.py
"""
import json
import urllib.request

BOT_TOKEN   = "8678443827:AAEr2vrMU9pYWbldZoMv0bWBg2P4vitHCnE"
CHANNEL_ID  = "@PanaceaPlus"

PHOTO_URL = "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/PanaceaGift.png"

TEXT = (
    "<blockquote>Panacea Plus</blockquote>\n\n"
    "Открой полный доступ к возможностям платформы.\n\n"
    "<blockquote>Оракул и Консилиум</blockquote>\n"
    "Оракул сам выбирает модель под твой запрос. Консилиум даёт ответ от всех шести моделей одновременно.\n\n"
    "<blockquote>Протоколы сеансов в PDF</blockquote>\n"
    "Полная запись диалога с саммари и выводами. Можно передать модели в начале следующего сеанса.\n\n"
    "<blockquote>История хранится бессрочно</blockquote>\n"
    "Без подписки история удаляется через 24 часа. С Plus — все сеансы в архиве навсегда.\n\n"
    "<blockquote>Голосовой режим</blockquote>\n"
    "Говори вместо того чтобы печатать, и слушай ответы моделей вслух.\n\n"
    "<blockquote>Без ограничений</blockquote>\n"
    "Начинай новый сеанс в любое время без лимитов."
)

KEYBOARD = {
    "inline_keyboard": [
        [{"text": "Купить подписку Panacea Plus", "url": "https://t.me/PanaceaRobot", "style": "success"}],
    ]
}

def post(method, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        result = json.loads(r.read())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

post("sendPhoto", {
    "chat_id":      CHANNEL_ID,
    "photo":        PHOTO_URL,
    "caption":      TEXT,
    "parse_mode":   "HTML",
    "reply_markup": KEYBOARD,
})
