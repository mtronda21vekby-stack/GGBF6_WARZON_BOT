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

# как часто можно дергать editMessageText (анимация)
PULSE_MIN_SECONDS = 1.05

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("Missing ENV: TELEGRAM_BOT_TOKEN (BotFather token)")

# OpenAI client (таймаут + меньше шанс зависнуть)
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=30,
            max_retries=1,  # мы сами делаем retry
        )
    except TypeError:
        openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


# =========================
# Requests session (faster + stabler)
# =========================
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "render-telegram-bot/night/3.0"})
SESSION.adapters["https://"] = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)


# =========================
# Data (in-memory)
# =========================
USER_PROFILE = {}  # chat_id -> dict
USER_MEMORY = {}   # chat_id -> list[{role, content}]
MEMORY_MAX_TURNS = 10

LAST_MSG_TS = {}   # chat_id -> float
MIN_SECONDS_BETWEEN_MSG = 0.25  # чуть быстрее

# если Telegram конфликтует (2 инстанса) — делаем спокойный backoff
CONFLICT_BACKOFF_MIN = 10
CONFLICT_BACKOFF_MAX = 30

# Глобальная защита от двойного запуска polling внутри одного процесса
POLLING_STARTED = False


# =========================
# Knowledge base (расширенная структура)
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
            "• Ротации: не поздно, а заранее\n"
            "• После контакта — репозиция\n"
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
            "📼 VOD/ситуация (Warzone)\n"
            "1) Режим/сквад\n2) Где бой\n3) Как умер\n4) Ресурсы (плиты/смок/саморез)\n"
            "5) План (пуш/отход/ротация)\n\n"
            "Я верну: 1 ошибка + 2 действия + дрилл 💪"
        ),
    },
    "bf6": {
        "name": "BF6",
        "settings": (
            "🌑 BF6 — база сетапа\n"
            "• Sens: средняя, ADS чуть ниже\n"
            "• Deadzone: минимум без дрифта\n"
            "• FOV: высокий (комфорт)\n"
            "• После контакта — смена позиции\n"
        ),
        "pillars": (
            "🧠 BF6 — фундамент\n"
            "• Линии фронта и спавн-логика\n"
            "• Игра от укрытий и углов\n"
            "• Короткий пик → инфо → откат\n"
            "• Смена позиции после серии\n"
        ),
        "drills": {
            "aim": "🎯 BF6 Aim (15–20м)\nпрефайр\nтрекинг\nпосле серии — смена позиции",
            "movement": "🕹 BF6 Movement (15м)\nвыглянул→инфо→откат\nрепик с другого угла",
            "recoil": "🔫 BF6 Recoil (15м)\nкороткие очереди\nконтроль на средней",
        },
        "plan": (
            "📅 План на 7 дней — BF6\n"
            "Д1–2: aim 15м + позиции 15м\n"
            "Д3–4: фронт/спавны 20м + дуэли 10м\n"
            "Д5–6: игра от инфо 25м + разбор 5м\n"
            "Д7: 45–60м + разбор 2 смертей\n"
        ),
        "vod": "📼 BF6 разбор: карта/режим, класс, где умер/почему, что хотел сделать.",
    },
    "bo7": {
        "name": "Call of Duty: BO7",
        "settings": (
            "🌑 BO7 — базовый сетап (контроллер)\n"
            "• Sens: 6–8 (перелетаешь → -1)\n"
            "• ADS: 0.80–0.95 (стабильность > скорость)\n"
            "• Deadzone min: 0.03–0.07 (дрифт → 0.08+)\n"
            "• Curve: Dynamic/Standard (что стабильнее)\n"
            "• FOV: 100–115\n\n"
            "🔥 Быстрые правила\n"
            "• Килл → репозиция 1–2 сек\n"
            "• Репик только с другого угла\n"
            "• Меньше “геройства”, больше дисциплины\n"
        ),
        "pillars": (
            "🧠 BO7 — фундамент\n"
            "• Центр экрана + префайр\n"
            "• Тайминги: пикать после инфы\n"
            "• 2 секунды на позиции → смена\n"
            "• Репики только с другого угла\n"
        ),
        "drills": {
            "aim": "🎯 BO7 Aim (20м)\n5м префайр\n7м трекинг\n5м микро\n3м дисциплина",
            "movement": "🕹 BO7 Movement (15–20м)\nрепики\nтайминг\nстрейф + центр",
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
    },
}


