import os
import time
import json
import threading
import logging
import random
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
from openai import OpenAI
from openai import APIConnectionError, AuthenticationError, RateLimitError, BadRequestError, APIError


# =========================
# Logging
# =========================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
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

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("Missing ENV: TELEGRAM_BOT_TOKEN (BotFather token)")

# OpenAI client (таймаут + не зависаем)
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=30,
            max_retries=1,  # мы сами ретраим ниже
        )
    except TypeError:
        openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


# =========================
# Requests session (faster + stabler)
# =========================
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "render-telegram-bot/3.0"})
SESSION.adapters["https://"] = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)


# =========================
# Data (in-memory)
# =========================
USER_PROFILE = {}  # chat_id -> dict
USER_MEMORY = {}   # chat_id -> list[{role, content}]
MEMORY_MAX_TURNS = 10

LAST_MSG_TS = {}   # chat_id -> float
MIN_SECONDS_BETWEEN_MSG = 0.30


# =========================
# Knowledge base (обновишь потом — это скелет “учителя”)
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
        "pillars": (
            "🧠 Warzone — база про-игры\n"
            "• Выживание > киллы, игра от укрытий/высоты\n"
            "• Ротации раньше драки (тайминг — король)\n"
            "• Инфо: пинги/звуки/мини-карта/чек углов\n"
            "• Первые 0.7 сек решают: пре-эйм + дисциплина\n"
        ),
        "drills": {
            "aim": "🎯 Warzone Aim (20м)\n10м warm-up\n5м трекинг\n5м микро-коррекции",
            "recoil": "🔫 Warzone Recoil (20м)\n5м 15–25м\n10м 25–40м\n5м дисциплина",
            "movement": "🕹 Warzone Movement (15м)\nугол→слайд→пик\nджамп-пики\nreposition",
        },
        "plan": (
            "📅 План 7 дней — Warzone\n"
            "Д1–2: warm-up 10м + aim 15м + movement 10м + мини-разбор 5м\n"
            "Д3–4: warm-up 10м + дуэли/углы 15м + дисциплина 10м\n"
            "Д5–6: инфо+позиции 25м + разбор 5м\n"
            "Д7: 45–60м игры + разбор 2 смертей 10м\n"
        ),
        "vod": (
            "📼 VOD/ситуация (шаблон)\n"
            "1) Режим (solo/duo/trio/quad)\n"
            "2) Где бой (дом/крыша/поле)\n"
            "3) Как умер (угол/решение/ошибка)\n"
            "4) Ресурсы (плиты/смок/стим/саморес)\n"
            "5) План (пуш/отход/ротация)\n\n"
            "Я верну: ошибка №1 + 2 действия + мини-дрилл 💪"
        ),
    },
    "bf6": {
        "name": "Battlefield 6 (BF6)",
        "settings": (
            "🎮 BF6 — настройки (база)\n"
            "• Sens: средняя, ADS чуть ниже\n"
            "• Deadzone: минимум без дрифта\n"
            "• FOV: высокий (комфорт)\n"
            "• После контакта — смена позиции\n"
        ),
        "pillars": (
            "🧠 BF6 — база\n"
            "• Линии фронта + логика спавнов\n"
            "• Не стой: выстрелил → сместился\n"
            "• Игра от инфы/углов, минимальный пик\n"
            "• Командная ценность: метки, рес, прикрытие\n"
        ),
        "drills": {
            "aim": "🎯 BF6 Aim (15–20м)\nпрефайр углов\nтрекинг\nсмена позиции после серии",
            "movement": "🕹 BF6 Movement (15м)\nпик→инфо→откат\nрепик с другого угла",
            "recoil": "🔫 BF6 Recoil (15м)\nкороткие очереди\nконтроль на средней",
        },
        "plan": (
            "📅 План 7 дней — BF6\n"
            "Д1–2: aim 15м + позиции 15м\n"
            "Д3–4: спавны/линии 20м + дуэли 10м\n"
            "Д5–6: инфо 25м + разбор 5м\n"
            "Д7: 45–60м + разбор 2 смертей\n"
        ),
        "vod": "📼 BF6 разбор: карта/режим, класс, где умер/почему, что хотел сделать.",
    },
    "bo7": {
        "name": "Call of Duty: BO7",
        "settings": (
            "🎮 BO7 — настройки (контроллер)\n"
            "• Sens: 6–8 (перелёт → -1)\n"
            "• ADS: 0.80–0.95 (стабильность > скорость)\n"
            "• Deadzone min: 0.03–0.07 (дрифт → 0.08+)\n"
            "• Curve: Dynamic/Standard\n"
            "• FOV: 100–115\n\n"
            "🔥 Правила\n"
            "• После килла: репозиция 1–2 сек\n"
            "• Репик только с другого угла\n"
            "• Пик короткий: инфо → откат → другой пик\n"
        ),
        "pillars": (
            "🧠 BO7 — база\n"
            "• Центр экрана + пре-эйм углов\n"
            "• Тайминги: когда пикать/когда ждать\n"
            "• 2 секунды на позиции → сместился\n"
            "• Не жадничай пики, дисциплина решает\n"
        ),
        "drills": {
            "aim": "🎯 BO7 Aim (20м)\n5м префайр\n7м трекинг\n5м микро\n3м дисциплина",
            "movement": "🕹 BO7 Movement (15–20м)\nрепики с другого угла\nтайминг\nстрейф + центр",
            "recoil": "🔫 BO7 Recoil (15м)\nкороткие очереди\nпервая пуля\nне жадничай",
        },
        "plan": (
            "📅 План 7 дней — BO7\n"
            "Д1–2: aim 20м + movement 10м\n"
            "Д3–4: углы/тайминги 25м + разбор 5м\n"
            "Д5–6: дуэли 30м (репики/углы)\n"
            "Д7: 45–60м + разбор 2–3 смертей\n"
        ),
        "vod": "📼 BO7 разбор: режим/карта, момент смерти, инфо (радар/звук), что хотел сделать.",
    },
}


