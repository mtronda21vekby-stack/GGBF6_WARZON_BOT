import os
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
from openai import OpenAI

# =========================
# ENV (Render -> Environment)
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
MODEL = os.getenv("OPENAI_MODEL", "gpt-5").strip()

HTTP_TIMEOUT = 25
TG_LONGPOLL_TIMEOUT = 50   # это НЕ задержка ответа, это timeout для getUpdates
TG_RETRIES = 3

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("ENV TELEGRAM_BOT_TOKEN is missing")
if not OPENAI_API_KEY:
    raise SystemExit("ENV OPENAI_API_KEY is missing")

openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

# =========================
# MEMORY / PROFILE (in-memory)
# =========================
USER_PROFILE = {}
USER_MEMORY = {}
MEMORY_MAX_TURNS = 8

# =========================
# KB
# =========================
GAME_KB = {
    "warzone": {
        "name": "Call of Duty: Warzone",
        "quick_settings": "🎮 Warzone — базовые настройки: Sens 7/7, ADS 0.90/0.85, Dynamic, FOV 105–110",
        "pillars": "🧠 Warzone — основа: позиция, инфо, выживание>киллы, первые 0.7 сек, микро без паники",
        "vod_template": "📼 Разбор: режим/сквад, где бой, как умер, ресурсы, что хотел сделать.",
        "drills": {
            "aim": "🎯 Aim 20 мин: warm-up 10, трекинг 5, микро 5",
            "recoil": "🔫 Recoil 20 мин: 15–25м 5, 25–40м 10, дисциплина 5",
            "movement": "🕹 Movement 15 мин: угол→слайд→пик, джамп-пики, reposition"
        }
    },
    "bf6": {
        "name": "BF6",
        "quick_settings": "🎮 BF6 — база: sens средняя, ADS чуть ниже, deadzone минимум, FOV высокий",
        "pillars": "🧠 BF6 — фронт, спавны, минимальный пик, командная ценность, смена позиции",
        "vod_template": "📼 BF6 разбор: карта/режим, класс, где умер/почему, что хотел сделать.",
        "drills": {
            "aim": "🎯 BF6 Aim: префайр, трекинг, смена позиции после серии",
            "movement": "🕹 BF6 Movement: выглянул→дал инфо→откатился"
        }
    },
    "bo7": {
        "name": "BO7",
        "quick_settings": "🎮 BO7 — база: sens быстрее если агро, ADS чуть ниже, FOV комфортный",
        "pillars": "🧠 BO7 — тайминги, центр экрана, 2 сек на позиции, игра от инфо, репики",
        "vod_template": "📼 BO7 разбор: режим/карта, оружие/роль, момент смерти, инфо.",
        "drills": {
            "aim": "🎯 BO7 Aim: pre-aim, ближний трекинг, флик→контроль",
            "movement": "🕹 BO7 Movement: короткий пик, смена угла после контакта"
        }
    }
}

SYSTEM_PROMPT = """Ты профессиональный киберспортивный коуч по FPS (Warzone/BF6/BO7).
Язык: русский. Тон: уверенный, дружелюбный.
Формат: коротко и структурно.

Запрещено: любые читы/хаки/обходы.
Всегда: 1 ключевая ошибка + 1–2 действия + мини-дрилл.
"""

# =========================
# Telegram API
# =========================
def tg_request(method: str, payload=None, params=None, is_post=False, retries=TG_RETRIES):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    last = None
    for i in range(retries):
        try:
            if is_post:
                r = requests.post(url, json=payload, timeout=HTTP_TIMEOUT)
            else:
                r = requests.get(url, params=params, timeout=HTTP_TIMEOUT)

            data = r.json()
            if r.status_code == 200 and data.get("ok"):
                return data
            last = RuntimeError(data.get("description", f"Telegram HTTP {r.status_code}"))
        except Exception as e:
            last = e
        time.sleep(1.2 * (i + 1))
    raise last

def send_message(chat_id: int, text: str):
    for i in range(0, len(text), 3900):
        tg_request("sendMessage", payload={"chat_id": chat_id, "text": text[i:i+3900]}, is_post=True)

# =========================
# Profile/memory
# =========================
def ensure_profile(chat_id: int) -> dict:
    return USER_PROFILE.setdefault(chat_id, {"game": "warzone", "platform": "", "style": "", "goal": ""})

def update_memory(chat_id: int, role: str, content: str):
    mem = USER_MEMORY.setdefault(chat_id, [])
    mem.append({"role": role, "content": content})
    if len(mem) > MEMORY_MAX_TURNS * 2:
        USER_MEMORY[chat_id] = mem[-MEMORY_MAX_TURNS*2:]