# =========================
# Persona + style
# =========================
SYSTEM_PROMPT = (
    "Ты харизматичный FPS-коуч по Warzone / BF6 / BO7. Пишешь по-русски.\n"
    "Тон: уверенный, быстрый, с юмором и лёгкими подколами (без токсичности и унижений).\n"
    "Запрещено: читы/хаки/обход античита/эксплойты. Если просят — откажи и дай честные тренировки.\n\n"
    "Формат ответа ВСЕГДА:\n"
    "1) 🎯 Диагноз (1 главная ошибка)\n"
    "2) ✅ Что делать (2 конкретных действия прямо сейчас)\n"
    "3) 🧪 Дрилл (1 упражнение на 5–10 минут)\n"
    "4) 😈 Панчик/мотивация (1 короткая фраза)\n\n"
    "Если информации мало — задай 1 короткий вопрос в конце."
)

PERSONA_HINT = {
    "spicy": "Стиль: дерзкий, смешной, короткие панчи. Без грубости и унижений.",
    "chill": "Стиль: спокойный, дружелюбный, мягкий юмор.",
    "pro": "Стиль: максимально профессионально, строго по делу, минимум шуток.",
}

VERBOSITY_HINT = {
    "short": "Длина: очень коротко (до 6–10 строк).",
    "normal": "Длина: обычно (10–18 строк).",
    "talkative": "Длина: подробнее (15–30 строк), добавь 1–2 доп. совета.",
}

THINKING_LINES = [
    "🧠 Думаю… сейчас будет жара 😈",
    "⌛ Секунду… раскладываю по полочкам 🧩",
    "🎮 Окей, коуч на связи. Сейчас разнесём 👊",
    "🌑 Анализирую… не моргай 😈",
]


# =========================
# Telegram helpers
# =========================
def _sleep_backoff(i: int):
    time.sleep((0.7 * (i + 1)) + random.random() * 0.25)

def tg_request(method: str, *, params=None, payload=None, is_post=False, retries=TG_RETRIES):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    last = None

    for i in range(retries):
        try:
            if is_post:
                r = SESSION.post(url, json=payload, timeout=HTTP_TIMEOUT)
            else:
                r = SESSION.get(url, params=params, timeout=HTTP_TIMEOUT)

            # Telegram почти всегда JSON
            try:
                data = r.json()
            except Exception:
                raise RuntimeError(f"Telegram non-JSON (HTTP {r.status_code}): {r.text[:200]}")

            if r.status_code == 200 and data.get("ok"):
                return data

            desc = data.get("description", f"Telegram HTTP {r.status_code}")
            last = RuntimeError(desc)

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


# =========================
# "Animation" helpers (safe)
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
            txt = base + ("." * dots)
            try:
                edit_message(chat_id, message_id, txt, reply_markup=None)
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
# Profile / memory / UI state
# =========================
def ensure_profile(chat_id: int) -> dict:
    default_coach = bool(OPENAI_API_KEY)
    return USER_PROFILE.setdefault(chat_id, {
        "game": "warzone",
        "platform": "",
        "style": "",
        "goal": "",
        "coach": default_coach,
        "persona": "spicy",      # spicy | chill | pro
        "verbosity": "normal",   # short | normal | talkative
        "ui": "show",            # show | hide
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
        f"Persona: {p.get('persona','spicy')}\n"
        f"Talk: {p.get('verbosity','normal')}\n"
        f"UI: {p.get('ui','show')}\n\n"
        "Команды:\n"
        "/persona spicy|chill|pro\n"
        "/talk short|normal|talkative\n"
        "/ui show|hide\n"
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
        USER_MEMORY[chat_id] = mem[-MEMORY_MAX_TURNS * 2:]


# =========================
# Keyboards (Telegram colors нет, но делаем “dark vibe”)
# =========================
def kb_main(chat_id: int):
    p = ensure_profile(chat_id)
    coach_on = "🧠 ON" if p.get("coach", True) else "🧠 OFF"
    persona = p.get("persona", "spicy")
    verb = p.get("verbosity", "normal")
    ui = p.get("ui", "show")

    # “скрыть кнопки” — это просто отправлять сообщения без reply_markup
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
             {"text": f"{coach_on}", "callback_data": "action:coach"}],
            [{"text": f"😈 Persona: {persona}", "callback_data": "action:persona"},
             {"text": f"🗣 Talk: {verb}", "callback_data": "action:talk"}],
            [{"text": ui_btn, "callback_data": "action:ui"}],
            [{"text": "🧹 Reset", "callback_data": "action:reset"}],
        ]
    }

