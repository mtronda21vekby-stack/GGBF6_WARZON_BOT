import os
import time
import json
import threading
import requests
from openai import OpenAI

# =========================
# ENV (Render -> Environment -> Add)
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

MODEL = os.getenv("OPENAI_MODEL", "gpt-5").strip()

HTTP_TIMEOUT = 25
TG_LONGPOLL_TIMEOUT = 50   # это НЕ “задержка ответа”, просто длинный опрос
TG_RETRIES = 3

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("ENV TELEGRAM_BOT_TOKEN is missing")
if not OPENAI_API_KEY:
    raise SystemExit("ENV OPENAI_API_KEY is missing")

openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

# =========================
# MEMORY / PROFILE (in-memory)
# =========================
USER_PROFILE = {}   # chat_id -> dict
USER_MEMORY = {}    # chat_id -> list[{"role":..,"content":..}]
MEMORY_MAX_TURNS = 8

# =========================
# KB
# =========================
GAME_KB = {
    "warzone": {
        "name": "Call of Duty: Warzone",
        "quick_settings": """🎮 Warzone — базовые настройки (контроллер)
• Sens: 7/7 (если мажешь → 6/6)
• ADS: 0.90 low / 0.85 high (если отдача/трекинг слабый → 0.85)
• Aim Assist: Dynamic (fallback Standard)
• Response Curve: Dynamic
• Deadzone min: 0.05 (дрифт → 0.07–0.10)
• FOV: 105–110
• ADS FOV Affected: ON
• Weapon FOV: Wide
• Camera Movement: Least
""",
        "pillars": """🧠 Warzone — что делает “про”
1) Позиция и тайминги (высота/укрытия/ротации)
2) Инфо и коммуникация (пинги, короткие коллы)
3) Выживание > киллы (ресурсы, перезанятие позиции)
4) Бой: первые 0.7 сек решают (пре-эйм, хед-глич, центр экрана)
5) Микро: слайд/стрэф/джамп тайминги без паники
""",
        "vod_template": """📼 Разбор ситуации (шаблон)
1) Режим/сквад (solo/duo/trio/quad)
2) Где был бой (“дом/крыша/поле”)
3) Как умер (угол, чем наказали)
4) Ресурсы (плиты/смок/стим/саморес)
5) Что хотел сделать (пуш/отход/ротация)

Я верну:
• Ошибка №1
• 1–2 действия
• Мини-дрилл 💪
""",
        "drills": {
            "aim": "🎯 Warzone — 20 минут Aim\n10 мин warm-up\n5 мин трекинг\n5 мин микро-коррекции",
            "recoil": "🔫 Warzone — 20 минут Recoil\n5 мин 15–25м\n10 мин 25–40м\n5 мин дисциплина",
            "movement": "🕹 Warzone — 15 минут Movement\nугол→слайд→пик\nджамп-пики\nreposition"
        }
    },
    "bf6": {
        "name": "BF6",
        "quick_settings": "🎮 BF6 — базовые про-настройки: sens средняя, ADS чуть ниже, deadzone минимум без дрифта, FOV высокий.",
        "pillars": "🧠 BF6 — основа: линии фронта, спавн-логика, минимальный пик, командная ценность, смена позиции.",
        "vod_template": "📼 BF6 разбор: карта/режим, класс, где умер/почему, что хотел сделать.",
        "drills": {
            "aim": "🎯 BF6 Aim: префайр углов, трекинг, смена позиции после серии",
            "movement": "🕹 BF6 Movement: выглянул→дал инфо→откатился"
        }
    },
    "bo7": {
        "name": "BO7",
        "quick_settings": "🎮 BO7 — база: sens быстрее если агро, ADS чуть ниже, FOV комфортный.",
        "pillars": "🧠 BO7 — тайминги, центр экрана, 2 сек на позиции, игра от инфо, репики с другого угла.",
        "vod_template": "📼 BO7 разбор: режим/карта, оружие/роль, момент смерти, инфо.",
        "drills": {
            "aim": "🎯 BO7 Aim: pre-aim, ближний трекинг, флик→контроль",
            "movement": "🕹 BO7 Movement: короткий пик, смена угла после контакта"
        }
    }
}

