"""
Админ-панель бота для управления постами.
Запуск: python admin_bot.py
"""
import json
import urllib.request
import urllib.parse
import subprocess
import sys
import os

BOT_TOKEN = "8678443827:AAEr2vrMU9pYWbldZoMv0bWBg2P4vitHCnE"
ADMIN_PASSWORD = "12345"  # ← Замени на свой пароль

# Хранилище состояний пользователей (в памяти)
user_states = {}  # {user_id: {"state": "waiting_password" | "admin_panel" | "waiting_url", "data": {...}}}

# ─── Отправка сообщения в Telegram ────────────────────────────────────────────
def send_message(chat_id: int, text: str, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# ─── Ответ на callback ────────────────────────────────────────────────────────
def answer_callback(callback_query_id: str, text: str = "", show_alert: bool = False):
    payload = {
        "callback_query_id": callback_query_id,
        "text": text,
        "show_alert": show_alert,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# ─── Запуск Python скрипта ────────────────────────────────────────────────────
def run_script(script_name: str, args: list = None) -> str:
    try:
        cmd = [sys.executable, script_name]
        if args:
            cmd.extend(args)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        if result.returncode == 0:
            return f"✓ Успешно!\n\n{result.stdout}"
        else:
            return f"✗ Ошибка:\n\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "✗ Скрипт выполнялся слишком долго (>60 сек)"
    except Exception as e:
        return f"✗ Ошибка: {str(e)}"

# ─── Админ-панель ────────────────────────────────────────────────────────────
def show_admin_panel(chat_id: int):
    text = (
        "<b>🔧 Админ-панель</b>\n\n"
        "Выбери действие:"
    )
    
    keyboard = {
        "inline_keyboard": [
            [{"text": "📹 Выложить видео", "callback_data": "post_video"}],
            [{"text": "🚪 Выход", "callback_data": "logout"}],
        ]
    }
    
    user_states[chat_id] = {"state": "admin_panel"}
    send_message(chat_id, text, keyboard)

# ─── Запрос пароля ────────────────────────────────────────────────────────────
def ask_password(chat_id: int):
    text = "🔐 Введи пароль для доступа к админ-панели:"
    user_states[chat_id] = {"state": "waiting_password"}
    send_message(chat_id, text)

# ─── Запрос ссылки на видео ────────────────────────────────────────────────────
def ask_video_url(chat_id: int):
    text = "📹 Отправь ссылку на YouTube видео:\n\nПример: https://www.youtube.com/watch?v=UKUOGqeRWjk"
    user_states[chat_id] = {"state": "waiting_url"}
    send_message(chat_id, text)

# ─── Обработка callback'ов ────────────────────────────────────────────────────
def handle_callback(callback_query: dict):
    callback_id = callback_query["id"]
    chat_id = callback_query["from"]["id"]
    data = callback_query["data"]
    
    # Проверяем, что пользователь в админ-панели
    if chat_id not in user_states or user_states[chat_id].get("state") != "admin_panel":
        answer_callback(callback_id, "❌ Сначала введи пароль", show_alert=True)
        return
    
    if data == "post_video":
        answer_callback(callback_id, "")
        ask_video_url(chat_id)
    
    elif data == "logout":
        answer_callback(callback_id, "")
        if chat_id in user_states:
            del user_states[chat_id]
        send_message(chat_id, "👋 Вышел из админ-панели")

# ─── Обработка текстовых сообщений ────────────────────────────────────────────
def handle_message(message: dict):
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    
    # Если пользователь не в состоянии, проверяем команду
    if chat_id not in user_states:
        if text == "/admin":
            ask_password(chat_id)
        else:
            send_message(chat_id, "Привет! Используй /admin для входа в админ-панель")
        return
    
    state = user_states[chat_id].get("state")
    
    # Ожидаем пароль
    if state == "waiting_password":
        if text == ADMIN_PASSWORD:
            send_message(chat_id, "✓ Пароль верный!")
            show_admin_panel(chat_id)
        else:
            send_message(chat_id, "❌ Неверный пароль. Попробуй ещё раз:")
            user_states[chat_id] = {"state": "waiting_password"}
    
    # Ожидаем ссылку на видео
    elif state == "waiting_url":
        if "youtube.com" in text or "youtu.be" in text:
            send_message(chat_id, "⏳ Выкладываю видео...")
            
            # Запускаем скрипт
            output = run_script("post_youtube.py", [text])
            
            # Отправляем результат
            send_message(chat_id, f"<b>Результат:</b>\n\n<code>{output}</code>")
            
            # Возвращаемся в админ-панель
            show_admin_panel(chat_id)
        else:
            send_message(chat_id, "❌ Это не похоже на YouTube ссылку. Попробуй ещё раз:")

# ─── Основной обработчик ────────────────────────────────────────────────────
def handle_update(update: dict):
    if "message" in update:
        handle_message(update["message"])
    elif "callback_query" in update:
        handle_callback(update["callback_query"])

# ─── Получение обновлений (polling) ────────────────────────────────────────
def get_updates(offset: int = 0) -> tuple:
    params = urllib.parse.urlencode({"offset": offset, "timeout": 30})
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?{params}"
    
    try:
        with urllib.request.urlopen(url, timeout=35) as r:
            data = json.loads(r.read())
            if data.get("ok"):
                return data.get("result", []), offset
    except Exception as e:
        print(f"Ошибка при получении обновлений: {e}")
    
    return [], offset

# ─── Главный цикл ────────────────────────────────────────────────────────────
def main():
    print("🤖 Админ-бот запущен")
    print(f"Пароль: {ADMIN_PASSWORD}")
    print("Отправь /admin для входа\n")
    
    offset = 0
    
    try:
        while True:
            updates, offset = get_updates(offset)
            
            for update in updates:
                try:
                    handle_update(update)
                except Exception as e:
                    print(f"Ошибка при обработке update: {e}")
                
                offset = update["update_id"] + 1
    
    except KeyboardInterrupt:
        print("\n✓ Бот остановлен")

if __name__ == "__main__":
    main()
