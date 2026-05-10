"""
Запусти этот скрипт один раз после деплоя на Vercel,
чтобы зарегистрировать webhook в Telegram.

Использование:
  BOT_TOKEN=xxx WEBHOOK_URL=https://your-project.vercel.app python set_webhook.py
"""
import os
import urllib.request
import json

BOT_TOKEN   = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]

url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
data = json.dumps({"url": f"{WEBHOOK_URL}/api/webhook"}).encode()

req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as resp:
    print(json.loads(resp.read()))
