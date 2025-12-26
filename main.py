# -*- coding: utf-8 -*-
import os
import time
import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API = f"https://api.telegram.org/bot{TOKEN}"

def tg(method, data=None):
    r = requests.post(f"{API}/{method}", json=data, timeout=30)
    return r.json()

def send(chat_id, text):
    tg("sendMessage", {
        "chat_id": chat_id,
        "text": text
    })

def main():
    print("🚀 FPS Coach Bot STARTED (SAFE SINGLE FILE MODE)")
    offset = 0

    while True:
        try:
            res = tg("getUpdates", {
                "timeout": 60,
                "offset": offset
            })

            for upd in res.get("result", []):
                offset = upd["update_id"] + 1

                if "message" in upd:
                    msg = upd["message"]
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")

                    if text.startswith("/start"):
                        send(chat_id,
                             "🎮 FPS Coach Bot\n"
                             "🧠 Brain v3 (BOOT MODE)\n\n"
                             "Напиши где умер и почему думаешь.\n"
                             "Я помогу.")
                    else:
                        send(chat_id,
                             "🧠 Принял.\n"
                             "Скоро подключим полный мозг 💪")

        except Exception as e:
            print("ERROR:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()