def profile_hint(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    kb = GAME_KB.get(p["game"], {})
    return f"Профиль: game={p['game']}, platform={p.get('platform','')}, style={p.get('style','')}, goal={p.get('goal','')}. Игра: {kb.get('name', p['game'])}"

def parse_tune_text(text: str):
    t = text.lower()
    platform = "Xbox" if "xbox" in t else ("PlayStation" if "ps" in t or "playstation" in t else ("KBM" if "kbm" in t or "мыш" in t or "клав" in t else ""))
    style = "Aggressive" if ("агро" in t or "aggressive" in t) else ("Calm" if ("спокой" in t or "calm" in t or "деф" in t) else "")
    goal = "Aim" if ("aim" in t or "аим" in t) else ("Recoil" if ("recoil" in t or "отдач" in t) else ("Tracking" if ("track" in t or "трекинг" in t) else ("Rank" if ("rank" in t or "ранг" in t) else "")))
    return platform, style, goal

def tune_prompt() -> str:
    return (
        "🎯 Настройка профиля (1 сообщение)\n"
        'Пример: "Xbox, Aggressive, Aim"\n\n'
        "Команды:\n"
        "• /game warzone | bf6 | bo7\n"
        "• /settings\n"
        "• /drills aim | recoil | movement\n"
        "• /vod\n"
        "• /plan\n"
        "• /profile\n"
        "• /reset"
    )

def settings_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    kb = GAME_KB[p["game"]]
    extra = []
    if p.get("platform"): extra.append(f"Платформа: {p['platform']}")
    if p.get("style"): extra.append(f"Стиль: {p['style']}")
    if p.get("goal"): extra.append(f"Цель: {p['goal']}")
    return kb.get("quick_settings", "") + ("\n" + "\n".join(extra) if extra else "")

def drills_text(chat_id: int, kind: str) -> str:
    p = ensure_profile(chat_id)
    drills = GAME_KB[p["game"]].get("drills", {})
    return drills.get(kind, "Доступно: aim | recoil | movement")

def plan_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    game = GAME_KB[p["game"]]["name"]
    goal = p.get("goal") or "стабильность"
    return (f"📅 План на 7 дней — {game}\nЦель: {goal}\n\n"
            "1–2: warm-up 10м + aim 15м + movement 10м + разбор 5м\n"
            "3–4: warm-up 10м + дуэли 15м + дисциплина 10м + вывод 5м\n"
            "5–6: warm-up 10м + игра от инфо 20м + фиксация 5м\n"
            "7: 30–60м игры + разбор 2 смертей 10м")

def set_game(chat_id: int, game_key: str) -> str:
    p = ensure_profile(chat_id)
    if game_key not in GAME_KB:
        return "Доступно: warzone, bf6, bo7"
    p["game"] = game_key
    return f"Ок ✅ Текущая игра: {GAME_KB[game_key]['name']}\nНапиши /settings или /drills"

# =========================
# OpenAI reply
# =========================
def openai_reply(chat_id: int, user_text: str) -> str:
    p = ensure_profile(chat_id)
    kb = GAME_KB[p["game"]]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": profile_hint(chat_id)},
        {"role": "system", "content": kb.get("pillars", "")},
    ]
    messages.extend(USER_MEMORY.get(chat_id, []))
    messages.append({"role": "user", "content": user_text})

    resp = openai_client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_completion_tokens=700
    )
    return resp.choices[0].message.content or "Не получил ответ. Напиши ещё раз 🙌"

# =========================
# Render Web Service HTTP server (важно!)
# =========================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/health", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def run_http_server():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"HTTP server listening on 0.0.0.0:{port}")
    server.serve_forever()

# =========================
# Telegram bot loop
# =========================
def run_bot():
    print("Bot started (long polling)")
    offset = 0

    while True:
        try:
            data = tg_request("getUpdates", params={"offset": offset, "timeout": TG_LONGPOLL_TIMEOUT}, is_post=False)
            for upd in data.get("result", []):
                offset = upd.get("update_id", offset) + 1
                msg = upd.get("message") or upd.get("edited_message") or {}
                text = (msg.get("text") or "").strip()
                chat_id = (msg.get("chat") or {}).get("id")
                if not chat_id or not text:
                    continue

                try:
                    p = ensure_profile(chat_id)

                    if text.startswith("/start"):
                        send_message(chat_id, "Я про-коуч по Warzone / BF6 / BO7 🎮\n\n" + tune_prompt())
                        continue

                    if text.startswith("/reset"):
                        USER_PROFILE.pop(chat_id, None)
                        USER_MEMORY.pop(chat_id, None)
                        send_message(chat_id, "Сбросил профиль и память ✅ Начнём заново: /tune")
                        continue

                    if text.startswith("/profile"):
                        send_message(chat_id, "Профиль:\n" + json.dumps(ensure_profile(chat_id), ensure_ascii=False, indent=2))
                        continue

                    if text.startswith("/tune"):
                        send_message(chat_id, tune_prompt())
                        continue

                    if text.startswith("/game"):
                        parts = text.split()
                        send_message(chat_id, set_game(chat_id, parts[1].lower()) if len(parts) >= 2 else "Используй: /game warzone|bf6|bo7")
                        continue

                    if text.startswith("/settings"):
                        send_message(chat_id, settings_text(chat_id))
                        continue

                    if text.startswith("/drills"):
                        parts = text.split()
                        kind = parts[1].lower() if len(parts) >= 2 else "aim"
                        send_message(chat_id, drills_text(chat_id, kind))
                        continue

                    if text.startswith("/vod"):
                        send_message(chat_id, GAME_KB[p["game"]].get("vod_template", "Опиши ситуацию."))
                        continue

                    if text.startswith("/plan"):
                        send_message(chat_id, plan_text(chat_id))
                        continue

                    platform, style, goal = parse_tune_text(text)
                    if platform or style or goal:
                        if platform: p["platform"] = platform
                        if style: p["style"] = style
                        if goal: p["goal"] = goal
                        send_message(chat_id, "Принял ✅\n\n" + settings_text(chat_id))
                        continue

                    update_memory(chat_id, "user", text)
                    reply = openai_reply(chat_id, text)
                    update_memory(chat_id, "assistant", reply)
                    send_message(chat_id, reply)

                except Exception as e:
                    print("Message error:", repr(e))
                    send_message(chat_id, "Ошибка 😅 Попробуй ещё раз через минуту.")

        except Exception as e:
            print("Loop error:", repr(e))
            time.sleep(3)

if __name__ == "__main__":
    # Важно: запускаем HTTP сервер (для Render) и бота параллельно
    threading.Thread(target=run_bot, daemon=True).start()
    run_http_server()
