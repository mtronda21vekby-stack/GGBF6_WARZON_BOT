import os
import time
import json
import threading
import logging
import random
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
from openai import OpenAI
from openai import APIConnectionError, AuthenticationError, RateLimitError, BadRequestError, APIError


# =========================
# Logging
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("bot")


# =========================
# ENV
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

HTTP_TIMEOUT = 25
TG_LONGPOLL_TIMEOUT = 50
TG_RETRIES = 5

# анимация: не чаще 1.2 сек, чтобы Telegram не ругался
PULSE_MIN_SECONDS = 1.20

# backoff на конфликт getUpdates (если 2 инстанса или webhook)
CONFLICT_BACKOFF_MIN = 12
CONFLICT_BACKOFF_MAX = 30

# лёгкий троттлинг на чат
MIN_SECONDS_BETWEEN_MSG = 0.25

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("Missing ENV: TELEGRAM_BOT_TOKEN")


# =========================
# OpenAI client
# =========================
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=30,
            max_retries=0,
        )
    except TypeError:
        openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


# =========================
# Requests session
# =========================
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "render-telegram-bot/night/3.1"})
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20))


# =========================
# In-memory storage
# =========================
USER_PROFILE = {}
USER_MEMORY = {}
MEMORY_MAX_TURNS = 10

LAST_MSG_TS = {}
POLLING_STARTED = False


# =========================
# Knowledge base
# =========================
GAME_KB = {
    "warzone": {
        "name": "Call of Duty: Warzone",
        "settings": (
            "🌑 Warzone — быстрый сетап (контроллер)\n"
            "• Sens: 7/7 (мимо → 6/6)\n"
            "• ADS: 0.90 low / 0.85 high\n"
            "• Aim Assist: Dynamic (если не заходит → Standard)\n"
            "• Deadzone min: 0.05 (дрифт → 0.07–0.10)\n"
            "• FOV: 105–110 | ADS FOV Affected: ON | Weapon FOV: Wide\n"
            "• Camera Movement: Least\n"
        ),
        "pillars": (
            "🧠 Warzone — фундамент\n"
            "• Позиция/тайминг важнее киллов\n"
            "• Инфо: радар/звук/пинги\n"
            "• Пре-эйм и игра от укрытий\n"
            "• Ротации: заранее\n"
            "• После контакта — репозиция\n"
        ),
        "drills": {
            "aim": "🎯 Aim (20м)\n10м warm-up\n5м трекинг\n5м микро-коррекции",
            "recoil": "🔫 Recoil (20м)\n5м 15–25м\n10м 25–40м\n5м дисциплина",
            "movement": "🕹 Movement (15м)\nугол→слайд→пик\nджамп-пики\nрепозиция",
        },
        "plan": (
            "📅 План на 7 дней — Warzone\n"
            "Д1–2: warm-up 10м + aim 15м + movement 10м + мини-разбор 5м\n"
            "Д3–4: warm-up 10м + дуэли/углы 15м + дисциплина 10м + вывод 5м\n"
            "Д5–6: warm-up 10м + игра от инфо 20м + фиксация ошибок 5м\n"
            "Д7: 30–60м игры + разбор 2 смертей 10м\n"
        ),
        "vod": (
            "📼 VOD/ситуация (Warzone)\n"
            "1) Режим/сквад\n2) Где бой\n3) Как умер\n"
            "4) Ресурсы (плиты/смок/саморез)\n5) План (пуш/отход/ротация)\n"
        ),
    },
    "bf6": {
        "name": "BF6",
        "settings": (
            "🌑 BF6 — база\n"
            "• Sens: средняя, ADS ниже\n"
            "• Deadzone: минимум без дрифта\n"
            "• FOV: высокий (комфорт)\n"
            "• После контакта — смена позиции\n"
        ),
        "pillars": (
            "🧠 BF6 — фундамент\n"
            "• линии фронта/спавны\n"
            "• пик→инфо→откат\n"
            "• серия → репозиция\n"
        ),
        "drills": {
            "aim": "🎯 Aim (15–20м)\nпрефайр\nтрекинг\nрепозиция",
            "movement": "🕹 Movement (15м)\nвыглянул→инфо→откат\nрепик с другого угла",
            "recoil": "🔫 Recoil (15м)\nкороткие очереди\nконтроль",
        },
        "plan": (
            "📅 План на 7 дней — BF6\n"
            "Д1–2: aim 15м + позиции 15м\n"
            "Д3–4: фронт/спавны 20м + дуэли 10м\n"
            "Д5–6: игра от инфо 25м + разбор 5м\n"
            "Д7: 45–60м + разбор 2 смертей\n"
        ),
        "vod": "📼 BF6: карта/режим, класс, где умер/почему, что хотел сделать.",
    },
    "bo7": {
        "name": "Call of Duty: BO7",
        "settings": (
            "🌑 BO7 — базовый сетап (контроллер)\n"
            "• Sens: 6–8 (перелетаешь → -1)\n"
            "• ADS: 0.80–0.95\n"
            "• Deadzone min: 0.03–0.07\n"
            "• Curve: Dynamic/Standard\n"
            "• FOV: 100–115\n"
        ),
        "pillars": (
            "🧠 BO7 — фундамент\n"
            "• центр экрана + префайр\n"
            "• тайминги\n"
            "• 2 сек на позиции → смена\n"
        ),
        "drills": {
            "aim": "🎯 Aim (20м)\nпрефайр\nтрекинг\nмикро",
            "movement": "🕹 Movement (15–20м)\nрепики\nтайминг\nстрейф",
            "recoil": "🔫 Recoil (15м)\nкороткие очереди\nпервая пуля",
        },
        "plan": (
            "📅 План на 7 дней — BO7\n"
            "Д1–2: aim 20м + movement 10м\n"
            "Д3–4: углы/тайминги 25м + мини-разбор 5м\n"
            "Д5–6: дуэли 30м\n"
            "Д7: 45–60м + разбор 2–3 смертей\n"
        ),
        "vod": "📼 BO7: режим/карта, смерть, инфо (радар/звук), что хотел сделать.",
    },
}