def kb_drills():
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
    if p.get("ui", "show") == "hide":
        return None
    return kb_main(chat_id)


# =========================
# OpenAI (safe + retry + personality)
# =========================
def openai_reply_safe(chat_id: int, user_text: str) -> str:
    if not OPENAI_API_KEY or openai_client is None:
        return "⚠️ AI выключен: нет OPENAI_API_KEY. Render → Environment Variables → add → Redeploy."

    p = ensure_profile(chat_id)
    kb = GAME_KB[p["game"]]
    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")

    # extra “коуч-рамка” чтобы ответы были реально полезные
    coach_frame = (
        "Пиши конкретно, без воды. Если пользователь пишет абстрактно — попроси 1 уточнение.\n"
        "Не выдумывай факты про патчи/мету. Если не уверен — говори общими принципами.\n"
        "Фокус: позиционка, тайминги, дисциплина, микромув, инфо, контроль отдачи.\n"
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

    for attempt in range(2):
        try:
            resp = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                max_completion_tokens=650 if verbosity == "talkative" else 520,
            )
            out = (resp.choices[0].message.content or "").strip()
            return out or "Не получил ответ. Напиши ещё раз 🙌"

        except APIConnectionError:
            if attempt == 0:
                time.sleep(0.9)
                continue
            return "⚠️ AI: проблема соединения. Попробуй ещё раз через минуту."
        except AuthenticationError:
            return "❌ AI: неверный ключ. Проверь OPENAI_API_KEY в Render и сделай Redeploy."
        except RateLimitError:
            return "⏳ AI: лимит/перегруз. Подожди 20–60 сек и попробуй снова."
        except BadRequestError:
            return f"❌ AI: bad request. Модель сейчас: {OPENAI_MODEL}."
        except APIError:
            return "⚠️ AI: временная ошибка. Попробуй ещё раз через минуту."
        except Exception:
            log.exception("OpenAI unknown error")
            return "⚠️ AI: неизвестная ошибка. Напиши /status — посмотрим конфиг."


# =========================
# Actions
# =========================
def render_menu_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "🌑 FPS Coach Bot\n"
        f"Игра: {GAME_KB[p['game']]['name']}\n"
        f"Coach: {'ON' if p.get('coach') else 'OFF'}\n"
        f"Persona: {p.get('persona','spicy')} | Talk: {p.get('verbosity','normal')} | UI: {p.get('ui','show')}\n\n"
        "Жми кнопки 👇"
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
        "Если ловишь Conflict 409 — значит 2 инстанса. На Render оставь Instances=1.\n"
    )

def throttle(chat_id: int) -> bool:
    now = time.time()
    last = LAST_MSG_TS.get(chat_id, 0.0)
    if now - last < MIN_SECONDS_BETWEEN_MSG:
        return True
    LAST_MSG_TS[chat_id] = now
    return False