# =========================
# Persona / style
# =========================
SYSTEM_PROMPT = (
    "Ты харизматичный FPS-коуч по Warzone/BF6/BO7. Пишешь по-русски.\n"
    "Тон: уверенный, быстрый, с юмором и лёгкими подколами (без токсичности).\n"
    "Структура ответа ВСЕГДА:\n"
    "1) 🎯 Диагноз (1 главная ошибка)\n"
    "2) ✅ Что делать (2 конкретных действия прямо сейчас)\n"
    "3) 🧪 Дрилл (1 упражнение на 5–10 минут)\n"
    "4) 😈 Панчик/мотивация (1 короткая фраза)\n\n"
    "Запрещено: читы/хаки/обход античита. Если просят — откажи и предложи честные тренировки."
)

PERSONA_HINT = {
    "spicy": "Стиль: дерзкий, смешной, короткие панчи. Никакой грубости.",
    "chill": "Стиль: спокойный, дружелюбный, мягкий юмор.",
    "pro": "Стиль: максимально профессионально, строго по делу, минимум шуток.",
}

VERBOSITY_HINT = {
    "short": "Длина: очень коротко (до 6–10 строк).",
    "normal": "Длина: обычно (10–18 строк).",
    "talkative": "Длина: чуть подробнее (15–30 строк), добавь 1–2 доп. совета.",
}

THINKING_LINES = [
    "🧠 Думаю… сейчас будет жара 😈",
    "⌛ Секунду… раскладываю по полочкам 🧩",
    "🎮 Коуч на связи. Сейчас разнесём 👊",
]


# =========================
# Telegram helpers
# =========================
def _sleep_backoff(i: int, retry_after: Optional[float] = None):
    if retry_after is not None:
        time.sleep(min(6.0, max(0.5, retry_after)))
        return
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

            try:
                data = r.json()
            except Exception:
                raise RuntimeError(f"Telegram non-JSON (HTTP {r.status_code}): {r.text[:200]}")

            if r.status_code == 200 and data.get("ok"):
                return data

            desc = data.get("description", f"Telegram HTTP {r.status_code}")
            retry_after = None
            if r.status_code == 429:
                retry_after = float((data.get("parameters") or {}).get("retry_after") or 2)
            last = RuntimeError(desc)
            _sleep_backoff(i, retry_after=retry_after)

        except Exception as e:
            last = e
            _sleep_backoff(i)

    raise last


def send_message(chat_id: int, text: str, reply_markup=None) -> Optional[int]:
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [""]
    last_msg_id = None
    for ch in chunks:
        res = tg_request(
            "sendMessage",
            payload={"chat_id": chat_id, "text": ch, "reply_markup": reply_markup},
            is_post=True
        )
        last_msg_id = (res.get("result") or {}).get("message_id")
    return last_msg_id


def edit_message(chat_id: int, message_id: int, text: str, reply_markup=None):
    tg_request(
        "editMessageText",
        payload={"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": reply_markup},
        is_post=True
    )


def safe_edit_message(chat_id: int, message_id: int, text: str, reply_markup=None) -> bool:
    try:
        edit_message(chat_id, message_id, text, reply_markup=reply_markup)
        return True
    except Exception as e:
        s = str(e).lower()
        if "message is not modified" in s:
            return True
        return False


