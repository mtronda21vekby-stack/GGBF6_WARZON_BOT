import os
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests

# Optional OpenAI (бот НЕ упадет, если ключа нет)
OPENAI_AVAILABLE = True
try:
    from openai import OpenAI
except Exception:
    OPENAI_AVAILABLE = False

# =======================
# ENV
# =======================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-nano").strip()

if not BOT_TOKEN:
    raise SystemExit("❌ Missing ENV: TELEGRAM_BOT_TOKEN")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# =======================
# STATE (in-memory)
# =======================
STATE = {}  # chat_id -> dict(game, mode, profile, memory)
MEM_TURNS = 6

def st(chat_id: int) -> dict:
    return STATE.setdefault(chat_id, {
        "game": "warzone",
        "mode": "menu",   # menu | coach
        "profile": {"platform": "", "style": "", "goal": ""},
        "memory": []      # [{"role": "user"/"assistant", "content": "..."}]
    })

# =======================
# CONTENT (быстрая база без ИИ)
# =======================
KB = {
    "warzone": {
        "name": "Warzone",
        "settings": "🎮 Warzone — настройки\n• Sens: 7/7 (мимо → 6/6)\n• ADS: 0.90\n• FOV: 105–110\n• Deadzone min: 0.05",
        "drills": "💪 Warzone — дриллы\n🎯 Aim: 10м warmup + 5м трекинг + 5м микро\n🔫 Recoil: 5м ближ + 10м средн + 5м дисциплина\n🕹 Movement: углы → пик → откат",
        "plan": "📅 Warzone — план 7 дней\nД1–2: aim 15м + movement 10м\nД3–4: дуэли/углы 15м + дисциплина\nД5–6: игра от инфо 20м + ошибки\nД7: 45–60м + разбор 2 смертей",
        "vod": "📼 Warzone VOD-шаблон\n1) Режим (solo/duo...)\n2) Где бой (дом/крыша/поле)\n3) Что видел по инфо\n4) Чем умер\n5) Что хотел сделать\n\nНапиши это — дам 1 ошибку + 2 действия + дрилл."
    },
    "bf6": {
        "name": "BF6",
        "settings": "🎮 BF6 — настройки\n• Sens средняя, ADS чуть ниже\n• Deadzone минимальная без дрифта\n• FOV высокий (комфорт)\n• После контакта — смена позиции",
        "drills": "💪 BF6 — дриллы\n🎯 Aim: префайр углов + трекинг\n🔫 Recoil: короткие очереди\n🕹 Movement: выглянул → дал инфо → откат",
        "plan": "📅 BF6 — план 7 дней\nД1–2: aim 15м + позиции\nД3–4: спавны/линии фронта\nД5–6: игра от инфо\nД7: 45–60м + разбор 2 смертей",
        "vod": "📼 BF6 VOD-шаблон\nКарта/режим, класс, где умер, почему, что хотел сделать."
    },
    "bo7": {
        "name": "BO7",
        "settings": "🎮 BO7 — настройки\n• Sens: 6–8 (перелёт → -1)\n• ADS: 0.80–0.95\n• Deadzone: 0.03–0.07\n• Curve: Dynamic/Standard\n• FOV: 100–115\n\n🔥 Правило: килл → репозиция 1–2 сек",
        "drills": "💪 BO7 — дриллы\n🎯 Aim (20м): 5м префайр + 7м трекинг + 5м микро + 3м дисциплина\n🕹 Movement: репики с другого угла\n🔫 Recoil: короткие очереди, контроль первой пули",
        "plan": "📅 BO7 — план 7 дней\nД1–2: aim 20м + movement 10м\nД3–4: углы/тайминги\nД5–6: дуэли (репики)\nД7: 45–60м + разбор 2–3 смертей",
        "vod": "📼 BO7 VOD-шаблон\nРежим/карта, оружие/роль, момент смерти, что видел по радару/звуку."
    }
}

SYSTEM_PROMPT = (
    "Ты киберспортивный коуч по FPS (Warzone/BF6/BO7). "
    "Отвечай по-русски, коротко, структурно. "
    "Всегда: 1 ключевая ошибка + 1–2 действия + мини-дрилл. "
    "Никаких читов/аимботов/обходов античита."
)

# =======================
# Telegram helpers
# =======================
def tg_post(method: str, payload: dict):
    r = requests.post(f"{TG_API}/{method}", json=payload, timeout=20)
    return r.json()

def tg_get(method: str, params: dict):
    r = requests.get(f"{TG_API}/{method}", params=params, timeout=35)
    return r.json()