# =========================
# Persona
# =========================
SYSTEM_PROMPT = (
    "Ты харизматичный FPS-коуч по Warzone/BF6/BO7. Пишешь по-русски.\n"
    "Тон: уверенный, быстрый, с юмором и лёгкими подколами (без токсичности).\n"
    "Запрещено: читы/хаки/обход античита/эксплойты.\n\n"
    "Формат ответа ВСЕГДА:\n"
    "1) 🎯 Диагноз (1 главная ошибка)\n"
    "2) ✅ Что делать (2 действия прямо сейчас)\n"
    "3) 🧪 Дрилл (5–10 минут)\n"
    "4) 😈 Панчик/мотивация (1 строка)\n"
    "Если данных мало — задай 1 вопрос в конце."
)

PERSONA_HINT = {
    "spicy": "Стиль: дерзко и смешно, но без оскорблений.",
    "chill": "Стиль: спокойный, дружелюбный, мягкий юмор.",
    "pro": "Стиль: строго по делу, минимум шуток.",
}

VERBOSITY_HINT = {
    "short": "Длина: коротко.",
    "normal": "Длина: обычно.",
    "talkative": "Длина: подробнее + 1–2 доп. совета.",
}

THINKING_LINES = [
    "🧠 Думаю… сейчас будет жара 😈",
    "⌛ Секунду… раскладываю по полочкам 🧩",
    "🎮 Окей, коуч на связи. Сейчас разнесём 👊",
    "🌑 Анализирую… не моргай 😈",
]


# =========================
# Telegram API
# =========================
def _sleep_backoff(i: int):
    time.sleep((0.6 * (i + 1)) + random.random() * 0.25)

def tg_request(method: str, *, params=None, payload=None, is_post=False, retries=TG_RETRIES):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    last = None

    for i in range(retries):
        try:
            if is_post:
                r = SESSION.post(url, json=payload, timeout=HTTP_TIMEOUT)
            else:
                r = SESSION.get(url, params=params, timeout=HTTP_TIMEOUT)

            try:
                data = r.json()
            except Exception:
                raise RuntimeError(f"Telegram non-JSON (HTTP {r.status_code}): {r.text[:200]}")

            if r.status_code == 200 and data.get("ok"):
                return data

            last = RuntimeError(data.get("description", f"Telegram HTTP {r.status_code}"))

        except Exception as e:
            last = e

        _sleep_backoff(i)

    raise last

