import os
import time
import json
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from openai import OpenAI

# =========================
# ENV
# =========================
def _env(*names, default=""):
    for n in names:
        v = os.getenv(n)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return default

TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = _env("OPENAI_API_KEY", "AI_INTEGRATIONS_OPENAI_API_KEY")
OPENAI_BASE_URL = _env("OPENAI_BASE_URL", "AI_INTEGRATIONS_OPENAI_BASE_URL", default="https://api.openai.com/v1")
MODEL = _env("OPENAI_MODEL", default="gpt-5")

HTTP_TIMEOUT = int(_env("HTTP_TIMEOUT", default="25") or 25)
TG_LONGPOLL_TIMEOUT = int(_env("TG_LONGPOLL_TIMEOUT", default="50") or 50)  # это не “задержка ответа”
TG_RETRIES = int(_env("TG_RETRIES", default="3") or 3)

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("ENV TELEGRAM_BOT_TOKEN is missing")
if not OPENAI_API_KEY:
    raise SystemExit("ENV OPENAI_API_KEY (or AI_INTEGRATIONS_OPENAI_API_KEY) is missing")

openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

# =========================
# MEMORY / PROFILE
# =========================
USER_PROFILE = {}   # chat_id -> dict
USER_MEMORY = {}    # chat_id -> list[{"role":..,"content":..}]
MEMORY_MAX_TURNS = 10  # чуть больше

# =========================
# KB (Warzone / BF6 / BO7)
# =========================
GAME_KB = {
    "warzone": {
        "name": "Call of Duty: Warzone",
        "quick_settings": """🎮 Warzone — базовые настройки (контроллер)
• Sens: 7/7 (если мажешь → 6/6)
• ADS: 0.90 low / 0.85 high
• Aim Assist: Dynamic (fallback Standard)
• Response Curve: Dynamic
• Deadzone min: 0.05 (дрифт → 0.07–0.10)
• FOV: 105–110
• ADS FOV Affected: ON
• Weapon FOV: Wide
• Camera Movement: Least
""",
        "pillars": """🧠 Warzone — фундамент
1) Позиция/тайминги (высота/укрытия/ротации)
2) Инфо/коммуникация (короткие коллы)
3) Выживание > киллы (ресурсы, репозиция)
4) Первые 0.7 сек решают (пре-эйм, центр экрана)
5) Микро: слайд/стрэф/джамп без паники
""",
        "vod_template": """📼 Разбор ситуации (шаблон)
1) Режим/сквад
2) Где был бой
3) Как умер
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
            "movement": "🕹 Warzone — 15 минут Movement\nугол→слайд→пик\nджамп-пики\nрепозиция"
        }
    },

    "bf6": {
        "name": "BF6",
        "quick_settings": """🎮 BF6 — базовые настройки
• Sens: средняя (чтобы не “рвать” прицел)
• ADS: чуть ниже base sens
• Deadzone: минимум без дрифта
• FOV: высокий (комфортно)
• Кнопки: удобный прыжок/присед на быстрых
""",
        "pillars": """🧠 BF6 — фундамент
1) Линия фронта и спавн-логика
2) Минимальный пик (углы под контроль)
3) Командная ценность (ресы/инфо/точки)
4) Серия → смена позиции
5) Дисциплина: не “перепушивать”
""",
        "vod_template": "📼 BF6 разбор: карта/режим, класс, где умер/почему, что хотел сделать.",
        "drills": {
            "aim": "🎯 BF6 Aim: префайр углов, трекинг, серия→репозиция",
            "movement": "🕹 BF6 Movement: выглянул→дал инфо→откатился"
        }
    },

    "bo7": {
        "name": "BO7",
        "quick_settings": """🎮 BO7 — настройки (быстро)
Контроллер:
• Sens: 7–9 (агро) / 6–7 (стабильно)
• ADS Mult: 0.85–0.95 (если “перелетаешь” → ниже)
• Response Curve: Dynamic (если дёргает → Standard)
• Deadzone min: 0.03–0.06 (дрифт → 0.07+)
• FOV: 100–110 (выше = больше инфы, ниже = проще контроль)
• Aim Assist: ON (если доступно — Dynamic/Black Ops style)

KBM:
• DPI: 800 (база) / 1600 (если привык)
• In-game sens: под 25–35 см на 360° как старт
• ADS: 0.80–1.00
• Raw Input: ON
• Acceleration: OFF
""",
        "pillars": """🧠 BO7 — как играть “как про”
1) Центр экрана всегда на уровне головы/верх-грудь
2) Тайминг: 2 секунды на позиции → смена угла
3) Не репикай один и тот же угол (репик = другой угол)
4) Первые пули важнее всего: префайр/пре-эйм
5) Мини-карта/спавн: угадывай где враг появится
6) Игра от трейда: не геройствуй, играй сериями
""",
        "vod_template": """📼 BO7 разбор (шаблон)
1) Режим/карта
2) Роль (агро/анкёр/поддержка)
3) Оружие + дистанция боя
4) Где умер и почему (пик/репик/позиция/тайминг)
5) Что хотел сделать (пуш/холд/фланг)

