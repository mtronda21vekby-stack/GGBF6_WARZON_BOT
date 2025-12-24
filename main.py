import os
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
from openai import OpenAI
from openai import APIConnectionError, AuthenticationError, RateLimitError, BadRequestError, APIError

# =========================
# ENV
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()  # можно менять в Render ENV

HTTP_TIMEOUT = 25
TG_LONGPOLL_TIMEOUT = 45
TG_RETRIES = 3

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("Missing ENV: TELEGRAM_BOT_TOKEN (BotFather token)")

# OpenAI клиент создаём даже без ключа — бот не должен падать
openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

# =========================
# Data (in-memory)
# =========================
USER_PROFILE = {}  # chat_id -> dict
USER_MEMORY = {}   # chat_id -> list[{role, content}]
MEMORY_MAX_TURNS = 8

# =========================
# Knowledge base
# =========================
GAME_KB = {
    "warzone": {
        "name": "Call of Duty: Warzone",
        "settings": (
            "🎮 Warzone — настройки (контроллер)\n"
            "• Sens: 7/7 (мимо → 6/6)\n"
            "• ADS: 0.90 low / 0.85 high\n"
            "• Aim Assist: Dynamic (если не заходит → Standard)\n"
            "• Deadzone min: 0.05 (дрифт → 0.07–0.10)\n"
            "• FOV: 105–110 | ADS FOV Affected: ON | Weapon FOV: Wide\n"
            "• Camera Movement: Least\n"
        ),
        "drills": {
            "aim": "🎯 Warzone Aim (20м)\n10м warm-up\n5м трекинг\n5м микро-коррекции",
            "recoil": "🔫 Warzone Recoil (20м)\n5м 15–25м\n10м 25–40м\n5м дисциплина",
            "movement": "🕹 Warzone Movement (15м)\nугол→слайд→пик\nджамп-пики\nreposition",
        },
        "plan": (
            "📅 План на 7 дней — Warzone\n"
            "Д1–2: warm-up 10м + aim 15м + movement 10м + мини-разбор 5м\n"
            "Д3–4: warm-up 10м + дуэли/углы 15м + дисциплина 10м + вывод 5м\n"
            "Д5–6: warm-up 10м + игра от инфо 20м + фиксация ошибок 5м\n"
            "Д7: 30–60м игры + разбор 2 смертей 10м\n"
        ),
        "vod": (
            "📼 VOD/ситуация (шаблон)\n"
            "1) Режим (solo/duo/trio/quad)\n"
            "2) Где бой (дом/крыша/поле)\n"
            "3) Как умер (угол, чем наказали)\n"
            "4) Ресурсы (плиты/смок/стим/саморес)\n"
            "5) Что хотел сделать (пуш/отход/ротация)\n\n"
            "Я верну: ошибка №1 + 1–2 действия + мини-дрилл 💪"
        ),
        "pillars": (
            "🧠 Warzone — база\n"
            "1) Позиция и тайминг\n2) Инфо\n3) Выживание > киллы\n"
            "4) Пре-эйм решает\n5) Микро без паники\n"
        ),
    },
    "bf6": {
        "name": "BF6",
        "settings": (
            "🎮 BF6 — настройки (база)\n"
            "• Sens: средняя, ADS чуть ниже\n"
            "• Deadzone: минимум без дрифта\n"
            "• FOV: высокий (комфорт)\n"
            "• После контакта — смена позиции\n"
        ),
        "drills": {
            "aim": "🎯 BF6 Aim (15–20м)\nпрефайр углов\nтрекинг\nсмена позиции после серии",
            "movement": "🕹 BF6 Movement (15м)\nвыглянул→дал инфо→откатился\nрепик с другого угла",
            "recoil": "🔫 BF6 Recoil (15м)\nкороткие очереди\nконтроль на средней",
        },
        "plan": (
            "📅 План на 7 дней — BF6\n"
            "Д1–2: aim 15м + позиции 15м\n"
            "Д3–4: линии фронта/спавны 20м + дуэли 10м\n"
            "Д5–6: игра от инфо 25м + разбор 5м\n"
            "Д7: 45–60м + разбор 2 смертей\n"
        ),
        "vod": "📼 BF6 разбор: карта/режим, класс, где умер/почему, что хотел сделать.",
        "pillars": "🧠 BF6: линии фронта, спавны, минимальный пик, ротации.",
    },
    "bo7": {
        "name": "BO7",
        "settings": (
            "🎮 BO7 — настройки (контроллер)\n"
            "• Sens: 6–8 (если перелетаешь → -1)\n"
            "• ADS: 0.80–0.95 (стабильность > скорость)\n"
            "• Deadzone min: 0.03–0.07 (дрифт → 0.08+)\n"
            "• Curve: Dynamic/Standard\n"
            "• FOV: 100–115\n\n"
            "🔥 Быстрые правила\n"
            "• После килла: репозиция 1–2 сек\n"
            "• Проиграл дуэль → упрощай углы\n"
            "• Короткий пик → инфо → откат → другой пик\n"
        ),
        "drills": {
            "aim": "🎯 BO7 Aim (20м)\n5м префайр\n7м трекинг\n5м микро\n3м дисциплина",
            "movement": "🕹 BO7 Movement (15–20м)\nрепики с другого угла\nтайминг\nстрейф + центр",
            "recoil": "🔫 BO7 Recoil (15м)\nкороткие очереди\nпервая пуля\nне жадничай",
        },
        "plan": (
            "📅 План на 7 дней — BO7\n"
            "Д1–2: aim 20м + movement 10м\n"
            "Д3–4: углы/тайминги 25м + мини-разбор 5м\n"
            "Д5–6: дуэли 30м\n"
            "Д7: 45–60м + разбор 2–3 смертей\n"
        ),
        "vod": "📼 BO7 разбор: режим/карта, момент смерти, инфо (радар/звук), что хотел сделать.",
        "pillars": "🧠 BO7: центр+префайр, тайминги, 2 сек на позиции→смена, репик только с другого угла.",
    },
}