# =========================
# Telegram handlers
# =========================
def handle_message(chat_id: int, text: str):
    if throttle(chat_id):
        return

    p = ensure_profile(chat_id)
    low = text.lower().strip()

    if low in ("привет", "хай", "yo", "здарова", "hello", "ку"):
        send_message(chat_id, "Йо 😈 Ты сюда за победами или за оправданиями? Выбирай игру и погнали.", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/start") or text.startswith("/menu"):
        send_message(chat_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/reset"):
        USER_PROFILE.pop(chat_id, None)
        USER_MEMORY.pop(chat_id, None)
        ensure_profile(chat_id)
        send_message(chat_id, "🧹 Сбросил профиль и память.", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/profile"):
        send_message(chat_id, profile_text(chat_id), reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/status"):
        send_message(chat_id, status_text(), reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/persona"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].strip().lower() in ("spicy", "chill", "pro"):
            p["persona"] = parts[1].strip().lower()
            send_message(chat_id, f"✅ Persona = {p['persona']}", reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "Используй: /persona spicy | chill | pro", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/talk"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].strip().lower() in ("short", "normal", "talkative"):
            p["verbosity"] = parts[1].strip().lower()
            send_message(chat_id, f"✅ Talk = {p['verbosity']}", reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "Используй: /talk short | normal | talkative", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/ui"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].strip().lower() in ("show", "hide"):
            p["ui"] = parts[1].strip().lower()
            send_message(chat_id, f"✅ UI = {p['ui']}", reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "Используй: /ui show | /ui hide", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/game"):
        parts = text.split()
        if len(parts) >= 2:
            msg = set_game(chat_id, parts[1].lower())
            send_message(chat_id, msg, reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "Используй: /game warzone | bf6 | bo7", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/settings"):
        send_message(chat_id, get_settings(chat_id), reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/plan"):
        send_message(chat_id, get_plan(chat_id), reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/vod"):
        send_message(chat_id, get_vod(chat_id), reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/drills"):
        send_message(chat_id, "Выбери дрилл:", reply_markup=(None if p.get("ui") == "hide" else kb_drills()))
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
        send_message(
            chat_id,
            "🧠 Coach OFF. Включи кнопкой Coach в меню.\nПока используй Settings/Drills/Plan/VOD.",
            reply_markup=maybe_kb(chat_id),
        )
        return

    # ====== AI “анимация”: typing + пульс + потом заменяем текст ======
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
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")
    data = cb.get("data", "")

    if not chat_id or not message_id:
        answer_callback(cb_id)
        return

    try:
        p = ensure_profile(chat_id)

        # мгновенная реакция на клик
        quick_loading_edit(chat_id, message_id, "⌛ Загружаю…")

        if data == "action:menu":
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data.startswith("game:"):
            game = data.split(":", 1)[1]
            set_game(chat_id, game)
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:settings":
            edit_message(chat_id, message_id, get_settings(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:plan":
            edit_message(chat_id, message_id, get_plan(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:vod":
            edit_message(chat_id, message_id, get_vod(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:profile":
            edit_message(chat_id, message_id, profile_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:coach":
            p["coach"] = not p.get("coach", True)
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:persona":
            cur = p.get("persona", "spicy")
            nxt = {"spicy": "chill", "chill": "pro", "pro": "spicy"}.get(cur, "spicy")
            p["persona"] = nxt
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:talk":
            cur = p.get("verbosity", "normal")
            nxt = {"short": "normal", "normal": "talkative", "talkative": "short"}.get(cur, "normal")
            p["verbosity"] = nxt
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:ui":
            p["ui"] = "hide" if p.get("ui", "show") == "show" else "show"
            # когда hide — редактируем без клавы
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:reset":
            USER_PROFILE.pop(chat_id, None)
            USER_MEMORY.pop(chat_id, None)
            ensure_profile(chat_id)
            edit_message(chat_id, message_id, "🧹 Сбросил профиль и память.", reply_markup=maybe_kb(chat_id))

        elif data == "action:drills":
            edit_message(chat_id, message_id, "Выбери дрилл:", reply_markup=(None if p.get("ui") == "hide" else kb_drills()))

        elif data.startswith("drill:"):
            kind = data.split(":", 1)[1]
            edit_message(chat_id, message_id, get_drill(chat_id, kind), reply_markup=(None if p.get("ui") == "hide" else kb_drills()))

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
        log.warning("Polling already started in this process. Skipping second start.")
        return
    POLLING_STARTED = True

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
            # ЛОВИМ ТВОЮ ОШИБКУ: Conflict 409 (два getUpdates)
            msg = str(e)
            if "Conflict:" in msg and "getUpdates" in msg:
                sleep_s = random.randint(CONFLICT_BACKOFF_MIN, CONFLICT_BACKOFF_MAX)
                log.warning("Telegram conflict (2 instances?). Backing off for %ss: %s", sleep_s, msg)
                time.sleep(sleep_s)
                continue

            log.warning("Loop RuntimeError: %r", e)
            time.sleep(2)

        except Exception as e:
            log.warning("Loop error: %r", e)
            time.sleep(2)


# =========================
# Render health endpoint
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