def send(chat_id: int, text: str, kb=None):
    # chunk to avoid 4096 limit
    chunks = [text[i:i+3900] for i in range(0, len(text), 3900)] or [""]
    for ch in chunks:
        tg_post("sendMessage", {"chat_id": chat_id, "text": ch, "reply_markup": kb})

def edit(chat_id: int, msg_id: int, text: str, kb=None):
    tg_post("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": text, "reply_markup": kb})

def answer_cb(cb_id: str):
    tg_post("answerCallbackQuery", {"callback_query_id": cb_id})

# =======================
# Keyboards
# =======================
def kb_main(chat_id: int):
    game = st(chat_id)["game"]
    title = f"✅ {KB[game]['name']}"
    return {
        "inline_keyboard": [
            [
                {"text": "🎮 Warzone", "callback_data": "game:warzone"},
                {"text": "🎮 BF6", "callback_data": "game:bf6"},
                {"text": "🎮 BO7", "callback_data": "game:bo7"},
            ],
            [
                {"text": "⚙ Settings", "callback_data": "show:settings"},
                {"text": "💪 Drills", "callback_data": "show:drills"},
                {"text": "📅 Plan", "callback_data": "show:plan"},
            ],
            [
                {"text": "📼 VOD", "callback_data": "show:vod"},
                {"text": "👤 Profile", "callback_data": "show:profile"},
                {"text": "🧠 Coach", "callback_data": "mode:coach"},
            ],
            [
                {"text": f"Текущая игра: {title}", "callback_data": "noop"},
                {"text": "🧹 Reset", "callback_data": "reset"},
            ]
        ]
    }

def menu_text(chat_id: int) -> str:
    s = st(chat_id)
    g = s["game"]
    p = s["profile"]
    return (
        "🧠 FPS Coach Bot\n"
        f"Текущая игра: {KB[g]['name']}\n"
        f"Режим: {'🧠 Coach' if s['mode']=='coach' else '📋 Menu'}\n\n"
        "Профиль (для точных советов):\n"
        f"• Platform: {p['platform'] or '—'}\n"
        f"• Style: {p['style'] or '—'}\n"
        f"• Goal: {p['goal'] or '—'}\n\n"
        "Нажми кнопки ниже 👇"
    )

# =======================
# Profile parsing
# =======================
def parse_profile(text: str):
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
    if "aim" in t or "аим" in t or "прицел" in t:
        goal = "Aim"
    elif "recoil" in t or "отдач" in t:
        goal = "Recoil"
    elif "movement" in t or "мува" in t or "движ" in t:
        goal = "Movement"
    elif "rank" in t or "ранг" in t:
        goal = "Rank"

    return platform, style, goal

def profile_text(chat_id: int) -> str:
    p = st(chat_id)["profile"]
    return (
        "👤 Профиль\n"
        "Напиши одним сообщением: платформа, стиль, цель\n"
        "Пример: `KBM, Aggressive, Aim`\n\n"
        f"Сейчас:\n• Platform: {p['platform'] or '—'}\n• Style: {p['style'] or '—'}\n• Goal: {p['goal'] or '—'}"
    )

# =======================
# AI (optional)
# =======================
_openai_client = None
def openai_client():
    global _openai_client
    if not OPENAI_AVAILABLE or not OPENAI_KEY:
        return None
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_KEY)
    return _openai_client

def mem_add(chat_id: int, role: str, content: str):
    m = st(chat_id)["memory"]
    m.append({"role": role, "content": content})
    if len(m) > MEM_TURNS * 2:
        st(chat_id)["memory"] = m[-MEM_TURNS*2:]

def coach_reply(chat_id: int, user_text: str) -> str:
    s = st(chat_id)
    game = s["game"]
    p = s["profile"]

    # Если ИИ нет — даём “умный шаблон” без падений
    if not openai_client():
        return (
            f"⚠️ AI сейчас выключен (нет OPENAI_API_KEY).\n\n"
            f"Игра: {KB[game]['name']}\n"
            "Скажи:\n"
            "1) режим/карта\n2) как умер\n3) что хотел сделать\n\n"
            "Я дам: 1 ошибку + 2 действия + дрилл.\n"
            "Или включи OPENAI_API_KEY — будет умнее."
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Текущая игра: {KB[game]['name']}"},
        {"role": "system", "content": f"Профиль: {json.dumps(p, ensure_ascii=False)}"},
    ]
    messages.extend(s["memory"])
    messages.append({"role": "user", "content": user_text})

    try:
        resp = openai_client().chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_completion_tokens=450
        )
        out = (resp.choices[0].message.content or "").strip()
        return out or "Не получил ответ. Повтори вопрос 🙌"
    except Exception as e:
        return f"⚠️ AI ошибка: {type(e).__name__}. Попробуй ещё раз или переключись в Menu."