def safe_edit_or_send(chat_id: int, message_id: Optional[int], text: str, reply_markup=None):
    if message_id:
        ok = safe_edit_message(chat_id, message_id, text, reply_markup=reply_markup)
        if ok:
            return
    send_message(chat_id, text, reply_markup=reply_markup)


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
# "Animation"
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
        if now - last_edit >= 1.0:
            dots = (dots + 1) % 4
            txt = base + ("." * dots)
            safe_edit_message(chat_id, message_id, txt, reply_markup=None)
            last_edit = now
        stop_event.wait(0.2)


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
        "persona": "spicy",      # spicy | chill | pro
        "verbosity": "normal",   # short | normal | talkative
        "buttons": True,         # показывать ли кнопки
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
        f"Persona: {p.get('persona')}\n"
        f"Talk: {p.get('verbosity')}\n"
        f"Buttons: {'ON' if p.get('buttons', True) else 'OFF'}\n\n"
        "Команды:\n"
        "• /persona spicy|chill|pro\n"
        "• /talk short|normal|talkative\n"
        "• /buttons on|off\n"
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
# Keyboards (визуально "dark" через эмодзи)
# =========================
def kb_main(chat_id: int):
    p = ensure_profile(chat_id)
    coach_on = "🧠 Coach: ON" if p.get("coach", True) else "🧠 Coach: OFF"
    persona = p.get("persona", "spicy")
    verb = p.get("verbosity", "normal")
    buttons_on = p.get("buttons", True)

    # кнопка “убрать/вернуть”
    toggle_buttons_text = "⬛️ Скрыть кнопки" if buttons_on else "🌑 Показать кнопки"
    toggle_cb = "action:buttons_off" if buttons_on else "action:buttons_on"

    return {
        "inline_keyboard": [
            [{"text": "⬛️ Warzone", "callback_data": "game:warzone"},
             {"text": "⬛️ BF6", "callback_data": "game:bf6"},
             {"text": "⬛️ BO7", "callback_data": "game:bo7"}],
            [{"text": "⚙️ Settings", "callback_data": "action:settings"},
             {"text": "💪 Drills", "callback_data": "action:drills"}],
            [{"text": "📅 Plan", "callback_data": "action:plan"},
             {"text": "📼 VOD", "callback_data": "action:vod"}],
            [{"text": "👤 Profile", "callback_data": "action:profile"},
             {"text": coach_on, "callback_data": "action:coach"}],
            [{"text": f"😈 Persona: {persona}", "callback_data": "action:persona"},
             {"text": f"🗣 Talk: {verb}", "callback_data": "action:talk"}],
            [{"text": toggle_buttons_text, "callback_data": toggle_cb}],
            [{"text": "🧹 Reset", "callback_data": "action:reset"}],
        ]
    }


def kb_drills(chat_id: int):
    p = ensure_profile(chat_id)
    if not p.get("buttons", True):
        return None
    return {
        "inline_keyboard": [
            [{"text": "🎯 Aim", "callback_data": "drill:aim"},
             {"text": "🔫 Recoil", "callback_data": "drill:recoil"},
             {"text": "🕹 Movement", "callback_data": "drill:movement"}],
            [{"text": "⬅️ Меню", "callback_data": "action:menu"}],
        ]
    }


def maybe_kb(chat_id: int):
    p = ensure_profile(chat_id)
    return kb_main(chat_id) if p.get("buttons", True) else None


# =========================
# OpenAI
# =========================
def openai_reply_safe(chat_id: int, user_text: str) -> str:
    if not OPENAI_API_KEY or openai_client is None:
        return "⚠️ AI выключен: нет OPENAI_API_KEY. Render → Environment Variables → add → Redeploy."

    p = ensure_profile(chat_id)
    kb = GAME_KB[p["game"]]
    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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
                max_completion_tokens=560 if verbosity == "talkative" else 440,
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
# Actions / texts
# =========================
def render_menu_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "🧠 FPS Coach Bot\n"
        f"Текущая игра: {GAME_KB[p['game']]['name']}\n"
        f"Coach: {'ON' if p.get('coach') else 'OFF'}\n"
        f"Persona: {p.get('persona')} | Talk: {p.get('verbosity')} | Buttons: {'ON' if p.get('buttons', True) else 'OFF'}\n\n"
        "Жми кнопки ниже (или отключи их) 👇"
    )


