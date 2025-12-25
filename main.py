# -*- coding: utf-8 -*-
# FPS Coach Telegram Bot — PUBLIC STABLE v5
# Render + long polling (NO webhook)
# Warzone / BF6 / BO7

import os
import time
import json
import threading
import logging
import random
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

# ======================
# CONFIG
# ======================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "fps-coach-bot-v5"})

DATA_FILE = "/tmp/state.json"
LOCK = threading.Lock()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("FPS_COACH")

# ======================
# STATE
# ======================
STATE = {
    "users": {}
}

def load_state():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                STATE.update(json.load(f))
        except Exception as e:
            log.warning(f"State load error: {e}")

def save_state():
    with LOCK:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(STATE, f, ensure_ascii=False)

load_state()

# ======================
# TELEGRAM HELPERS
# ======================
def tg(method, payload=None, params=None):
    url = f"{API_URL}/{method}"
    r = SESSION.post(url, json=payload, timeout=30) if payload else SESSION.get(url, params=params, timeout=30)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description"))
    return data["result"]

def send(chat_id, text, kb=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if kb:
        payload["reply_markup"] = kb
    tg("sendMessage", payload=payload)

def edit(chat_id, msg_id, text, kb=None):
    payload = {
        "chat_id": chat_id,
        "message_id": msg_id,
        "text": text
    }
    if kb:
        payload["reply_markup"] = kb
    tg("editMessageText", payload=payload)

# ======================
# KEYBOARD
# ======================
def main_kb():
    return {
        "inline_keyboard": [
            [
                {"text": "🎮 Warzone", "callback_data": "game:warzone"},
                {"text": "🎮 BF6", "callback_data": "game:bf6"},
                {"text": "🎮 BO7", "callback_data": "game:bo7"}
            ],
            [
                {"text": "⚙️ Settings", "callback_data": "settings"},
                {"text": "🧠 Coach ON/OFF", "callback_data": "coach"}
            ],
            [
                {"text": "🧹 Reset", "callback_data": "reset"}
            ]
        ]
    }

# ======================
# LOGIC
# ======================
def ensure_user(chat_id):
    return STATE["users"].setdefault(chat_id, {
        "game": "warzone",
        "coach": True
    })

def menu_text(chat_id):
    u = ensure_user(chat_id)
    return (
        "🎯 FPS Coach Bot\n\n"
        f"Игра: {u['game'].upper()}\n"
        f"AI Coach: {'ON' if u['coach'] else 'OFF'}\n\n"
        "Выбери действие 👇"
    )

# ======================
# UPDATE HANDLERS
# ======================
def handle_message(msg):
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if text.startswith("/start"):
        send(chat_id, menu_text(chat_id), main_kb())
        save_state()
        return

    send(chat_id, "Напиши /start чтобы открыть меню")

def handle_callback(cb):
    chat_id = cb["message"]["chat"]["id"]
    msg_id = cb["message"]["message_id"]
    data = cb["data"]

    u = ensure_user(chat_id)

    if data.startswith("game:"):
        u["game"] = data.split(":")[1]
        save_state()
        edit(chat_id, msg_id, menu_text(chat_id), main_kb())

    elif data == "coach":
        u["coach"] = not u["coach"]
        save_state()
        edit(chat_id, msg_id, menu_text(chat_id), main_kb())

    elif data == "reset":
        STATE["users"].pop(chat_id, None)
        save_state()
        edit(chat_id, msg_id, "🧹 Профиль сброшен\n\nНапиши /start", None)

    tg("answerCallbackQuery", payload={"callback_query_id": cb["id"]})

# ======================
# POLLING LOOP
# ======================
def polling():
    offset = 0
    tg("deleteWebhook", payload={"drop_pending_updates": True})
    log.info("Bot polling started")

    while True:
        try:
            updates = tg("getUpdates", params={"timeout": 50, "offset": offset})
            for u in updates:
                offset = u["update_id"] + 1
                if "message" in u:
                    handle_message(u["message"])
                elif "callback_query" in u:
                    handle_callback(u["callback_query"])
        except Exception as e:
            log.warning(f"Polling error: {e}")
            time.sleep(5)

# ======================
# HEALTHCHECK
# ======================
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def health_server():
    port = int(os.getenv("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), Health).serve_forever()

# ======================
# START
# ======================
if __name__ == "__main__":
    threading.Thread(target=polling, daemon=True).start()
    health_server()