SYSTEM_PROMPT = (
    "Ты профессиональный киберспортивный коуч по FPS (Warzone/BF6/BO7). "
    "Язык русский. Тон уверенный, дружелюбный. "
    "Формат: коротко и структурно, без воды. Эмодзи иногда.\n\n"
    "Запрещено: читы/хаки/аимботы/обход античита. "
    "Если просят — откажи и предложи честные тренировки.\n\n"
    "Всегда: 1 ключевая ошибка + 1–2 действия + мини-дрилл."
)

# =========================
# Telegram helpers
# =========================
def tg_request(method: str, *, params=None, payload=None, is_post=False, retries=TG_RETRIES):
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

def send_message(chat_id: int, text: str, reply_markup=None):
    chunks = [text[i:i+3900] for i in range(0, len(text), 3900)] or [""]
    for ch in chunks:
        tg_request("sendMessage", payload={"chat_id": chat_id, "text": ch, "reply_markup": reply_markup}, is_post=True)

def edit_message(chat_id: int, message_id: int, text: str, reply_markup=None):
    tg_request("editMessageText", payload={"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": reply_markup}, is_post=True)

def answer_callback(callback_id: str):
    tg_request("answerCallbackQuery", payload={"callback_query_id": callback_id}, is_post=True)

# =========================
# UI
# =========================
def kb_main(chat_id: int):
    p = ensure_profile(chat_id)
    coach_on = "🧠 Coach: ON" if p.get("coach", True) else "🧠 Coach: OFF"
    return {
        "inline_keyboard": [
            [{"text": "🎮 Warzone", "callback_data": "game:warzone"},
             {"text": "🎮 BF6", "callback_data": "game:bf6"},
             {"text": "🎮 BO7", "callback_data": "game:bo7"}],
            [{"text": "⚙️ Settings", "callback_data": "action:settings"},
             {"text": "💪 Drills", "callback_data": "action:drills"}],
            [{"text": "📅 Plan", "callback_data": "action:plan"},
             {"text": "📼 VOD", "callback_data": "action:vod"}],
            [{"text": "👤 Profile", "callback_data": "action:profile"},
             {"text": coach_on, "callback_data": "action:coach"}],
            [{"text": "🧹 Reset", "callback_data": "action:reset"}],
        ]
    }

