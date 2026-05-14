"""
Получить свой Telegram ID.
Запуск: python get_my_id.py
Затем отправь боту любое сообщение и увидишь свой ID.
"""
import json
import urllib.request
import urllib.parse

BOT_TOKEN = "8678443827:AAEr2vrMU9pYWbldZoMv0bWBg2P4vitHCnE"

def get_updates():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read())
        
    if data.get("ok") and data.get("result"):
        for update in data["result"]:
            if "message" in update:
                user_id = update["message"]["from"]["id"]
                username = update["message"]["from"].get("username", "N/A")
                first_name = update["message"]["from"].get("first_name", "N/A")
                text = update["message"].get("text", "")
                
                print(f"User ID: {user_id}")
                print(f"Username: @{username}")
                print(f"Name: {first_name}")
                print(f"Message: {text}")
                print()

if __name__ == "__main__":
    print("Получаю последние сообщения...\n")
    get_updates()
