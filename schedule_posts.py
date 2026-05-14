"""
Распределяет посты из MD файла на 90 дней с отложенной публикацией через APScheduler.
Каждый пост публикуется в 10:00 UTC в свой день.

Установка зависимостей:
  pip install apscheduler

Запуск:
  python schedule_posts.py 1-90.md
"""
import sys
import re
import json
import urllib.request
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import time

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN   = "8678443827:AAEr2vrMU9pYWbldZoMv0bWBg2P4vitHCnE"
CHANNEL_ID  = "@PanaceaPlus"

# Маппинг менторов на аватарки
MENTOR_AVATARS = {
    "астра": "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/Astra.png",
    "карма": "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/Karma.png",
    "психея": "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/Psychea.png",
    "тара": "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/Tara.png",
    "ева": "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/Eva.png",
    "гера": "https://raw.githubusercontent.com/CakeBoxDeveloper/PanaceaBot/main/Gera.png",
}

# ─── Парсинг MD файла ─────────────────────────────────────────────────────────
def parse_posts(md_file: str) -> list:
    """Парсит MD файл и возвращает список постов"""
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Разбиваем по дням (## День N)
    day_blocks = re.split(r'^## День \d+\n', content, flags=re.MULTILINE)[1:]
    
    posts = []
    for day_num, block in enumerate(day_blocks, 1):
        lines = block.strip().split('\n')
        
        # Первая строка — имя ментора (может быть **Имя** или просто текст)
        mentor = None
        title = None
        text_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Ищем имя ментора (в **скобках**)
            if mentor is None and line.startswith('**') and line.endswith('**'):
                mentor = line.strip('*').lower()
                continue
            
            # Ищем заголовок (может быть **Заголовок:** или просто текст)
            if title is None and (line.startswith('**') or line.startswith('Заголовок:')):
                title = line.replace('**', '').replace('Заголовок:', '').strip()
                continue
            
            # Остальное — текст поста
            if line:
                text_lines.append(line)
        
        # Если нет явного заголовка, берём первую строку текста
        if not title and text_lines:
            title = text_lines.pop(0)
        
        text = '\n'.join(text_lines).strip()
        
        posts.append({
            "day": day_num,
            "mentor": mentor,
            "title": title,
            "text": text,
        })
    
    return posts

# ─── Отправка в Telegram ──────────────────────────────────────────────────────
def publish_post(post: dict) -> bool:
    """Публикует пост в канал"""
    
    # Получаем аватарку ментора
    mentor_key = post["mentor"] or "психея"
    photo_url = MENTOR_AVATARS.get(mentor_key, MENTOR_AVATARS["психея"])
    
    # Формируем текст поста
    caption = f"<b>{post['title']}</b>"
    if post["text"]:
        caption += f"\n\n{post['text']}"
    
    # Экранируем HTML
    caption = caption.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # Отправляем фото
    payload = {
        "chat_id": CHANNEL_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML",
    }
    
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read())
            if result.get("ok"):
                print(f"✓ День {post['day']}: {post['title'][:40]}... опубликовано")
                return True
            else:
                print(f"✗ День {post['day']}: {result.get('description', 'Unknown error')}")
                return False
    except Exception as e:
        print(f"✗ День {post['day']}: {str(e)}")
        return False

# ─── Главная функция ──────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Использование: python schedule_posts.py <md_file>")
        sys.exit(1)
    
    md_file = sys.argv[1]
    
    print(f"📖 Парсю {md_file}...")
    posts = parse_posts(md_file)
    print(f"✓ Найдено {len(posts)} постов\n")
    
    print(f"📅 Планирую публикацию на {len(posts)} дней...\n")
    
    # Инициализируем планировщик
    scheduler = BackgroundScheduler()
    scheduler.start()
    
    # Вычисляем время публикации для каждого поста
    start_date = datetime.utcnow()
    
    for post in posts:
        day_num = post["day"]
        # Публикуем в 10:00 UTC каждого дня
        publish_date = start_date + timedelta(days=day_num - 1)
        publish_time = publish_date.replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Если время уже прошло, публикуем сразу
        if publish_time <= datetime.utcnow():
            print(f"День {day_num}: время прошло, публикую сразу...")
            publish_post(post)
        else:
            # Планируем публикацию
            scheduler.add_job(
                publish_post,
                'date',
                run_date=publish_time,
                args=[post],
                id=f"post_{day_num}"
            )
            print(f"День {day_num}: запланировано на {publish_time.strftime('%Y-%m-%d %H:%M UTC')}")
    
    print(f"\n{'='*60}")
    print(f"✓ Все {len(posts)} постов запланированы!")
    print(f"{'='*60}\n")
    print("Планировщик работает. Нажми Ctrl+C для остановки.\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n✓ Планировщик остановлен")
        scheduler.shutdown()

if __name__ == "__main__":
    main()