def status_text() -> str:
    ok_key = "✅" if bool(OPENAI_API_KEY) else "❌"
    ok_tg = "✅" if bool(TELEGRAM_BOT_TOKEN) else "❌"
    return (
        "🧾 Status\n"
        f"TELEGRAM_BOT_TOKEN: {ok_tg}\n"
        f"OPENAI_API_KEY: {ok_key}\n"
        f"OPENAI_BASE_URL: {OPENAI_BASE_URL}\n"
        f"OPENAI_MODEL: {OPENAI_MODEL}\n"
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
        return "❌ /ai_test: неверный ключ."
    except APIConnectionError:
        return "⚠️ /ai_test: проблема сети/Render."
    except Exception as e:
        return f"⚠️ /ai_test: ошибка: {type(e).__name__}"


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
        send_message(chat_id, "Йо 😈 Ты сюда за победами или за оправданиями? Выбирай игру и поехали.", reply_markup=maybe_kb(chat_id))
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

    if text.startswith("/ai_test"):
        send_message(chat_id, ai_test(), reply_markup=maybe_kb(chat_id))
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

    if text.startswith("/buttons"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].strip().lower() in ("on", "off"):
            p["buttons"] = (parts[1].strip().lower() == "on")
            send_message(chat_id, f"✅ Buttons = {'ON' if p['buttons'] else 'OFF'}", reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "Используй: /buttons on | /buttons off", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/game"):
        parts = text.split()
        if len(parts) >= 2:
            g = parts[1].lower().strip()
            if g in GAME_KB:
                p["game"] = g
                send_message(chat_id, f"✅ Игра: {GAME_KB[g]['name']}", reply_markup=maybe_kb(chat_id))
            else:
                send_message(chat_id, "Доступно: /game warzone | bf6 | bo7", reply_markup=maybe_kb(chat_id))
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
        kb = kb_drills(chat_id)
        send_message(chat_id, "Выбери дрилл:", reply_markup=kb)
        return

    # профиль одной строкой
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
        send_message(chat_id, "🧠 Coach OFF. Включи его в меню (Coach) — и начнём тренировать мозг 😈", reply_markup=maybe_kb(chat_id))
        return

    # ===== AI: “анимация” + safe edit =====
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

    # Если кнопки OFF — не прикрепляем меню
    safe_edit_or_send(chat_id, tmp_id, reply, reply_markup=maybe_kb(chat_id))


def handle_callback(cb: dict):
    cb_id = cb["id"]
    msg = cb.get("message", {}) or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = cb.get("data", "")

    if not chat_id or not message_id:
        answer_callback(cb_id)
        return

    p = ensure_profile(chat_id)

    try:
        # мгновенная реакция
        safe_edit_message(chat_id, message_id, "⌛ Загружаю…", reply_markup=None)

        if data == "action:menu":
            safe_edit_or_send(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data.startswith("game:"):
            g = data.split(":", 1)[1]
            if g in GAME_KB:
                p["game"] = g
            safe_edit_or_send(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:settings":
            safe_edit_or_send(chat_id, message_id, GAME_KB[p["game"]]["settings"], reply_markup=maybe_kb(chat_id))

        elif data == "action:plan":
            safe_edit_or_send(chat_id, message_id, GAME_KB[p["game"]]["plan"], reply_markup=maybe_kb(chat_id))

        elif data == "action:vod":
            safe_edit_or_send(chat_id, message_id, GAME_KB[p["game"]]["vod"], reply_markup=maybe_kb(chat_id))

        elif data == "action:profile":
            safe_edit_or_send(chat_id, message_id, profile_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:coach":
            p["coach"] = not p.get("coach", True)
            safe_edit_or_send(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:persona":
            cur = p.get("persona", "spicy")
            p["persona"] = {"spicy": "chill", "chill": "pro", "pro": "spicy"}.get(cur, "spicy")
            safe_edit_or_send(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:talk":
            cur = p.get("verbosity", "normal")
            p["verbosity"] = {"short": "normal", "normal": "talkative", "talkative": "short"}.get(cur, "normal")
            safe_edit_or_send(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:buttons_off":
            p["buttons"] = False
            # “убрать кнопки” = редактируем сообщение и ставим reply_markup=None
            safe_edit_or_send(chat_id, message_id, render_menu_text(chat_id), reply_markup=None)

        elif data == "action:buttons_on":
            p["buttons"] = True
            safe_edit_or_send(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:reset":
            USER_PROFILE.pop(chat_id, None)
            USER_MEMORY.pop(chat_id, None)
            ensure_profile(chat_id)
            safe_edit_or_send(chat_id, message_id, "🧹 Сбросил профиль и память.", reply_markup=maybe_kb(chat_id))

        elif data == "action:drills":
            kb = kb_drills(chat_id)
            safe_edit_or_send(chat_id, message_id, "Выбери дрилл:", reply_markup=kb)

        elif data.startswith("drill:"):
            kind = data.split(":", 1)[1]
            drills = GAME_KB[p["game"]]["drills"]
            txt = drills.get(kind, "Доступно: aim / recoil / movement")
            kb = kb_drills(chat_id)
            safe_edit_or_send(chat_id, message_id, txt, reply_markup=kb)

        else:
            safe_edit_or_send(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

    finally:
        answer_callback(cb_id)


def run_telegram_bot():
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