def send_message(chat_id: int, text: str, reply_markup=None):
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [""]
    last_msg_id = None
    for ch in chunks:
        res = tg_request(
            "sendMessage",
            payload={"chat_id": chat_id, "text": ch, "reply_markup": reply_markup},
            is_post=True
        )
        last_msg_id = res.get("result", {}).get("message_id")
    return last_msg_id

def edit_message(chat_id: int, message_id: int, text: str, reply_markup=None):
    tg_request(
        "editMessageText",
        payload={"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": reply_markup},
        is_post=True
    )

def answer_callback(callback_id: str):
    try:
        tg_request("answerCallbackQuery", payload={"callback_query_id": callback_id}, is_post=True, retries=2)
    except Exception:
        pass

def send_chat_action(chat_id: int, action: str = "typing"):
    try:
        tg_request("sendChatAction", payload={"chat_id": chat_id, "action": action}, is_post=True, retries=2)
    except Exception:
        pass

def delete_webhook_on_start():
    # КРИТИЧНО: если был webhook, getUpdates может конфликтовать.
    try:
        tg_request("deleteWebhook", payload={"drop_pending_updates": True}, is_post=True, retries=3)
        log.info("Webhook deleted (drop_pending_updates=true)")
    except Exception as e:
        log.warning("Could not delete webhook: %r", e)


# =========================
# Animation (safe)
# =========================
def typing_loop(chat_id: int, stop_event: threading.Event, interval: float = 4.0):
    while not stop_event.is_set():
        send_chat_action(chat_id, "typing")
        stop_event.wait(interval)

def pulse_edit_loop(chat_id: int, message_id: int, stop_event: threading.Event, base: str = "⌛ Думаю"):
    dots = 0
    last_edit = 0.0
    while not stop_event.is_set():
        now = time.time()
        if now - last_edit >= PULSE_MIN_SECONDS:
            dots = (dots + 1) % 4
            try:
                edit_message(chat_id, message_id, base + ("." * dots), reply_markup=None)
            except Exception:
                pass
            last_edit = now
        stop_event.wait(0.2)

def quick_loading_edit(chat_id: int, message_id: int, text: str = "⌛ Загружаю…"):
    try:
        edit_message(chat_id, message_id, text, reply_markup=None)
    except Exception:
        pass


# =========================
# Profile / memory
# =========================
def ensure_profile(chat_id: int) -> dict:
    default_coach = bool(OPENAI_API_KEY)
    return USER_PROFILE.setdefault(chat_id, {
        "game": "warzone",
        "platform": "",
        "style": "",
        "goal": "",
        "coach": default_coach,
        "persona": "spicy",
        "verbosity": "normal",
        "ui": "show",
    })

def update_memory(chat_id: int, role: str, content: str):
    mem = USER_MEMORY.setdefault(chat_id, [])
    mem.append({"role": role, "content": content})
    if len(mem) > MEMORY_MAX_TURNS * 2:
        USER_MEMORY[chat_id] = mem[-MEMORY_MAX_TURNS * 2:]

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

def profile_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "👤 Профиль\n"
        f"Игра: {GAME_KB[p['game']]['name']}\n"
        f"Платформа: {p.get('platform') or '—'}\n"
        f"Стиль: {p.get('style') or '—'}\n"
        f"Цель: {p.get('goal') or '—'}\n"
        f"Coach: {'ON' if p.get('coach') else 'OFF'}\n"
        f"Persona: {p.get('persona','spicy')}\n"
        f"Talk: {p.get('verbosity','normal')}\n"
        f"UI: {p.get('ui','show')}\n\n"
        "Команды:\n"
        "/persona spicy|chill|pro\n"
        "/talk short|normal|talkative\n"
        "/ui show|hide\n"
    )


