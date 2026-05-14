"""
Публикует пост в канал на основе YouTube-видео.
Берёт обложку, название и описание из YouTube Data API.

Запуск:
  python post_youtube.py https://www.youtube.com/watch?v=KtTLGPG7XNY
"""
import sys
import json
import re
import urllib.request
import urllib.parse

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN   = "8678443827:AAEr2vrMU9pYWbldZoMv0bWBg2P4vitHCnE"
CHANNEL_ID  = "@PanaceaPlus"
YT_API_KEY  = "AIzaSyAPorCwQsWZZ1Jv4aMr8dw3KQvbTLc6MU0"  # ← вставь свой ключ здесь

# ─── Извлекаем video_id из ссылки ─────────────────────────────────────────────
def extract_video_id(url: str) -> str:
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    raise ValueError(f"Не удалось извлечь video_id из: {url}")

# ─── Получаем данные видео через YouTube Data API ─────────────────────────────
def get_video_info(video_id: str) -> dict:
    params = urllib.parse.urlencode({
        "part":  "snippet",
        "id":    video_id,
        "key":   YT_API_KEY,
    })
    url = f"https://www.googleapis.com/youtube/v3/videos?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read())
    items = data.get("items", [])
    if not items:
        raise ValueError(f"Видео не найдено: {video_id}")
    return items[0]["snippet"]

# ─── Выбираем лучшую обложку ──────────────────────────────────────────────────
def best_thumbnail(thumbnails: dict) -> str:
    for quality in ("maxres", "standard", "high", "medium", "default"):
        if quality in thumbnails:
            url = thumbnails[quality]["url"]
            # Проверяем что обложка реально доступна
            try:
                req = urllib.request.Request(url, method="HEAD",
                                             headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as r:
                    if r.status == 200:
                        return url
            except Exception:
                continue
    raise ValueError("Обложка не найдена")

# ─── Отправка в Telegram ──────────────────────────────────────────────────────
def tg_post(method: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    print(f"Отправляю {method}: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        result = json.loads(r.read())
        if not result.get("ok"):
            raise RuntimeError(f"Telegram error: {result}")
        return result

# ─── Основная логика ──────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Использование: python post_youtube.py <youtube_url>")
        sys.exit(1)

    yt_url   = sys.argv[1]
    video_id = extract_video_id(yt_url)
    print(f"Video ID: {video_id}")
    snippet  = get_video_info(video_id)
    print(f"Snippet получен")

    title       = snippet["title"]
    description = snippet.get("description", "").strip()
    # Берём только первый абзац, максимум 500 символов
    desc_short  = description.split("\n\n")[0].strip() if description else ""
    if len(desc_short) > 500:
        desc_short = desc_short[:497] + "..."
    print(f"Title: {title}")
    print(f"Description length: {len(desc_short)}")
    thumbnail   = best_thumbnail(snippet["thumbnails"])
    watch_url   = f"https://www.youtube.com/watch?v={video_id}"

    # Экранируем HTML-символы
    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")

    caption = f"<b>{esc(title)}</b>"
    if desc_short:
        caption += f"\n\n{esc(desc_short)}"

    keyboard = {
        "inline_keyboard": [
            [{"text": "Смотреть выпуск", "url": watch_url, "style": "danger"}],
        ]
    }

    result = tg_post("sendPhoto", {
        "chat_id":      CHANNEL_ID,
        "photo":        thumbnail,
        "caption":      caption,
        "parse_mode":   "HTML",
        "reply_markup": keyboard,
    })

    msg_id = result["result"]["message_id"]
    print(f"✓ Опубликовано: message_id={msg_id}")
    print(f"  Видео: {title}")
    print(f"  Канал: https://t.me/{CHANNEL_ID.lstrip('@')}/{msg_id}")

if __name__ == "__main__":
    main()