def kb_drills():
    return {
        "inline_keyboard": [
            [{"text": "🎯 Aim", "callback_data": "drill:aim"},
             {"text": "🔫 Recoil", "callback_data": "drill:recoil"},
             {"text": "🕹 Movement", "callback_data": "drill:movement"}],
            [{"text": "⬅️ Меню", "callback_data": "action:menu"}],
        ]
    }

# =========================
# Profile / memory
# =========================
def ensure_profile(chat_id: int) -> dict:
    # coach по умолчанию включаем ТОЛЬКО если есть ключ
    default_coach = bool(OPENAI_API_KEY)
    return USER_PROFILE.setdefault(chat_id, {
        "game": "warzone",
        "platform": "",
        "style": "",
        "goal": "",
        "coach": default_coach,
    })

def profile_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "👤 Профиль\n"
        f"Игра: {GAME_KB[p['game']]['name']}\n"
        f"Платформа: {p.get('platform') or '—'}\n"
        f"Стиль: {p.get('style') or '—'}\n"
        f"Цель: {p.get('goal') or '—'}\n"
        f"Coach: {'ON' if p.get('coach') else 'OFF'}\n"
    )

def parse_profile_line(text: str):
    t = text.lower()
    platform = ""
    if "xbox" in t:
        platform = "Xbox"
    elif "ps" in t or "playstation" in t:
        platform = "PlayStation"
    elif "kbm" in t or "мыш" in t or "клав" in t:
        platform = "KBM"

    style = ""
    if "агро" in t or "aggressive" in t:
        style = "Aggressive"
    elif "спокой" in t or "calm" in t or "деф" in t:
        style = "Calm"

    goal = ""
    if "aim" in t or "аим" in t:
        goal = "Aim"
    elif "recoil" in t or "отдач" in t:
        goal = "Recoil"
    elif "rank" in t or "ранг" in t:
        goal = "Rank"

    return platform, style, goal

def update_memory(chat_id: int, role: str, content: str):
    mem = USER_MEMORY.setdefault(chat_id, [])
    mem.append({"role": role, "content": content})
    if len(mem) > MEMORY_MAX_TURNS * 2:
        USER_MEMORY[chat_id] = mem[-MEMORY_MAX_TURNS*2:]

# =========================
# OpenAI (safe)
# =========================
def openai_reply_safe(chat_id: int, user_text: str) -> str:
    if not OPENAI_API_KEY or openai_client is None:
        return "⚠️ AI выключен: нет OPENAI_API_KEY. Открой Render → Environment Variables и добавь ключ, затем Redeploy."

    p = ensure_profile(chat_id)
    kb = GAME_KB[p["game"]]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Текущая игра: {kb['name']}. {kb.get('pillars','')}"},
        {"role": "system", "content": f"Профиль: {json.dumps(p, ensure_ascii=False)}"},
    ]
    messages.extend(USER_MEMORY.get(chat_id, []))
    messages.append({"role": "user", "content": user_text})

    try:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_completion_tokens=450,
        )
        out = (resp.choices[0].message.content or "").strip()
        return out or "Не получил ответ. Напиши ещё раз 🙌"

    except AuthenticationError:
        return "❌ AI: неверный ключ (AuthenticationError). Проверь OPENAI_API_KEY в Render и сделай Redeploy."
    except RateLimitError:
        return "⏳ AI: лимит/перегруз (RateLimitError). Подожди 20–60 сек и попробуй снова."
    except BadRequestError as e:
        return f"❌ AI: bad request. Часто это модель/параметры. Модель сейчас: {OPENAI_MODEL}."
    except APIConnectionError:
        return "⚠️ AI: проблема соединения (APIConnectionError). Это сеть/Render. Попробуй ещё раз через минуту."
    except APIError:
        return "⚠️ AI: временная ошибка OpenAI. Попробуй ещё раз через минуту."
    except Exception:
        return "⚠️ AI: неизвестная ошибка. Напиши /status — посмотрим конфиг."