# =========================
# Keyboards
# =========================
def kb_main(chat_id: int):
    p = ensure_profile(chat_id)
    coach_on = "🧠 ON" if p.get("coach", True) else "🧠 OFF"
    ui = p.get("ui", "show")
    ui_btn = "🕶 Hide UI" if ui == "show" else "🕶 Show UI"

    return {
        "inline_keyboard": [
            [{"text": "🌑 Warzone", "callback_data": "game:warzone"},
             {"text": "🌑 BF6", "callback_data": "game:bf6"},
             {"text": "🌑 BO7", "callback_data": "game:bo7"}],
            [{"text": "⚙️ Settings", "callback_data": "action:settings"},
             {"text": "💪 Drills", "callback_data": "action:drills"}],
            [{"text": "📅 Plan", "callback_data": "action:plan"},
             {"text": "📼 VOD", "callback_data": "action:vod"}],
            [{"text": "👤 Profile", "callback_data": "action:profile"},
             {"text": coach_on, "callback_data": "action:coach"}],
            [{"text": "😈 Persona", "callback_data": "action:persona"},
             {"text": "🗣 Talk", "callback_data": "action:talk"}],
            [{"text": ui_btn, "callback_data": "action:ui"}],
            [{"text": "🧹 Reset", "callback_data": "action:reset"}],
        ]
    }

def kb_drills(chat_id: int):
    p = ensure_profile(chat_id)
    if p.get("ui") == "hide":
        return None
    return {
        "inline_keyboard": [
            [{"text": "🎯 Aim", "callback_data": "drill:aim"},
             {"text": "🔫 Recoil", "callback_data": "drill:recoil"},
             {"text": "🕹 Movement", "callback_data": "drill:movement"}],
            [{"text": "⬅️ Menu", "callback_data": "action:menu"}],
        ]
    }

def maybe_kb(chat_id: int):
    p = ensure_profile(chat_id)
    return None if p.get("ui", "show") == "hide" else kb_main(chat_id)


# =========================
# OpenAI (compat: max_tokens / max_completion_tokens)
# =========================
def _openai_create(messages, max_tokens: int):
    # В разных версиях SDK разные имена параметра — делаем совместимость.
    try:
        return openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_completion_tokens=max_tokens,
        )
    except TypeError:
        return openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=max_tokens,
        )

def openai_reply_safe(chat_id: int, user_text: str) -> str:
    if not OPENAI_API_KEY or openai_client is None:
        return "⚠️ AI выключен: нет OPENAI_API_KEY (Render → Environment Variables → add → Redeploy)."

    p = ensure_profile(chat_id)
    kb = GAME_KB[p["game"]]
    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")

    coach_frame = (
        "Пиши конкретно и полезно. Если инфы мало — спроси 1 вопрос.\n"
        "Не придумывай патчи/мету. Если не уверен — общие принципы.\n"
        "Фокус: позиция, тайминг, инфо, дисциплина, микромув, отдача.\n"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": coach_frame},
        {"role": "system", "content": PERSONA_HINT.get(persona, PERSONA_HINT["spicy"])},
        {"role": "system", "content": VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"])},
        {"role": "system", "content": f"Текущая игра: {kb['name']}. {kb.get('pillars','')}"},
        {"role": "system", "content": f"Профиль: {json.dumps(p, ensure_ascii=False)}"},
    ]
    messages.extend(USER_MEMORY.get(chat_id, []))
    messages.append({"role": "user", "content": user_text})

    max_out = 650 if verbosity == "talkative" else 520

    for attempt in range(2):
        try:
            resp = _openai_create(messages, max_out)
            out = (resp.choices[0].message.content or "").strip()
            return out or "Не получил ответ. Напиши ещё раз 🙌"

        except APIConnectionError:
            if attempt == 0:
                time.sleep(0.9)
                continue
            return "⚠️ AI: проблема соединения. Попробуй ещё раз через минуту."
        except AuthenticationError:
            return "❌ AI: неверный ключ OPENAI_API_KEY. Проверь Render → Env → Redeploy."
        except RateLimitError:
            return "⏳ AI: лимит/перегруз. Подожди 20–60 сек и попробуй снова."
        except BadRequestError:
            return f"❌ AI: bad request. Модель: {OPENAI_MODEL}."
        except APIError:
            return "⚠️ AI: временная ошибка сервиса. Попробуй ещё раз через минуту."
        except Exception:
            log.exception("OpenAI unknown error")
            return "⚠️ AI: неизвестная ошибка. Напиши /status — посмотрим конфиг."


# =========================
# Misc
# =========================
def status_text() -> str:
    ok_key = "✅" if bool(OPENAI_API_KEY) else "❌"
    ok_tg = "✅" if bool(TELEGRAM_BOT_TOKEN) else "❌"
    return (
        "🧾 Status\n"
        f"TELEGRAM_BOT_TOKEN: {ok_tg}\n"
        f"OPENAI_API_KEY: {ok_key}\n"
        f"OPENAI_BASE_URL: {OPENAI_BASE_URL}\n"
        f"OPENAI_MODEL: {OPENAI_MODEL}\n\n"
        "Если ловишь Conflict 409 — значит 2 инстанса или webhook. Код вебхук снимает сам.\n"
    )

def render_menu_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "🌑 FPS Coach Bot\n"
        f"Игра: {GAME_KB[p['game']]['name']}\n"
        f"Coach: {'ON' if p.get('coach') else 'OFF'} | Persona: {p.get('persona')} | Talk: {p.get('verbosity')} | UI: {p.get('ui')}\n"
        "Жми кнопки 👇"
    )