Я верну:
• Ошибка №1
• 1–2 действия
• Мини-дрилл 💪
""",
        "extra": """🔥 BO7 — быстрые правила, которые реально апают
• “Шаг 1”: инфо → “Шаг 2”: угол → “Шаг 3”: серия → “Шаг 4”: смена позиции
• Если проиграл дуэль: не “ускоряй sens”, а “упрости углы” и держи центр
• На агро: 1 килл = откат/перезаряд → другой пик
• На деф: держи head-glitch, не давай бесплатный широкий угол
• Коммуникация: 3 слова (где, сколько, хп) — всё
""",
        "drills": {
            "aim": """🎯 BO7 — Aim 20 минут
1) 5м — префайр углов (в голове “враг тут”)
2) 7м — трекинг ближний (без паники, мелкие коррекции)
3) 5м — флик→стоп (выстрел только после остановки)
4) 3м — дисциплина (не спрей на эмоциях)
""",
            "movement": """🕹 BO7 — Movement 15 минут
• Пик короткий (плечо) → инфо → откат
• Джамп-пик только с планом (не “в никуда”)
• После контакта — смена угла (обязательный закон)
""",
            "recoil": """🔫 BO7 — Контроль 15 минут
• 5м — короткие очереди на средней
• 5м — “перевод” с цели на цель
• 5м — удержание центра без овер-движений
"""
        },
        "loadout_tips": """🧩 BO7 — про лоадаут (универсально)
• Выбирай оружие под свою дистанцию (а не “мету”)
• Если много ближнего — быстрее ADS/спринт-аут
• Если средняя — стабильность/контроль/минимум разброса
• Пристрел: выбери 2 дистанции (ближняя + средняя) и играй от них
""",
    }
}

SYSTEM_PROMPT = """Ты профессиональный киберспортивный коуч по FPS (Warzone/BF6/BO7).
Язык: русский. Тон: уверенный, дружелюбный, мотивирующий.
Формат: коротко и структурно, без воды. Эмодзи иногда 🎮🔥💪

Запрещено:
- Любые читы/хаки/аимботы/обход античита/эксплойты.
Если просят такое — вежливо откажи и предложи честные альтернативы.

Всегда:
- 1 ключевая ошибка
- 1–2 конкретных действия
- мини-дрилл
"""

# =========================
# Telegram API
# =========================
def tg_request(method: str, *, payload=None, params=None, is_post=False, retries=TG_RETRIES):
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

            last = RuntimeError(
                data.get("description", f"Telegram error HTTP {r.status_code}") if data else f"Telegram HTTP {r.status_code}"
            )
        except Exception as e:
            last = e
        time.sleep(1.2 * (i + 1))
    raise last

def send_message(chat_id: int, text: str):
    for i in range(0, len(text), 3900):
        tg_request("sendMessage", payload={"chat_id": chat_id, "text": text[i:i+3900]}, is_post=True)

# =========================
# Profile / memory
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
    elif "спокой" in t or "calm" in t or "деф" in t or "анк" in t:
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
    elif "пози" in t or "позиция" in t:
        goal = "Positioning"

    return platform, style, goal

def tune_prompt() -> str:
    return (
        "🎯 Настройка профиля (1 сообщение)\n"
        "Напиши: платформа, стиль, цель\n"
        'Пример: "KBM, Aggressive, Aim"\n\n'
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
    base = kb.get("quick_settings", "")
    if kb.get("extra") and p["game"] == "bo7":
        base = base + "\n" + kb["extra"]
    return base + ("\n\n" + "\n".join(extra) if extra else "")

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
        "День 3–4: warm-up 10м + дуэли/углы 15м + дисциплина 10м + вывод 5м\n"
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
# OpenAI
# =========================
def openai_reply(chat_id: int, user_text: str) -> str:
    p = ensure_profile(chat_id)
    kb = GAME_KB[p["game"]]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": profile_hint(chat_id)},
        {"role": "system", "content": kb.get("pillars", "")},
    ]

    if p["game"] == "bo7":
        # чуть больше контекста именно под BO7
        messages.append({"role": "system", "content": kb.get("loadout_tips", "")})

    messages.extend(USER_MEMORY.get(chat_id, []))
    messages.append({"role": "user", "content": user_text})

    resp = openai_client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_completion_tokens=750,
    )
    return resp.choices[0].message.content or "Не получил ответ. Напиши ещё раз 🙌"

# =========================
# Render health server (Web Service требует слушать PORT)
# =========================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK\n")

    def log_message(self, fmt, *args):
        return

def start_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[health] listening on :{port}")
    server.serve_forever()

# =========================
# Bot loop (Long Polling)
# =========================
def run_bot():
    print("[bot] started (long polling)")
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

                    # tune-like сообщение (обычный текст)
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
                    print("[msg] error:", repr(e))
                    send_message(chat_id, "Ошибка 😅 Попробуй ещё раз через минуту.")

        except Exception as e:
            print("[loop] error:", repr(e))
            time.sleep(3)

if __name__ == "__main__":
    threading.Thread(target=start_health_server, daemon=True).start()
    run_bot()