SYSTEM_PROMPT = """Ты профессиональный киберспортивный коуч по FPS (Warzone/BF6/BO7).
Язык: русский. Тон: уверенный, дружелюбный, мотивирующий.
Формат: коротко и структурно, без воды. Эмодзи иногда 🎮🔥💪

Запрещено:
- Любые читы/хаки/аимботы/обход античита/эксплойты.
Если просят такое — вежливо откажи и предложи честные альтернативы.

Поведение:
- Учитывай профиль игрока.
- Если не хватает данных — задай 1–2 коротких вопроса.
- Всегда: 1 ключевая ошибка + 1–2 действия + мини-дрилл.
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

            data = r.json() if "application/json" in r.headers.get("content-type", "") else None
            if r.status_code == 200 and data and data.get("ok"):
                return data
            last = RuntimeError(data.get("description", f"Telegram error HTTP {r.status_code}") if data else f"Telegram HTTP {r.status_code}")
        except Exception as e:
            last = e
        time.sleep(1.2 * (i + 1))
    raise last

def send_message(chat_id: int, text: str):
    # Телега лимит ~4096, безопасно режем
    for i in range(0, len(text), 3900):
        tg_request("sendMessage", payload={"chat_id": chat_id, "text": text[i:i+3900]}, is_post=True)

# =========================
# Profile/memory helpers
# =========================
def ensure_profile(chat_id: int) -> dict:
    return USER_PROFILE.setdefault(chat_id, {
        "game": "warzone",
        "platform": "",
        "style": "",
        "goal": "",
    })

def update_memory(chat_id: int, role: str, content: str):
    mem = USER_MEMORY.setdefault(chat_id, [])
    mem.append({"role": role, "content": content})
    if len(mem) > MEMORY_MAX_TURNS * 2:
        USER_MEMORY[chat_id] = mem[-MEMORY_MAX_TURNS*2:]

def profile_hint(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    kb = GAME_KB.get(p["game"], {})
    parts = [f"game={p['game']}"]
    for k in ("platform", "style", "goal"):
        if p.get(k):
            parts.append(f"{k}={p[k]}")
    return f"Профиль игрока: {', '.join(parts)}. Игра: {kb.get('name', p['game'])}"

def parse_tune_text(text: str):
    t = text.lower()
    platform = ""
    if "xbox" in t:
        platform = "Xbox"
    elif "ps" in t or "playstation" in t:
        platform = "PlayStation"
    elif "kbm" in t or "k&m" in t or "мыш" in t or "клав" in t:
        platform = "KBM"

    style = ""
    if "агро" in t or "aggressive" in t or "агресс" in t:
        style = "Aggressive"
    elif "спокой" in t or "calm" in t or "деф" in t:
        style = "Calm"

    goal = ""
    if "aim" in t or "аим" in t or "прицел" in t:
        goal = "Aim"
    elif "recoil" in t or "отдач" in t:
        goal = "Recoil"
    elif "track" in t or "трекинг" in t:
        goal = "Tracking"
    elif "rank" in t or "ранг" in t:
        goal = "Rank"

    return platform, style, goal

def tune_prompt() -> str:
    return (
        "🎯 Настройка профиля (1 сообщение)\n"
        "Напиши так: платформа, стиль, цель\n"
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
    if kind not in drills:
        return "Доступно: aim | recoil | movement"
    return drills[kind]

def plan_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    game = GAME_KB[p["game"]]["name"]
    goal = p.get("goal") or "стабильность"
    return (
        f"📅 План на 7 дней — {game}\nЦель: {goal}\n\n"
        "День 1–2: warm-up 10м + aim 15м + movement 10м + мини-разбор 5м\n"
        "День 3–4: warm-up 10м + дуэли 15м + дисциплина 10м + вывод 5м\n"
        "День 5–6: warm-up 10м + игра от инфо 20м + фиксация ошибок 5м\n"
        "День 7: 30–60м игры + разбор 2 смертей 10м"
    )

def set_game(chat_id: int, game_key: str) -> str:
    p = ensure_profile(chat_id)
    if game_key not in GAME_KB:
        return "Не знаю такую игру. Доступно: warzone, bf6, bo7"
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
# Main loop
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
                        if len(parts) >= 2:
                            send_message(chat_id, set_game(chat_id, parts[1].lower()))
                        else:
                            send_message(chat_id, "Используй: /game warzone  или  /game bf6  или  /game bo7")
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

                    # tune-like message
                    platform, style, goal = parse_tune_text(text)
                    if platform or style or goal:
                        if platform: p["platform"] = platform
                        if style: p["style"] = style
                        if goal: p["goal"] = goal
                        send_message(chat_id, "Принял ✅\n\n" + settings_text(chat_id))
                        continue

                    # AI
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
    run_bot()