# =======================
# Handlers
# =======================
def on_start(chat_id: int):
    st(chat_id)  # init
    send(chat_id, menu_text(chat_id), kb_main(chat_id))

def on_text(chat_id: int, text: str):
    s = st(chat_id)

    # команды
    if text.startswith("/start"):
        return on_start(chat_id)
    if text.startswith("/menu"):
        s["mode"] = "menu"
        return send(chat_id, menu_text(chat_id), kb_main(chat_id))
    if text.startswith("/reset"):
        STATE.pop(chat_id, None)
        st(chat_id)
        return send(chat_id, "🧹 Сбросил всё.", kb_main(chat_id))

    # профиль (одной строкой)
    platform, style, goal = parse_profile(text)
    if platform or style or goal:
        if platform: s["profile"]["platform"] = platform
        if style: s["profile"]["style"] = style
        if goal: s["profile"]["goal"] = goal
        return send(chat_id, "✅ Профиль обновлён.\n\n" + profile_text(chat_id), kb_main(chat_id))

    # режим coach: любой обычный текст -> AI
    if s["mode"] == "coach":
        mem_add(chat_id, "user", text)
        ans = coach_reply(chat_id, text)
        mem_add(chat_id, "assistant", ans)
        return send(chat_id, ans, kb_main(chat_id))

    # режим menu: подсказываем как пользоваться
    send(chat_id, "Нажимай кнопки 👇 или включи 🧠 Coach и задавай вопросы текстом.", kb_main(chat_id))

def on_callback(cb: dict):
    cb_id = cb["id"]
    msg = cb.get("message", {})
    chat_id = (msg.get("chat") or {}).get("id")
    msg_id = msg.get("message_id")
    data = cb.get("data", "")

    try:
        if not chat_id or not msg_id:
            return

        s = st(chat_id)

        if data == "noop":
            return

        if data == "reset":
            STATE.pop(chat_id, None)
            st(chat_id)
            return edit(chat_id, msg_id, "🧹 Сбросил всё.", kb_main(chat_id))

        if data.startswith("game:"):
            g = data.split(":", 1)[1]
            if g in KB:
                s["game"] = g
            return edit(chat_id, msg_id, menu_text(chat_id), kb_main(chat_id))

        if data.startswith("show:"):
            what = data.split(":", 1)[1]
            g = s["game"]
            if what == "profile":
                return edit(chat_id, msg_id, profile_text(chat_id), kb_main(chat_id))
            if what in ("settings", "drills", "plan", "vod"):
                return edit(chat_id, msg_id, KB[g][what], kb_main(chat_id))

        if data.startswith("mode:"):
            mode = data.split(":", 1)[1]
            if mode == "coach":
                s["mode"] = "coach"
                txt = (
                    "🧠 Coach включён.\n"
                    "Теперь просто пиши вопрос текстом.\n\n"
                    "Пример: «Какое оружие в мете?» или «Почему я проигрываю дуэли?»\n"
                    "Чтобы вернуться: /menu"
                )
                return edit(chat_id, msg_id, txt, kb_main(chat_id))

    finally:
        answer_cb(cb_id)

# =======================
# Telegram loop (long polling)
# =======================
def bot_loop():
    print("🤖 Bot loop started")
    offset = 0
    while True:
        try:
            upd = tg_get("getUpdates", {"timeout": 30, "offset": offset})
            for u in upd.get("result", []):
                offset = u["update_id"] + 1
                if "callback_query" in u:
                    on_callback(u["callback_query"])
                else:
                    msg = u.get("message") or u.get("edited_message") or {}
                    text = (msg.get("text") or "").strip()
                    chat_id = (msg.get("chat") or {}).get("id")
                    if chat_id and text:
                        on_text(chat_id, text)
        except Exception as e:
            print("Loop error:", repr(e))
            time.sleep(3)

# =======================
# HTTP server for Render healthcheck
# =======================
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")

def run_http():
    port = int(os.getenv("PORT", "10000"))
    print(f"🌐 HTTP on :{port}")
    HTTPServer(("0.0.0.0", port), Health).serve_forever()

# =======================
# START
# =======================
if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    run_http()