# =========================
# Actions
# =========================
def render_menu_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "🧠 FPS Coach Bot\n"
        f"Текущая игра: {GAME_KB[p['game']]['name']}\n"
        f"Coach: {'ON' if p.get('coach') else 'OFF'}\n\n"
        "Жми кнопки ниже 👇"
    )

def set_game(chat_id: int, game_key: str) -> str:
    p = ensure_profile(chat_id)
    if game_key not in GAME_KB:
        return "Не знаю такую игру."
    p["game"] = game_key
    return f"✅ Игра: {GAME_KB[game_key]['name']}"

def get_settings(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return GAME_KB[p["game"]]["settings"]

def get_plan(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return GAME_KB[p["game"]]["plan"]

def get_vod(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return GAME_KB[p["game"]]["vod"]

def get_drill(chat_id: int, kind: str) -> str:
    p = ensure_profile(chat_id)
    drills = GAME_KB[p["game"]]["drills"]
    return drills.get(kind, "Доступно: aim / recoil / movement")

def status_text() -> str:
    ok_key = "✅" if bool(OPENAI_API_KEY) else "❌"
    ok_tg = "✅" if bool(TELEGRAM_BOT_TOKEN) else "❌"
    return (
        "🧾 Status\n"
        f"TELEGRAM_BOT_TOKEN: {ok_tg}\n"
        f"OPENAI_API_KEY: {ok_key}\n"
        f"OPENAI_BASE_URL: {OPENAI_BASE_URL}\n"
        f"OPENAI_MODEL: {OPENAI_MODEL}\n\n"
        "Если OPENAI_API_KEY: ❌ → Render → Environment Variables → add → Redeploy."
    )

def ai_test() -> str:
    if not OPENAI_API_KEY or openai_client is None:
        return "❌ /ai_test: нет OPENAI_API_KEY."
    try:
        r = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": "Ответь одним словом: OK"}],
            max_completion_tokens=10,
        )
        out = (r.choices[0].message.content or "").strip()
        return f"✅ /ai_test: {out or 'OK'} (model={OPENAI_MODEL})"
    except AuthenticationError:
        return "❌ /ai_test: неверный ключ (AuthenticationError)."
    except APIConnectionError:
        return "⚠️ /ai_test: APIConnectionError (сеть/Render)."
    except Exception as e:
        return f"⚠️ /ai_test: ошибка: {type(e).__name__}"

# =========================
# Telegram handlers
# =========================
def handle_message(chat_id: int, text: str):
    p = ensure_profile(chat_id)

    if text.startswith("/start") or text.startswith("/menu"):
        send_message(chat_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/reset"):
        USER_PROFILE.pop(chat_id, None)
        USER_MEMORY.pop(chat_id, None)
        ensure_profile(chat_id)
        send_message(chat_id, "🧹 Сбросил профиль и память.", reply_markup=kb_main(chat_id))
        return

    if text.startswith("/profile"):
        send_message(chat_id, profile_text(chat_id), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/status"):
        send_message(chat_id, status_text(), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/ai_test"):
        send_message(chat_id, ai_test(), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/game"):
        parts = text.split()
        if len(parts) >= 2:
            msg = set_game(chat_id, parts[1].lower())
            send_message(chat_id, msg, reply_markup=kb_main(chat_id))
        else:
            send_message(chat_id, "Используй: /game warzone | bf6 | bo7", reply_markup=kb_main(chat_id))
        return

    if text.startswith("/settings"):
        send_message(chat_id, get_settings(chat_id), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/plan"):
        send_message(chat_id, get_plan(chat_id), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/vod"):
        send_message(chat_id, get_vod(chat_id), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/drills"):
        send_message(chat_id, "Выбери дрилл:", reply_markup=kb_drills())
        return

    # 1) профиль одной строкой
    platform, style, goal = parse_profile_line(text)
    if platform or style or goal:
        if platform:
            p["platform"] = platform
        if style:
            p["style"] = style
        if goal:
            p["goal"] = goal
        send_message(chat_id, "✅ Профиль обновлён.\n\n" + profile_text(chat_id), reply_markup=kb_main(chat_id))
        return

    # 2) Coach OFF -> подсказка, что включить
    if not p.get("coach", True):
        send_message(
            chat_id,
            "🧠 Coach сейчас OFF. Нажми кнопку **Coach** в меню чтобы включить.\n"
            "А пока используй кнопки Settings/Drills/Plan/VOD.",
            reply_markup=kb_main(chat_id),
        )
        return

    # 3) AI ответ
    update_memory(chat_id, "user", text)
    reply = openai_reply_safe(chat_id, text)
    update_memory(chat_id, "assistant", reply)
    send_message(chat_id, reply, reply_markup=kb_main(chat_id))

def handle_callback(cb: dict):
    cb_id = cb["id"]
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")
    data = cb.get("data", "")

    if not chat_id or not message_id:
        answer_callback(cb_id)
        return

    try:
        if data == "action:menu":
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

        elif data.startswith("game:"):
            game = data.split(":", 1)[1]
            set_game(chat_id, game)
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:settings":
            edit_message(chat_id, message_id, get_settings(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:plan":
            edit_message(chat_id, message_id, get_plan(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:vod":
            edit_message(chat_id, message_id, get_vod(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:profile":
            edit_message(chat_id, message_id, profile_text(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:coach":
            p = ensure_profile(chat_id)
            p["coach"] = not p.get("coach", True)
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:reset":
            USER_PROFILE.pop(chat_id, None)
            USER_MEMORY.pop(chat_id, None)
            ensure_profile(chat_id)
            edit_message(chat_id, message_id, "🧹 Сбросил профиль и память.", reply_markup=kb_main(chat_id))

        elif data == "action:drills":
            edit_message(chat_id, message_id, "Выбери дрилл:", reply_markup=kb_drills())

        elif data.startswith("drill:"):
            kind = data.split(":", 1)[1]
            edit_message(chat_id, message_id, get_drill(chat_id, kind), reply_markup=kb_drills())

    finally:
        answer_callback(cb_id)

def run_telegram_bot():
    print("Telegram bot started (long polling)")
    offset = 0
    while True:
        try:
            data = tg_request("getUpdates", params={"offset": offset, "timeout": TG_LONGPOLL_TIMEOUT})
            for upd in data.get("result", []):
                offset = upd.get("update_id", offset) + 1

                if "callback_query" in upd:
                    handle_callback(upd["callback_query"])
                    continue

                msg = upd.get("message") or upd.get("edited_message") or {}
                text = (msg.get("text") or "").strip()
                chat_id = (msg.get("chat") or {}).get("id")
                if not chat_id or not text:
                    continue

                try:
                    handle_message(chat_id, text)
                except Exception as e:
                    print("Message error:", repr(e))
                    send_message(chat_id, "Ошибка 😅 Попробуй ещё раз.", reply_markup=kb_main(chat_id))

        except Exception as e:
            print("Loop error:", repr(e))
            time.sleep(3)

# =========================
# Render health endpoint
# =========================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/healthz"):
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def run_http_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"HTTP server listening on :{port}")
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    run_http_server()