def set_game(chat_id: int, game_key: str) -> str:
    p = ensure_profile(chat_id)
    if game_key not in GAME_KB:
        return "Не знаю такую игру."
    p["game"] = game_key
    return f"✅ Игра: {GAME_KB[game_key]['name']}"

def throttle(chat_id: int) -> bool:
    now = time.time()
    last = LAST_MSG_TS.get(chat_id, 0.0)
    if now - last < MIN_SECONDS_BETWEEN_MSG:
        return True
    LAST_MSG_TS[chat_id] = now
    return False


# =========================
# Handlers
# =========================
def handle_message(chat_id: int, text: str):
    if throttle(chat_id):
        return

    p = ensure_profile(chat_id)
    low = text.lower().strip()

    if text.startswith("/start") or text.startswith("/menu"):
        send_message(chat_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/status"):
        send_message(chat_id, status_text(), reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/profile"):
        send_message(chat_id, profile_text(chat_id), reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/reset"):
        USER_PROFILE.pop(chat_id, None)
        USER_MEMORY.pop(chat_id, None)
        ensure_profile(chat_id)
        send_message(chat_id, "🧹 Сбросил профиль и память.", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/persona"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].lower() in ("spicy", "chill", "pro"):
            p["persona"] = parts[1].lower()
            send_message(chat_id, f"✅ Persona = {p['persona']}", reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "Используй: /persona spicy | chill | pro", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/talk"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].lower() in ("short", "normal", "talkative"):
            p["verbosity"] = parts[1].lower()
            send_message(chat_id, f"✅ Talk = {p['verbosity']}", reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "Используй: /talk short | normal | talkative", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/ui"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].lower() in ("show", "hide"):
            p["ui"] = parts[1].lower()
            send_message(chat_id, f"✅ UI = {p['ui']}", reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "Используй: /ui show | /ui hide", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/game"):
        parts = text.split()
        if len(parts) >= 2:
            send_message(chat_id, set_game(chat_id, parts[1].lower()), reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "Используй: /game warzone | bf6 | bo7", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/settings"):
        send_message(chat_id, GAME_KB[p["game"]]["settings"], reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/plan"):
        send_message(chat_id, GAME_KB[p["game"]]["plan"], reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/vod"):
        send_message(chat_id, GAME_KB[p["game"]]["vod"], reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/drills"):
        send_message(chat_id, "Выбери дрилл:", reply_markup=kb_drills(chat_id))
        return

    if low in ("привет", "хай", "yo", "здарова", "hello", "ку"):
        send_message(chat_id, "Йо 😈 Выбирай игру и погнали. Я тут не для ласки — я для побед.", reply_markup=maybe_kb(chat_id))
        return

    platform, style, goal = parse_profile_line(text)
    if platform or style or goal:
        if platform:
            p["platform"] = platform
        if style:
            p["style"] = style
        if goal:
            p["goal"] = goal
        send_message(chat_id, "✅ Профиль обновлён.\n\n" + profile_text(chat_id), reply_markup=maybe_kb(chat_id))
        return

    if not p.get("coach", True):
        send_message(chat_id, "🧠 Coach OFF. Включи в меню.", reply_markup=maybe_kb(chat_id))
        return

    # AI + анимация
    update_memory(chat_id, "user", text)

    tmp_id = send_message(chat_id, random.choice(THINKING_LINES), reply_markup=None)

    stop = threading.Event()
    threading.Thread(target=typing_loop, args=(chat_id, stop), daemon=True).start()
    if tmp_id:
        threading.Thread(target=pulse_edit_loop, args=(chat_id, tmp_id, stop, "⌛ Думаю"), daemon=True).start()

    try:
        reply = openai_reply_safe(chat_id, text)
    finally:
        stop.set()

    update_memory(chat_id, "assistant", reply)

    if tmp_id:
        try:
            edit_message(chat_id, tmp_id, reply, reply_markup=maybe_kb(chat_id))
        except Exception:
            send_message(chat_id, reply, reply_markup=maybe_kb(chat_id))
    else:
        send_message(chat_id, reply, reply_markup=maybe_kb(chat_id))


def handle_callback(cb: dict):
    cb_id = cb["id"]
    msg = cb.get("message", {})
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = cb.get("data", "")

    if not chat_id or not message_id:
        answer_callback(cb_id)
        return

    try:
        p = ensure_profile(chat_id)
        quick_loading_edit(chat_id, message_id, "⌛ Загружаю…")

        if data == "action:menu":
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data.startswith("game:"):
            game = data.split(":", 1)[1]
            set_game(chat_id, game)
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:settings":
            edit_message(chat_id, message_id, GAME_KB[p["game"]]["settings"], reply_markup=maybe_kb(chat_id))

        elif data == "action:plan":
            edit_message(chat_id, message_id, GAME_KB[p["game"]]["plan"], reply_markup=maybe_kb(chat_id))

        elif data == "action:vod":
            edit_message(chat_id, message_id, GAME_KB[p["game"]]["vod"], reply_markup=maybe_kb(chat_id))

        elif data == "action:profile":
            edit_message(chat_id, message_id, profile_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:coach":
            p["coach"] = not p.get("coach", True)
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:persona":
            cur = p.get("persona", "spicy")
            p["persona"] = {"spicy": "chill", "chill": "pro", "pro": "spicy"}.get(cur, "spicy")
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:talk":
            cur = p.get("verbosity", "normal")
            p["verbosity"] = {"short": "normal", "normal": "talkative", "talkative": "short"}.get(cur, "normal")
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:ui":
            p["ui"] = "hide" if p.get("ui", "show") == "show" else "show"
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:reset":
            USER_PROFILE.pop(chat_id, None)
            USER_MEMORY.pop(chat_id, None)
            ensure_profile(chat_id)
            edit_message(chat_id, message_id, "🧹 Сбросил профиль и память.", reply_markup=maybe_kb(chat_id))

        elif data == "action:drills":
            edit_message(chat_id, message_id, "Выбери дрилл:", reply_markup=kb_drills(chat_id))

        elif data.startswith("drill:"):
            kind = data.split(":", 1)[1]
            drills = GAME_KB[p["game"]]["drills"]
            edit_message(chat_id, message_id, drills.get(kind, "Доступно: aim/recoil/movement"), reply_markup=kb_drills(chat_id))

        else:
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

    finally:
        answer_callback(cb_id)


# =========================
# Polling loop (hardened)
# =========================
def run_telegram_bot():
    global POLLING_STARTED
    if POLLING_STARTED:
        log.warning("Polling already started. Skip.")
        return
    POLLING_STARTED = True

    delete_webhook_on_start()

    log.info("Telegram bot started (long polling)")
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
                except Exception:
                    log.exception("Message handling error")
                    send_message(chat_id, "Ошибка 😅 Попробуй ещё раз.", reply_markup=maybe_kb(chat_id))

        except RuntimeError as e:
            s = str(e)
            if "Conflict:" in s and "getUpdates" in s:
                sleep_s = random.randint(CONFLICT_BACKOFF_MIN, CONFLICT_BACKOFF_MAX)
                log.warning("Telegram conflict. Backoff %ss: %s", sleep_s, s)
                time.sleep(sleep_s)
                continue
            log.warning("Loop RuntimeError: %r", e)
            time.sleep(2)

        except Exception as e:
            log.warning("Loop error: %r", e)
            time.sleep(2)


# =========================
# Health endpoint
# =========================
class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _ok(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()

    def do_HEAD(self):
        if self.path in ("/", "/healthz"):
            self._ok()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/healthz"):
            self._ok()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()


def run_http_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    log.info("HTTP server listening on :%s", port)
    server.serve_forever()


if __name__ == "__main__":
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    run_http_server()
